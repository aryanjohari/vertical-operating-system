# backend/tests/test_auth.py
"""Auth routes: verify and register; success and validation/error paths."""
import pytest
import jwt
from unittest.mock import patch

import backend.core.auth as auth_module


@pytest.mark.asyncio
async def test_auth_verify_success(async_client, temp_db, test_user):
    """Login with valid credentials returns 200, success True, and valid JWT."""
    with patch("backend.core.memory.memory", temp_db):
        with patch("backend.main.memory", temp_db):
            with patch("backend.core.auth.memory", temp_db):
                r = await async_client.post(
                    "/api/auth/verify",
                    json={"email": test_user["email"], "password": test_user["password"]},
                )
                assert r.status_code == 200
                data = r.json()
                assert data["success"] is True
                assert data["user_id"] == test_user["user_id"]
                assert data.get("token")
                payload = jwt.decode(
                    data["token"],
                    auth_module.JWT_SECRET,
                    algorithms=[auth_module.JWT_ALGORITHM],
                )
                assert payload["user_id"] == test_user["user_id"]


@pytest.mark.asyncio
async def test_auth_verify_wrong_password(async_client, temp_db, test_user):
    """Wrong password returns 200 with success False and no token."""
    with patch("backend.core.memory.memory", temp_db):
        with patch("backend.main.memory", temp_db):
            with patch("backend.core.auth.memory", temp_db):
                r = await async_client.post(
                    "/api/auth/verify",
                    json={"email": test_user["email"], "password": "wrongpassword"},
                )
                assert r.status_code == 200
                data = r.json()
                assert data["success"] is False
                assert data.get("token") is None


@pytest.mark.asyncio
async def test_auth_verify_empty_email(async_client, temp_db, test_user):
    """Empty email returns 200 with success False."""
    with patch("backend.core.memory.memory", temp_db):
        with patch("backend.main.memory", temp_db):
            with patch("backend.core.auth.memory", temp_db):
                r = await async_client.post(
                    "/api/auth/verify",
                    json={"email": "", "password": test_user["password"]},
                )
                assert r.status_code == 200
                assert r.json()["success"] is False


@pytest.mark.asyncio
async def test_auth_verify_empty_password(async_client, temp_db, test_user):
    """Empty password returns 200 with success False."""
    with patch("backend.core.memory.memory", temp_db):
        with patch("backend.main.memory", temp_db):
            with patch("backend.core.auth.memory", temp_db):
                r = await async_client.post(
                    "/api/auth/verify",
                    json={"email": test_user["email"], "password": ""},
                )
                assert r.status_code == 200
                assert r.json()["success"] is False


@pytest.mark.asyncio
async def test_auth_verify_missing_body(async_client):
    """Missing body yields 422 (FastAPI validation)."""
    r = await async_client.post("/api/auth/verify", json={})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_auth_register_success(async_client, temp_db):
    """Register new user returns 200 and success True."""
    with patch("backend.core.memory.memory", temp_db):
        with patch("backend.main.memory", temp_db):
            with patch("backend.core.auth.memory", temp_db):
                r = await async_client.post(
                    "/api/auth/register",
                    json={"email": "new@example.com", "password": "securepass123"},
                )
                assert r.status_code == 200
                data = r.json()
                assert data["success"] is True
                assert data["user_id"] == "new@example.com"


@pytest.mark.asyncio
async def test_auth_register_duplicate(async_client, temp_db, test_user):
    """Register same email again returns 200 with success False."""
    with patch("backend.core.memory.memory", temp_db):
        with patch("backend.main.memory", temp_db):
            with patch("backend.core.auth.memory", temp_db):
                r = await async_client.post(
                    "/api/auth/register",
                    json={"email": test_user["email"], "password": "otherpass"},
                )
                assert r.status_code == 200
                assert r.json()["success"] is False


@pytest.mark.asyncio
async def test_auth_register_empty(async_client, temp_db):
    """Empty email or password returns 200 with success False."""
    with patch("backend.core.memory.memory", temp_db):
        with patch("backend.main.memory", temp_db):
            with patch("backend.core.auth.memory", temp_db):
                r = await async_client.post(
                    "/api/auth/register",
                    json={"email": "a@b.com", "password": ""},
                )
                assert r.status_code == 200
                assert r.json()["success"] is False


@pytest.mark.asyncio
async def test_auth_register_missing_body(async_client):
    """Missing body yields 422."""
    r = await async_client.post("/api/auth/register", json={})
    assert r.status_code == 422
