import asyncio
import logging
from typing import Optional

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.aggregator import HackerNewsAPIError, TechDataAggregator

logger = logging.getLogger("background_worker")


class BackgroundWorker:
    """Async background worker for periodic data ingestion and trend analysis."""

    def __init__(self):
        self._task: Optional[asyncio.Task] = None
        self._is_running: bool = False

    async def _worker_loop(self):
        """Infinite loop periodically executing the synchronization pipeline."""
        logger.info(f"Starting background aggregation worker (interval: {settings.SYNC_INTERVAL_SECONDS}s)...")
        # Run initial sync after a short delay on startup
        await asyncio.sleep(2)

        while self._is_running:
            db = SessionLocal()
            try:
                logger.info("Executing periodic tech news synchronization...")
                new_count, total, _ = await TechDataAggregator.run_sync(
                    db, limit=settings.MAX_FEED_ITEMS
                )
                logger.info(f"Periodic sync completed: {new_count} new articles added. Total articles: {total}.")
            except HackerNewsAPIError as e:
                logger.warning(f"Periodic background sync skipped: external API unreachable ({e}).")
            except Exception as e:
                logger.error(f"Error during background sync execution: {e}", exc_info=True)
            finally:
                db.close()

            # Wait for next interval or until cancelled
            try:
                await asyncio.sleep(settings.SYNC_INTERVAL_SECONDS)
            except asyncio.CancelledError:
                break

    def start(self):
        """Starts the background worker task."""
        if not self._is_running:
            self._is_running = True
            self._task = asyncio.create_task(self._worker_loop())
            logger.info("Background worker task created.")

    async def stop(self):
        """Gracefully cancels and stops the background worker task."""
        if self._is_running:
            logger.info("Stopping background worker...")
            self._is_running = False
            if self._task:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            logger.info("Background worker stopped.")


background_worker = BackgroundWorker()
