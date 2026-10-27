def test_register_user_success(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "newdev",
            "email": "newdev@example.com",
            "password": "strongpassword123"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "newdev"
    assert data["email"] == "newdev@example.com"
    assert "id" in data
    assert "hashed_password" not in data


def test_register_user_duplicate_email(client, test_user):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "anotherdev",
            "email": test_user.email,  # duplicate
            "password": "password123"
        }
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_register_user_duplicate_username(client, test_user):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": test_user.username,  # duplicate
            "email": "unique@example.com",
            "password": "password123"
        }
    )
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


def test_register_user_validation_error(client):
    # Short password
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "validname",
            "email": "valid@example.com",
            "password": "123"  # too short (<6)
        }
    )
    assert response.status_code == 422


def test_login_success_with_username(client, test_user):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": test_user.username,
            "password": "securepassword123"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == test_user.username
    assert "access_token" in response.cookies


def test_login_success_with_email(client, test_user):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": test_user.email,
            "password": "securepassword123"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == test_user.email


def test_login_invalid_password(client, test_user):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": test_user.username,
            "password": "wrongpassword"
        }
    )
    assert response.status_code == 401
    assert "Invalid" in response.json()["detail"]


def test_login_nonexistent_user(client):
    response = client.post(
        "/api/v1/auth/login",
        json={
            "username_or_email": "nonexistent_user",
            "password": "password123"
        }
    )
    assert response.status_code == 401


def test_logout_without_token_fails(client):
    """Logging out without an authentication token must return 401 Unauthorized."""
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 401


def test_logout_with_token_blacklists_token(client):
    """Verifies that logging out invalidates token on blacklist, and using it afterwards returns 401."""
    # 1. Register and login to obtain a real token
    client.post(
        "/api/v1/auth/register",
        json={"username": "logoutuser", "email": "logoutuser@example.com", "password": "securepwd123"}
    )
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username_or_email": "logoutuser", "password": "securepwd123"}
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Before logout: token works on protected endpoints
    me_res1 = client.get("/api/v1/auth/me", headers=headers)
    assert me_res1.status_code == 200
    assert me_res1.json()["username"] == "logoutuser"

    # 3. Perform logout
    logout_res = client.post("/api/v1/auth/logout", headers=headers)
    assert logout_res.status_code == 200
    assert logout_res.json()["revoked"] is True
    assert "Token has been revoked" in logout_res.json()["message"]

    # 4. After logout: using the old token must return 401 Unauthorized with "Token has been revoked"
    me_res2 = client.get("/api/v1/auth/me", headers=headers)
    assert me_res2.status_code == 401
    assert "Token has been revoked" in me_res2.json()["detail"]

    # 5. Using it on another protected endpoint (e.g. sync) must also be blocked
    sync_res = client.post("/api/v1/sync", headers=headers)
    assert sync_res.status_code == 401
    assert "Token has been revoked" in sync_res.json()["detail"]
