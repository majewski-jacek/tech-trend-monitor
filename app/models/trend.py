from sqlalchemy import Column, DateTime, Float, Integer, String
from app.core.database import Base
from app.core.datetime_utils import utc_now


class TrendSnapshot(Base):
    """Stores historical aggregations of tech tags and their average sentiment."""
    __tablename__ = "trend_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    tag = Column(String(100), index=True, nullable=False)
    count = Column(Integer, default=0, nullable=False)
    avg_sentiment = Column(Float, default=0.0, nullable=False)
    recorded_at = Column(DateTime, default=utc_now, nullable=False, index=True)
