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

# --- NEW: Google Embedding Wrapper (The Fix) ---
class GoogleEmbeddingFunction:
    def __init__(self):
        # Uses your existing GOOGLE_API_KEY with validation
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is not set. Please set it in your .env file.")
        self.client = genai.Client(api_key=api_key)
        # ChromaDB requires a 'name' attribute for embedding functions
        self.name = "google_embedding_function"

    def __call__(self, input: List[str]) -> List[List[float]]:
        if not input:
            return []
        # Uses Google's efficient model instead of local download
        response = self.client.models.embed_content(
            model="text-embedding-004",
            contents=input
        )
        return [e.values for e in response.embeddings]

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
            
            # Create embedding function instance
            embedding_fn = GoogleEmbeddingFunction()
            
            # Try to get existing collection first (without embedding_function)
            try:
                self.vector_collection = self.chroma_client.get_collection(name="apex_context")
                self.logger.info("Reusing existing ChromaDB collection")
            except Exception:
                # Collection doesn't exist, create it with embedding function
                self.vector_collection = self.chroma_client.create_collection(
                    name="apex_context",
                    embedding_function=embedding_fn
                )
                self.logger.info("Created new ChromaDB collection")
            
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
                query += " AND (project_id = ? OR project_id IS NULL)"
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
                return {
                    "wp_url": row["wp_url"],
                    "wp_user": row["wp_user"],
                    # Note: In production you'd decrypt wp_auth_hash here
                    "wp_password": row["wp_auth_hash"] 
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
            
            # Use INSERT OR REPLACE to update if exists
            cursor.execute('''
                INSERT OR REPLACE INTO client_secrets (user_id, wp_url, wp_user, wp_auth_hash)
                VALUES (?, ?, ?, ?)
            ''', (user_id, wp_url, wp_user, wp_password))
            
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
                
            self.vector_collection.add(
                documents=[text],
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
                
            results = self.vector_collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where_clause
            )
            return results['documents'][0] if results['documents'] else []
        except Exception as e:
            self.logger.warning(f"Failed to query context from ChromaDB: {e}")
            return []

# Singleton
memory = MemoryManager()