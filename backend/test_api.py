import sys
import os
import pytest
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Add backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import app
from app.database import Base, get_db

from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(element, compiler, **kw):
    return "JSON"

# Use in-memory SQLite database for testing (SQLAlchemy compiles JSONB to JSON in SQLite)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestAsyncSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def override_get_db():
    async with TestAsyncSessionLocal() as session:
        yield session

# Inject test database connection
app.dependency_overrides[get_db] = override_get_db

import pytest_asyncio

@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

# Mocked responses for Vedanta and Tata Steel
MOCK_VEDANTA_METRICS = {
    "ticker": "VEDL.NS",
    "company_name": "Vedanta Limited",
    "current_price": 420.50,
    "trailing_pe": 15.4,
    "market_cap": 156000000000,
    "fifty_two_week_high": 480.0,
    "fifty_two_week_low": 210.0,
    "price_history_7d": [410.0, 412.0, 415.0, 411.0, 418.0, 419.0, 420.50]
}

MOCK_TATA_METRICS = {
    "ticker": "TATASTEEL.NS",
    "company_name": "Tata Steel Limited",
    "current_price": 150.25,
    "trailing_pe": 12.8,
    "market_cap": 185000000000,
    "fifty_two_week_high": 170.0,
    "fifty_two_week_low": 110.0,
    "price_history_7d": [145.0, 147.0, 148.0, 146.0, 149.0, 150.0, 150.25]
}

@pytest.mark.asyncio
@patch("app.routers.stocks.validate_and_fetch_stock_data")
@patch("app.routers.stocks.analyze_stock")
async def test_watchlist_rest_flow(mock_analyze, mock_fetch):
    # Configure mock returns
    mock_fetch.side_effect = lambda ticker: MOCK_VEDANTA_METRICS if ticker == "VEDL.NS" else MOCK_TATA_METRICS
    mock_analyze.return_value = "## Valuation Assessment\nMocked report output."

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Watchlist should initially be empty
        res = await ac.get("/api/stocks")
        assert res.status_code == 200
        assert len(res.json()) == 0

        # 2. Add Vedanta (VEDL.NS)
        res = await ac.post("/api/stocks", json={"ticker": "VEDL.NS"})
        assert res.status_code == 201
        data = res.json()
        assert data["ticker"] == "VEDL.NS"
        assert data["company_name"] == "Vedanta Limited"
        assert data["latest_metrics"]["current_price"] == 420.50
        assert "Mocked report" in data["latest_report"]["analysis_report"]
        stock_id = data["id"]

        # 3. Add Tata Steel (TATASTEEL.NS)
        res = await ac.post("/api/stocks", json={"ticker": "TATASTEEL.NS"})
        assert res.status_code == 201
        assert res.json()["ticker"] == "TATASTEEL.NS"

        # 4. Get Watchlist (should contain both securities)
        res = await ac.get("/api/stocks")
        assert res.status_code == 200
        watchlist = res.json()
        assert len(watchlist) == 2
        assert any(item["ticker"] == "VEDL.NS" for item in watchlist)
        assert any(item["ticker"] == "TATASTEEL.NS" for item in watchlist)

        # 5. Trigger on-demand AI analysis for VEDL.NS
        res = await ac.post(f"/api/stocks/{stock_id}/analyze")
        assert res.status_code == 200
        report = res.json()
        assert "Mocked report" in report["analysis_report"]

        # 6. Delete VEDL.NS from watchlist
        res = await ac.delete(f"/api/stocks/{stock_id}")
        assert res.status_code == 204

        # 7. Get watchlist (should only contain TATASTEEL.NS now)
        res = await ac.get("/api/stocks")
        assert res.status_code == 200
        assert len(res.json()) == 1
        assert res.json()[0]["ticker"] == "TATASTEEL.NS"
