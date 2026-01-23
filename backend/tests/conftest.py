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

# Load .env file if it exists
from dotenv import load_dotenv
load_dotenv()

import pytest
import httpx
import sqlite3
import tempfile
from unittest.mock import Mock, patch, MagicMock
from backend.core.memory import MemoryManager


@pytest.fixture
def temp_db():
    """Create a temporary in-memory SQLite database for testing."""
    # Create a temporary file path
    fd, temp_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    # Create MemoryManager with temp DB
    memory = MemoryManager(db_path=temp_path)
    
    yield memory
    
    # Cleanup
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
async def async_client():
    """Create an async HTTP client for testing."""
    from backend.main import app
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
