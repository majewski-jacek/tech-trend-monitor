import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db
from app.core.config import settings
from app.core.datetime_utils import utc_now
from app.models.user import User
from app.schemas.sync import SyncResultResponse
from app.services.aggregator import HackerNewsAPIError, TechDataAggregator

router = APIRouter(prefix="/sync", tags=["Sync"])
logger = logging.getLogger("sync_endpoint")


@router.post("", response_model=SyncResultResponse, status_code=status.HTTP_200_OK)
async def trigger_sync(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Protected endpoint to manually trigger a data aggregation cycle.
    Fetches the latest public tech news, performs NLP sentiment analysis,
    updates trend snapshots, and broadcasts real-time updates to connected WebSocket clients.
    """
    try:
        new_count, total_count, sync_time = await TechDataAggregator.run_sync(
            db, limit=settings.MAX_FEED_ITEMS
        )
    except HackerNewsAPIError as e:
        logger.warning(f"Manual sync failed: external API unreachable ({e})")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Brak połączenia z zewnętrznym API Hacker News. Sprawdź połączenie z internetem."
        )

    if new_count > 0:
        message = f"Pobrano i przeanalizowano {new_count} nowych artykułów."
    else:
        message = "Baza jest aktualna. Brak nowych wpisów w API."

    return SyncResultResponse(
        status="success",
        message=message,
        new_articles_count=new_count,
        total_articles=total_count,
        timestamp=sync_time
    )
