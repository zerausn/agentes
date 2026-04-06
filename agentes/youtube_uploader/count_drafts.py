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
    
    # 1. Obtener ID de lista de subidas
    channels_response = youtube.channels().list(mine=True, part="contentDetails").execute()
    uploads_playlist_id = channels_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    
    drafts = []
    private_with_date = []
    public = []
    unlisted = []
    
    next_page_token = None
    print("Auditando canal... esto puede tardar un momento...")
    
    while True:
        playlist_request = youtube.playlistItems().list(
            part="snippet,status",
            playlistId=uploads_playlist_id,
            maxResults=50,
            pageToken=next_page_token
        )
        playlist_response = playlist_request.execute()
        
        # Para cada item de la lista, necesitamos consultar el objeto 'video' para ver publishAt real
        video_ids = [item['snippet']['resourceId']['videoId'] for item in playlist_response.get("items", [])]
        
        videos_request = youtube.videos().list(
            part="status,snippet",
            id=",".join(video_ids)
        )
        videos_response = videos_request.execute()
        
        for video in videos_response.get("items", []):
            status = video.get('status', {})
            snippet = video.get('snippet', {})
            privacy = status.get('privacyStatus')
            publish_at = status.get('publishAt')
            title = snippet.get('title')
            
            info = {"id": video['id'], "title": title}
            
            if privacy == 'public':
                public.append(info)
            elif privacy == 'unlisted':
                unlisted.append(info)
            elif privacy == 'private':
                if publish_at:
                    private_with_date.append(info)
                else:
                    drafts.append(info)
                    
        next_page_token = playlist_response.get("nextPageToken")
        if not next_page_token:
            break

    print("\n--- REPORTE DE ESTADO ---")
    print(f"Total videos analizados: {len(public) + len(unlisted) + len(private_with_date) + len(drafts)}")
    print(f"Públicos: {len(public)}")
    print(f"Ocultos (Unlisted): {len(unlisted)}")
    print(f"Privados Programados (Tienen fecha): {len(private_with_date)}")
    print(f"Borradores Reales (Privados sin fecha): {len(drafts)}")
    
    print("\nPrimeros 10 borradores encontrados:")
    for d in drafts[:10]:
        print(f"- {d['title']}")

if __name__ == "__main__":
    main()
