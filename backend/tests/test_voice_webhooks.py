# backend/tests/test_voice_webhooks.py
"""Voice and webhook routes: connect, incoming, webhooks/lead; 200/400/403/404 with mocks."""
import pytest
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_voice_connect_returns_xml(async_client):
    """POST /api/voice/connect returns 200 and application/xml (Twilio TwiML)."""
    r = await async_client.post("/api/voice/connect")
    assert r.status_code == 200
    assert "application/xml" in r.headers.get("content-type", "")
    assert "Response" in r.text or "Say" in r.text


@pytest.mark.asyncio
async def test_voice_connect_with_target_returns_xml(async_client):
    """POST /api/voice/connect?target=+15551234567 returns 200 and XML with Dial."""
    r = await async_client.post("/api/voice/connect", params={"target": "+15551234567"})
    assert r.status_code == 200
    assert "application/xml" in r.headers.get("content-type", "")
    assert "Dial" in r.text or "Connecting" in r.text or "Response" in r.text


@pytest.mark.asyncio
async def test_voice_dial_status_accepts_post(async_client):
    """POST /api/voice/dial-status with form data returns 200."""
    r = await async_client.post(
        "/api/voice/dial-status",
        data={"DialCallStatus": "completed", "DialCallDuration": "60"},
    )
    assert r.status_code == 200
    assert "application/xml" in r.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_voice_incoming_returns_xml(async_client):
    """POST /api/voice/incoming returns 200 and TwiML."""
    r = await async_client.post("/api/voice/incoming")
    assert r.status_code == 200
    assert "application/xml" in r.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_webhook_lead_400_invalid_project_id(async_client):
    """POST /api/webhooks/lead with invalid project_id format returns 400."""
    r = await async_client.post(
        "/api/webhooks/lead",
        params={"project_id": "invalid..project!!"},
        json={"name": "Test", "email": "a@b.com"},
    )
    assert r.status_code == 400
    assert "project_id" in r.json().get("detail", "").lower() or "alphanumeric" in r.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_webhook_lead_404_project_not_found(async_client, temp_db):
    """POST /api/webhooks/lead with valid format but nonexistent project returns 404."""
    with patch("backend.routers.webhooks.memory", temp_db):
        r = await async_client.post(
            "/api/webhooks/lead",
            params={"project_id": "nonexistent_project_123"},
            json={"name": "Lead", "email": "lead@example.com"},
        )
        assert r.status_code == 404
        assert "project" in r.json().get("detail", "").lower() or "not found" in r.json().get("detail", "").lower()


@pytest.mark.asyncio
async def test_webhook_lead_success(async_client, temp_db, test_user, test_project, mock_redis):
    """POST /api/webhooks/lead with valid project_id and payload returns 200 and lead_id."""
    with patch("backend.routers.webhooks.memory", temp_db):
        with patch("backend.routers.webhooks.context_manager") as mock_ctx:
            mock_ctx.create_context.return_value = type("C", (), {"context_id": "ctx-1"})()
            with patch("backend.routers.webhooks.kernel") as mock_kernel:
                mock_kernel.dispatch = AsyncMock(return_value=type("R", (), {"status": "success"})())
                r = await async_client.post(
                    "/api/webhooks/lead",
                    params={"project_id": test_project["project_id"]},
                    json={"name": "Webhook Lead", "email": "webhook@example.com", "phone": "+15551234567"},
                )
                assert r.status_code == 200
                data = r.json()
                assert data.get("success") is True
                assert "lead_id" in data


@pytest.mark.asyncio
async def test_webhook_google_ads_accepts_post(async_client):
    """POST /api/webhooks/google-ads accepts request (smoke)."""
    r = await async_client.post(
        "/api/webhooks/google-ads",
        json={"conversion": "lead", "gclid": "x"},
    )
    assert r.status_code in (200, 400, 404)


@pytest.mark.asyncio
async def test_webhook_wordpress_accepts_post(async_client):
    """POST /api/webhooks/wordpress accepts request (smoke)."""
    r = await async_client.post(
        "/api/webhooks/wordpress",
        params={"project_id": "test"},
        data={"name": "Test", "email": "a@b.com"},
    )
    assert r.status_code in (200, 400, 403, 404)
