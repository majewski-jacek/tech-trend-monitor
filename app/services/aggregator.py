import asyncio
from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional, Tuple
import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.datetime_utils import format_utc_iso, utc_now
from app.models.article import Article
from app.models.trend import TrendSnapshot
from app.models.sync_meta import SyncMetadata
from app.services.sentiment_analyzer import SentimentAnalyzer
from app.services.websocket_manager import ws_manager

logger = logging.getLogger("aggregator")


class HackerNewsAPIError(Exception):
    """Raised when external Hacker News API call fails due to network outage, connection error, or timeout."""
    pass


# High-quality fallback items representing diverse tech news and sentiment spectrum
SEED_TECH_STORIES: List[Dict[str, Any]] = [
    {
        "id": "hn-seed-1",
        "title": "Show HN: Fast and lightweight ASGI server written in Rust with Python bindings",
        "url": "https://github.com/example/rust-asgi",
        "by": "alex_rustacean",
        "score": 342,
        "descendants": 87,
        "time": 1729600000
    },
    {
        "id": "hn-seed-2",
        "title": "Critical remote code execution vulnerability discovered in widespread open-source library",
        "url": "https://cybersecurity.news/critical-rce-flaw",
        "by": "sec_analyst",
        "score": 512,
        "descendants": 145,
        "time": 1729598000
    },
    {
        "id": "hn-seed-3",
        "title": "Next-generation LLM delivers outstanding reasoning capabilities at a fraction of compute cost",
        "url": "https://ai-research.org/breakthrough-reasoning-model",
        "by": "ml_researcher",
        "score": 890,
        "descendants": 320,
        "time": 1729595000
    },
    {
        "id": "hn-seed-4",
        "title": "Major cloud provider experiences global DNS outage affecting thousands of services",
        "url": "https://status.cloud.com/outage-report",
        "by": "sysadmin_dan",
        "score": 620,
        "descendants": 210,
        "time": 1729592000
    },
    {
        "id": "hn-seed-5",
        "title": "Python 3.13 introduces experimental free-threaded mode without the Global Interpreter Lock (GIL)",
        "url": "https://docs.python.org/3.13/whatsnew/3.13.html",
        "by": "guido_fan",
        "score": 750,
        "descendants": 298,
        "time": 1729590000
    },
    {
        "id": "hn-seed-6",
        "title": "PostgreSQL 17 released with major query optimization and memory management improvements",
        "url": "https://www.postgresql.org/about/news/postgresql-17-released-2722/",
        "by": "db_guru",
        "score": 415,
        "descendants": 95,
        "time": 1729588000
    },
    {
        "id": "hn-seed-7",
        "title": "Docker announces native WebAssembly support directly inside container engine",
        "url": "https://docker.com/blog/native-wasm-support",
        "by": "containerman",
        "score": 380,
        "descendants": 84,
        "time": 1729585000
    },
    {
        "id": "hn-seed-8",
        "title": "Malware campaign targets developers through malicious typosquatting npm packages",
        "url": "https://threatintel.io/npm-malware-wave",
        "by": "hunter_sec",
        "score": 290,
        "descendants": 73,
        "time": 1729580000
    },
    {
        "id": "hn-seed-9",
        "title": "Why we migrated our microservices architecture back to an elegant modular monolith",
        "url": "https://eng.blog/back-to-modular-monolith",
        "by": "lead_arch",
        "score": 930,
        "descendants": 450,
        "time": 1729575000
    },
    {
        "id": "hn-seed-10",
        "title": "FastAPI meets TypeScript: End-to-end type safety for modern full-stack web applications",
        "url": "https://fullstack-tech.dev/fastapi-typescript",
        "by": "tiangolo_admirer",
        "score": 310,
        "descendants": 62,
        "time": 1729570000
    }
]


class TechDataAggregator:
    """Service to fetch, analyze sentiment, tag tech trends, and store articles."""

    _sync_lock: Optional[asyncio.Lock] = None
    _sync_lock_loop: Optional[asyncio.AbstractEventLoop] = None

    @classmethod
    def _get_sync_lock(cls) -> asyncio.Lock:
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if cls._sync_lock is None or cls._sync_lock_loop != current_loop:
            cls._sync_lock = asyncio.Lock()
            cls._sync_lock_loop = current_loop
        return cls._sync_lock

    @classmethod
    async def fetch_hn_story_ids(cls, client: httpx.AsyncClient, limit: int = 25) -> List[int]:
        """Fetches top story IDs from Hacker News Firebase API."""
        url = f"{settings.HACKER_NEWS_API_BASE}/topstories.json"
        try:
            response = await client.get(url, timeout=5.0)
            response.raise_for_status()
            ids = response.json()
            return ids[:limit] if isinstance(ids, list) else []
        except (httpx.RequestError, httpx.HTTPStatusError, asyncio.TimeoutError) as e:
            logger.error(f"Failed to reach Hacker News API endpoint {url}: {e}")
            raise HackerNewsAPIError(f"Brak połączenia z zewnętrznym API Hacker News: {e}") from e

    @classmethod
    async def fetch_hn_item(cls, client: httpx.AsyncClient, item_id: int) -> Optional[Dict[str, Any]]:
        """Fetches item details from Hacker News Firebase API."""
        url = f"{settings.HACKER_NEWS_API_BASE}/item/{item_id}.json"
        try:
            response = await client.get(url, timeout=4.0)
            if response.status_code == 200:
                data = response.json()
                if data and data.get("type") == "story" and data.get("title"):
                    return data
        except Exception as e:
            logger.debug(f"Error fetching HN item {item_id}: {e}")
        return None

    @classmethod
    async def collect_raw_stories(cls, limit: int = 25, fallback_to_seed: bool = False) -> List[Dict[str, Any]]:
        """Collects raw stories from Hacker News. If network/API fails, raises HackerNewsAPIError unless fallback_to_seed=True."""
        stories: List[Dict[str, Any]] = []
        client = httpx.AsyncClient(timeout=8.0)
        try:
            story_ids = await cls.fetch_hn_story_ids(client, limit=limit)
            if story_ids:
                tasks = [cls.fetch_hn_item(client, sid) for sid in story_ids]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for res in results:
                    if isinstance(res, dict) and res.get("title"):
                        stories.append(res)
        except HackerNewsAPIError:
            if fallback_to_seed:
                logger.warning("Using fallback curated tech dataset (fallback_to_seed=True).")
                return SEED_TECH_STORIES
            raise
        except (httpx.RequestError, httpx.HTTPStatusError, asyncio.TimeoutError) as e:
            logger.error(f"Network error while collecting stories from Hacker News: {e}")
            if fallback_to_seed:
                logger.warning("Using fallback curated tech dataset (fallback_to_seed=True).")
                return SEED_TECH_STORIES
            raise HackerNewsAPIError(f"Brak połączenia z zewnętrznym API Hacker News: {e}") from e
        finally:
            await client.aclose()
            await asyncio.sleep(0.01)

        return stories

    @classmethod
    def process_and_save_stories(
        cls, db: Session, raw_stories: List[Dict[str, Any]], sync_time: Optional[datetime] = None
    ) -> Tuple[int, List[Article]]:
        """Processes raw stories: applies NLP sentiment, extracts tags, and upserts to DB."""
        new_articles: List[Article] = []
        now = sync_time if sync_time is not None else utc_now()

        for item in raw_stories:
            ext_id = str(item.get("id"))
            title = (item.get("title") or "").strip()
            if not title:
                continue

            # Analyze sentiment and extract tags/keywords
            sentiment_score, sentiment_label = SentimentAnalyzer.analyze_sentiment(title)
            tags = SentimentAnalyzer.extract_tags(title)
            keywords = SentimentAnalyzer.extract_keywords(title)

            # Format published date
            published_at = None
            if item.get("time"):
                try:
                    published_at = datetime.fromtimestamp(item["time"], tz=timezone.utc)
                except Exception:
                    published_at = now

            existing = db.query(Article).filter(Article.external_id == ext_id).first()
            if existing:
                # Update dynamic metrics
                existing.score = int(item.get("score") or existing.score)
                existing.comments_count = int(item.get("descendants") or existing.comments_count)
            else:
                article = Article(
                    external_id=ext_id,
                    title=title,
                    url=item.get("url"),
                    author=item.get("by") or "anonymous",
                    score=int(item.get("score") or 0),
                    comments_count=int(item.get("descendants") or 0),
                    source="Hacker News",
                    sentiment_score=sentiment_score,
                    sentiment_label=sentiment_label,
                    keywords=json.dumps(keywords),
                    tags=json.dumps(tags),
                    published_at=published_at,
                    created_at=now
                )
                db.add(article)
                new_articles.append(article)

        db.commit()

        # Update historical trend snapshots
        cls.record_trend_snapshots(db)

        # Update last_sync_timestamp metadata
        meta = db.query(SyncMetadata).filter(SyncMetadata.key == "last_sync_timestamp").first()
        if not meta:
            meta = SyncMetadata(
                key="last_sync_timestamp",
                timestamp=now,
                details="Stories processed"
            )
            db.add(meta)
        else:
            meta.timestamp = now
        db.commit()

        return len(new_articles), new_articles

    @classmethod
    def record_trend_snapshots(cls, db: Session):
        """Calculates current tag frequency and average sentiment and records TrendSnapshot."""
        all_articles = db.query(Article).all()
        if not all_articles:
            return

        tag_counts: Dict[str, int] = {}
        tag_sentiment_sums: Dict[str, float] = {}

        for art in all_articles:
            try:
                tags = json.loads(art.tags) if isinstance(art.tags, str) else art.tags
            except Exception:
                tags = []
            
            for tag in tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
                tag_sentiment_sums[tag] = tag_sentiment_sums.get(tag, 0.0) + art.sentiment_score

        now = utc_now()
        for tag, count in tag_counts.items():
            avg_sent = round(tag_sentiment_sums[tag] / count, 3) if count > 0 else 0.0
            snapshot = TrendSnapshot(
                tag=tag,
                count=count,
                avg_sentiment=avg_sent,
                recorded_at=now
            )
            db.add(snapshot)

        db.commit()

    @classmethod
    async def run_sync(cls, db: Session, limit: int = 25) -> Tuple[int, int, datetime]:
        """
        Executes complete sync workflow:
        1. Collects raw stories
        2. Analyzes & saves to database
        3. Broadcasts real-time events over WebSockets
        Returns (new_articles_count, total_articles_count, sync_timestamp).
        """
        async with cls._get_sync_lock():
            # Notify WebSocket clients that sync has started
            await ws_manager.broadcast({
                "type": "SYNC_STATUS",
                "status": "started",
                "timestamp": format_utc_iso(utc_now())
            })

            try:
                raw_stories = await cls.collect_raw_stories(limit=limit, fallback_to_seed=False)
            except HackerNewsAPIError as e:
                logger.warning(f"Sync operation aborted due to external network failure: {e}")
                await ws_manager.broadcast({
                    "type": "SYNC_STATUS",
                    "status": "failed",
                    "error": "Brak połączenia z zewnętrznym API Hacker News. Sprawdź połączenie z internetem.",
                    "timestamp": format_utc_iso(utc_now())
                })
                raise

            sync_time = utc_now()
            new_count, new_articles = cls.process_and_save_stories(db, raw_stories, sync_time=sync_time)
            total_articles = db.query(Article).count()

            # Update last_sync_timestamp in metadata
            meta = db.query(SyncMetadata).filter(SyncMetadata.key == "last_sync_timestamp").first()
            if not meta:
                meta = SyncMetadata(
                    key="last_sync_timestamp",
                    timestamp=sync_time,
                    details="Sync action completed"
                )
                db.add(meta)
            else:
                meta.timestamp = sync_time
            db.commit()

            # Format newly added articles for broadcast
            new_items_payload = [
                {
                    "id": a.id,
                    "title": a.title,
                    "url": a.url,
                    "author": a.author,
                    "sentiment_score": a.sentiment_score,
                    "sentiment_label": a.sentiment_label,
                    "tags": json.loads(a.tags) if isinstance(a.tags, str) else a.tags,
                    "created_at": format_utc_iso(a.created_at)
                }
                for a in new_articles
            ]

            # Broadcast newly ingested articles only if new articles were actually added
            if new_count > 0:
                await ws_manager.broadcast({
                    "type": "NEW_ARTICLES",
                    "new_count": new_count,
                    "total_articles": total_articles,
                    "articles": new_items_payload,
                    "last_sync_time": format_utc_iso(sync_time),
                    "timestamp": format_utc_iso(sync_time)
                })

            await ws_manager.broadcast({
                "type": "SYNC_STATUS",
                "status": "completed",
                "new_count": new_count,
                "total_articles": total_articles,
                "last_sync_time": format_utc_iso(sync_time),
                "timestamp": format_utc_iso(sync_time)
            })

            return new_count, total_articles, sync_time
