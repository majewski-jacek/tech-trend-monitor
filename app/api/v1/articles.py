import json
import math
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.article import Article
from app.schemas.article import ArticleResponse, PaginatedArticlesResponse

router = APIRouter(prefix="/articles", tags=["Articles"])


@router.get("", response_model=PaginatedArticlesResponse)
def list_articles(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(15, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search term in title or author"),
    tag: Optional[str] = Query(None, description="Filter by tech tag (e.g. AI, Python, Rust)"),
    sentiment: Optional[str] = Query(None, description="Filter by sentiment (Positive, Neutral, Negative)"),
    sort_by: str = Query("created_at", description="Field to sort by (created_at, score, sentiment_score)"),
    order: str = Query("desc", description="Sort order (asc, desc)"),
    db: Session = Depends(get_db)
):
    """Retrieves paginated, searchable, and filtered tech articles."""
    query = db.query(Article)

    # Search filter
    if search:
        search_pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Article.title.ilike(search_pattern),
                Article.author.ilike(search_pattern),
                Article.keywords.ilike(search_pattern)
            )
        )

    # Tag filter
    if tag:
        tag_pattern = f'%"{tag.strip()}"%'
        query = query.filter(Article.tags.ilike(tag_pattern))

    # Sentiment filter
    if sentiment:
        query = query.filter(Article.sentiment_label.ilike(sentiment.strip()))

    # Sorting
    sort_column = Article.created_at
    if sort_by == "score":
        sort_column = Article.score
    elif sort_by == "sentiment_score":
        sort_column = Article.sentiment_score

    if order.lower() == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    total = query.count()
    total_pages = max(1, math.ceil(total / size))
    offset = (page - 1) * size
    items = query.offset(offset).limit(size).all()

    return PaginatedArticlesResponse(
        items=[ArticleResponse.model_validate(item) for item in items],
        total=total,
        page=page,
        size=size,
        total_pages=total_pages
    )


@router.get("/{article_id}", response_model=ArticleResponse)
def get_article(article_id: int, db: Session = Depends(get_db)):
    """Retrieves a single article by ID."""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Article with ID {article_id} not found."
        )
    return ArticleResponse.model_validate(article)
