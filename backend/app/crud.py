from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.models import StockWatchlist, StockMetricsSnapshot, GeminiAnalysisReport, StockHolding
from uuid import UUID

async def get_watchlist_with_latest(db: AsyncSession):
    # Fetch all stock watchlist entries
    stmt = select(StockWatchlist).order_by(StockWatchlist.ticker)
    result = await db.execute(stmt)
    stocks = result.scalars().all()
    
    watchlist_data = []
    for stock in stocks:
        # Get latest metric snapshot
        metric_stmt = (
            select(StockMetricsSnapshot)
            .where(StockMetricsSnapshot.stock_id == stock.id)
            .order_by(desc(StockMetricsSnapshot.fetched_at))
            .limit(1)
        )
        metric_result = await db.execute(metric_stmt)
        latest_metric = metric_result.scalar_one_or_none()
        
        # Get latest report
        report_stmt = (
            select(GeminiAnalysisReport)
            .where(GeminiAnalysisReport.stock_id == stock.id)
            .order_by(desc(GeminiAnalysisReport.created_at))
            .limit(1)
        )
        report_result = await db.execute(report_stmt)
        latest_report = report_result.scalar_one_or_none()
        
        watchlist_data.append({
            "id": stock.id,
            "ticker": stock.ticker,
            "company_name": stock.company_name,
            "added_at": stock.added_at,
            "latest_metrics": latest_metric,
            "latest_report": latest_report
        })
        
    return watchlist_data

async def get_watchlist_item_by_ticker(db: AsyncSession, ticker: str):
    stmt = select(StockWatchlist).where(StockWatchlist.ticker == ticker.upper())
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def get_watchlist_item_by_id(db: AsyncSession, stock_id: UUID):
    stmt = select(StockWatchlist).where(StockWatchlist.id == stock_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def create_stock_watchlist_item(db: AsyncSession, ticker: str, company_name: str):
    stock = StockWatchlist(ticker=ticker.upper(), company_name=company_name)
    db.add(stock)
    await db.flush()  # Populates id prior to commit
    return stock

async def create_metrics_snapshot(db: AsyncSession, stock_id: UUID, metrics: dict):
    snapshot = StockMetricsSnapshot(
        stock_id=stock_id,
        current_price=metrics["current_price"],
        trailing_pe=metrics["trailing_pe"],
        market_cap=metrics["market_cap"],
        fifty_two_week_high=metrics["fifty_two_week_high"],
        fifty_two_week_low=metrics["fifty_two_week_low"],
        price_history_7d=metrics["price_history_7d"],
        volume=metrics.get("volume")
    )
    db.add(snapshot)
    await db.flush()
    return snapshot

async def create_gemini_report(db: AsyncSession, stock_id: UUID, report_text: str, trigger_type: str):
    report = GeminiAnalysisReport(
        stock_id=stock_id,
        analysis_report=report_text,
        trigger_type=trigger_type
    )
    db.add(report)
    await db.flush()
    return report

async def delete_stock_watchlist_item(db: AsyncSession, stock_id: UUID) -> bool:
    stock = await get_watchlist_item_by_id(db, stock_id)
    if not stock:
        return False
    await db.delete(stock)
    return True

# Portfolio Holdings CRUD helpers
async def get_holdings(db: AsyncSession):
    stmt = select(StockHolding).order_by(StockHolding.ticker)
    result = await db.execute(stmt)
    return result.scalars().all()

async def get_holding_by_ticker(db: AsyncSession, ticker: str):
    stmt = select(StockHolding).where(StockHolding.ticker == ticker.upper())
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def get_holding_by_id(db: AsyncSession, holding_id: UUID):
    stmt = select(StockHolding).where(StockHolding.id == holding_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def upsert_stock_holding(db: AsyncSession, ticker: str, company_name: str, quantity: float, average_buy_price: float):
    existing = await get_holding_by_ticker(db, ticker)
    if existing:
        total_quantity = existing.quantity + quantity
        if total_quantity > 0:
            weighted_avg = ((existing.quantity * existing.average_buy_price) + (quantity * average_buy_price)) / total_quantity
            existing.average_buy_price = weighted_avg
            existing.quantity = total_quantity
            existing.company_name = company_name
        else:
            await db.delete(existing)
            return None
        await db.flush()
        return existing
    else:
        if quantity <= 0:
            return None
        holding = StockHolding(
            ticker=ticker.upper(),
            company_name=company_name,
            quantity=quantity,
            average_buy_price=average_buy_price
        )
        db.add(holding)
        await db.flush()
        return holding

async def delete_stock_holding(db: AsyncSession, holding_id: UUID) -> bool:
    holding = await get_holding_by_id(db, holding_id)
    if not holding:
        return False
    await db.delete(holding)
    return True
