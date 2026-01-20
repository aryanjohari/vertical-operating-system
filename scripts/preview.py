import csv
import os

# Config
INPUT_FILE = "data_dumps/entities_page_draft.csv"
OUTPUT_FILE = "preview.html"

def generate_preview():
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Error: {INPUT_FILE} not found. Run system_dump.py first.")
        return

    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                # Find the 'Ready' page
                if row.get("status") == "ready_to_publish":
                    raw_content = row.get("content", "")
                    
                    # CLEANING: Remove CSV/JSON escaping to make it real HTML
                    # 1. Replace literal "\n" with actual newlines
                    clean_content = raw_content.replace("\\n", "\n")
                    # 2. Replace escaped quotes
                    clean_content = clean_content.replace('\\"', '"')
                    
                    # Wrap in a basic HTML shell for viewing
                    full_html = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>Apex Preview: {row.get('name')}</title>
                        <style>
                            body {{ font-family: sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; line-height: 1.6; }}
                            img {{ max-width: 100%; height: auto; }}
                        </style>
                    </head>
                    <body>
                        <div style="background:#f0f0f0; padding:10px; margin-bottom:20px; border-bottom:2px solid #ccc;">
                            <strong>Slug:</strong> {row.get('slug')}<br>
                            <strong>Tool:</strong> {row.get('tool_type')} (Active: {row.get('has_tool')})
                        </div>
                        {clean_content}
                    </body>
                    </html>
                    """
                    
                    with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
                        out.write(full_html)
                        
                    print(f"✅ Success! Open '{OUTPUT_FILE}' in your browser to see the page.")
                    return

        print("⚠️ No 'ready_to_publish' pages found in the CSV.")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    generate_preview()