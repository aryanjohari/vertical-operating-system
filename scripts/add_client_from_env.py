#!/usr/bin/env python3
"""
Helper script to add WordPress credentials from .env file for a specific user.
Reads WP_URL, WP_USER, and WP_APP_PASSWORD from .env and saves to database.
"""
import sys
import os
from dotenv import load_dotenv

# Add parent directory to path so we can import backend modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables from .env
load_dotenv()

from backend.core.memory import memory

def main():
    # Get credentials from environment variables
    wp_url = os.getenv("WP_URL")
    wp_user = os.getenv("WP_USER")
    wp_password = os.getenv("WP_APP_PASSWORD")
    
    if not wp_url or not wp_user or not wp_password:
        print("❌ Error: Missing credentials in .env file.")
        print("   Required: WP_URL, WP_USER, WP_APP_PASSWORD")
        return
    
    # Use admin@admin.com as the user_id
    user_id = "admin@admin.com"
    
    print(f"Adding credentials for user: {user_id}")
    print(f"WordPress URL: {wp_url}")
    print(f"WordPress User: {wp_user}")
    print()
    
    # Save to database
    success = memory.save_client_secrets(user_id, wp_url, wp_user, wp_password)
    
    if success:
        print(f"✅ Successfully saved credentials for user: {user_id}")
    else:
        print(f"❌ Failed to save credentials. Check logs for details.")

if __name__ == "__main__":
    main()
