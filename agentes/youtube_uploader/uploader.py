import os
import shutil
import json
import time
import httplib2
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("uploader.log"), logging.StreamHandler()]
)

# Configuración
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
JSON_DB = 'scanned_videos.json'
CREDENTIALS_DIR = 'credentials'
CONFIG_FILE = 'config.json'
QUOTA_STATUS_FILE = 'quota_status.json'

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

config = load_config()

def get_next_publish_date(videos):
    """Calcula la próxima fecha de publicación basándose en los videos ya programados."""
    max_date = None
    for v in videos:
        if v.get('uploaded') and v.get('publishAt'):
            try:
                dt_str = v['publishAt'].replace('Z', '+00:00')
                dt_obj = datetime.fromisoformat(dt_str)
                if max_date is None or dt_obj > max_date:
                    max_date = dt_obj
            except ValueError:
                pass

    now_utc = datetime.now(timezone.utc)
    tz_offset = config.get('scheduling', {}).get('colombia_time_offset', -5)
    target_hour = config.get('scheduling', {}).get('publish_hour', 17)
    target_minute = config.get('scheduling', {}).get('publish_minute', 45)
    
    colombia_tz = timezone(timedelta(hours=tz_offset))
    now_col = now_utc.astimezone(colombia_tz)
    
    if max_date is None or max_date < now_utc:
        tomorrow_col = now_col + timedelta(days=1)
        next_pub_col = tomorrow_col.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        return next_pub_col.astimezone(timezone.utc)
    else:
        max_col = max_date.astimezone(colombia_tz)
        next_pub_col = max_col + timedelta(days=1)
        next_pub_col = next_pub_col.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        return next_pub_col.astimezone(timezone.utc)

def get_authenticated_service(client_secret_file, creds_cache_file):
    creds = None
    if os.path.exists(creds_cache_file):
        creds = Credentials.from_authorized_user_file(creds_cache_file, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(creds_cache_file, 'w') as token:
            token.write(creds.to_json())
    return build('youtube', 'v3', credentials=creds)

def upload_video(youtube, file_path, title, description, publish_at_dt):
    """Sube un video de forma fraccionada con soporte para resumir y reglas de audiencia."""
    
    publish_at_str = publish_at_dt.isoformat().replace('+00:00', 'Z')
    metadata = config.get('default_metadata', {})
    audience = config.get('audience_settings', {"selfDeclaredMadeForKids": False})

    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': metadata.get('tags', []),
            'categoryId': metadata.get('categoryId', '24')
        },
        'status': {
            'privacyStatus': metadata.get('privacyStatus', 'private'),
            'publishAt': publish_at_str,
            'selfDeclaredMadeForKids': audience.get('selfDeclaredMadeForKids', False),
            'hasAlteredContentDisclosure': audience.get('hasAlteredContentDisclosure', False),
            'license': metadata.get('license', 'youtube')
        }
    }

    media = MediaFileUpload(file_path, chunksize=1024*1024*10, resumable=True)
    insert_request = youtube.videos().insert(
        part=','.join(body.keys()),
        body=body,
        media_body=media
    )

    logging.info(f"Iniciando subida: {title} ({file_path})")
    logging.info(f"Programado para: {publish_at_str} (MadeForKids: {body['status']['selfDeclaredMadeForKids']})")
    
    response = None
    retry_count = 0
    max_retries = 5

    while response is None:
        try:
            status, response = insert_request.next_chunk()
            if status:
                logging.info(f"Progreso: {int(status.progress() * 100)}%")
                retry_count = 0 # Reset retries on successful chunk
        except (httplib2.HttpLib2Error, ConnectionError, TimeoutError) as e:
            retry_count += 1
            if retry_count > max_retries:
                logging.error(f"Fallo crítico tras {max_retries} reintentos de red: {e}")
                return None
            wait_time = retry_count * 5
            logging.warning(f"Error de red ({e}). Reintentando en {wait_time}s... (Intento {retry_count}/{max_retries})")
            time.sleep(wait_time)
        except HttpError as e:
            if e.resp.status in [403]:
                error_content = json.loads(e.content.decode('utf-8'))
                reason = error_content['error']['errors'][0]['reason']
                if reason in ['quotaExceeded', 'rateLimitExceeded']:
                    return "QUOTA_EXCEEDED"
            logging.error(f"Error HTTP: {e}")
            return None
        except Exception as e:
            logging.error(f"Error inesperado: {e}")
            return None

    logging.info(f"✅ Éxito! Video ID: {response['id']}")
    return response['id']

def update_quota_status(client_name):
    status = {}
    if os.path.exists(QUOTA_STATUS_FILE):
        with open(QUOTA_STATUS_FILE, 'r') as f:
            status = json.load(f)
    
    status[client_name] = {
        "last_quota_exceeded": datetime.now().isoformat(),
        "date": datetime.now().strftime("%Y-%m-%d")
    }
    
    with open(QUOTA_STATUS_FILE, 'w') as f:
        json.dump(status, f, indent=4)

def is_client_available(client_name):
    if not os.path.exists(QUOTA_STATUS_FILE):
        return True
    with open(QUOTA_STATUS_FILE, 'r') as f:
        status = json.load(f)
    
    entry = status.get(client_name)
    if entry and entry.get('date') == datetime.now().strftime("%Y-%m-%d"):
        return False
    return True

def main():
    if not os.path.exists(CREDENTIALS_DIR):
        os.makedirs(CREDENTIALS_DIR)
        logging.error(f"Crea la carpeta '{CREDENTIALS_DIR}' y pon los client_secret_X.json ahí.")
        return

    client_files = sorted([f for f in os.listdir(CREDENTIALS_DIR) if f.startswith('client_secret') and f.endswith('.json')])
    if not client_files:
        logging.error("No hay client_secret_X.json en credentials/")
        return

    if not os.path.exists(JSON_DB):
        logging.error("Falta scanned_videos.json. Ejecuta video_scanner.py primero.")
        return
        
    with open(JSON_DB, 'r', encoding='utf-8') as f:
        videos = json.load(f)

    pendientes = [v for v in videos if not v.get('uploaded', False)]
    logging.info(f"Videos pendientes: {len(pendientes)}")

    if not pendientes: return

    current_idx = 0
    # Buscar el primer cliente con cuota disponible
    while current_idx < len(client_files) and not is_client_available(client_files[current_idx]):
        current_idx += 1

    if current_idx >= len(client_files):
        logging.warning("Todas las llaves están agotadas por hoy según quota_status.json.")
        return

    youtube = get_authenticated_service(
        os.path.join(CREDENTIALS_DIR, client_files[current_idx]), 
        os.path.join(CREDENTIALS_DIR, f'token_{current_idx}.json')
    )

    for video in pendientes:
        if not os.path.exists(video['path']):
            logging.warning(f"Archivo no encontrado: {video['path']}")
            continue

        # Extraer fecha de grabación para el título
        date_str = video.get('creation_date', 'N/A').split(' ')[0]
        # Formato aprobado: Performatic Writings | 2026-03-10 | (20260310_191216)
        title = f"Performatic Writings | {date_str} | ({Path(video['filename']).stem})"
        
        desc = config.get('default_metadata', {}).get('description', '')
        desc_file = Path(video['path']).with_suffix('.txt')
        if desc_file.exists():
            with open(desc_file, 'r', encoding='utf-8') as df:
                desc = df.read().strip()
                logging.info(f"Usando descripción personalizada de {desc_file.name}")

        next_date = get_next_publish_date(videos)
        
        while True:
            result = upload_video(youtube, video['path'], title, desc, next_date)

            if result == "QUOTA_EXCEEDED":
                client_name = client_files[current_idx]
                logging.warning(f"Cuota agotada en {client_name}. Registrando y rotando...")
                update_quota_status(client_name)
                current_idx += 1
                if current_idx < len(client_files):
                    youtube = get_authenticated_service(
                        os.path.join(CREDENTIALS_DIR, client_files[current_idx]), 
                        os.path.join(CREDENTIALS_DIR, f'token_{current_idx}.json')
                    )
                    continue
                else:
                    logging.error("Se agotaron todas las llaves.")
                    return
            
            elif result:
                video['uploaded'] = True
                video['youtube_id'] = result
                video['publishAt'] = next_date.isoformat().replace('+00:00', 'Z')
                
                try:
                    success_folder = os.path.join(os.path.dirname(video['path']), "videos subidos exitosamente")
                    os.makedirs(success_folder, exist_ok=True)
                    new_path = os.path.join(success_folder, os.path.basename(video['path']))
                    shutil.move(video['path'], new_path)
                    video['path'] = new_path
                except Exception as e:
                    logging.error(f"Error moviendo archivo: {e}")
                
                with open(JSON_DB, 'w', encoding='utf-8') as f:
                    json.dump(videos, f, indent=4, ensure_ascii=False)
                break
            else:
                break

if __name__ == "__main__":
    main()
