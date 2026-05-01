import os
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

BASE_DIR = Path(__file__).resolve().parent
CREDENTIALS_DIR = BASE_DIR / 'credentials'
SCOPES = ['https://www.googleapis.com/auth/youtube.upload', 'https://www.googleapis.com/auth/youtube.readonly']

def get_authenticated_service():
    creds_cache_file = os.path.join(CREDENTIALS_DIR, f'token_0.json')
    creds = Credentials.from_authorized_user_file(creds_cache_file, SCOPES)
    return build('youtube', 'v3', credentials=creds)

def main():
    youtube = get_authenticated_service()
    
    # 1. Identificar los 2 borradores (simplificado)
    channels_response = youtube.channels().list(mine=True, part="contentDetails").execute()
    uploads_playlist_id = channels_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    
    drafts = []
    next_page_token = None
    while len(drafts) < 2:
        res = youtube.playlistItems().list(part="status,snippet", playlistId=uploads_playlist_id, maxResults=50, pageToken=next_page_token).execute()
        for item in res.get("items", []):
            if item['status']['privacyStatus'] == 'private' and not item['status'].get('publishAt'):
                drafts.append(item['snippet']['resourceId']['videoId'])
        next_page_token = res.get("nextPageToken")
        if not next_page_token: break

    print(f"Borradores encontrados para programar: {drafts}")
    
    dates = [
        datetime.now(timezone.utc).replace(hour=22, minute=45, second=0, microsecond=0) + timedelta(days=1), # April 7
        datetime.now(timezone.utc).replace(hour=22, minute=45, second=0, microsecond=0) + timedelta(days=2)  # April 8
    ]

    for i, vid_id in enumerate(drafts[:2]):
        publish_at = dates[i].isoformat().replace('+00:00', 'Z')
        print(f"Programando {vid_id} para {publish_at}...")
        try:
            youtube.videos().update(
                part="status",
                body={
                    "id": vid_id,
                    "status": {
                        "privacyStatus": "private",
                        "publishAt": publish_at
                    }
                }
            ).execute()
            print("✅ Exito!")
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
