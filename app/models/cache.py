from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.sqlite import JSON
from datetime import datetime, timedelta, timezone
from app.database import Base
class QueryCache(Base):
    __tablename__ = "query_cache"

    id = Column(String, primary_key=True)
    query_hash = Column(String, unique=True, nullable=False)
    result_json = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(
    DateTime,
    default=lambda: datetime.now(timezone.utc) + timedelta(minutes=30)
)