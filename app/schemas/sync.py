from datetime import datetime
from pydantic import BaseModel, field_serializer

from app.core.datetime_utils import format_utc_iso


class SyncResultResponse(BaseModel):
    status: str
    message: str
    new_articles_count: int
    total_articles: int
    timestamp: datetime

    @field_serializer("timestamp")
    def serialize_timestamp(self, v: datetime) -> str:
        return format_utc_iso(v)
