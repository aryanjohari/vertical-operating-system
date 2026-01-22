#!/usr/bin/env python3
"""
Script to delete the ChromaDB collection so it can be recreated with Google embeddings.

This script deletes the 'apex_context' collection from ChromaDB.
On the next run, the system will recreate it with the GoogleEmbeddingFunction.
"""
import os
import sys
import logging

from dotenv import load_dotenv

load_dotenv()
# Add parent directory to path to import backend modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import chromadb
from backend.core.memory import GoogleEmbeddingFunction

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def delete_chromadb_collection():
    """Delete the ChromaDB collection and database to force recreation with Google embeddings."""
    try:
        # Use the same path as MemoryManager
        vector_path = os.path.abspath("data/chroma_db")
        
        logger.info(f"Connecting to ChromaDB at: {vector_path}")
        client = chromadb.PersistentClient(path=vector_path)
        
        # Check if collection exists and delete it
        try:
            collection = client.get_collection(name="apex_context")
            logger.info(f"Found collection 'apex_context' with {collection.count()} documents")
            
            # Delete the collection
            client.delete_collection(name="apex_context")
            logger.info("✅ Successfully deleted 'apex_context' collection")
            
        except Exception as e:
            error_msg = str(e).lower()
            if "does not exist" in error_msg or "not found" in error_msg:
                logger.warning("Collection 'apex_context' does not exist.")
            else:
                logger.warning(f"Error deleting collection: {e}")
        
        # Also delete the SQLite database and UUID directories to ensure clean slate
        import shutil
        sqlite_path = os.path.join(vector_path, "chroma.sqlite3")
        if os.path.exists(sqlite_path):
            os.remove(sqlite_path)
            logger.info("✅ Deleted chroma.sqlite3 database")
        
        # Delete UUID directories (ChromaDB stores data in these)
        for item in os.listdir(vector_path):
            item_path = os.path.join(vector_path, item)
            if os.path.isdir(item_path) and len(item) == 36:  # UUID format
                shutil.rmtree(item_path)
                logger.info(f"✅ Deleted UUID directory: {item}")
        
        logger.info("✅ ChromaDB fully cleared. The collection will be recreated with Google embeddings on next run.")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to delete ChromaDB collection: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    logger.info("🗑️  Deleting ChromaDB collection...")
    success = delete_chromadb_collection()
    sys.exit(0 if success else 1)
