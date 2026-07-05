from pydantic import BaseModel, Field, field_serializer
from uuid import UUID
from datetime import datetime
from typing import List, Optional

class StockWatchlistCreate(BaseModel):
    ticker: str = Field(..., description="Stock ticker symbol (e.g., AAPL, TATASTEEL.NS)")

class StockMetricsSnapshotResponse(BaseModel):
    id: UUID
    stock_id: UUID
    current_price: float
    trailing_pe: Optional[float] = None
    market_cap: Optional[int] = None
    fifty_two_week_high: float
    fifty_two_week_low: float
    price_history_7d: List[float]
    volume: Optional[int] = None
    fetched_at: datetime

    @field_serializer('fetched_at')
    def serialize_fetched_at(self, dt: datetime, _info):
        return dt.isoformat() + "Z" if dt.tzinfo is None else dt.isoformat()

    class Config:
        from_attributes = True

class GeminiAnalysisReportResponse(BaseModel):
    id: UUID
    stock_id: UUID
    analysis_report: str
    trigger_type: str
    created_at: datetime

    @field_serializer('created_at')
    def serialize_created_at(self, dt: datetime, _info):
        return dt.isoformat() + "Z" if dt.tzinfo is None else dt.isoformat()

    class Config:
        from_attributes = True

class StockWatchlistResponse(BaseModel):
    id: UUID
    ticker: str
    company_name: Optional[str] = None
    added_at: datetime
    latest_metrics: Optional[StockMetricsSnapshotResponse] = None
    latest_report: Optional[GeminiAnalysisReportResponse] = None

    @field_serializer('added_at')
    def serialize_added_at(self, dt: datetime, _info):
        return dt.isoformat() + "Z" if dt.tzinfo is None else dt.isoformat()

    class Config:
        from_attributes = True

class StockHoldingCreate(BaseModel):
    ticker: str
    quantity: float
    average_buy_price: float

class StockHoldingResponse(BaseModel):
    id: UUID
    ticker: str
    company_name: Optional[str] = None
    quantity: float
    average_buy_price: float
    updated_at: datetime

    @field_serializer('updated_at')
    def serialize_updated_at(self, dt: datetime, _info):
        return dt.isoformat() + "Z" if dt.tzinfo is None else dt.isoformat()

    class Config:
        from_attributes = True
