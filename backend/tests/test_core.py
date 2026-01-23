# backend/tests/test_core.py
import pytest
import jwt
import os
import sqlite3
from unittest.mock import patch, MagicMock
import backend.core.auth as auth_module


@pytest.mark.asyncio
async def test_auth_login_and_token(async_client, temp_db, test_user):
    """Test authentication: login and get JWT token."""
    # Patch the global memory instance to use our test DB
    with patch('backend.core.memory.memory', temp_db):
        with patch('backend.main.memory', temp_db):
            with patch('backend.core.auth.memory', temp_db):
                # Test login
                response = await async_client.post(
                    "/api/auth/verify",
                    json={
                        "email": test_user["email"],
                        "password": test_user["password"]
                    }
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert data["user_id"] == test_user["user_id"]
                assert "token" in data
                assert data["token"] is not None
                
                # Verify token can be decoded
                token = data["token"]
                payload = jwt.decode(token, auth_module.JWT_SECRET, algorithms=[auth_module.JWT_ALGORITHM])
                assert payload["user_id"] == test_user["user_id"]


@pytest.mark.asyncio
async def test_health_endpoint(async_client, mock_redis):
    """Test health endpoint with Redis available."""
    response = await async_client.get("/api/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["system"] == "Apex Kernel"
    assert "loaded_agents" in data
    assert isinstance(data["loaded_agents"], list)


@pytest.mark.asyncio
async def test_health_endpoint_redis_unavailable(async_client, mock_redis_unavailable):
    """Test health endpoint when Redis is unavailable."""
    response = await async_client.get("/api/health")
    
    # Health endpoint should still work even if Redis is unavailable
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "loaded_agents" in data


@pytest.mark.asyncio
async def test_sniper_agent_returns_context_id(async_client, temp_db, test_user, test_project):
    """Test that sniper_agent returns a context_id when triggered as async task."""
    # Patch memory and create minimal DNA config
    import yaml
    import tempfile
    
    # Create a temporary DNA config directory
    with tempfile.TemporaryDirectory() as temp_dir:
        profile_dir = os.path.join(temp_dir, test_project["project_id"])
        os.makedirs(profile_dir, exist_ok=True)
        
        # Create minimal DNA config
        dna_config = {
            "modules": {
                "lead_gen": {
                    "sniper": {
                        "enabled": True,
                        "keywords": ["test"],
                        "geo_filter": ["Auckland"],
                        "platforms": ["trademe_jobs"]
                    }
                }
            }
        }
        
        dna_path = os.path.join(profile_dir, "dna.generated.yaml")
        with open(dna_path, 'w') as f:
            yaml.dump(dna_config, f)
        
        # Patch memory and config loader
        with patch('backend.core.memory.memory', temp_db):
            with patch('backend.main.memory', temp_db):
                with patch('backend.core.kernel.memory', temp_db):
                    with patch('backend.core.auth.memory', temp_db):
                        # Mock ConfigLoader to use temp directory
                        # Patch at the module level where it's imported
                        with patch('backend.core.config.ConfigLoader') as mock_config_loader_class:
                            mock_config_instance = MagicMock()
                            mock_config_instance.profiles_dir = temp_dir
                            mock_config_instance.load.return_value = dna_config
                            mock_config_loader_class.return_value = mock_config_instance
                            
                            # Mock the scraper and LLM to avoid actual API calls
                            with patch('backend.modules.lead_gen.agents.sniper.UniversalScraper') as mock_scraper:
                                mock_scraper_instance = MagicMock()
                                mock_scraper.return_value = mock_scraper_instance
                                mock_scraper_instance.scrape.return_value = {
                                    "content": "<html>Test content</html>",
                                    "error": None
                                }
                                
                                with patch('backend.modules.lead_gen.agents.sniper.llm_gateway') as mock_llm:
                                    mock_llm.generate_content.return_value = '[]'
                                    
                                    # Get auth token first
                                    auth_response = await async_client.post(
                                        "/api/auth/verify",
                                        json={
                                            "email": test_user["email"],
                                            "password": test_user["password"]
                                        }
                                    )
                                    assert auth_response.status_code == 200
                                    auth_data = auth_response.json()
                                    assert auth_data["success"] is True
                                    assert "token" in auth_data
                                    token = auth_data["token"]
                                    
                                    # Trigger sniper agent (should return context_id for async task)
                                    response = await async_client.post(
                                        "/api/run",
                                        json={
                                            "task": "sniper_agent",
                                            "params": {
                                                "project_id": test_project["project_id"]
                                            }
                                        },
                                        headers={"Authorization": f"Bearer {token}"}
                                    )
                                    
                                    assert response.status_code == 200
                                    data = response.json()
                                    assert data["status"] == "processing"
                                    assert "data" in data
                                    assert "context_id" in data["data"]
                                    
                                    # Verify context_id is a valid UUID format
                                    import uuid
                                    context_id = data["data"]["context_id"]
                                    assert context_id is not None
                                    # Try to parse as UUID to verify format
                                    uuid.UUID(context_id)


@pytest.mark.asyncio
async def test_accountant_writes_to_usage_ledger(async_client, temp_db, test_user, test_project):
    """Test that AccountantAgent writes to usage_ledger table."""
    # Ensure usage_ledger table exists
    temp_db.create_usage_table_if_not_exists()
    
    # Patch memory (including auth)
    with patch('backend.core.memory.memory', temp_db):
        with patch('backend.main.memory', temp_db):
            with patch('backend.core.kernel.memory', temp_db):
                with patch('backend.core.auth.memory', temp_db):
                    with patch('backend.modules.system_ops.agents.accountant.memory', temp_db):
                        # Get auth token
                        auth_response = await async_client.post(
                            "/api/auth/verify",
                            json={
                                "email": test_user["email"],
                                "password": test_user["password"]
                            }
                        )
                        assert auth_response.status_code == 200
                        auth_data = auth_response.json()
                        assert auth_data["success"] is True
                        assert "token" in auth_data
                        token = auth_data["token"]
                        
                        # Trigger log_usage task
                        response = await async_client.post(
                            "/api/run",
                            json={
                                "task": "log_usage",
                                "params": {
                                    "project_id": test_project["project_id"],
                                    "resource": "twilio_voice",
                                    "quantity": 10
                                }
                            },
                            headers={"Authorization": f"Bearer {token}"}
                        )
                        
                        assert response.status_code == 200
                        data = response.json()
                        assert data["status"] == "success"
                        assert "data" in data
                        assert "cost_logged" in data["data"]
                        
                        # Verify record was written to usage_ledger table
                        conn = sqlite3.connect(temp_db.db_path)
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT * FROM usage_ledger WHERE project_id = ?",
                            (test_project["project_id"],)
                        )
                        rows = cursor.fetchall()
                        conn.close()
                        
                        assert len(rows) == 1
                        row = rows[0]
                        # Row structure: (id, project_id, resource_type, quantity, cost_usd, timestamp)
                        assert row[1] == test_project["project_id"]  # project_id
                        assert row[2] == "twilio_voice"  # resource_type
                        assert row[3] == 10.0  # quantity
                        assert row[4] == 0.5  # cost_usd (10 * 0.05)
                        
                        # Verify cost_logged matches
                        assert data["data"]["cost_logged"] == 0.5
