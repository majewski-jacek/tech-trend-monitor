from datetime import datetime
from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from app.core.database import Base


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String(100), unique=True, index=True, nullable=False)
    title = Column(String(500), nullable=False)
    url = Column(String(1000), nullable=True)
    author = Column(String(100), nullable=True)
    score = Column(Integer, default=0, nullable=False)
    comments_count = Column(Integer, default=0, nullable=False)
    source = Column(String(50), default="Hacker News", nullable=False)
    
    # NLP & Trend features
    sentiment_score = Column(Float, default=0.0, nullable=False)  # Range -1.0 to 1.0
    sentiment_label = Column(String(20), default="Neutral", nullable=False)  # Positive, Neutral, Negative
    keywords = Column(Text, default="[]", nullable=False)  # JSON-encoded array of extracted keywords
    tags = Column(Text, default="[]", nullable=False)  # JSON-encoded array of matched tech tags
    
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
