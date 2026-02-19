import sys
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build

# Resolve project root (parent of scripts/)
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Candidate paths for GSC credentials (first existing wins)
CANDIDATE_PATHS = [
    PROJECT_ROOT / "backend" / "secrets" / "gcp-sercret.json",
    PROJECT_ROOT / "backend" / "secrets" / "gcp_service_account.json",
    PROJECT_ROOT / "backend" / "data" / "secrets" / "gcp_service_account.json",
]

SERVICE_ACCOUNT_FILE = None
for p in CANDIDATE_PATHS:
    if p.is_file():
        SERVICE_ACCOUNT_FILE = str(p)
        break

if not SERVICE_ACCOUNT_FILE:
    print("Error: GSC credentials file not found. Tried:")
    for p in CANDIDATE_PATHS:
        print(f"  - {p}")
    sys.exit(1)

print(f"Using credentials: {SERVICE_ACCOUNT_FILE}")
SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]

creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)

# 2. Build the service
service = build('searchconsole', 'v1', credentials=creds)

# 3. List all verified properties
try:
    site_list = service.sites().list().execute()
    verified_sites = site_list.get('siteEntry', [])

    if not verified_sites:
        print("Success: Connected to Google, but no sites found. check Search Console permissions.")
    else:
        print(f"Connected! You have access to {len(verified_sites)} properties:")
        for site in verified_sites:
            print(f"- Site: {site['siteUrl']} (Permission: {site['permissionLevel']})")
except Exception as e:
    print(f"Connection Failed: {e}")