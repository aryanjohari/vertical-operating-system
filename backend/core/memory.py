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
        
        # The Master Table for all Entities (Leads, Jobs, etc.)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS entities (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                name TEXT NOT NULL,
                primary_contact TEXT,
                metadata JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # An Audit Log for RLS tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id TEXT PRIMARY KEY,
                tenant_id TEXT,
                action TEXT,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()

    # ====================================================
    # SECTION A: STRUCTURED MEMORY (Leads, Jobs)
    # ====================================================
    def save_entity(self, entity: Entity) -> bool:
        """Saves a lead/job to SQLite."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO entities (id, tenant_id, entity_type, name, primary_contact, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                entity.id,
                entity.tenant_id,
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

    def get_entities(self, tenant_id: str, entity_type: Optional[str] = None) -> List[Dict]:
        """
        RLS ENFORCED: Only returns data for the specific tenant_id.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row # Return dicts instead of tuples
        cursor = conn.cursor()
        
        if entity_type:
            cursor.execute("SELECT * FROM entities WHERE tenant_id = ? AND entity_type = ?", (tenant_id, entity_type))
        else:
            cursor.execute("SELECT * FROM entities WHERE tenant_id = ?", (tenant_id,))
            
        rows = cursor.fetchall()
        conn.close()
        
        # Convert JSON strings back to dicts
        results = []
        for row in rows:
            item = dict(row)
            item['metadata'] = json.loads(item['metadata'])
            results.append(item)
            
        return results

    # ====================================================
    # SECTION B: SEMANTIC MEMORY (Context/DNA)
    # ====================================================
    def save_context(self, tenant_id: str, text: str, metadata: Dict = {}):
        """
        Embeds text into the Vector DB.
        Use this for storing strategy docs, email templates, or competitor analysis.
        """
        # We enforce RLS in metadata
        metadata['tenant_id'] = tenant_id
        
        self.vector_collection.add(
            documents=[text],
            metadatas=[metadata],
            ids=[str(uuid.uuid4())]
        )

    def query_context(self, tenant_id: str, query: str, n_results: int = 3):
        """
        Finds relevant context for the AI.
        RLS ENFORCED: Filters by tenant_id automatically.
        """
        results = self.vector_collection.query(
            query_texts=[query],
            n_results=n_results,
            where={"tenant_id": tenant_id} # <--- THE MAGIC RLS FILTER
        )
        return results['documents'][0] if results['documents'] else []

# Initialize Singleton (So the whole app shares one connection)
memory = MemoryManager()