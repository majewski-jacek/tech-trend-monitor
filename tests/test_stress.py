import asyncio
import pytest


@pytest.mark.asyncio
async def test_concurrent_read_load(async_client, db_session):
    """
    Stress / Concurrency Test 1:
    Executes 50 concurrent requests to /api/trends/summary and 50 concurrent requests to /api/articles.
    Verifies that the server and database handle high concurrent read load without failure.
    """
    # 50 concurrent requests to trends summary endpoint
    summary_tasks = [async_client.get("/api/trends/summary") for _ in range(50)]
    # 50 concurrent requests to articles endpoint
    articles_tasks = [async_client.get("/api/articles?page=1&size=10") for _ in range(50)]

    all_read_tasks = summary_tasks + articles_tasks
    responses = await asyncio.gather(*all_read_tasks, return_exceptions=True)

    assert len(responses) == 100, f"Expected 100 responses, got {len(responses)}"

    for i, resp in enumerate(responses):
        assert not isinstance(resp, Exception), f"Request #{i} failed with exception: {resp}"
        assert resp.status_code == 200, f"Request #{i} returned status {resp.status_code}: {resp.text}"
        assert resp.status_code != 500, f"Request #{i} resulted in internal server error 500"

        data = resp.json()
        assert isinstance(data, dict), f"Request #{i} response is not a valid JSON object"

    # Give proactor event loop on Windows time to flush transport closing callbacks
    await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_concurrent_sync_requests_sqlite_concurrency(async_client, auth_headers):
    """
    Stress / Concurrency Test 2:
    Simulates 5 concurrent POST requests to /api/sync fired in the exact same fraction of a second.
    Verifies that SQLite handles concurrency without 'sqlite3.OperationalError: database is locked'
    and ensures that no request returns HTTP 500 Internal Server Error.
    """
    # Dispatch 5 simultaneous sync requests in the same millisecond
    sync_tasks = [
        async_client.post("/api/sync", headers=auth_headers)
        for _ in range(5)
    ]

    responses = await asyncio.gather(*sync_tasks, return_exceptions=True)

    assert len(responses) == 5, f"Expected 5 sync responses, got {len(responses)}"

    for i, resp in enumerate(responses):
        assert not isinstance(resp, Exception), (
            f"Concurrent sync #{i} raised an unhandled exception (e.g. database locked): {resp}"
        )
        assert resp.status_code != 500, f"Concurrent sync #{i} failed with HTTP 500: {resp.text}"
        assert resp.status_code == 200, f"Concurrent sync #{i} failed with HTTP {resp.status_code}: {resp.text}"

        data = resp.json()
        assert data["status"] == "success"
        assert "new_articles_count" in data
        assert "total_articles" in data
        assert "timestamp" in data
        assert data["timestamp"].endswith("Z")

    # Give proactor event loop on Windows time to flush transport closing callbacks
    await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_concurrent_mixed_read_write_stress(async_client, auth_headers):
    """
    Stress / Concurrency Test 3:
    Simulates a heavy mixed workload: 50 concurrent read requests (/api/trends/summary, /api/articles)
    executed simultaneously alongside 5 concurrent write requests (/api/sync).
    Verifies no race conditions, no locked database errors, and zero HTTP 500 responses.
    """
    read_tasks = (
        [async_client.get("/api/trends/summary") for _ in range(25)] +
        [async_client.get("/api/articles?page=1&size=5") for _ in range(25)]
    )
    sync_tasks = [
        async_client.post("/api/sync", headers=auth_headers)
        for _ in range(5)
    ]

    all_workload = read_tasks + sync_tasks
    responses = await asyncio.gather(*all_workload, return_exceptions=True)

    assert len(responses) == 55

    for i, resp in enumerate(responses):
        assert not isinstance(resp, Exception), f"Mixed load task #{i} raised exception: {resp}"
        assert resp.status_code != 500, f"Task #{i} returned HTTP 500: {resp.text}"
        assert resp.status_code == 200, f"Task #{i} returned HTTP {resp.status_code}: {resp.text}"

    await asyncio.sleep(0.01)
