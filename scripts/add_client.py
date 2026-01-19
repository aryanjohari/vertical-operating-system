#!/usr/bin/env python3
"""
Helper script to add WordPress credentials for a client.
This allows manual setup of client credentials in the database.
"""
import sys
import os
from getpass import getpass

# Add parent directory to path so we can import backend modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.core.memory import memory

def main():
    print("=" * 60)
    print("Add WordPress Client Credentials")
    print("=" * 60)
    print()
    
    # Prompt for user_id
    user_id = input("User ID (email): ").strip()
    if not user_id:
        print("❌ Error: User ID cannot be empty.")
        return
    
    # Prompt for WordPress URL
    wp_url = input("WordPress API URL (e.g., https://site.com/wp-json/wp/v2/posts): ").strip()
    if not wp_url:
        print("❌ Error: WordPress URL cannot be empty.")
        return
    
    # Prompt for WordPress username
    wp_user = input("WordPress Username: ").strip()
    if not wp_user:
        print("❌ Error: WordPress username cannot be empty.")
        return
    
    # Prompt for password (use getpass to hide input)
    wp_pass = getpass("WordPress Application Password: ").strip()
    if not wp_pass:
        print("❌ Error: WordPress password cannot be empty.")
        return
    
    print()
    print("Saving credentials...")
    
    # Save to database
    success = memory.save_client_secrets(user_id, wp_url, wp_user, wp_pass)
    
    if success:
        print(f"✅ Successfully saved credentials for user: {user_id}")
    else:
        print(f"❌ Failed to save credentials. Check logs for details.")

if __name__ == "__main__":
    main()
