import json
from app.models.article import Article
from app.models.trend import TrendSnapshot
from app.services.aggregator import TechDataAggregator
from app.services.sentiment_analyzer import SentimentAnalyzer


def test_sentiment_analyzer_logic():
    # Positive text with booster
    pos_score, pos_label = SentimentAnalyzer.analyze_sentiment(
        "Supercharged release introduces massive speedup and outstanding reliability"
    )
    assert pos_score > 0.3
    assert pos_label == "Positive"

    # Negative text with vulnerability
    neg_score, neg_label = SentimentAnalyzer.analyze_sentiment(
        "Critical vulnerability and dangerous ransomware attack causes massive outage"
    )
    assert neg_score < -0.3
    assert neg_label == "Negative"

    # Negation handling ("not good" should not be positive)
    negated_score, negated_label = SentimentAnalyzer.analyze_sentiment(
        "The new framework is not good and hardly stable"
    )
    assert negated_score < 0.0

    # Neutral text
    neu_score, neu_label = SentimentAnalyzer.analyze_sentiment(
        "Meeting notes from standard committee discussion on Tuesday"
    )
    assert neu_label == "Neutral"


def test_tag_extraction_taxonomy():
    tags_ai = SentimentAnalyzer.extract_tags("Deploying LLM applications with ChatGPT and PyTorch")
    assert "AI" in tags_ai or "LLM" in tags_ai

    tags_rust_python = SentimentAnalyzer.extract_tags("High-speed web server built in Rust with Python bindings")
    assert "Rust" in tags_rust_python
    assert "Python" in tags_rust_python

    tags_cloud = SentimentAnalyzer.extract_tags("Kubernetes cluster autoscaling on AWS cloud infrastructure")
    assert "Cloud" in tags_cloud or "DevOps" in tags_cloud


def test_aggregator_stores_data_in_db(db_session):
    """Verifies that the aggregator correctly parses, scores, and persists articles into the database."""
    test_stories = [
        {
            "id": "test-story-1",
            "title": "Innovative Python library for scalable asynchronous data pipelines",
            "url": "https://example.com/python-pipeline",
            "by": "data_engineer",
            "score": 120,
            "descendants": 35,
            "time": 1700000000
        },
        {
            "id": "test-story-2",
            "title": "Severe security exploit and flaw discovered in web server",
            "url": "https://example.com/security-alert",
            "by": "sec_researcher",
            "score": 450,
            "descendants": 90,
            "time": 1700003600
        }
    ]

    new_count, articles = TechDataAggregator.process_and_save_stories(db_session, test_stories)
    assert new_count == 2
    assert len(articles) == 2

    # Verify records in database
    db_articles = db_session.query(Article).all()
    assert len(db_articles) == 2

    first_art = db_session.query(Article).filter(Article.external_id == "test-story-1").first()
    assert first_art is not None
    assert first_art.author == "data_engineer"
    assert first_art.sentiment_label == "Positive"
    assert first_art.sentiment_score > 0
    assert "Python" in json.loads(first_art.tags)

    second_art = db_session.query(Article).filter(Article.external_id == "test-story-2").first()
    assert second_art is not None
    assert second_art.sentiment_label == "Negative"
    assert second_art.sentiment_score < 0

    # Verify trend snapshots were generated
    snapshots = db_session.query(TrendSnapshot).all()
    assert len(snapshots) > 0


def test_aggregator_idempotency_no_duplicates(db_session):
    """Verifies that re-ingesting existing stories updates stats without duplicating records."""
    test_story = [{
        "id": "idempotent-id-100",
        "title": "Exciting Rust release improves compile times",
        "url": "https://rust-lang.org/release",
        "by": "rustacean",
        "score": 50,
        "descendants": 10,
        "time": 1700000000
    }]

    # Ingest first time
    count1, _ = TechDataAggregator.process_and_save_stories(db_session, test_story)
    assert count1 == 1
    assert db_session.query(Article).count() == 1

    # Ingest second time with updated score
    test_story[0]["score"] = 150
    test_story[0]["descendants"] = 30
    count2, _ = TechDataAggregator.process_and_save_stories(db_session, test_story)
    assert count2 == 0  # 0 new articles
    assert db_session.query(Article).count() == 1  # Still 1 record

    updated_record = db_session.query(Article).filter(Article.external_id == "idempotent-id-100").first()
    assert updated_record.score == 150
    assert updated_record.comments_count == 30


def test_articles_api_filtering_and_pagination(client, db_session):
    test_stories = [
        {"id": "api-1", "title": "Great Python breakthrough", "by": "dev1", "score": 10},
        {"id": "api-2", "title": "Critical Rust security failure", "by": "dev2", "score": 20},
        {"id": "api-3", "title": "Standard Linux update changelog", "by": "dev3", "score": 30},
    ]
    TechDataAggregator.process_and_save_stories(db_session, test_stories)

    # 1. Total articles listing
    res = client.get("/api/v1/articles?page=1&size=10")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3

    # 2. Search query filter
    res_search = client.get("/api/v1/articles?search=breakthrough")
    assert res_search.status_code == 200
    assert res_search.json()["total"] == 1
    assert res_search.json()["items"][0]["external_id"] == "api-1"

    # 3. Sentiment filter
    res_pos = client.get("/api/v1/articles?sentiment=Positive")
    assert res_pos.status_code == 200
    for item in res_pos.json()["items"]:
        assert item["sentiment_label"] == "Positive"

    # 4. Single article by ID
    first_id = data["items"][0]["id"]
    res_single = client.get(f"/api/v1/articles/{first_id}")
    assert res_single.status_code == 200
    assert res_single.json()["id"] == first_id


def test_trends_summary_metrics(client, db_session):
    test_stories = [
        {"id": "t-1", "title": "Wonderful Python web improvements", "by": "a", "score": 10},
        {"id": "t-2", "title": "Terrible malware crash outage", "by": "b", "score": 10},
    ]
    TechDataAggregator.process_and_save_stories(db_session, test_stories)

    res = client.get("/api/v1/trends/summary")
    assert res.status_code == 200
    data = res.json()
    assert data["total_articles"] == 2
    assert "sentiment" in data
    assert data["sentiment"]["positive"] >= 1
    assert data["sentiment"]["negative"] >= 1
    assert len(data["top_tags"]) > 0
    if data.get("last_sync_time"):
        assert data["last_sync_time"].endswith("Z")
    if data.get("timeline"):
        first_pt = data["timeline"][0]
        assert "avg_sentiment" in first_pt
        assert "active_sentiment" in first_pt
        assert "article_count" in first_pt


def test_timezone_utc_iso_serialization(client, db_session):
    """Verifies that all API date/time fields are serialized as ISO-8601 strings ending with 'Z'."""
    test_stories = [
        {"id": "tz-1", "title": "Python timezone verification story", "by": "tz_tester", "score": 10}
    ]
    TechDataAggregator.process_and_save_stories(db_session, test_stories)

    # 1. Summary endpoint last_sync_time and timeline
    res_summary = client.get("/api/v1/trends/summary")
    assert res_summary.status_code == 200
    data_summary = res_summary.json()
    assert data_summary["last_sync_time"] is not None
    assert data_summary["last_sync_time"].endswith("Z")
    assert len(data_summary["timeline"]) > 0
    assert data_summary["timeline"][0]["timestamp"].endswith("Z")

    # 2. Articles endpoint created_at
    res_articles = client.get("/api/v1/articles")
    assert res_articles.status_code == 200
    data_articles = res_articles.json()
    assert len(data_articles["items"]) > 0
    assert data_articles["items"][0]["created_at"].endswith("Z")

