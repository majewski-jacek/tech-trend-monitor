from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, field_serializer

from app.core.datetime_utils import format_utc_iso


class TagTrendItem(BaseModel):
    tag: str
    count: int
    avg_sentiment: float
    sentiment_label: str


class SentimentDistribution(BaseModel):
    positive: int
    neutral: int
    negative: int
    overall_score: float
    overall_label: str


class TimelinePoint(BaseModel):
    timestamp: str
    avg_sentiment: float
    active_sentiment: float
    article_count: int


class DashboardStatsResponse(BaseModel):
    total_articles: int
    sentiment: SentimentDistribution
    top_tags: List[TagTrendItem]
    timeline: List[TimelinePoint]
    last_sync_time: Optional[datetime] = None

    @field_serializer("last_sync_time")
    def serialize_last_sync_time(self, v: Optional[datetime]) -> Optional[str]:
        return format_utc_iso(v)
