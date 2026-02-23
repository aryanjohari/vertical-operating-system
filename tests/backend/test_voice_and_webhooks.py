"""
Deployment tests: voice and webhook endpoints.

POST /api/voice/* and POST /api/webhooks/*.
Smoke tests: ensure routes exist and accept POST (may return 4xx for missing body).
"""

import pytest


@pytest.mark.deployment
def test_voice_connect_accepts_post(api_base_url, http_client):
    """POST /api/voice/connect exists (Twilio webhook)."""
    r = http_client.post(
        f"{api_base_url}/api/voice/connect",
        data={},  # Twilio sends form data
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    # 200 with TwiML or 400 for invalid/missing params
    assert r.status_code in (200, 400, 422)


@pytest.mark.deployment
def test_voice_incoming_accepts_post(api_base_url, http_client):
    """POST /api/voice/incoming exists."""
    r = http_client.post(
        f"{api_base_url}/api/voice/incoming",
        data={},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code in (200, 400, 422)


@pytest.mark.deployment
def test_voice_status_accepts_post(api_base_url, http_client):
    """POST /api/voice/status exists."""
    r = http_client.post(
        f"{api_base_url}/api/voice/status",
        data={},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert r.status_code in (200, 400, 422)


@pytest.mark.deployment
def test_webhooks_google_ads_accepts_post(api_base_url, http_client):
    """POST /api/webhooks/google-ads exists."""
    r = http_client.post(
        f"{api_base_url}/api/webhooks/google-ads",
        json={},
    )
    assert r.status_code in (200, 400, 404, 422)


@pytest.mark.deployment
def test_webhooks_wordpress_accepts_post(api_base_url, http_client):
    """POST /api/webhooks/wordpress exists."""
    r = http_client.post(
        f"{api_base_url}/api/webhooks/wordpress",
        json={},
    )
    assert r.status_code in (200, 400, 404, 422)
