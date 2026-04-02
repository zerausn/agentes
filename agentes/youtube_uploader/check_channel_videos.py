import os
import json
import logging
import shutil
from pathlib import Path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

BASE_DIR = Path(__file__).parent.absolute()
LOG_FILE = BASE_DIR / "check_videos.log"
JSON_DB = BASE_DIR / 'scanned_videos.json'
CREDENTIALS_DIR = BASE_DIR / 'credentials'
SCOPES = ['https://www.googleapis.com/auth/youtube.upload', 'https://www.googleapis.com/auth/youtube.readonly']

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler(LOG_FILE)]
)

def get_authenticated_service():
    client_files = sorted([f for f in os.listdir(CREDENTIALS_DIR) if f.startswith('client_secret') and f.endswith('.json')])
    if not client_files:
        logging.error("No hay client_secret_X.json disponibles.")
        return None
        
    client_file = client_files[0] # Usar el primer secreto
    client_secret_path = os.path.join(CREDENTIALS_DIR, client_file)
    creds_cache_file = os.path.join(CREDENTIALS_DIR, f'token_0.json')
    
    creds = None
    if os.path.exists(creds_cache_file):
        creds = Credentials.from_authorized_user_file(creds_cache_file, SCOPES)
        
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                logging.warning("Fallo el refresco, solicitando nueva autenticación...")
                flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
                creds = flow.run_local_server(port=0)
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
            creds = flow.run_local_server(port=0)
            
        with open(creds_cache_file, 'w') as token:
            token.write(creds.to_json())
            
    return build('youtube', 'v3', credentials=creds)

def fetch_all_channel_videos(youtube):
    videos = []
    request = youtube.search().list(
        part="snippet",
        forMine=True,
        type="video",
        maxResults=50
    )
    while request is not None:
        try:
            response = request.execute()
            for item in response.get("items", []):
                videos.append({
                    "id": item["id"]["videoId"],
                    "title": item["snippet"]["title"]
                })
            request = youtube.search().list_next(request, response)
        except Exception as e:
            logging.error(f"Error fetching videos: {e}")
            break
    return videos

def main():
    youtube = get_authenticated_service()
    if not youtube:
        return

    logging.info("Buscando videos en el canal de YouTube...")
    yt_videos = fetch_all_channel_videos(youtube)
    logging.info(f"Se encontraron {len(yt_videos)} videos en YouTube (incluyendo borradores y privados).")
    
    if not os.path.exists(JSON_DB):
        logging.error("scanned_videos.json no existe.")
        return
        
    with open(JSON_DB, 'r', encoding='utf-8') as f:
        local_videos = json.load(f)

    yt_stems = set()
    for v in yt_videos:
        title = v['title']
        if "(" in title and ")" in title:
            stem = title.split("(")[-1].split(")")[0]
            yt_stems.add(stem)

    changes_made = 0
    for v in local_videos:
        if not v.get('uploaded', False):
            stem = Path(v['filename']).stem
            if stem in yt_stems:
                logging.info(f"✅ Video en YouTube, actualizando local: {v['filename']}")
                v['uploaded'] = True
                
                if os.path.exists(v['path']):
                    try:
                        success_folder = os.path.join(os.path.dirname(v['path']), "videos subidos exitosamente")
                        os.makedirs(success_folder, exist_ok=True)
                        new_path = os.path.join(success_folder, os.path.basename(v['path']))
                        shutil.move(v['path'], new_path)
                        v['path'] = new_path
                    except Exception as e:
                        logging.error(f"Error moviendo {v['path']}: {e}")
                
                changes_made += 1

    if changes_made > 0:
        with open(JSON_DB, 'w', encoding='utf-8') as f:
            json.dump(local_videos, f, indent=4, ensure_ascii=False)
        logging.info(f"Se marcaron y actualizaron {changes_made} videos en scanned_videos.json.")
    else:
        logging.info("Ningún video pendiente nuevo se encontró subido a YouTube.")

if __name__ == "__main__":
    main()
