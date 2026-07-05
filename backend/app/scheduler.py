import logging
from datetime import datetime, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.database import AsyncSessionLocal
from app.crud import create_metrics_snapshot, create_gemini_report
from app.data_fetcher import validate_and_fetch_stock_data
from app.ai_analyst import analyze_stock
from sqlalchemy import select
from app.models import StockWatchlist

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stock_scheduler")

scheduler = AsyncIOScheduler()

async def update_stocks_job():
    logger.info("Starting scheduled hourly stock scrape and AI report generation cycle...")
    
    async with AsyncSessionLocal() as db:
        stmt = select(StockWatchlist)
        result = await db.execute(stmt)
        stocks = result.scalars().all()
        
        if not stocks:
            logger.info("Watchlist is empty. No stocks to scrape.")
            return
            
        for stock in stocks:
            try:
                logger.info(f"Scraping metrics for ticker: {stock.ticker}...")
                metrics = validate_and_fetch_stock_data(stock.ticker)
                
                # Sync company name back to StockWatchlist if not already filled
                if not stock.company_name and metrics.get("company_name"):
                    stock.company_name = metrics["company_name"]
                
                # 1. Insert latest metrics snapshot
                await create_metrics_snapshot(db, stock.id, metrics)
                
                # 2. Run Gemini analysis
                logger.info(f"Generating scheduled Gemini analysis for {stock.ticker}...")
                report_text = analyze_stock(stock.ticker, metrics)
                await create_gemini_report(db, stock.id, report_text, "SCHEDULED")
                
                # Commit updates for this stock independently
                await db.commit()
                logger.info(f"Successfully snapshot and analyzed ticker: {stock.ticker}")
                
            except Exception as e:
                logger.error(f"Failed to process scheduled update for {stock.ticker}: {str(e)}")
                await db.rollback()

def start_scheduler():
    if not scheduler.running:
        # Schedule the job to run every hour, with the first execution happening immediately on startup
        scheduler.add_job(
            update_stocks_job,
            "interval",
            hours=1,
            next_run_time=datetime.now(timezone.utc)
        )
        scheduler.start()
        logger.info("Background AsyncIO Scheduler has started.")

def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Background AsyncIO Scheduler shut down successfully.")
