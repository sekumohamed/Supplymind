from sqlalchemy import Column, String, Float, Integer, DateTime
from sqlalchemy.dialects.sqlite import JSON
from datetime import datetime, timezone
from app.database import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(String, primary_key=True)
    croo_order_id = Column(String, unique=True, nullable=False)
    service_tier = Column(String, nullable=False)
    query_text = Column(String)
    query_hash = Column(String)
    status = Column(String, default="pending")
    price_usdc = Column(Float)
    caller_agent_id = Column(String)
    result_json = Column(JSON)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    delivered_at = Column(DateTime, nullable=True)
    processing_ms = Column(Integer, nullable=True)

    def __repr__(self):
        return f"<Order {self.croo_order_id} | {self.status}>"