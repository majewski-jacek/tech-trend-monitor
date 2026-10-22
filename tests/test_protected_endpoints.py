import pytest
from unittest.mock import patch
import httpx


def test_me_endpoint_without_token(client):
    """Accessing /auth/me without an authentication token must return 401 Unauthorized."""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert "detail" in response.json()


def test_me_endpoint_with_invalid_token(client):
    """Accessing /auth/me with an invalid JWT token must return 401 Unauthorized."""
    headers = {"Authorization": "Bearer invalid.malformed.token"}
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 401


def test_me_endpoint_with_valid_token(client, test_user, auth_headers):
    """Accessing /auth/me with a valid JWT token must return 200 OK and user profile."""
    response = client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_user.id
    assert data["username"] == test_user.username
    assert data["email"] == test_user.email


def test_sync_endpoint_without_token(client):
    """Protected POST /sync without token must return 401 Unauthorized."""
    response = client.post("/api/v1/sync")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_sync_endpoint_with_valid_token(async_client, auth_headers):
    """Protected POST /sync with valid token must return 200 OK and synchronization stats."""
    response = await async_client.post("/api/v1/sync", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "new_articles_count" in data
    assert "total_articles" in data
    assert data["total_articles"] >= data["new_articles_count"]
    assert "timestamp" in data
    assert data["timestamp"].endswith("Z")


@pytest.mark.asyncio
async def test_sync_updates_metadata_timestamp_even_without_new_articles(async_client, auth_headers):
    """Verifies that calling sync updates last_sync_timestamp in metadata even when 0 new articles arrive."""
    res1 = await async_client.post("/api/v1/sync", headers=auth_headers)
    assert res1.status_code == 200
    time1 = res1.json()["timestamp"]

    res_summary1 = await async_client.get("/api/v1/trends/summary")
    assert res_summary1.status_code == 200
    summary1 = res_summary1.json()
    assert summary1["last_sync_time"] == time1

    # Second sync (simulating sync with no new posts)
    res2 = await async_client.post("/api/v1/sync", headers=auth_headers)
    assert res2.status_code == 200
    time2 = res2.json()["timestamp"]

    res_summary2 = await async_client.get("/api/v1/trends/summary")
    assert res_summary2.status_code == 200
    summary2 = res_summary2.json()
    assert summary2["last_sync_time"] == time2


@pytest.mark.asyncio
async def test_sync_network_failure_returns_503(async_client, auth_headers):
    """Verifies that network errors (no internet) return HTTP 503 instead of pretending sync succeeded."""
    with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("Network is unreachable")):
        response = await async_client.post("/api/v1/sync", headers=auth_headers)
        assert response.status_code == 503
        data = response.json()
        assert "detail" in data
        assert "Brak połączenia z zewnętrznym API Hacker News" in data["detail"]
