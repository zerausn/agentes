import os
import json
import logging
import re
from datetime import datetime, timedelta
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
    if not client_files: return None
    client_file = client_files[0]
    client_secret_path = os.path.join(CREDENTIALS_DIR, client_file)
    creds_cache_file = os.path.join(CREDENTIALS_DIR, f'token_0.json')
    creds = Credentials.from_authorized_user_file(creds_cache_file, SCOPES)
    return build('youtube', 'v3', credentials=creds)

def parse_duration(duration_str):
    """Convierte duración ISO 8601 (PT#H#M#S) a segundos."""
    hours = re.search(r'(\d+)H', duration_str)
    minutes = re.search(r'(\d+)M', duration_str)
    seconds = re.search(r'(\d+)S', duration_str)
    
    h = int(hours.group(1)) if hours else 0
    m = int(minutes.group(1)) if minutes else 0
    s = int(seconds.group(1)) if seconds else 0
    
    return h * 3600 + m * 60 + s

def main():
    youtube = get_authenticated_service()
    if not youtube: return
    channels_response = youtube.channels().list(mine=True, part="contentDetails").execute()
    uploads_playlist_id = channels_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    
    schedule_map = {} # date_str -> {"videos": 0, "shorts": 0}
    draft_videos = []
    draft_shorts = []
    
    next_page_token = None
    print("Analizando canal y duraciones... esto puede tardar...")
    
    while True:
        playlist_request = youtube.playlistItems().list(
            part="snippet",
            playlistId=uploads_playlist_id,
            maxResults=50,
            pageToken=next_page_token
        )
        playlist_response = playlist_request.execute()
        
        video_ids = [item['snippet']['resourceId']['videoId'] for item in playlist_response.get("items", [])]
        
        videos_request = youtube.videos().list(
            part="status,snippet,contentDetails",
            id=",".join(video_ids)
        )
        videos_response = videos_request.execute()
        
        for video in videos_response.get("items", []):
            status = video.get('status', {})
            content = video.get('contentDetails', {})
            snippet = video.get('snippet', {})
            
            duration_sec = parse_duration(content.get('duration', ''))
            is_short = duration_sec < 60
            privacy = status.get('privacyStatus')
            publish_at = status.get('publishAt')
            
            video_info = {
                "id": video['id'],
                "title": snippet.get('title'),
                "is_short": is_short
            }

            if publish_at:
                date_str = publish_at.split("T")[0]
                if date_str not in schedule_map:
                    schedule_map[date_str] = {"videos": 0, "shorts": 0}
                
                if is_short:
                    schedule_map[date_str]["shorts"] += 1
                else:
                    schedule_map[date_str]["videos"] += 1
            elif privacy == 'private':
                if is_short:
                    draft_shorts.append(video_info)
                else:
                    draft_videos.append(video_info)
                    
        next_page_token = playlist_response.get("nextPageToken")
        if not next_page_token:
            break

    print("\n--- ANALISIS DE CALENDARIO ---")
    today = datetime.now()
    print(f"Borradores detectados: {len(draft_videos)} Videos, {len(draft_shorts)} Shorts")
    
    print("\nCalendario de los próximos 30 días:")
    gaps = []
    for i in range(30):
        current_date = today + timedelta(days=i)
        date_str = current_date.strftime("%Y-%m-%d")
        counts = schedule_map.get(date_str, {"videos": 0, "shorts": 0})
        
        missing_v = counts["videos"] == 0
        missing_s = counts["shorts"] == 0
        
        if missing_v or missing_s:
            gaps.append((date_str, missing_v, missing_s))
            status_str = ""
            if missing_v: status_str += "[FALTA VIDEO] "
            if missing_s: status_str += "[FALTA SHORT] "
            print(f"{date_str}: V:{counts['videos']} S:{counts['shorts']} -> {status_str}")
        else:
            print(f"{date_str}: V:{counts['videos']} S:{counts['shorts']} -> [OK]")

if __name__ == "__main__":
    main()
