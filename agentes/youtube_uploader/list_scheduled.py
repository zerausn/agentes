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
    
    scheduled = []
    
    next_page_token = None
    while True:
        playlist_request = youtube.playlistItems().list(
            part="status,snippet",
            playlistId=uploads_playlist_id,
            maxResults=50,
            pageToken=next_page_token
        )
        playlist_response = playlist_request.execute()
        
        video_ids = [item['snippet']['resourceId']['videoId'] for item in playlist_response.get("items", [])]
        
        videos_request = youtube.videos().list(
            part="status,snippet",
            id=",".join(video_ids)
        )
        videos_response = videos_request.execute()
        
        for video in videos_response.get("items", []):
            status = video.get('status', {})
            snippet = video.get('snippet', {})
            publish_at = status.get('publishAt')
            
            if publish_at:
                scheduled.append({
                    "id": video['id'],
                    "title": snippet.get('title'),
                    "publishAt": publish_at,
                    "privacy": status.get('privacyStatus')
                })
                    
        next_page_token = playlist_response.get("nextPageToken")
        if not next_page_token:
            break

    print(f"\nSe encontraron {len(scheduled)} videos con fecha de publicación programada:")
    for s in sorted(scheduled, key=lambda x: x['publishAt']):
        print(f"- [{s['publishAt']}] {s['title']} (Privacidad: {s['privacy']})")

if __name__ == "__main__":
    main()
