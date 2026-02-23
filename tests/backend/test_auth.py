"""
Deployment tests: auth endpoints.

POST /api/auth/verify, POST /api/auth/register.
Uses DEPLOYMENT_TEST_USER_EMAIL / DEPLOYMENT_TEST_USER_PASSWORD when set.
"""

import os
import uuid

import pytest


@pytest.mark.deployment
def test_auth_verify_accepts_json(api_base_url, http_client):
    """POST /api/auth/verify with valid JSON returns 200 (success or failure)."""
    r = http_client.post(
        f"{api_base_url}/api/auth/verify",
        json={"email": "nonexistent@example.com", "password": "wrong"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "success" in data
    assert data["success"] is False


@pytest.mark.deployment
def test_auth_verify_with_deployment_credentials(api_base_url, http_client):
    """If DEPLOYMENT_TEST_USER_* are set, verify returns token."""
    email = os.getenv("DEPLOYMENT_TEST_USER_EMAIL")
    password = os.getenv("DEPLOYMENT_TEST_USER_PASSWORD")
    if not email or not password:
        pytest.skip("DEPLOYMENT_TEST_USER_EMAIL and DEPLOYMENT_TEST_USER_PASSWORD not set")
    r = http_client.post(
        f"{api_base_url}/api/auth/verify",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("success") is True
    assert "token" in data
    assert data["token"]


@pytest.mark.deployment
def test_auth_register_rejects_duplicate_or_returns_success(api_base_url, http_client):
    """POST /api/auth/register with unique email returns success or user exists."""
    unique = f"deploytest-{uuid.uuid4().hex[:12]}@example.com"
    r = http_client.post(
        f"{api_base_url}/api/auth/register",
        json={"email": unique, "password": "testpassword123"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "success" in data
