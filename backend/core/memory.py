# backend/core/memory.py
import sqlite3
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
        self.model = "text-embedding-004"

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
        
        # Ensure directories exist with proper permissions
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(self.vector_path, exist_ok=True)
        
        self._init_sqlite()
        
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

    def _init_sqlite(self):
        """Creates tables with Market-Ready schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 1. USERS (With Hashed Passwords)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY, 
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL
            )
        ''')

        # 2. PROJECTS
        cursor.execute('''
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
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS entities (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                project_id TEXT,
                entity_type TEXT NOT NULL,
                name TEXT NOT NULL,
                primary_contact TEXT,
                metadata JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_tenant ON entities(tenant_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_project ON entities(project_id)")

        # 4. SECRETS
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS client_secrets (
                user_id TEXT PRIMARY KEY,
                wp_url TEXT,
                wp_user TEXT,
                wp_auth_hash TEXT,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')
        
        conn.commit()
        conn.close()

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
        conn = None
        try:
            pwd_hash, salt = self._hash_password(password)
            conn = sqlite3.connect(self.db_path)
            conn.execute("INSERT INTO users (user_id, password_hash, salt) VALUES (?, ?, ?)", 
                         (email, pwd_hash, salt))
            conn.commit()
            self.logger.info(f"Successfully created user {email}")
            return True
        except sqlite3.IntegrityError as e:
            self.logger.warning(f"User {email} already exists: {e}")
            return False
        except sqlite3.Error as e:
            self.logger.error(f"Database error creating user {email}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error creating user {email}: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def _user_exists(self, user_id: str) -> bool:
        """Check if user exists (for JWT validation)."""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
            exists = cursor.fetchone() is not None
            return exists
        except sqlite3.Error as e:
            self.logger.error(f"Database error checking user existence for {user_id}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error checking user existence for {user_id}: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def verify_user(self, email, password):
        self.logger.debug(f"Verifying user credentials for {email}")
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute("SELECT password_hash, salt FROM users WHERE user_id = ?", (email,))
            row = cursor.fetchone()
            
            if row:
                stored_hash, salt = row
                check_hash, _ = self._hash_password(password, salt)
                is_valid = check_hash == stored_hash
                if is_valid:
                    self.logger.debug(f"Credentials verified for user {email}")
                else:
                    self.logger.debug(f"Invalid credentials for user {email}")
                return is_valid
            self.logger.debug(f"User {email} not found")
            return False
        except sqlite3.Error as e:
            self.logger.error(f"Database error verifying user {email}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error verifying user {email}: {e}")
            return False
        finally:
            if conn:
                conn.close()

    # ====================================================
    # SECTION B: PROJECT MANAGEMENT
    # ====================================================
    def register_project(self, user_id, project_id, niche):
        self.logger.debug(f"Registering project {project_id} for user {user_id}")
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            path = f"data/profiles/{project_id}/dna.generated.yaml"
            conn.execute(
                "INSERT OR REPLACE INTO projects (project_id, user_id, niche, dna_path) VALUES (?, ?, ?, ?)",
                (project_id, user_id, niche, path)
            )
            conn.commit()
            self.logger.info(f"Successfully registered project {project_id} for user {user_id}")
        except sqlite3.Error as e:
            self.logger.error(f"Database error registering project {project_id} for user {user_id}: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error registering project {project_id} for user {user_id}: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def get_user_project(self, user_id):
        self.logger.debug(f"Fetching user project for user {user_id}")
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM projects WHERE user_id = ? ORDER BY created_at DESC LIMIT 1", (user_id,))
            row = cursor.fetchone()
            result = dict(row) if row else None
            if result:
                self.logger.debug(f"Found project {result.get('project_id')} for user {user_id}")
            else:
                self.logger.debug(f"No project found for user {user_id}")
            return result
        except sqlite3.Error as e:
            self.logger.error(f"Database error fetching user project for user {user_id}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error fetching user project for user {user_id}: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def get_projects(self, user_id: str) -> List[Dict]:
        """Get all projects for a specific user."""
        self.logger.debug(f"Fetching all projects for user {user_id}")
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM projects WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
            rows = cursor.fetchall()
            results = [dict(row) for row in rows]
            self.logger.debug(f"Found {len(results)} projects for user {user_id}")
            return results
        except sqlite3.Error as e:
            self.logger.error(f"Database error fetching projects for user {user_id}: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error fetching projects for user {user_id}: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def verify_project_ownership(self, user_id: str, project_id: str) -> bool:
        """
        Verify that a project belongs to a specific user.
        
        Critical for multi-tenant security.
        Future: With Supabase RLS, this check happens at database level.
        """
        self.logger.debug(f"Verifying project ownership: user={user_id}, project={project_id}")
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute(
                "SELECT 1 FROM projects WHERE project_id = ? AND user_id = ?",
                (project_id, user_id)
            )
            exists = cursor.fetchone() is not None
            if not exists:
                self.logger.warning(f"Project ownership verification failed: user={user_id}, project={project_id}")
            return exists
        except sqlite3.Error as e:
            self.logger.error(f"Database error verifying project ownership: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error verifying project ownership: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def get_project_owner(self, project_id: str) -> Optional[str]:
        """
        Get the user_id (owner) of a project.
        
        Used to find the correct tenant_id for operations.
        Returns None if project doesn't exist.
        """
        self.logger.debug(f"Getting project owner for project {project_id}")
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM projects WHERE project_id = ?", (project_id,))
            row = cursor.fetchone()
            
            if row:
                user_id = row[0]
                self.logger.debug(f"Found project owner: {user_id} for project {project_id}")
                return user_id
            else:
                self.logger.warning(f"Project {project_id} not found in database")
                return None
        except sqlite3.Error as e:
            self.logger.error(f"Database error getting project owner for {project_id}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error getting project owner for {project_id}: {e}")
            return None
        finally:
            if conn:
                conn.close()

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
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            
            # Priority: parameter > entity attribute > metadata
            if project_id is None:
                # Check if entity has project_id attribute (set by agents)
                project_id = getattr(entity, 'project_id', None)
                if project_id is None:
                    # Fallback to metadata (for legacy data)
                    project_id = entity.metadata.get("project_id")
            
            conn.execute('''
                INSERT OR REPLACE INTO entities 
                (id, tenant_id, project_id, entity_type, name, primary_contact, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                entity.id,
                entity.tenant_id,
                project_id,
                entity.entity_type,
                entity.name,
                entity.primary_contact,
                json.dumps(entity.metadata),
                entity.created_at
            ))
            conn.commit()
            self.logger.info(f"Successfully saved entity {entity.id} of type {entity.entity_type}")
            return True
        except sqlite3.Error as e:
            self.logger.error(f"Database error saving entity {entity.id}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error saving entity {entity.id}: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def get_entities(self, tenant_id: str, entity_type: Optional[str] = None, 
                     project_id: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[Dict]:
        self.logger.debug(f"Fetching entities for tenant {tenant_id}, type: {entity_type}, project: {project_id}")
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT * FROM entities WHERE tenant_id = ?"
            params = [tenant_id]
            
            if entity_type:
                query += " AND entity_type = ?"
                params.append(entity_type)
            
            if project_id:
                query += " AND project_id = ?"
                params.append(project_id)
                
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor.execute(query, params)
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
        except sqlite3.Error as e:
            self.logger.error(f"Database error fetching entities for tenant {tenant_id}: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error fetching entities for tenant {tenant_id}: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def update_entity(self, entity_id: str, new_metadata: dict) -> bool:
        """Updates the metadata of an existing entity."""
        self.logger.debug(f"Updating entity {entity_id}")
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 1. Fetch existing metadata
            cursor.execute("SELECT metadata FROM entities WHERE id = ?", (entity_id,))
            row = cursor.fetchone()
            
            if not row:
                self.logger.warning(f"Entity {entity_id} not found for update")
                return False
            
            # 2. Merge new data with old data
            try:
                current_meta = json.loads(row[0])
            except (json.JSONDecodeError, TypeError) as e:
                self.logger.warning(f"Failed to parse existing metadata JSON for entity {entity_id}: {e}")
                current_meta = {}
            current_meta.update(new_metadata)
            
            # 3. Save back
            cursor.execute(
                "UPDATE entities SET metadata = ? WHERE id = ?", 
                (json.dumps(current_meta), entity_id)
            )
            
            conn.commit()
            self.logger.info(f"Successfully updated entity {entity_id}")
            return True
        except sqlite3.Error as e:
            self.logger.error(f"Database error updating entity {entity_id}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error updating entity {entity_id}: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def delete_entity(self, entity_id: str, tenant_id: str) -> bool:
        """Deletes an entity with RLS check."""
        self.logger.debug(f"Deleting entity {entity_id} for tenant {tenant_id}")
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Verify entity belongs to tenant (RLS)
            cursor.execute("SELECT id FROM entities WHERE id = ? AND tenant_id = ?", (entity_id, tenant_id))
            row = cursor.fetchone()
            
            if not row:
                self.logger.warning(f"Entity {entity_id} not found or access denied for tenant {tenant_id}")
                return False
            
            # Delete the entity
            cursor.execute("DELETE FROM entities WHERE id = ? AND tenant_id = ?", (entity_id, tenant_id))
            conn.commit()
            self.logger.info(f"Successfully deleted entity {entity_id} for tenant {tenant_id}")
            return True
        except sqlite3.Error as e:
            self.logger.error(f"Database error deleting entity {entity_id} for tenant {tenant_id}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error deleting entity {entity_id} for tenant {tenant_id}: {e}")
            return False
        finally:
            if conn:
                conn.close()
            
    def get_client_secrets(self, user_id: str) -> Optional[Dict[str, str]]:
        self.logger.debug(f"Fetching client secrets for user {user_id}")
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT wp_url, wp_user, wp_auth_hash FROM client_secrets WHERE user_id = ?", (user_id,))
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
        except sqlite3.Error as e:
            self.logger.error(f"Database error retrieving client secrets for user {user_id}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error retrieving client secrets for user {user_id}: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def save_client_secrets(self, user_id: str, wp_url: str, wp_user: str, wp_password: str) -> bool:
        """Save or update WordPress credentials for a user."""
        self.logger.debug(f"Saving client secrets for user {user_id}")
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            try:
                encrypted_password = security_core.encrypt(wp_password)
            except Exception as e:
                self.logger.error(f"Encryption failed for wp_password for user {user_id}: {e}")
                return False
            
            # Use INSERT OR REPLACE to update if exists
            cursor.execute('''
                INSERT OR REPLACE INTO client_secrets (user_id, wp_url, wp_user, wp_auth_hash)
                VALUES (?, ?, ?, ?)
            ''', (user_id, wp_url, wp_user, encrypted_password))
            
            conn.commit()
            self.logger.info(f"Successfully saved client secrets for user {user_id}")
            return True
        except sqlite3.Error as e:
            self.logger.error(f"Database error saving client secrets for user {user_id}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error saving client secrets for user {user_id}: {e}")
            return False
        finally:
            if conn:
                conn.close()

    # ====================================================
    # SECTION C.5: USAGE TRACKING & BILLING
    # ====================================================
    def create_usage_table_if_not_exists(self):
        """Creates the usage_ledger table if it doesn't exist."""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
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
            
            conn.commit()
            self.logger.debug("Usage ledger table ready")
        except sqlite3.Error as e:
            self.logger.error(f"Database error creating usage_ledger table: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error creating usage_ledger table: {e}")
            raise
        finally:
            if conn:
                conn.close()

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
        conn = None
        try:
            # Ensure table exists
            self.create_usage_table_if_not_exists()
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Generate ID
            import uuid
            usage_id = str(uuid.uuid4())
            
            cursor.execute('''
                INSERT INTO usage_ledger (id, project_id, resource_type, quantity, cost_usd, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (usage_id, project_id, resource_type, quantity, cost_usd, datetime.now()))
            
            conn.commit()
            self.logger.debug(f"Successfully logged usage record {usage_id}")
            return True
        except sqlite3.Error as e:
            self.logger.error(f"Database error logging usage for project {project_id}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error logging usage for project {project_id}: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def get_monthly_spend(self, project_id: str) -> float:
        """
        Gets the total monthly spend for a project (current month).
        
        Args:
            project_id: Project identifier
            
        Returns:
            Total spend in USD for the current month (0.0 if no records)
        """
        self.logger.debug(f"Getting monthly spend for project {project_id}")
        conn = None
        try:
            # Ensure table exists
            self.create_usage_table_if_not_exists()
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Query for current month's spend
            cursor.execute('''
                SELECT SUM(cost_usd) 
                FROM usage_ledger 
                WHERE project_id = ? 
                AND timestamp >= date('now', 'start of month')
            ''', (project_id,))
            
            row = cursor.fetchone()
            total_spend = float(row[0]) if row and row[0] is not None else 0.0
            
            self.logger.debug(f"Monthly spend for project {project_id}: ${total_spend:.2f}")
            return total_spend
        except sqlite3.Error as e:
            self.logger.error(f"Database error getting monthly spend for project {project_id}: {e}")
            return 0.0
        except Exception as e:
            self.logger.error(f"Unexpected error getting monthly spend for project {project_id}: {e}")
            return 0.0
        finally:
            if conn:
                conn.close()

    # ====================================================
    # SECTION D: SEMANTIC MEMORY (RAG)
    # ====================================================
    def save_context(self, tenant_id: str, text: str, metadata: Dict = {}, project_id: str = None):
        """Saves embeddings with Project Context."""
        if not self.chroma_enabled or not self.vector_collection:
            self.logger.debug("ChromaDB not available, skipping context save")
            return
            
        try:
            metadata['tenant_id'] = tenant_id
            if project_id:
                metadata['project_id'] = project_id
            
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

    def query_context(self, tenant_id: str, query: str, n_results: int = 3, project_id: str = None):
        """Retrieves embeddings filtered by Project."""
        if not self.chroma_enabled or not self.vector_collection:
            self.logger.debug("ChromaDB not available, returning empty results")
            return []
            
        try:
            where_clause = {"tenant_id": tenant_id}
            if project_id:
                where_clause = {
                    "$and": [
                        {"tenant_id": tenant_id},
                        {"project_id": project_id}
                    ]
                }
            
            # Manually embed query using our Google embedding function to ensure consistency
            query_embedding = self.embedding_fn.embed_query(query)
                
            results = self.vector_collection.query(
                query_embeddings=[query_embedding],  # Use pre-embedded vector instead of query_texts
                n_results=n_results,
                where=where_clause
            )
            return results['documents'][0] if results['documents'] else []
        except Exception as e:
            self.logger.warning(f"Failed to query context from ChromaDB: {e}")
            return []

# Singleton
memory = MemoryManager()