from collections import defaultdict
from datetime import datetime
import json
from typing import Dict, List
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.datetime_utils import format_utc_iso
from app.models.article import Article
from app.models.sync_meta import SyncMetadata
from app.models.trend import TrendSnapshot
from app.schemas.trend import (
    DashboardStatsResponse,
    SentimentDistribution,
    TagTrendItem,
    TimelinePoint,
)

router = APIRouter(prefix="/trends", tags=["Trends"])


@router.get("/summary", response_model=DashboardStatsResponse)
def get_trends_summary(db: Session = Depends(get_db)):
    """Computes comprehensive dashboard metrics, sentiment breakdown, and tag trends."""
    total_articles = db.query(Article).count()

    # Query persistent sync metadata for the exact last sync execution timestamp
    sync_meta = db.query(SyncMetadata).filter(SyncMetadata.key == "last_sync_timestamp").first()
    last_sync = sync_meta.timestamp if sync_meta else None

    if total_articles == 0:
        return DashboardStatsResponse(
            total_articles=0,
            sentiment=SentimentDistribution(
                positive=0,
                neutral=0,
                negative=0,
                overall_score=0.0,
                overall_label="Neutral"
            ),
            top_tags=[],
            timeline=[],
            last_sync_time=last_sync
        )

    # Sentiment distribution
    pos_count = db.query(Article).filter(Article.sentiment_label == "Positive").count()
    neu_count = db.query(Article).filter(Article.sentiment_label == "Neutral").count()
    neg_count = db.query(Article).filter(Article.sentiment_label == "Negative").count()

    avg_score_raw = db.query(func.avg(Article.sentiment_score)).scalar() or 0.0
    overall_score = round(float(avg_score_raw), 3)

    if overall_score >= 0.05:
        overall_label = "Positive"
    elif overall_score <= -0.05:
        overall_label = "Negative"
    else:
        overall_label = "Neutral"

    sentiment_dist = SentimentDistribution(
        positive=pos_count,
        neutral=neu_count,
        negative=neg_count,
        overall_score=overall_score,
        overall_label=overall_label
    )

    # Top tech tags from articles
    all_articles = db.query(Article).all()
    tag_counts: Dict[str, int] = defaultdict(int)
    tag_sentiments: Dict[str, List[float]] = defaultdict(list)

    for art in all_articles:
        try:
            tags = json.loads(art.tags) if isinstance(art.tags, str) else art.tags
        except Exception:
            tags = []
        for tag in tags:
            tag_counts[tag] += 1
            tag_sentiments[tag].append(art.sentiment_score)

    top_tags_list: List[TagTrendItem] = []
    # Sort by frequency descending
    sorted_tags = sorted(tag_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
    for tag, count in sorted_tags:
        scores = tag_sentiments[tag]
        avg_tag_sentiment = round(sum(scores) / len(scores), 3) if scores else 0.0
        if avg_tag_sentiment >= 0.05:
            lbl = "Positive"
        elif avg_tag_sentiment <= -0.05:
            lbl = "Negative"
        else:
            lbl = "Neutral"
        top_tags_list.append(
            TagTrendItem(
                tag=tag,
                count=count,
                avg_sentiment=avg_tag_sentiment,
                sentiment_label=lbl
            )
        )

    # Timeline data points for chart
    timeline_map: Dict[str, List[float]] = defaultdict(list)
    articles_sorted = sorted(all_articles, key=lambda a: a.created_at)

    for art in articles_sorted:
        # Group by UTC ISO timestamp
        time_key = format_utc_iso(art.created_at)
        timeline_map[time_key].append(art.sentiment_score)

    timeline_points: List[TimelinePoint] = []
    # Populate granular points
    for t_key, scores in list(timeline_map.items())[-20:]:
        avg_s = round(sum(scores) / len(scores), 3)
        # Calculate active sentiment excluding neutral entries (|s| >= 0.05)
        active_scores = [s for s in scores if abs(s) >= 0.05]
        if active_scores:
            active_s = round(sum(active_scores) / len(active_scores), 3)
        else:
            active_s = avg_s

        timeline_points.append(
            TimelinePoint(
                timestamp=t_key,
                avg_sentiment=avg_s,
                active_sentiment=active_s,
                article_count=len(scores)
            )
        )

    # Fallback to last article if sync metadata was somehow never populated
    if not last_sync:
        last_article = db.query(Article).order_by(Article.created_at.desc()).first()
        last_sync = last_article.created_at if last_article else None

    return DashboardStatsResponse(
        total_articles=total_articles,
        sentiment=sentiment_dist,
        top_tags=top_tags_list,
        timeline=timeline_points,
        last_sync_time=last_sync
    )
