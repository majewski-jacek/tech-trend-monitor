import json
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, field_serializer, field_validator

from app.core.datetime_utils import format_utc_iso


class ArticleBase(BaseModel):
    external_id: str
    title: str
    url: Optional[str] = None
    author: Optional[str] = None
    score: int = 0
    comments_count: int = 0
    source: str = "Hacker News"
    sentiment_score: float = 0.0
    sentiment_label: str = "Neutral"
    keywords: List[str] = []
    tags: List[str] = []
    published_at: Optional[datetime] = None


class ArticleResponse(ArticleBase):
    id: int
    created_at: datetime

    @field_validator("keywords", mode="before")
    def parse_keywords(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return [k.strip() for k in v.split(",") if k.strip()]
        return v or []

    @field_validator("tags", mode="before")
    def parse_tags(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return [t.strip() for t in v.split(",") if t.strip()]
        return v or []

    @field_serializer("created_at")
    def serialize_created_at(self, v: datetime) -> str:
        return format_utc_iso(v)

    @field_serializer("published_at")
    def serialize_published_at(self, v: Optional[datetime]) -> Optional[str]:
        return format_utc_iso(v)

    model_config = ConfigDict(from_attributes=True)


class PaginatedArticlesResponse(BaseModel):
    items: List[ArticleResponse]
    total: int
    page: int
    size: int
    total_pages: int
