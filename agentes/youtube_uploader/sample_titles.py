import os
import json
import logging
from pathlib import Path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

BASE_DIR = Path(r"C:\Users\ZN-\Documents\Antigravity\agentes\agentes\youtube_uploader")
CREDENTIALS_DIR = BASE_DIR / 'credentials'
SCOPES = ['https://www.googleapis.com/auth/youtube.upload', 'https://www.googleapis.com/auth/youtube.readonly']

def get_authenticated_service():
    client_files = sorted([f for f in os.listdir(CREDENTIALS_DIR) if f.startswith('client_secret') and f.endswith('.json')])
    client_file = client_files[0]
    client_secret_path = os.path.join(CREDENTIALS_DIR, client_file)
    creds_cache_file = os.path.join(CREDENTIALS_DIR, f'token_0.json')
    creds = Credentials.from_authorized_user_file(creds_cache_file, SCOPES)
    return build('youtube', 'v3', credentials=creds)

def main():
    youtube = get_authenticated_service()
    channels_response = youtube.channels().list(mine=True, part="contentDetails").execute()
    uploads_playlist_id = channels_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    
    playlist_request = youtube.playlistItems().list(part="snippet", playlistId=uploads_playlist_id, maxResults=20)
    playlist_response = playlist_request.execute()
    
    print("Muestra de los últimos 20 videos en YouTube:")
    for item in playlist_response.get("items", []):
        print(f"- {item['snippet']['title']}")

if __name__ == "__main__":
    main()
