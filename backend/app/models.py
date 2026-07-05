import uuid
import datetime
from sqlalchemy import Column, String, Float, BigInteger, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.database import Base

class StockWatchlist(Base):
    __tablename__ = "stock_watchlist"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker = Column(String, unique=True, index=True, nullable=False)
    company_name = Column(String, nullable=True)
    added_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None))

    metrics = relationship("StockMetricsSnapshot", back_populates="stock", cascade="all, delete-orphan")
    reports = relationship("GeminiAnalysisReport", back_populates="stock", cascade="all, delete-orphan")

class StockMetricsSnapshot(Base):
    __tablename__ = "stock_metrics_snapshot"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stock_id = Column(UUID(as_uuid=True), ForeignKey("stock_watchlist.id", ondelete="CASCADE"), nullable=False)
    current_price = Column(Float, nullable=False)
    trailing_pe = Column(Float, nullable=True)
    market_cap = Column(BigInteger, nullable=True)
    fifty_two_week_high = Column(Float, nullable=False)
    fifty_two_week_low = Column(Float, nullable=False)
    price_history_7d = Column(JSONB, nullable=False)  # JSONB array of floats
    volume = Column(BigInteger, nullable=True)
    fetched_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None))

    stock = relationship("StockWatchlist", back_populates="metrics")

class GeminiAnalysisReport(Base):
    __tablename__ = "gemini_analysis_report"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stock_id = Column(UUID(as_uuid=True), ForeignKey("stock_watchlist.id", ondelete="CASCADE"), nullable=False)
    analysis_report = Column(Text, nullable=False)  # Text content
    trigger_type = Column(String, nullable=False)  # "SCHEDULED" or "MANUAL"
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None))

    stock = relationship("StockWatchlist", back_populates="reports")

class StockHolding(Base):
    __tablename__ = "stock_holdings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker = Column(String, unique=True, index=True, nullable=False)
    company_name = Column(String, nullable=True)
    quantity = Column(Float, nullable=False)
    average_buy_price = Column(Float, nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None))
