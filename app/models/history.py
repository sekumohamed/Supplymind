from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON
from app.database import Base


class QueryHistory(Base):
    __tablename__ = "query_history"

    id = Column(Integer, primary_key=True, index=True)
    query = Column(String, nullable=False, index=True)
    query_hash = Column(String, index=True)
    depth = Column(String, default="standard")
    risk_level = Column(String)
    risk_score = Column(Float)
    executive_summary = Column(String)
    disruption_signals = Column(JSON)
    tariff_exposure = Column(JSON)
    confidence_score = Column(Float)
    processing_time_ms = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)