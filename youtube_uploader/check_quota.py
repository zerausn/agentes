import json
import logging
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

BASE_DIR = Path(__file__).resolve().parent
CREDENTIALS_DIR = BASE_DIR / "credentials"
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]

logging.basicConfig(level=logging.INFO)

def check_quota(token_index):
    client_secret_path = CREDENTIALS_DIR / f"client_secret_{token_index + 1}.json"
    token_path = CREDENTIALS_DIR / f"token_{token_index}.json"
    
    if not token_path.exists():
        print(f"Token {token_index} not found.")
        return

    try:
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
        
        youtube = build("youtube", "v3", credentials=creds)
        # Simple call to check quota
        youtube.channels().list(mine=True, part="id").execute()
        print(f"Token {token_index}: OK (Has Quota)")
    except Exception as e:
        print(f"Token {token_index}: Failed - {e}")

for i in range(4):
    check_quota(i)
