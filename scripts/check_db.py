import sqlite3, json

# Connect
conn = sqlite3.connect('backend/data/apex.db')
c = conn.cursor()

print("\n--- 📍 ANCHORS (Sample) ---")
for r in c.execute("SELECT name, metadata FROM entities WHERE entity_type='anchor_location' LIMIT 3"):
    data = json.loads(r[1])
    print(f"🏠 {r[0]} | {data.get('address', 'No Address')}")

print("\n--- 💡 INTEL (Sample) ---")
for r in c.execute("SELECT name, metadata FROM entities WHERE entity_type='knowledge_fragment' LIMIT 3"):
    data = json.loads(r[1])
    print(f"🧠 [{data.get('type', 'unknown').upper()}] {r[0]}")
    print(f"   Snippet: {data.get('snippet', '')[:100]}...")