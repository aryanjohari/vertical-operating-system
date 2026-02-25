# backend/core/memory.py
import chromadb
import uuid
import json
import logging
import os
import hashlib
import secrets
from datetime import datetime
from typing import List, Dict, Any, Optional
from google import genai  # <--- REQUIRED
from backend.core.models import Entity
from backend.core.security import security_core
from backend.core.db import get_db_factory, DatabaseError

# --- Google Embedding Wrapper using LLM Gateway ---
class GoogleEmbeddingFunction:
    """
    ChromaDB-compatible embedding function using Google Gemini API via LLMGateway.
    Ensures consistent embedding generation across the system.
    """
    def __init__(self):
        # Import here to avoid circular dependency
        from backend.core.services.llm_gateway import llm_gateway
        self.llm_gateway = llm_gateway
        # ChromaDB requires a 'name' attribute for embedding functions
        self.name = "google_embedding_function"
        self.model = os.getenv("APEX_EMBEDDING_MODEL", "text-embedding-005")

    def __call__(self, input: List[str]) -> List[List[float]]:
        """
        Generate embeddings for input texts using Google Gemini API.
        
        Args:
            input: List of text strings to embed
            
        Returns:
            List of embedding vectors (list of floats)
        """
        if not input:
            return []
        
        try:
            # Use LLM Gateway for consistent embedding generation
            return self.llm_gateway.generate_embeddings(
                texts=input,
                model=self.model
            )
        except Exception as e:
            logging.getLogger("ApexMemory").error(f"Failed to generate embeddings: {e}", exc_info=True)
            raise
    
    def embed_query(self, input: str) -> List[float]:
        """
        Generate embedding for a single query string.
        Required by ChromaDB for query operations.
        
        Args:
            input: Single query string to embed (ChromaDB passes this as keyword arg)
            
        Returns:
            Embedding vector (list of floats)
        """
        if not input:
            return []
        
        try:
            embeddings = self.__call__([input])
            return embeddings[0] if embeddings else []
        except Exception as e:
            logging.getLogger("ApexMemory").error(f"Failed to generate query embedding: {e}", exc_info=True)
            raise

class MemoryManager:
    def __init__(self, db_path="data/apex.db", vector_path="data/chroma_db"):
        self.logger = logging.getLogger("ApexMemory")
        
        # Convert to absolute paths to avoid path-related issues
        self.db_path = os.path.abspath(db_path)
        self.vector_path = os.path.abspath(vector_path)
        
        # Ensure directories exist with proper permissions (only for SQLite)
        if not os.getenv("DATABASE_URL"):
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(self.vector_path, exist_ok=True)
        
        # Initialize database factory
        self.db_factory = get_db_factory(db_path=self.db_path)
        
        self._init_database()
        
        # Initialize Vector DB with error handling
        try:
            self.chroma_client = chromadb.PersistentClient(path=self.vector_path)
            
            # Create and store embedding function instance (uses Google Gemini API)
            # We'll manually use this for all operations to ensure Google embeddings
            self.embedding_fn = GoogleEmbeddingFunction()
            
            # Try to get existing collection first
            try:
                # get_collection() uses the stored embedding function from when collection was created
                # Don't pass embedding_function - ChromaDB doesn't accept it for get_collection()
                self.vector_collection = self.chroma_client.get_collection(
                    name="apex_context"
                )
                # Manually set our embedding function to ensure we use Google embeddings
                # This overrides whatever ChromaDB stored
                try:
                    self.vector_collection._embedding_function = self.embedding_fn
                except Exception:
                    # If we can't set it directly, we'll manually embed in query/save methods
                    pass
                self.logger.info("Loaded existing ChromaDB collection (using Google embeddings)")
            except Exception as get_error:
                # Collection doesn't exist, create it with Google embedding function
                try:
                    self.vector_collection = self.chroma_client.create_collection(
                        name="apex_context",
                        embedding_function=self.embedding_fn
                    )
                    self.logger.info("Created new ChromaDB collection with Google embeddings")
                except Exception as create_error:
                    # Collection might have been created between get and create
                    error_msg = str(create_error).lower()
                    if "already exists" in error_msg or "duplicate" in error_msg:
                        # Collection exists, get it and set our embedding function
                        self.vector_collection = self.chroma_client.get_collection(
                            name="apex_context"
                        )
                        try:
                            self.vector_collection._embedding_function = self.embedding_fn
                        except Exception:
                            pass
                        self.logger.info("Loaded existing ChromaDB collection (recovered from race condition)")
                    else:
                        # Re-raise if it's a different error
                        raise create_error
            
            self.chroma_enabled = True
            self.logger.info("🧠 Memory Systems Online (SQL + Google RAG)")
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize ChromaDB: {e}")
            self.logger.warning("⚠️ Continuing without vector memory (RAG disabled)")
            self.chroma_client = None
            self.vector_collection = None
            self.chroma_enabled = False
            self.logger.info("🧠 Memory Systems Online (SQL only)")

    def _init_database(self):
        """Creates tables with Market-Ready schema (database-agnostic)."""
        json_type = self.db_factory.get_json_type()
        placeholder = self.db_factory.get_placeholder()
        
        with self.db_factory.get_cursor() as cursor:
            # 1. USERS (With Hashed Passwords)
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY, 
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL
                )
            ''')

            # 2. PROJECTS
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS projects (
                    project_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    niche TEXT,
                    dna_path TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                )
            ''')

            # 3. ENTITIES
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS entities (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    project_id TEXT,
                    entity_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    primary_contact TEXT,
                    metadata {json_type},
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_tenant ON entities(tenant_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_project ON entities(project_id)")

            # 4. CAMPAIGNS
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS campaigns (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    module TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'DRAFT',
                    config {json_type} NOT NULL,
                    stats {json_type},
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(project_id) REFERENCES projects(project_id)
                )
            ''')
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_campaigns_project ON campaigns(project_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_campaigns_module ON campaigns(module)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_campaigns_status ON campaigns(status)")

            # 5. SECRETS
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS client_secrets (
                    user_id TEXT PRIMARY KEY,
                    wp_url TEXT,
                    wp_user TEXT,
                    wp_auth_hash TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                )
            ''')

            # 6. ANALYTICS SNAPSHOTS (cached analytics by project/campaign/range/module)
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS analytics_snapshots (
                    tenant_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    campaign_id TEXT NOT NULL,
                    module TEXT NOT NULL,
                    from_date TEXT NOT NULL,
                    to_date TEXT NOT NULL,
                    fetched_at TIMESTAMP NOT NULL,
                    payload {json_type} NOT NULL,
                    PRIMARY KEY (tenant_id, project_id, campaign_id, from_date, to_date, module)
                )
            ''')
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_analytics_snapshots_lookup ON analytics_snapshots(tenant_id, project_id, campaign_id)")

    # ====================================================
    # SECTION A: SECURITY & AUTH
    # ====================================================
    def _hash_password(self, password: str, salt: Optional[str] = None) -> (str, str):
        if not salt:
            salt = secrets.token_hex(16)
        pwd_hash = hashlib.pbkdf2_hmac(
            'sha256', 
            password.encode('utf-8'), 
            salt.encode('utf-8'), 
            100000
        ).hex()
        return pwd_hash, salt

    def create_user(self, email, password):
        self.logger.debug(f"Creating user {email}")
        try:
            pwd_hash, salt = self._hash_password(password)
            placeholder = self.db_factory.get_placeholder()
            with self.db_factory.get_cursor() as cursor:
                cursor.execute(
                    f"INSERT INTO users (user_id, password_hash, salt) VALUES ({placeholder}, {placeholder}, {placeholder})", 
                    (email, pwd_hash, salt)
                )
            self.logger.info(f"Successfully created user {email}")
            return True
        except DatabaseError as e:
            # Check if it's an integrity error (duplicate key)
            error_str = str(e).lower()
            if "unique" in error_str or "duplicate" in error_str or "already exists" in error_str:
                self.logger.warning(f"User {email} already exists: {e}")
                return False
            self.logger.error(f"Database error creating user {email}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error creating user {email}: {e}")
            return False

    def _user_exists(self, user_id: str) -> bool:
        """Check if user exists (for JWT validation)."""
        try:
            placeholder = self.db_factory.get_placeholder()
            with self.db_factory.get_cursor(commit=False) as cursor:
                cursor.execute(f"SELECT 1 FROM users WHERE user_id = {placeholder}", (user_id,))
                exists = cursor.fetchone() is not None
                return exists
        except DatabaseError as e:
            self.logger.error(f"Database error checking user existence for {user_id}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error checking user existence for {user_id}: {e}")
            return False

    def health_check(self) -> bool:
        """
        Runs a simple query to verify database connectivity.
        Returns True if the database is reachable, False otherwise.
        """
        try:
            with self.db_factory.get_cursor(commit=False) as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            return True
        except DatabaseError as e:
            self.logger.error(f"Database health check failed: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Database health check failed: {e}")
            return False

    def verify_user(self, email, password):
        self.logger.debug(f"Verifying user credentials for {email}")
        try:
            placeholder = self.db_factory.get_placeholder()
            with self.db_factory.get_cursor(commit=False) as cursor:
                cursor.execute(f"SELECT password_hash, salt FROM users WHERE user_id = {placeholder}", (email,))
                row = cursor.fetchone()
                
                if row:
                    stored_hash, salt = row[0], row[1]
                    check_hash, _ = self._hash_password(password, salt)
                    is_valid = check_hash == stored_hash
                    if is_valid:
                        self.logger.debug(f"Credentials verified for user {email}")
                    else:
                        self.logger.debug(f"Invalid credentials for user {email}")
                    return is_valid
                self.logger.debug(f"User {email} not found")
                return False
        except DatabaseError as e:
            self.logger.error(f"Database error verifying user {email}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error verifying user {email}: {e}")
            return False

    # ====================================================
    # SECTION B: PROJECT MANAGEMENT
    # ====================================================
    def register_project(self, user_id, project_id, niche):
        self.logger.debug(f"Registering project {project_id} for user {user_id}")
        try:
            path = f"data/profiles/{project_id}/dna.generated.yaml"
            sql = self.db_factory.get_insert_or_replace_sql(
                table="projects",
                columns=["project_id", "user_id", "niche", "dna_path"],
                primary_key="project_id"
            )
            with self.db_factory.get_cursor() as cursor:
                cursor.execute(sql, (project_id, user_id, niche, path))
            self.logger.info(f"Successfully registered project {project_id} for user {user_id}")
        except DatabaseError as e:
            self.logger.error(f"Database error registering project {project_id} for user {user_id}: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error registering project {project_id} for user {user_id}: {e}")
            raise

    def get_user_project(self, user_id):
        self.logger.debug(f"Fetching user project for user {user_id}")
        cursor = None
        try:
            placeholder = self.db_factory.get_placeholder()
            conn = self.db_factory.get_connection()
            self.db_factory.set_row_factory(conn)
            try:
                cursor = conn.cursor()
                cursor.execute(f"SELECT * FROM projects WHERE user_id = {placeholder} ORDER BY created_at DESC LIMIT 1", (user_id,))
                row = cursor.fetchone()
                if row and cursor.description:
                    result = dict(zip([d[0] for d in cursor.description], row))
                else:
                    result = dict(row) if row else None
                if result:
                    self.logger.debug(f"Found project {result.get('project_id')} for user {user_id}")
                else:
                    self.logger.debug(f"No project found for user {user_id}")
                return result
            finally:
                if cursor is not None:
                    cursor.close()
                self.db_factory.return_connection(conn)
        except DatabaseError as e:
            self.logger.error(f"Database error fetching user project for user {user_id}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error fetching user project for user {user_id}: {e}")
            return None

    def get_projects(self, user_id: str) -> List[Dict]:
        """Get all projects for a specific user."""
        self.logger.debug(f"Fetching all projects for user {user_id}")
        cursor = None
        try:
            placeholder = self.db_factory.get_placeholder()
            conn = self.db_factory.get_connection()
            self.db_factory.set_row_factory(conn)
            try:
                cursor = conn.cursor()
                cursor.execute(f"SELECT * FROM projects WHERE user_id = {placeholder} ORDER BY created_at DESC", (user_id,))
                rows = cursor.fetchall()
                if cursor.description:
                    columns = [d[0] for d in cursor.description]
                    results = [dict(zip(columns, row)) for row in rows]
                else:
                    results = [dict(row) for row in rows]
                self.logger.debug(f"Found {len(results)} projects for user {user_id}")
                return results
            finally:
                if cursor is not None:
                    cursor.close()
                self.db_factory.return_connection(conn)
        except DatabaseError as e:
            self.logger.error(f"Database error fetching projects for user {user_id}: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error fetching projects for user {user_id}: {e}")
            return []

    def verify_project_ownership(self, user_id: str, project_id: str) -> bool:
        """
        Verify that a project belongs to a specific user.
        
        Critical for multi-tenant security.
        Future: With Supabase RLS, this check happens at database level.
        """
        self.logger.debug(f"Verifying project ownership: user={user_id}, project={project_id}")
        try:
            placeholder = self.db_factory.get_placeholder()
            with self.db_factory.get_cursor(commit=False) as cursor:
                cursor.execute(
                    f"SELECT 1 FROM projects WHERE project_id = {placeholder} AND user_id = {placeholder}",
                    (project_id, user_id)
                )
                exists = cursor.fetchone() is not None
                if not exists:
                    self.logger.warning(f"Project ownership verification failed: user={user_id}, project={project_id}")
                return exists
        except DatabaseError as e:
            self.logger.error(f"Database error verifying project ownership: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error verifying project ownership: {e}")
            return False

    def get_project_owner(self, project_id: str) -> Optional[str]:
        """
        Get the user_id (owner) of a project.
        
        Used to find the correct tenant_id for operations.
        Returns None if project doesn't exist.
        """
        self.logger.debug(f"Getting project owner for project {project_id}")
        try:
            placeholder = self.db_factory.get_placeholder()
            with self.db_factory.get_cursor(commit=False) as cursor:
                cursor.execute(f"SELECT user_id FROM projects WHERE project_id = {placeholder}", (project_id,))
                row = cursor.fetchone()
                
                if row:
                    user_id = row[0]
                    self.logger.debug(f"Found project owner: {user_id} for project {project_id}")
                    return user_id
                else:
                    self.logger.warning(f"Project {project_id} not found in database")
                    return None
        except DatabaseError as e:
            self.logger.error(f"Database error getting project owner for {project_id}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error getting project owner for {project_id}: {e}")
            return None

    # ====================================================
    # SECTION B.5: CAMPAIGN MANAGEMENT
    # ====================================================
    def create_campaign(self, user_id: str, project_id: str, name: str, module: str, config: Dict[str, Any]) -> str:
        """
        Create a new campaign for a project.
        Returns campaign_id (UUID format: cmp_xxxxx).
        """
        self.logger.debug(f"Creating campaign for project {project_id}, module {module}")
        try:
            # Verify project ownership
            if not self.verify_project_ownership(user_id, project_id):
                raise ValueError(f"User {user_id} does not own project {project_id}")
            
            # Generate campaign_id (format: cmp_xxxxx)
            import uuid
            campaign_id = f"cmp_{uuid.uuid4().hex[:10]}"
            
            # Insert campaign
            json_type = self.db_factory.get_json_type()
            placeholder = self.db_factory.get_placeholder()
            
            with self.db_factory.get_cursor() as cursor:
                cursor.execute(f'''
                    INSERT INTO campaigns (id, project_id, name, module, status, config, stats)
                    VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                ''', (
                    campaign_id,
                    project_id,
                    name,
                    module,
                    'DRAFT',
                    json.dumps(config),
                    json.dumps({})
                ))
            
            self.logger.info(f"Successfully created campaign {campaign_id} for project {project_id}")
            return campaign_id
        except DatabaseError as e:
            self.logger.error(f"Database error creating campaign: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error creating campaign: {e}")
            raise

    def get_campaign(self, campaign_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a campaign by ID with RLS check (via project ownership).
        Returns None if not found or access denied.
        """
        self.logger.debug(f"Fetching campaign {campaign_id} for user {user_id}")
        cursor = None
        try:
            placeholder = self.db_factory.get_placeholder()
            conn = self.db_factory.get_connection()
            self.db_factory.set_row_factory(conn)
            try:
                cursor = conn.cursor()
                cursor.execute(f'''
                    SELECT c.*, p.user_id 
                    FROM campaigns c
                    JOIN projects p ON c.project_id = p.project_id
                    WHERE c.id = {placeholder} AND p.user_id = {placeholder}
                ''', (campaign_id, user_id))
                row = cursor.fetchone()
                
                if row and cursor.description:
                    result = dict(zip([d[0] for d in cursor.description], row))
                else:
                    result = dict(row) if row else None
                if result:
                    # Parse JSON fields
                    if result.get('config'):
                        result['config'] = json.loads(result['config']) if isinstance(result['config'], str) else result['config']
                    if result.get('stats'):
                        result['stats'] = json.loads(result['stats']) if isinstance(result['stats'], str) else result['stats']
                    # Remove user_id from result (it's from join)
                    result.pop('user_id', None)
                    self.logger.debug(f"Found campaign {campaign_id}")
                    return result
                else:
                    self.logger.debug(f"Campaign {campaign_id} not found or access denied")
                    return None
            finally:
                if cursor is not None:
                    cursor.close()
                self.db_factory.return_connection(conn)
        except DatabaseError as e:
            self.logger.error(f"Database error fetching campaign {campaign_id}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error fetching campaign {campaign_id}: {e}")
            return None

    def get_campaigns_by_project(self, user_id: str, project_id: str, module: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all campaigns for a project, optionally filtered by module.
        Returns empty list if project not found or access denied.
        """
        self.logger.debug(f"Fetching campaigns for project {project_id}, module={module}")
        cursor = None
        try:
            # Verify project ownership
            if not self.verify_project_ownership(user_id, project_id):
                self.logger.warning(f"Access denied: user {user_id} does not own project {project_id}")
                return []
            
            placeholder = self.db_factory.get_placeholder()
            conn = self.db_factory.get_connection()
            self.db_factory.set_row_factory(conn)
            try:
                cursor = conn.cursor()
                if module:
                    cursor.execute(f'''
                        SELECT * FROM campaigns 
                        WHERE project_id = {placeholder} AND module = {placeholder}
                        ORDER BY created_at DESC
                    ''', (project_id, module))
                else:
                    cursor.execute(f'''
                        SELECT * FROM campaigns 
                        WHERE project_id = {placeholder}
                        ORDER BY created_at DESC
                    ''', (project_id,))
                
                rows = cursor.fetchall()
                if cursor.description:
                    columns = [d[0] for d in cursor.description]
                    raw_results = [dict(zip(columns, row)) for row in rows]
                else:
                    raw_results = [dict(row) for row in rows]
                results = []
                for result in raw_results:
                    # Parse JSON fields
                    if result.get('config'):
                        result['config'] = json.loads(result['config']) if isinstance(result['config'], str) else result['config']
                    if result.get('stats'):
                        result['stats'] = json.loads(result['stats']) if isinstance(result['stats'], str) else result['stats']
                    results.append(result)
                
                self.logger.debug(f"Found {len(results)} campaigns for project {project_id}")
                return results
            finally:
                if cursor is not None:
                    cursor.close()
                self.db_factory.return_connection(conn)
        except DatabaseError as e:
            self.logger.error(f"Database error fetching campaigns: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error fetching campaigns: {e}")
            return []

    def update_campaign_status(self, campaign_id: str, user_id: str, status: str) -> bool:
        """
        Update campaign status. Validates ownership via project.
        Returns True on success, False on failure.
        """
        self.logger.debug(f"Updating campaign {campaign_id} status to {status}")
        try:
            # Verify ownership by checking if campaign exists and user owns the project
            campaign = self.get_campaign(campaign_id, user_id)
            if not campaign:
                self.logger.warning(f"Cannot update campaign {campaign_id}: not found or access denied")
                return False
            
            placeholder = self.db_factory.get_placeholder()
            with self.db_factory.get_cursor() as cursor:
                cursor.execute(f'''
                    UPDATE campaigns 
                    SET status = {placeholder}, updated_at = CURRENT_TIMESTAMP
                    WHERE id = {placeholder}
                ''', (status, campaign_id))
            
            self.logger.info(f"Successfully updated campaign {campaign_id} status to {status}")
            return True
        except DatabaseError as e:
            self.logger.error(f"Database error updating campaign status: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error updating campaign status: {e}")
            return False

    def update_campaign_stats(self, campaign_id: str, user_id: str, stats: Dict[str, Any]) -> bool:
        """
        Update campaign stats. Validates ownership via project.
        Merges with existing stats (doesn't overwrite).
        Returns True on success, False on failure.
        """
        self.logger.debug(f"Updating campaign {campaign_id} stats")
        try:
            # Verify ownership
            campaign = self.get_campaign(campaign_id, user_id)
            if not campaign:
                self.logger.warning(f"Cannot update campaign {campaign_id}: not found or access denied")
                return False
            
            # Merge with existing stats
            existing_stats = campaign.get('stats', {}) or {}
            merged_stats = {**existing_stats, **stats}
            
            placeholder = self.db_factory.get_placeholder()
            with self.db_factory.get_cursor() as cursor:
                cursor.execute(f'''
                    UPDATE campaigns 
                    SET stats = {placeholder}, updated_at = CURRENT_TIMESTAMP
                    WHERE id = {placeholder}
                ''', (json.dumps(merged_stats), campaign_id))
            
            self.logger.info(f"Successfully updated campaign {campaign_id} stats")
            return True
        except DatabaseError as e:
            self.logger.error(f"Database error updating campaign stats: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error updating campaign stats: {e}")
            return False

    def update_campaign_config(self, campaign_id: str, user_id: str, new_config: Dict[str, Any]) -> bool:
        """
        Update campaign config. Validates ownership via project.

        Overwrites the existing config with the provided dictionary.
        """
        self.logger.debug(f"Updating campaign {campaign_id} config")
        try:
            # Verify ownership
            campaign = self.get_campaign(campaign_id, user_id)
            if not campaign:
                self.logger.warning(f"Cannot update campaign {campaign_id}: not found or access denied")
                return False

            placeholder = self.db_factory.get_placeholder()
            with self.db_factory.get_cursor() as cursor:
                cursor.execute(
                    f"""
                    UPDATE campaigns
                    SET config = {placeholder}, updated_at = CURRENT_TIMESTAMP
                    WHERE id = {placeholder}
                    """,
                    (json.dumps(new_config), campaign_id),
                )

            self.logger.info(f"Successfully updated campaign {campaign_id} config")
            return True
        except DatabaseError as e:
            self.logger.error(f"Database error updating campaign config: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error updating campaign config: {e}")
            return False

    # ====================================================
    # SECTION C: SCALABLE ENTITY STORAGE
    # ====================================================
    def save_entity(self, entity: Entity, project_id: Optional[str] = None) -> bool:
        """
        Saves an entity to the database.
        
        Priority for project_id:
        1. Explicit parameter (project_id argument)
        2. Entity.project_id attribute (if set by agent)
        3. Entity.metadata.get("project_id") (fallback for legacy data)
        """
        self.logger.debug(f"Saving entity {entity.id} of type {entity.entity_type} for tenant {entity.tenant_id}")
        try:
            # Priority: parameter > entity attribute > metadata
            if project_id is None:
                # Check if entity has project_id attribute (set by agents)
                project_id = getattr(entity, 'project_id', None)
                if project_id is None:
                    # Fallback to metadata (for legacy data)
                    project_id = entity.metadata.get("project_id")
            
            sql = self.db_factory.get_insert_or_replace_sql(
                table="entities",
                columns=["id", "tenant_id", "project_id", "entity_type", "name", "primary_contact", "metadata", "created_at"],
                primary_key="id"
            )
            with self.db_factory.get_cursor() as cursor:
                cursor.execute(sql, (
                    entity.id,
                    entity.tenant_id,
                    project_id,
                    entity.entity_type,
                    entity.name,
                    entity.primary_contact,
                    json.dumps(entity.metadata),
                    entity.created_at
                ))
            self.logger.info(f"Successfully saved entity {entity.id} of type {entity.entity_type}")
            return True
        except DatabaseError as e:
            self.logger.error(f"Database error saving entity {entity.id}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error saving entity {entity.id}: {e}")
            return False

    def get_entities(self, tenant_id: str, entity_type: Optional[str] = None,
                     project_id: Optional[str] = None, campaign_id: Optional[str] = None,
                     limit: int = 100, offset: int = 0, return_total: bool = False,
                     created_after: Optional[str] = None, created_before: Optional[str] = None) -> List[Dict]:
        """
        Fetch entities with optional filters. Use get_entities_count for total when paginating by campaign_id.
        created_after/created_before: ISO date or datetime strings for time-bound analytics.
        """
        self.logger.debug(f"Fetching entities for tenant {tenant_id}, type: {entity_type}, project: {project_id}, campaign: {campaign_id}")
        try:
            placeholder = self.db_factory.get_placeholder()
            conn = self.db_factory.get_connection()
            self.db_factory.set_row_factory(conn)
            cursor = None
            try:
                cursor = self.db_factory.get_cursor_with_row_factory(conn)

                query = f"SELECT * FROM entities WHERE tenant_id = {placeholder}"
                params: List[Any] = [tenant_id]

                if entity_type:
                    query += f" AND entity_type = {placeholder}"
                    params.append(entity_type)

                if project_id:
                    query += f" AND project_id = {placeholder}"
                    params.append(project_id)

                if campaign_id:
                    if self.db_factory.db_type == "postgresql":
                        query += f" AND metadata->>'campaign_id' = {placeholder}"
                    else:
                        query += " AND json_extract(metadata, '$.campaign_id') = " + placeholder
                    params.append(campaign_id)

                if created_after:
                    query += f" AND created_at >= {placeholder}"
                    params.append(created_after)
                if created_before:
                    query += f" AND created_at <= {placeholder}"
                    params.append(created_before)

                query += f" ORDER BY created_at DESC LIMIT {placeholder} OFFSET {placeholder}"
                params.extend([limit, offset])

                cursor.execute(query, tuple(params))
                rows = cursor.fetchall()

                results = []
                for row in rows:
                    item = dict(row)
                    try:
                        item['metadata'] = json.loads(item['metadata'])
                    except (json.JSONDecodeError, TypeError) as e:
                        self.logger.warning(f"Failed to parse metadata JSON for entity {item.get('id', 'unknown')}: {e}")
                        item['metadata'] = {}
                    results.append(item)

                self.logger.debug(f"Found {len(results)} entities for tenant {tenant_id}")
                return results
            finally:
                if cursor is not None:
                    cursor.close()
                self.db_factory.return_connection(conn)
        except DatabaseError as e:
            self.logger.error(f"Database error fetching entities for tenant {tenant_id}: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error fetching entities for tenant {tenant_id}: {e}")
            return []

    def get_entities_count(self, tenant_id: str, entity_type: Optional[str] = None,
                           project_id: Optional[str] = None, campaign_id: Optional[str] = None,
                           created_after: Optional[str] = None, created_before: Optional[str] = None) -> int:
        """Count entities with same filters as get_entities (no limit/offset). created_after/created_before for time-bound analytics."""
        try:
            placeholder = self.db_factory.get_placeholder()
            conn = self.db_factory.get_connection()
            cursor = None
            try:
                cursor = self.db_factory.get_cursor_with_row_factory(conn)
                query = f"SELECT COUNT(*) AS cnt FROM entities WHERE tenant_id = {placeholder}"
                params: List[Any] = [tenant_id]
                if entity_type:
                    query += f" AND entity_type = {placeholder}"
                    params.append(entity_type)
                if project_id:
                    query += f" AND project_id = {placeholder}"
                    params.append(project_id)
                if campaign_id:
                    if self.db_factory.db_type == "postgresql":
                        query += f" AND metadata->>'campaign_id' = {placeholder}"
                    else:
                        query += " AND json_extract(metadata, '$.campaign_id') = " + placeholder
                    params.append(campaign_id)
                if created_after:
                    query += f" AND created_at >= {placeholder}"
                    params.append(created_after)
                if created_before:
                    query += f" AND created_at <= {placeholder}"
                    params.append(created_before)
                cursor.execute(query, tuple(params))
                row = cursor.fetchone()
                if not row:
                    return 0
                # Key-based access for DictRow/RealDictRow; fallback for plain cursor
                count_val = row.get("cnt", row[0]) if hasattr(row, "get") else row[0]
                return int(count_val)
            finally:
                if cursor is not None:
                    cursor.close()
                self.db_factory.return_connection(conn)
        except DatabaseError as e:
            self.logger.error(f"Database error counting entities for tenant {tenant_id}: {e}")
            return 0
        except Exception as e:
            self.logger.error(f"Unexpected error counting entities for tenant {tenant_id}: {e}")
            return 0

    def save_analytics_snapshot(
        self,
        tenant_id: str,
        project_id: str,
        campaign_id: str,
        module: str,
        from_date: str,
        to_date: str,
        payload: Dict[str, Any],
    ) -> bool:
        """Upsert one analytics snapshot (by tenant, project, campaign, range, module). Caller must validate payload."""
        try:
            placeholder = self.db_factory.get_placeholder()
            fetched_at = datetime.utcnow()
            payload_json = json.dumps(payload)
            with self.db_factory.get_cursor() as cursor:
                if self.db_factory.db_type == "postgresql":
                    ph = placeholder
                    cursor.execute(
                        f"""
                        INSERT INTO analytics_snapshots
                        (tenant_id, project_id, campaign_id, module, from_date, to_date, fetched_at, payload)
                        VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
                        ON CONFLICT (tenant_id, project_id, campaign_id, from_date, to_date, module)
                        DO UPDATE SET fetched_at = EXCLUDED.fetched_at, payload = EXCLUDED.payload
                        """,
                        (tenant_id, project_id, campaign_id, module, from_date, to_date, fetched_at, payload_json),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO analytics_snapshots
                        (tenant_id, project_id, campaign_id, module, from_date, to_date, fetched_at, payload)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (tenant_id, project_id, campaign_id, module, from_date, to_date, fetched_at, payload_json),
                    )
            self.logger.debug(f"Saved analytics snapshot for {project_id}/{campaign_id} ({module})")
            return True
        except DatabaseError as e:
            self.logger.error(f"Database error saving analytics snapshot: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error saving analytics snapshot: {e}")
            return False

    def get_analytics_snapshot(
        self,
        tenant_id: str,
        project_id: str,
        campaign_id: str,
        from_date: str,
        to_date: str,
        module: str,
    ) -> Optional[Dict[str, Any]]:
        """Return latest snapshot for (tenant, project, campaign, from, to, module) or None. Keys: fetched_at, payload."""
        try:
            placeholder = self.db_factory.get_placeholder()
            conn = self.db_factory.get_connection()
            self.db_factory.set_row_factory(conn)
            cursor = None
            try:
                cursor = self.db_factory.get_cursor_with_row_factory(conn)
                cursor.execute(
                    f"""
                    SELECT fetched_at, payload FROM analytics_snapshots
                    WHERE tenant_id = {placeholder} AND project_id = {placeholder} AND campaign_id = {placeholder}
                    AND from_date = {placeholder} AND to_date = {placeholder} AND module = {placeholder}
                    """,
                    (tenant_id, project_id, campaign_id, from_date, to_date, module),
                )
                row = cursor.fetchone()
                if not row:
                    return None
                out = dict(row)
                try:
                    out["payload"] = json.loads(out["payload"]) if out.get("payload") else None
                except (json.JSONDecodeError, TypeError):
                    out["payload"] = None
                if out.get("fetched_at") and hasattr(out["fetched_at"], "isoformat"):
                    out["fetched_at"] = out["fetched_at"].isoformat()
                return out
            finally:
                if cursor is not None:
                    cursor.close()
                self.db_factory.return_connection(conn)
        except DatabaseError as e:
            self.logger.error(f"Database error getting analytics snapshot: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error getting analytics snapshot: {e}")
            return None

    def get_entity(self, entity_id: str, tenant_id: str) -> Optional[Dict]:
        """
        Get a single entity by id with RLS (tenant_id). Returns None if not found or access denied.
        """
        self.logger.debug(f"Fetching entity {entity_id} for tenant {tenant_id}")
        try:
            placeholder = self.db_factory.get_placeholder()
            conn = self.db_factory.get_connection()
            self.db_factory.set_row_factory(conn)
            cursor = None
            try:
                cursor = self.db_factory.get_cursor_with_row_factory(conn)
                cursor.execute(
                    f"SELECT * FROM entities WHERE id = {placeholder} AND tenant_id = {placeholder}",
                    (entity_id, tenant_id),
                )
                row = cursor.fetchone()
                if not row:
                    return None
                entity = dict(row)
                try:
                    entity["metadata"] = json.loads(entity["metadata"]) if entity.get("metadata") else {}
                except (json.JSONDecodeError, TypeError):
                    entity["metadata"] = {}
                return entity
            finally:
                if cursor is not None:
                    cursor.close()
                self.db_factory.return_connection(conn)
        except DatabaseError as e:
            self.logger.error(f"Database error fetching entity {entity_id}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error fetching entity {entity_id}: {e}")
            return None

    def update_entity_name_contact(
        self, entity_id: str, tenant_id: str, name: Optional[str] = None, primary_contact: Optional[str] = None
    ) -> bool:
        """
        Update name and/or primary_contact for an entity. RLS: WHERE id AND tenant_id.
        At least one of name or primary_contact must be provided.
        Returns True on success, False if entity not found or access denied.
        """
        if name is None and primary_contact is None:
            return True
        self.logger.debug(f"Updating entity {entity_id} name/contact for tenant {tenant_id}")
        try:
            placeholder = self.db_factory.get_placeholder()
            with self.db_factory.get_cursor() as cursor:
                if name is not None and primary_contact is not None:
                    cursor.execute(
                        f"UPDATE entities SET name = {placeholder}, primary_contact = {placeholder} WHERE id = {placeholder} AND tenant_id = {placeholder}",
                        (name, primary_contact, entity_id, tenant_id),
                    )
                elif name is not None:
                    cursor.execute(
                        f"UPDATE entities SET name = {placeholder} WHERE id = {placeholder} AND tenant_id = {placeholder}",
                        (name, entity_id, tenant_id),
                    )
                else:
                    cursor.execute(
                        f"UPDATE entities SET primary_contact = {placeholder} WHERE id = {placeholder} AND tenant_id = {placeholder}",
                        (primary_contact, entity_id, tenant_id),
                    )
            self.logger.info(f"Successfully updated entity {entity_id} name/contact")
            return True
        except DatabaseError as e:
            self.logger.error(f"Database error updating entity {entity_id} name/contact: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error updating entity {entity_id} name/contact: {e}")
            return False

    def update_entity(self, entity_id: str, new_metadata: dict, tenant_id: str) -> bool:
        """Updates the metadata of an existing entity. RLS: WHERE id AND tenant_id."""
        self.logger.debug(f"Updating entity {entity_id} for tenant {tenant_id}")
        try:
            placeholder = self.db_factory.get_placeholder()
            with self.db_factory.get_cursor() as cursor:
                cursor.execute(
                    f"SELECT metadata FROM entities WHERE id = {placeholder} AND tenant_id = {placeholder}",
                    (entity_id, tenant_id),
                )
                row = cursor.fetchone()
                if not row:
                    self.logger.warning(f"Entity {entity_id} not found or access denied for tenant {tenant_id}")
                    return False
                try:
                    current_meta = json.loads(row[0])
                except (json.JSONDecodeError, TypeError) as e:
                    self.logger.warning(f"Failed to parse existing metadata JSON for entity {entity_id}: {e}")
                    current_meta = {}
                current_meta.update(new_metadata)
                cursor.execute(
                    f"UPDATE entities SET metadata = {placeholder} WHERE id = {placeholder} AND tenant_id = {placeholder}",
                    (json.dumps(current_meta), entity_id, tenant_id),
                )
            self.logger.info(f"Successfully updated entity {entity_id}")
            return True
        except DatabaseError as e:
            self.logger.error(f"Database error updating entity {entity_id}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error updating entity {entity_id}: {e}")
            return False

    def delete_entity(self, entity_id: str, tenant_id: str) -> bool:
        """Deletes an entity with RLS check."""
        self.logger.debug(f"Deleting entity {entity_id} for tenant {tenant_id}")
        try:
            placeholder = self.db_factory.get_placeholder()
            with self.db_factory.get_cursor() as cursor:
                # Verify entity belongs to tenant (RLS)
                cursor.execute(f"SELECT id FROM entities WHERE id = {placeholder} AND tenant_id = {placeholder}", (entity_id, tenant_id))
                row = cursor.fetchone()
                
                if not row:
                    self.logger.warning(f"Entity {entity_id} not found or access denied for tenant {tenant_id}")
                    return False
                
                # Delete the entity
                cursor.execute(f"DELETE FROM entities WHERE id = {placeholder} AND tenant_id = {placeholder}", (entity_id, tenant_id))
            
            self.logger.info(f"Successfully deleted entity {entity_id} for tenant {tenant_id}")
            return True
        except DatabaseError as e:
            self.logger.error(f"Database error deleting entity {entity_id} for tenant {tenant_id}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error deleting entity {entity_id} for tenant {tenant_id}: {e}")
            return False
            
    def get_client_secrets(self, user_id: str) -> Optional[Dict[str, str]]:
        self.logger.debug(f"Fetching client secrets for user {user_id}")
        try:
            placeholder = self.db_factory.get_placeholder()
            conn = self.db_factory.get_connection()
            self.db_factory.set_row_factory(conn)
            cursor = None
            try:
                cursor = self.db_factory.get_cursor_with_row_factory(conn)
                cursor.execute(f"SELECT wp_url, wp_user, wp_auth_hash FROM client_secrets WHERE user_id = {placeholder}", (user_id,))
                row = cursor.fetchone()
                
                if row:
                    self.logger.debug(f"Found client secrets for user {user_id}")
                    decrypted_password = None
                    if row["wp_auth_hash"]:
                        try:
                            decrypted_password = security_core.decrypt(row["wp_auth_hash"])
                        except Exception as e:
                            self.logger.error(f"Failed to decrypt wp_auth_hash for {user_id}: {e}")
                            decrypted_password = None

                    return {
                        "wp_url": row["wp_url"],
                        "wp_user": row["wp_user"],
                        "wp_password": decrypted_password
                    }
                self.logger.debug(f"No client secrets found for user {user_id}")
                return None
            finally:
                if cursor is not None:
                    cursor.close()
                self.db_factory.return_connection(conn)
        except DatabaseError as e:
            self.logger.error(f"Database error retrieving client secrets for user {user_id}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error retrieving client secrets for user {user_id}: {e}")
            return None

    def save_client_secrets(self, user_id: str, wp_url: str, wp_user: str, wp_password: str) -> bool:
        """Save or update WordPress credentials for a user. Use save_client_secrets_partial to update only url/user."""
        self.logger.debug(f"Saving client secrets for user {user_id}")
        try:
            try:
                encrypted_password = security_core.encrypt(wp_password)
            except Exception as e:
                self.logger.error(f"Encryption failed for wp_password for user {user_id}: {e}")
                return False

            sql = self.db_factory.get_insert_or_replace_sql(
                table="client_secrets",
                columns=["user_id", "wp_url", "wp_user", "wp_auth_hash"],
                primary_key="user_id"
            )
            with self.db_factory.get_cursor() as cursor:
                cursor.execute(sql, (user_id, wp_url, wp_user, encrypted_password))

            self.logger.info(f"Successfully saved client secrets for user {user_id}")
            return True
        except DatabaseError as e:
            self.logger.error(f"Database error saving client secrets for user {user_id}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error saving client secrets for user {user_id}: {e}")
            return False

    def save_client_secrets_partial(self, user_id: str, wp_url: str, wp_user: str) -> bool:
        """Update only WordPress URL and username; leave password unchanged. Creates row if missing (with empty hash)."""
        self.logger.debug(f"Updating client secrets (url/user only) for user {user_id}")
        try:
            placeholder = self.db_factory.get_placeholder()
            with self.db_factory.get_cursor() as cursor:
                cursor.execute(
                    f"SELECT wp_auth_hash FROM client_secrets WHERE user_id = {placeholder}",
                    (user_id,),
                )
                row = cursor.fetchone()
                existing_hash = row[0] if row else None
                if existing_hash is not None:
                    cursor.execute(
                        f"UPDATE client_secrets SET wp_url = {placeholder}, wp_user = {placeholder} WHERE user_id = {placeholder}",
                        (wp_url, wp_user, user_id),
                    )
                else:
                    sql = self.db_factory.get_insert_or_replace_sql(
                        table="client_secrets",
                        columns=["user_id", "wp_url", "wp_user", "wp_auth_hash"],
                        primary_key="user_id",
                    )
                    cursor.execute(sql, (user_id, wp_url, wp_user, ""))
            self.logger.info(f"Updated WordPress URL/user for user {user_id}")
            return True
        except DatabaseError as e:
            self.logger.error(f"Database error updating client secrets for user {user_id}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error updating client secrets for user {user_id}: {e}")
            return False

    # ====================================================
    # SECTION C.5: USAGE TRACKING & BILLING
    # ====================================================
    def create_usage_table_if_not_exists(self):
        """Creates the usage_ledger table if it doesn't exist."""
        try:
            with self.db_factory.get_cursor() as cursor:
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS usage_ledger (
                        id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        resource_type TEXT NOT NULL,
                        quantity REAL NOT NULL,
                        cost_usd REAL NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Create index for faster monthly spend queries
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_project_timestamp ON usage_ledger(project_id, timestamp)")
            
            self.logger.debug("Usage ledger table ready")
        except DatabaseError as e:
            self.logger.error(f"Database error creating usage_ledger table: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error creating usage_ledger table: {e}")
            raise

    def log_usage(self, project_id: str, resource_type: str, quantity: float, cost_usd: float) -> bool:
        """
        Logs resource usage to the usage_ledger table.
        
        Args:
            project_id: Project identifier
            resource_type: Type of resource (e.g., "twilio_voice", "gemini_token")
            quantity: Quantity used (e.g., minutes, tokens)
            cost_usd: Cost in USD
            
        Returns:
            True on success, False on error
        """
        self.logger.debug(f"Logging usage: {resource_type} x {quantity} = ${cost_usd:.4f} for project {project_id}")
        try:
            # Ensure table exists
            self.create_usage_table_if_not_exists()
            
            # Generate ID
            usage_id = str(uuid.uuid4())
            placeholder = self.db_factory.get_placeholder()
            
            with self.db_factory.get_cursor() as cursor:
                cursor.execute(f'''
                    INSERT INTO usage_ledger (id, project_id, resource_type, quantity, cost_usd, timestamp)
                    VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
                ''', (usage_id, project_id, resource_type, quantity, cost_usd, datetime.now()))
            
            self.logger.debug(f"Successfully logged usage record {usage_id}")
            return True
        except DatabaseError as e:
            self.logger.error(f"Database error logging usage for project {project_id}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error logging usage for project {project_id}: {e}")
            return False

    def get_usage_ledger(
        self, user_id: str, project_id: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get usage records from usage_ledger. If project_id is set, verifies ownership and returns
        records for that project. Otherwise returns records for all projects owned by user_id.
        Creates usage_ledger table if it doesn't exist.
        """
        self.logger.debug(f"Fetching usage ledger for user {user_id}, project_id={project_id}")
        try:
            self.create_usage_table_if_not_exists()
            placeholder = self.db_factory.get_placeholder()

            if project_id:
                if not self.verify_project_ownership(user_id, project_id):
                    return []
                with self.db_factory.get_cursor(commit=False) as cursor:
                    cursor.execute(
                        f"""
                        SELECT id, project_id, resource_type, quantity, cost_usd, timestamp
                        FROM usage_ledger
                        WHERE project_id = {placeholder}
                        ORDER BY timestamp DESC
                        LIMIT {placeholder}
                        """,
                        (project_id, limit),
                    )
                    rows = cursor.fetchall()
            else:
                projects = self.get_projects(user_id=user_id)
                project_ids = [p.get("project_id") for p in projects] if projects else []
                if not project_ids:
                    return []
                placeholders = ",".join([placeholder] * len(project_ids))
                with self.db_factory.get_cursor(commit=False) as cursor:
                    cursor.execute(
                        f"""
                        SELECT id, project_id, resource_type, quantity, cost_usd, timestamp
                        FROM usage_ledger
                        WHERE project_id IN ({placeholders})
                        ORDER BY timestamp DESC
                        LIMIT {placeholder}
                        """,
                        (*project_ids, limit),
                    )
                    rows = cursor.fetchall()

            return [
                {
                    "id": row[0],
                    "project_id": row[1],
                    "resource_type": row[2],
                    "quantity": row[3],
                    "cost_usd": row[4],
                    "timestamp": row[5],
                }
                for row in rows
            ]
        except DatabaseError as e:
            self.logger.error(f"Database error fetching usage ledger: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error fetching usage ledger: {e}")
            return []

    def get_monthly_spend(self, project_id: str) -> float:
        """
        Gets the total monthly spend for a project (current month).
        
        Args:
            project_id: Project identifier
            
        Returns:
            Total spend in USD for the current month (0.0 if no records)
        """
        self.logger.debug(f"Getting monthly spend for project {project_id}")
        try:
            # Ensure table exists
            self.create_usage_table_if_not_exists()
            
            placeholder = self.db_factory.get_placeholder()
            date_expr = self.db_factory.get_date_start_of_month()
            
            with self.db_factory.get_cursor(commit=False) as cursor:
                # Query for current month's spend
                cursor.execute(f'''
                    SELECT SUM(cost_usd) 
                    FROM usage_ledger 
                    WHERE project_id = {placeholder} 
                    AND timestamp >= {date_expr}
                ''', (project_id,))
                
                row = cursor.fetchone()
                total_spend = float(row[0]) if row and row[0] is not None else 0.0
            
            self.logger.debug(f"Monthly spend for project {project_id}: ${total_spend:.2f}")
            return total_spend
        except DatabaseError as e:
            self.logger.error(f"Database error getting monthly spend for project {project_id}: {e}")
            return 0.0
        except Exception as e:
            self.logger.error(f"Unexpected error getting monthly spend for project {project_id}: {e}")
            return 0.0

    # ====================================================
    # SECTION D: SEMANTIC MEMORY (RAG)
    # ====================================================
    def save_context(self, tenant_id: str, text: str, metadata: Dict = {}, project_id: str = None, campaign_id: str = None):
        """Saves embeddings with Project and Campaign Context."""
        if not self.chroma_enabled or not self.vector_collection:
            self.logger.debug("ChromaDB not available, skipping context save")
            return
            
        try:
            metadata['tenant_id'] = tenant_id
            if project_id:
                metadata['project_id'] = project_id
            if campaign_id:
                metadata['campaign_id'] = campaign_id
            
            # Manually embed using our Google embedding function to ensure consistency
            embeddings = self.embedding_fn([text])
            
            self.vector_collection.add(
                documents=[text],
                embeddings=embeddings,  # Pass pre-embedded vectors
                metadatas=[metadata],
                ids=[str(uuid.uuid4())]
            )
        except Exception as e:
            self.logger.warning(f"Failed to save context to ChromaDB: {e}")

    def query_context(self, tenant_id: str, query: str, n_results: int = 3, project_id: str = None, campaign_id: str = None, return_metadata: bool = False):
        """Retrieves embeddings filtered by Project and Campaign.
        
        Args:
            tenant_id: User ID for RLS
            query: Search query text
            n_results: Number of results to return
            project_id: Optional project filter
            campaign_id: Optional campaign filter
            return_metadata: If True, returns list of dicts with 'text' and 'metadata'. If False, returns list of text strings.
        
        Returns:
            List of text strings (if return_metadata=False) or list of dicts with 'text' and 'metadata' (if return_metadata=True)
        """
        if not self.chroma_enabled or not self.vector_collection:
            self.logger.debug("ChromaDB not available, returning empty results")
            return []
            
        try:
            # Build where clause with tenant_id, project_id, and campaign_id filters
            where_conditions = [{"tenant_id": tenant_id}]
            
            if project_id:
                where_conditions.append({"project_id": project_id})
            
            if campaign_id:
                where_conditions.append({"campaign_id": campaign_id})
            
            if len(where_conditions) > 1:
                where_clause = {"$and": where_conditions}
            else:
                where_clause = where_conditions[0]
            
            # Manually embed query using our Google embedding function to ensure consistency
            query_embedding = self.embedding_fn.embed_query(query)
                
            results = self.vector_collection.query(
                query_embeddings=[query_embedding],  # Use pre-embedded vector instead of query_texts
                n_results=n_results,
                where=where_clause
            )
            
            if return_metadata:
                # Return list of dicts with text and metadata
                documents = results.get('documents', [[]])[0] if results.get('documents') else []
                metadatas = results.get('metadatas', [[]])[0] if results.get('metadatas') else []
                return [
                    {"text": doc, "metadata": meta}
                    for doc, meta in zip(documents, metadatas)
                ]
            else:
                # Return list of text strings (backward compatible)
                return results['documents'][0] if results['documents'] else []
        except Exception as e:
            self.logger.warning(f"Failed to query context from ChromaDB: {e}")
            return []

# Singleton
memory = MemoryManager()