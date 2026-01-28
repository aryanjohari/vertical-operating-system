import csv
import os

from dotenv import load_dotenv

load_dotenv()

import sys

# Add parent directory to path to import backend modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import json
import chromadb
import sqlite3
from backend.core.memory import memory

# CONFIG
OUTPUT_DIR = "data_dumps"
USER_ID = "admin@admin.com"

def setup_dirs():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"📁 Created directory: {OUTPUT_DIR}")

def dump_entities():
    print("--- 📦 DUMPING ENTITIES (JSON DB) ---")
    
    # UPDATED: Added 'seo_keyword' because that is what Strategist uses
    # Added 'knowledge_fragment' for intel entities (competitors/facts)
    entity_types = ["project", "anchor_location", "seo_keyword", "page_draft", "lead", "knowledge_fragment"]
    
    for e_type in entity_types:
        filename = f"{OUTPUT_DIR}/entities_{e_type}.csv"
        
        # Fetch entities
        entities = memory.get_entities(tenant_id=USER_ID, entity_type=e_type)
        
        if not entities:
            print(f"⚠️  No data found for: {e_type}")
            continue

        try:
            with open(filename, "w", newline="", encoding="utf-8") as f:
                # Dynamic Header Generation
                # We grab all keys from the first entity's metadata to ensure we see everything
                first_meta = entities[0].get("metadata", {})
                headers = ["id", "name", "project_id", "created_at"] + list(first_meta.keys())
                
                writer = csv.writer(f)
                writer.writerow(headers)
                
                for entity in entities:
                    meta = entity.get("metadata", {})
                    row = [
                        entity.get("id"),
                        entity.get("name"),
                        entity.get("project_id"),
                        entity.get("created_at")
                    ]
                    
                    # Fill metadata columns
                    for key in headers[4:]:
                        val = meta.get(key, "")

                        if key == "content":
                            row.append(val)
                            continue
                        # Truncate strictly for CSV, but keep enough to verify
                        if isinstance(val, str) and len(val) > 200:
                            val = val[:200] + "... [TRUNCATED]"
                        row.append(val)
                    
                    writer.writerow(row)
            
            print(f"✅ Exported {len(entities)} {e_type}s to {filename}")

            # SPECIAL CHECK: If this is a Page Draft, print the 'Ready' ones to console
            if e_type == "page_draft":
                for p in entities:
                    if p.get("metadata", {}).get("status") == "ready_to_publish":
                        print(f"\n   🎉 FOUND READY PAGE: {p.get('name')}")
                        print(f"      - Tool Type: {p.get('metadata', {}).get('tool_type')}")
                        print(f"      - Has Tool: {p.get('metadata', {}).get('has_tool')}")
                        print(f"      - Slug: {p.get('metadata', {}).get('slug')}")
            
            # SPECIAL CHECK: If this is Knowledge Fragments, print summary by type
            if e_type == "knowledge_fragment":
                competitor_count = sum(1 for e in entities if e.get("metadata", {}).get("type") == "competitor")
                fact_count = sum(1 for e in entities if e.get("metadata", {}).get("type") == "fact")
                print(f"\n   📊 Knowledge Fragment Summary:")
                print(f"      - Competitors: {competitor_count}")
                print(f"      - Facts: {fact_count}")
                print(f"      - Total: {len(entities)}")
                        
        except Exception as e:
            print(f"❌ Error dumping {e_type}: {e}")

def dump_chromadb():
    print("\n--- 🧠 DUMPING VECTORS (CHROMADB) ---")
    
    try:
        # Use the Persistent Client to read the actual disk DB
        client = chromadb.PersistentClient(path="data/chroma_db")
        
        collections = client.list_collections()
        
        if not collections:
            print("⚠️  No Chroma collections found on disk.")
            return

        for col in collections:
            print(f"🔎 Scanning Collection: {col.name}...")
            data = col.get()
            
            if not data['ids']:
                print(f"   (Empty Collection)")
                continue
                
            filename = f"{OUTPUT_DIR}/vector_{col.name}.csv"
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["ID", "Snippet", "Metadata"])
                
                for i, doc_id in enumerate(data['ids']):
                    content = data['documents'][i] if data['documents'] else ""
                    meta = data['metadatas'][i] if data['metadatas'] else {}
                    snippet = content[:100].replace("\n", " ") + "..." if content else "N/A"
                    writer.writerow([doc_id, snippet, json.dumps(meta)])
            
            print(f"✅ Exported {len(data['ids'])} vectors to {filename}")

    except Exception as e:
        print(f"❌ Error exporting Chroma: {e}")

if __name__ == "__main__":
    print("🚀 STARTING SYSTEM AUDIT...\n")
    setup_dirs()
    dump_entities()
    dump_chromadb()
    print("\n✨ Audit Complete. Check the 'data_dumps' folder.")