import asyncio
import logging
import yfinance as yf
from typing import List, Dict

logger = logging.getLogger("stock_cache")

# Precompiled list of Top 50 Indian Market tickers on NSE
NIFTY_50_TICKERS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "BHARTIARTL.NS", "ICICIBANK.NS",
    "INFY.NS", "SBIN.NS", "LICI.NS", "ITC.NS", "HINDUNILVR.NS",
    "LT.NS", "BAJFINANCE.NS", "HCLTECH.NS", "MARUTI.NS", "SUNPHARMA.NS",
    "ADANIENT.NS", "TATAMOTORS.NS", "AXISBANK.NS", "NTPC.NS", "ONGC.NS",
    "COALINDIA.NS", "TATASTEEL.NS", "JSWSTEEL.NS", "POWERGRID.NS", "M&M.NS",
    "KOTAKBANK.NS", "ULTRACEMCO.NS", "TITAN.NS", "GRASIM.NS", "SBILIFE.NS",
    "BPCL.NS", "HINDALCO.NS", "NESTLEIND.NS", "ADANIPORTS.NS", "BAJAJFINSV.NS",
    "TECHM.NS", "BRITANNIA.NS", "WIPRO.NS", "CIPLA.NS", "EICHERMOT.NS",
    "DIVISLAB.NS", "TATACONSUM.NS", "DRREDDY.NS", "APOLLOHOSP.NS", "JIOFIN.NS",
    "LTIM.NS", "HEROMOTOCO.NS", "ASIANPAINT.NS", "INDUSINDBK.NS", "BAJAJ-AUTO.NS"
]

# Global in-memory thread-safe cache store
INDIAN_MARKET_CACHE: List[Dict] = []

async def fetch_single_stock_cache(ticker_symbol: str) -> Dict | None:
    try:
        # Resolve metrics in separate thread since yfinance calls are blocking
        loop = asyncio.get_running_loop()
        ticker = yf.Ticker(ticker_symbol)
        
        # Pull minimal metrics
        hist = await loop.run_in_executor(None, lambda: ticker.history(period="5d"))
        if hist.empty:
            return None
            
        info = ticker.info or {}
        current_price = info.get("currentPrice") or info.get("regularMarketPrice")
        if not current_price:
            current_price = hist['Close'].iloc[-1]
            
        company_name = info.get("longName") or info.get("shortName") or ticker_symbol.split(".")[0]
        
        # Calculate daily change percentage if possible
        change_pct = 0.0
        if len(hist) >= 2:
            prev_close = hist['Close'].iloc[-2]
            curr_close = hist['Close'].iloc[-1]
            change_pct = ((curr_close - prev_close) / prev_close) * 100
            
        volume = info.get("volume") or info.get("regularMarketVolume") or 0
        
        return {
            "ticker": ticker_symbol,
            "company_name": company_name,
            "current_price": float(current_price),
            "change_percentage": float(change_pct),
            "volume": int(volume)
        }
    except Exception as e:
        logger.warning(f"Failed to fetch cache detail for {ticker_symbol}: {str(e)}")
        # Return fallback stub if failed so the ticker is still search-discoverable
        return {
            "ticker": ticker_symbol,
            "company_name": ticker_symbol.split(".")[0],
            "current_price": 0.0,
            "change_percentage": 0.0,
            "volume": 0
        }

async def populate_indian_market_cache():
    logger.info("Initializing background Indian stock cache build for Nifty 50...")
    
    # Run fetchers concurrently
    tasks = [fetch_single_stock_cache(symbol) for symbol in NIFTY_50_TICKERS]
    results = await asyncio.gather(*tasks)
    
    # Map results
    valid_results = [r for r in results if r is not None]
    
    global INDIAN_MARKET_CACHE
    INDIAN_MARKET_CACHE = valid_results
    
    logger.info(f"Asynchronous cache build completed successfully. Cached {len(INDIAN_MARKET_CACHE)} securities.")
