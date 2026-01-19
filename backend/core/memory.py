import sqlite3
import chromadb
import uuid
import json
import logging
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from backend.core.models import Entity

class MemoryManager:
    def __init__(self, db_path="data/apex.db", vector_path="data/chroma_db"):
        self.logger = logging.getLogger("ApexMemory")
        self.db_path = db_path
        self.vector_path = vector_path
        
        # Ensure directories exist
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        os.makedirs(vector_path, exist_ok=True)
        
        # 1. INITIALIZE SQLITE (The Structured Brain)
        self._init_sqlite()
        
        # 2. INITIALIZE VECTOR DB (The Semantic Brain)
        # using the local persistent client so data survives restarts
        self.chroma_client = chromadb.PersistentClient(path=vector_path)
        self.vector_collection = self.chroma_client.get_or_create_collection(name="apex_context")
        
        self.logger.info("Memory Systems Online (SQL + Vector)")

    def _init_sqlite(self):
        """Creates the tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # --- SYSTEM TABLES (Strict Schema for Security) ---
        
        # 1. USERS: The Gatekeeper
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY, -- Email is simplest for now
                password TEXT NOT NULL
            )
        ''')

        # 2. PROJECTS: The Link between User and DNA
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

        # --- DATA TABLES (Flexible Schema for AI) ---
        
        # 3. ENTITIES: The Master Table for Leads, Jobs, etc.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS entities (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL, -- Links to users.user_id
                project_id TEXT, -- Links to projects.project_id
                entity_type TEXT NOT NULL, -- 'lead', 'job', 'competitor'
                name TEXT NOT NULL,
                primary_contact TEXT,
                metadata JSON, -- The Flexible AI Brain
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Migration: Add project_id column if it doesn't exist (for existing databases)
        try:
            cursor.execute("ALTER TABLE entities ADD COLUMN project_id TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # 4. LOGS: Audit Trail
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id TEXT PRIMARY KEY,
                tenant_id TEXT,
                action TEXT,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 5. CLIENT_SECRETS: Per-user WordPress credentials
        # Note: Passwords stored as plain text for MVP. Should be encrypted in production.
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS client_secrets (
                user_id TEXT PRIMARY KEY,
                wp_url TEXT NOT NULL,
                wp_user TEXT NOT NULL,
                wp_password TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        ''')
        
        conn.commit()
        conn.close()

    # ====================================================
    # SECTION A: AUTHENTICATION & PROJECTS (New)
    # ====================================================
    def create_user(self, email, password):
        """Registers a new user."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("INSERT INTO users (user_id, password) VALUES (?, ?)", (email, password))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False # User already exists
        finally:
            conn.close()

    def verify_user(self, email, password):
        """Checks credentials."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute("SELECT password FROM users WHERE user_id = ?", (email,))
        row = cursor.fetchone()
        conn.close()
        return row and row[0] == password

    def register_project(self, user_id, project_id, niche):
        """Links a DNA Profile to a User."""
        conn = sqlite3.connect(self.db_path)
        # We assume standard path structure based on project_id
        path = f"data/profiles/{project_id}/dna.generated.yaml"
        
        conn.execute(
            "INSERT OR REPLACE INTO projects (project_id, user_id, niche, dna_path) VALUES (?, ?, ?, ?)",
            (project_id, user_id, niche, path)
        )
        conn.commit()
        conn.close()

    def get_user_project(self, user_id):
        """Retrieves the active project for a user (Simple 1-project limit for now)."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM projects WHERE user_id = ? ORDER BY created_at DESC LIMIT 1", (user_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_projects(self, user_id: str) -> List[Dict]:
        """Retrieves all projects for a user."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM projects WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # ====================================================
    # SECTION B: STRUCTURED MEMORY (Leads, Jobs)
    # ====================================================
    def save_entity(self, entity: Entity, project_id: Optional[str] = None) -> bool:
        """Saves a lead/job to SQLite."""
        try:
            conn = sqlite3.connect(self.db_path)
            
            # Get project_id from entity metadata if not provided
            if project_id is None:
                project_id = entity.metadata.get("project_id")
            
            conn.execute('''
                INSERT OR REPLACE INTO entities (id, tenant_id, project_id, entity_type, name, primary_contact, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                entity.id,
                entity.tenant_id,
                project_id,
                entity.entity_type,
                entity.name,
                entity.primary_contact,
                json.dumps(entity.metadata), # Store dict as JSON string
                entity.created_at
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            self.logger.error(f"SQL Error: {e}")
            return False

    def get_entities(self, tenant_id: str, entity_type: Optional[str] = None, project_id: Optional[str] = None) -> List[Dict]:
        """
        RLS ENFORCED: Only returns data for the specific tenant_id.
        Optionally filters by project_id.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row # Return dicts instead of tuples
        cursor = conn.cursor()
        
        query = "SELECT * FROM entities WHERE tenant_id = ?"
        params = [tenant_id]
        
        if entity_type:
            query += " AND entity_type = ?"
            params.append(entity_type)
        
        if project_id:
            query += " AND (project_id = ? OR project_id IS NULL)"
            params.append(project_id)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        # Convert JSON strings back to dicts
        results = []
        for row in rows:
            item = dict(row)
            item['metadata'] = json.loads(item['metadata'])
            results.append(item)
            
        return results
    
    def update_entity(self, entity_id: str, new_metadata: dict) -> bool:
        """Updates the metadata of an existing entity."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 1. Fetch existing metadata
            cursor.execute("SELECT metadata FROM entities WHERE id = ?", (entity_id,))
            row = cursor.fetchone()
            
            if not row:
                conn.close()
                return False
            
            # 2. Merge new data with old data
            current_meta = json.loads(row[0])
            current_meta.update(new_metadata)
            
            # 3. Save back
            cursor.execute(
                "UPDATE entities SET metadata = ? WHERE id = ?", 
                (json.dumps(current_meta), entity_id)
            )
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            self.logger.error(f"Update Error: {e}")
            return False
    
    def save_client_secrets(self, user_id: str, wp_url: str, wp_user: str, wp_password: str) -> bool:
        """Saves or updates WordPress credentials for a user."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO client_secrets (user_id, wp_url, wp_user, wp_password)
                VALUES (?, ?, ?, ?)
            ''', (user_id, wp_url, wp_user, wp_password))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            self.logger.error(f"Error saving client secrets: {e}")
            return False
    
    def get_client_secrets(self, user_id: str) -> Optional[Dict[str, str]]:
        """Retrieves WordPress credentials for a user."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT wp_url, wp_user, wp_password FROM client_secrets WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    "wp_url": row["wp_url"],
                    "wp_user": row["wp_user"],
                    "wp_password": row["wp_password"]
                }
            return None
        except Exception as e:
            self.logger.error(f"Error retrieving client secrets: {e}")
            return None

    # ====================================================
    # SECTION C: SEMANTIC MEMORY (Context/DNA)
    # ====================================================
    def save_context(self, tenant_id: str, text: str, metadata: Dict = {}):
        """Embeds text into the Vector DB."""
        metadata['tenant_id'] = tenant_id
        
        self.vector_collection.add(
            documents=[text],
            metadatas=[metadata],
            ids=[str(uuid.uuid4())]
        )

    def query_context(self, tenant_id: str, query: str, n_results: int = 3):
        """Finds relevant context with RLS."""
        results = self.vector_collection.query(
            query_texts=[query],
            n_results=n_results,
            where={"tenant_id": tenant_id}
        )
        return results['documents'][0] if results['documents'] else []

# Initialize Singleton
memory = MemoryManager()