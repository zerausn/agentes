import os
import json
import logging
import shutil
from pathlib import Path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

BASE_DIR = Path(__file__).resolve().parent
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
    try:
        # 1. Obtener el ID de la lista de reproducción "uploads" del canal
        channels_response = youtube.channels().list(
            mine=True,
            part="contentDetails"
        ).execute()
        
        if not channels_response.get("items"):
            logging.error("No se encontró el canal.")
            return []
            
        uploads_playlist_id = channels_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        logging.info(f"Obteniendo videos de la lista de reproducción: {uploads_playlist_id}")

        # 2. Iterar por todos los videos de esa lista
        next_page_token = None
        while True:
            playlist_request = youtube.playlistItems().list(
                part="snippet",
                playlistId=uploads_playlist_id,
                maxResults=50,
                pageToken=next_page_token
            )
            playlist_response = playlist_request.execute()
            
            for item in playlist_response.get("items", []):
                videos.append({
                    "id": item["snippet"]["resourceId"]["videoId"],
                    "title": item["snippet"]["title"]
                })
            
            next_page_token = playlist_response.get("nextPageToken")
            if not next_page_token:
                break
                
    except Exception as e:
        logging.error(f"Error fetching videos from playlist: {e}")
        
    return videos

def main():
    youtube = get_authenticated_service()
    if not youtube:
        return

    logging.info("Buscando videos en el canal de YouTube...")
    yt_videos = fetch_all_channel_videos(youtube)
    logging.info(f"Se encontraron {len(yt_videos)} videos en YouTube.")
    
    def normalize(s):
        return s.replace("_", "").replace(" ", "").replace("-", "").lower().strip()

    # Extraer todos los stems que aparecen en los títulos de YouTube
    yt_stems = set()
    for v in yt_videos:
        title = v['title']
        import re
        match = re.search(r'\((.*?)\)', title)
        if match:
            yt_stems.add(match.group(1).strip())
        
        # También agregar el título completo normalizado
        yt_stems.add(title.strip())

    norm_yt_stems = {normalize(s) for s in yt_stems}

    unified_folder = r"C:\Users\ZN-\Documents\ADM\Carpeta 1"
    exclude_folder = os.path.join(unified_folder, "videos_excluidos_ya_en_youtube")
    os.makedirs(exclude_folder, exist_ok=True)

    moved_count = 0
    local_files = [f for f in os.listdir(unified_folder) if os.path.isfile(os.path.join(unified_folder, f))]
    
    for filename in local_files:
        stem = Path(filename).stem
        norm_local = normalize(stem)
        
        if norm_local in norm_yt_stems:
            local_path = os.path.join(unified_folder, filename)
            dest_path = os.path.join(exclude_folder, filename)
            logging.info(f"🚀 Moviendo duplicado encontrado en YouTube: {filename}")
            try:
                shutil.move(local_path, dest_path)
                moved_count += 1
            except Exception as e:
                logging.error(f"Error moviendo {filename}: {e}")

    logging.info(f"Proceso finalizado. Se movieron {moved_count} archivos a: {exclude_folder}")
    
    # Actualizar JSON si existe
    if os.path.exists(JSON_DB):
        with open(JSON_DB, 'r', encoding='utf-8') as f:
            local_videos = json.load(f)
        
        updated = False
        for v in local_videos:
            base_name = os.path.basename(v['path'])
            norm_v = normalize(Path(base_name).stem)
            
            if norm_v in norm_yt_stems:
                if not v.get('uploaded'):
                    v['uploaded'] = True
                    updated = True
                # Actualizar ruta si se movió
                new_path = os.path.join(exclude_folder, base_name)
                if os.path.exists(new_path) and v['path'] != new_path:
                    v['path'] = new_path
                    updated = True
        
        if updated:
            with open(JSON_DB, 'w', encoding='utf-8') as f:
                json.dump(local_videos, f, indent=4, ensure_ascii=False)
            logging.info("scanned_videos.json actualizado con las nuevas ubicaciones.")

if __name__ == "__main__":
    main()
