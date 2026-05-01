import os
import json
import logging
import re
from pathlib import Path
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

BASE_DIR = Path(__file__).resolve().parent
JSON_DB = BASE_DIR / 'scanned_videos.json'
CREDENTIALS_DIR = BASE_DIR / 'credentials'
SCOPES = ['https://www.googleapis.com/auth/youtube.upload', 'https://www.googleapis.com/auth/youtube.readonly']

def get_authenticated_service():
    creds_cache_file = os.path.join(CREDENTIALS_DIR, f'token_0.json')
    creds = Credentials.from_authorized_user_file(creds_cache_file, SCOPES)
    return build('youtube', 'v3', credentials=creds)

def main():
    if not os.path.exists(JSON_DB):
        print("No se encontró el JSON.")
        return

    with open(JSON_DB, 'r', encoding='utf-8') as f:
        videos = json.load(f)

    # Obtener los últimos 5 subidos (que tengan YouTube ID)
    last_uploaded = [v for v in videos if v.get('uploaded') and v.get('youtube_id')]
    last_uploaded = sorted(last_uploaded, key=lambda x: x.get('publishAt', ''), reverse=True)[:5]

    if not last_uploaded:
        print("No se han subido videos en esta sesión todavía.")
        return

    youtube = get_authenticated_service()
    ids = [v['youtube_id'] for v in last_uploaded]
    
    res = youtube.videos().list(part="status,contentDetails,snippet", id=",".join(ids)).execute()
    
    print("\n--- AUDIT DE LOTE (Últimos 5) ---")
    for video in res.get("items", []):
        title = video['snippet']['title']
        dur = video['contentDetails']['duration']
        privacy = video['status']['privacyStatus']
        scheduled = video['status'].get('publishAt', 'N/A')
        
        # Check if considered Short (Logic: <180s vertical)
        # Note: API doesn't show dimensions for privacy reasons sometimes, but let's see.
        print(f"ID: {video['id']}")
        print(f"Título: {title}")
        print(f"Duración YouTube: {dur}")
        print(f"Estado: {privacy} | Programado: {scheduled}")
        print("-" * 30)

if __name__ == "__main__":
    main()
