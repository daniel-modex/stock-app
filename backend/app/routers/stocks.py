import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.schemas import StockWatchlistCreate, StockWatchlistResponse, GeminiAnalysisReportResponse, StockHoldingCreate, StockHoldingResponse
from app import crud
from app.data_fetcher import validate_and_fetch_stock_data, fetch_rich_market_data
from app.ai_analyst import analyze_stock
from app.cache import INDIAN_MARKET_CACHE
from uuid import UUID
from typing import List, Optional
from pydantic import BaseModel

logger = logging.getLogger("stocks_router")
router = APIRouter(tags=["stocks"])

@router.get("/stocks", response_model=List[StockWatchlistResponse])
async def get_stocks(db: AsyncSession = Depends(get_db)):
    """
    Returns all tickers in the watchlist with their latest metrics snapshot and latest AI report.
    """
    return await crud.get_watchlist_with_latest(db)

@router.post("/stocks", response_model=StockWatchlistResponse, status_code=status.HTTP_201_CREATED)
async def add_stock(payload: StockWatchlistCreate, model_name: str = "gemini-2.5-flash", db: AsyncSession = Depends(get_db)):
    """
    Adds a new stock to the watchlist. Automatically triggers immediate yfinance validation,
    captures initial metrics snapshot, and generates initial Gemini report before returning.
    """
    ticker = payload.ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker symbol cannot be empty.")
        
    # Check if stock already exists in the watchlist
    existing = await crud.get_watchlist_item_by_ticker(db, ticker)
    if existing:
        raise HTTPException(status_code=400, detail=f"Stock with ticker '{ticker}' is already in the watchlist.")
        
    # Pull metrics from yfinance immediately (serves as validation)
    try:
        metrics = validate_and_fetch_stock_data(ticker, model_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation failed (yfinance pull failed): {str(e)}")
        
    try:
        # Create watchlist item
        stock = await crud.create_stock_watchlist_item(db, metrics["ticker"], metrics["company_name"])
        
        # Create initial snapshot
        latest_metrics = await crud.create_metrics_snapshot(db, stock.id, metrics)
        
        # Generate initial report
        report_text = analyze_stock(metrics["ticker"], metrics, model_name)
        latest_report = await crud.create_gemini_report(db, stock.id, report_text, "MANUAL")
        
        # Commit transaction
        await db.commit()
        
        return {
            "id": stock.id,
            "ticker": stock.ticker,
            "company_name": stock.company_name,
            "added_at": stock.added_at,
            "latest_metrics": latest_metrics,
            "latest_report": latest_report
        }
    except Exception as e:
        await db.rollback()
        logger.exception("Failed to add stock to watchlist:")
        raise HTTPException(status_code=500, detail=f"Failed to complete initial database transaction: {str(e)}")

@router.delete("/stocks/{stock_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_stock(stock_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Drops the stock from the watchlist. Database-level constraints handle cascade deletions.
    """
    success = await crud.delete_stock_watchlist_item(db, stock_id)
    if not success:
        raise HTTPException(status_code=404, detail="Stock watchlist item not found.")
    await db.commit()

@router.post("/stocks/{stock_id}/analyze", response_model=GeminiAnalysisReportResponse)
async def analyze_stock_on_demand(stock_id: UUID, model_name: str = "gemini-2.5-flash", db: AsyncSession = Depends(get_db)):
    """
    On-Demand Execution Route. Instantly pulls fresh stock metrics, hits the Gemini API,
    stores the generated report in the database, and returns the result back to the user.
    """
    stock = await crud.get_watchlist_item_by_id(db, stock_id)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock watchlist item not found.")
        
    # Fetch fresh metrics
    try:
        metrics = validate_and_fetch_stock_data(stock.ticker, model_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch latest stock metrics from yfinance: {str(e)}")
        
    try:
        # Create new metrics snapshot
        await crud.create_metrics_snapshot(db, stock.id, metrics)
        
        # Generate Gemini report
        report_text = analyze_stock(stock.ticker, metrics, model_name)
        
        # Save Gemini report
        report = await crud.create_gemini_report(db, stock.id, report_text, "MANUAL")
        
        # Sync company name back to StockWatchlist if changed
        if metrics.get("company_name") and stock.company_name != metrics["company_name"]:
            stock.company_name = metrics["company_name"]
            
        await db.commit()
        return report
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"On-demand analysis database transaction failed: {str(e)}")

# ─── Indian Market Directory ──────────────────────────────────────────────────

@router.get("/directory")
async def get_market_directory(q: str = ""):
    """
    Returns the cached Indian market directory (Nifty 50 securities).
    Optionally filter by query string matching ticker or company name.
    """
    import app.cache as cache_module
    directory = cache_module.INDIAN_MARKET_CACHE
    if q:
        q_lower = q.lower()
        directory = [
            s for s in directory
            if q_lower in s["ticker"].lower() or q_lower in (s["company_name"] or "").lower()
        ]
    return directory

# ─── Portfolio Holdings ───────────────────────────────────────────────────────

@router.get("/holdings", response_model=List[StockHoldingResponse])
async def get_holdings(db: AsyncSession = Depends(get_db)):
    """Returns all portfolio holdings."""
    return await crud.get_holdings(db)

@router.post("/holdings", response_model=StockHoldingResponse, status_code=status.HTTP_201_CREATED)
async def add_holding(payload: StockHoldingCreate, db: AsyncSession = Depends(get_db)):
    """
    Upserts a portfolio holding. If the ticker already exists the quantity is
    added and the average buy price is recalculated using a weighted average.
    """
    ticker = payload.ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker symbol cannot be empty.")
    if payload.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be greater than zero.")
    if payload.average_buy_price <= 0:
        raise HTTPException(status_code=400, detail="Average buy price must be greater than zero.")

    # Resolve company name from cache, fall back gracefully
    company_name = ticker
    import app.cache as cache_module
    for entry in cache_module.INDIAN_MARKET_CACHE:
        if entry["ticker"].upper() == ticker:
            company_name = entry["company_name"]
            break

    holding = await crud.upsert_stock_holding(db, ticker, company_name, payload.quantity, payload.average_buy_price)
    if holding is None:
        raise HTTPException(status_code=400, detail="Could not create or update holding.")
    await db.commit()
    return holding

@router.delete("/holdings/{holding_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_holding(holding_id: UUID, db: AsyncSession = Depends(get_db)):
    """Removes a holding from the portfolio."""
    success = await crud.delete_stock_holding(db, holding_id)
    if not success:
        raise HTTPException(status_code=404, detail="Holding not found.")
    await db.commit()

# ─── Rich Market Data & Any-Ticker Analysis ───────────────────────────────────

@router.get("/market-data/{ticker}")
async def get_market_data(ticker: str, period: str = "3mo"):
    """
    Returns full OHLCV history plus RSI, MACD, Bollinger Bands, MA20/50/200
    for any ticker (does not need to be in the watchlist).
    period options: 1mo, 3mo, 6mo, 1y
    """
    valid_periods = {"1mo", "3mo", "6mo", "1y"}
    if period not in valid_periods:
        period = "3mo"
    try:
        data = fetch_rich_market_data(ticker.upper(), period)
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

class AnyTickerAnalyzeRequest(BaseModel):
    holding_context: Optional[dict] = None

@router.post("/analyze/{ticker}")
async def analyze_any_ticker(
    ticker: str,
    body: AnyTickerAnalyzeRequest = AnyTickerAnalyzeRequest(),
    model_name: str = "gemini-2.5-flash"
):
    """
    Run AI analysis for any ticker — not just watchlisted ones.
    Optionally pass holding_context: {quantity, average_buy_price} in the request body.
    """
    try:
        metrics = fetch_rich_market_data(ticker.upper(), "3mo")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch market data: {str(e)}")
    try:
        report = analyze_stock(
            ticker.upper(), metrics, model_name,
            holding_context=body.holding_context
        )
        return {"ticker": ticker.upper(), "report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {str(e)}")

