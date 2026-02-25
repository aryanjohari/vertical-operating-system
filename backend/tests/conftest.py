# backend/tests/conftest.py
import os
import sys

# Set test environment variables BEFORE any backend imports
# Generate a test Fernet key for encryption (this is a valid test key)
if "APEX_KMS_KEY" not in os.environ:
    from cryptography.fernet import Fernet
    test_key = Fernet.generate_key()
    os.environ["APEX_KMS_KEY"] = test_key.decode()

# Set JWT secret for testing (required by backend.core.auth)
if "APEX_JWT_SECRET" not in os.environ and "JWT_SECRET" not in os.environ:
    os.environ["APEX_JWT_SECRET"] = "test-jwt-secret-key-for-testing-only"
if "GOOGLE_API_KEY" not in os.environ:
    os.environ["GOOGLE_API_KEY"] = "test-google-api-key"

# Load .env file if it exists
from dotenv import load_dotenv
load_dotenv()

import pytest
import httpx
import sqlite3
import tempfile
from unittest.mock import Mock, patch, MagicMock
from backend.core.memory import MemoryManager
from backend.core.db import DatabaseFactory


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for testing with its own factory (isolated from app DB)."""
    fd, temp_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    # Use a fresh DatabaseFactory for this path so temp_db does not share the app's global factory
    with patch("backend.core.db.get_db_factory", lambda db_path=None: DatabaseFactory(db_path=db_path)):
        memory = MemoryManager(db_path=temp_path)
    yield memory
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def test_user(temp_db):
    """Create a test user in the temporary database."""
    email = "test@example.com"
    password = "testpassword123"
    temp_db.create_user(email, password)
    return {"email": email, "password": password, "user_id": email}


@pytest.fixture
def test_project(temp_db, test_user):
    """Create a test project in the temporary database."""
    project_id = "test_project"
    temp_db.register_project(
        user_id=test_user["user_id"],
        project_id=project_id,
        niche="Test Niche"
    )
    return {"project_id": project_id, "user_id": test_user["user_id"]}


@pytest.fixture
def mock_redis():
    """Mock Redis client for testing."""
    mock_client = MagicMock()
    mock_client.ping.return_value = True
    mock_client.get.return_value = None
    mock_client.setex.return_value = True
    mock_client.delete.return_value = True
    
    with patch('redis.from_url', return_value=mock_client):
        with patch('backend.core.context.context_manager.redis_client', mock_client):
            with patch('backend.core.context.context_manager.enabled', True):
                yield mock_client


@pytest.fixture
def mock_redis_unavailable():
    """Mock Redis as unavailable for testing."""
    with patch('redis.from_url', side_effect=Exception("Redis unavailable")):
        with patch('backend.core.context.context_manager.enabled', False):
            with patch('backend.core.context.context_manager.redis_client', None):
                yield


@pytest.fixture
def mock_llm_gateway():
    """Mock LLM gateway so agents do not call real Gemini. Patches the singleton."""
    mock = MagicMock()
    mock.generate_content.return_value = "mock llm response text"
    mock.generate_embeddings.return_value = [[0.1] * 256]  # single embedding, 256 dims
    with patch("backend.core.services.llm_gateway.llm_gateway", mock):
        yield mock


@pytest.fixture
def mock_llm_gateway_failing():
    """LLM gateway that raises on generate_content (for error path tests)."""
    mock = MagicMock()
    mock.generate_content.side_effect = RuntimeError("LLM generation failed")
    mock.generate_embeddings.side_effect = RuntimeError("Embedding failed")
    with patch("backend.core.services.llm_gateway.llm_gateway", mock):
        yield mock


@pytest.fixture
def mock_twilio():
    """Mock Twilio client for voice/webhook tests."""
    mock_client = MagicMock()
    mock_client.calls.create.return_value = MagicMock(sid="CAxxxx")
    mock_client.messages.create.return_value = MagicMock(sid="SMxxxx")
    with patch("twilio.rest.Client", return_value=mock_client):
        yield mock_client


@pytest.fixture
async def auth_headers(async_client, temp_db, test_user):
    """Return Authorization Bearer headers for test_user. Patches memory for auth."""
    with patch("backend.core.memory.memory", temp_db):
        with patch("backend.main.memory", temp_db):
            with patch("backend.core.auth.memory", temp_db):
                r = await async_client.post(
                    "/api/auth/verify",
                    json={"email": test_user["email"], "password": test_user["password"]},
                )
                assert r.status_code == 200, r.text
                data = r.json()
                assert data.get("success") and data.get("token")
                yield {"Authorization": f"Bearer {data['token']}"}


@pytest.fixture
async def async_client():
    """Create an async HTTP client for testing."""
    from backend.main import app
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
