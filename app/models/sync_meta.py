from datetime import datetime
from sqlalchemy import Column, DateTime, String
from app.core.database import Base


class SyncMetadata(Base):
    """Stores persistent system metadata such as the exact timestamp of the last sync run."""
    __tablename__ = "sync_metadata"

    key = Column(String(50), primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    details = Column(String(255), nullable=True)
