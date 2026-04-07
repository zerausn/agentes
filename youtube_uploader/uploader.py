import os
import shutil
import json
import time
import httplib2
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload

# Rutas absolutas para ejecución desde cualquier directorio
BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "uploader.log"
JSON_DB = BASE_DIR / 'scanned_videos.json'
CREDENTIALS_DIR = BASE_DIR / 'credentials'
CONFIG_FILE = BASE_DIR / 'config.json'
QUOTA_STATUS_FILE = BASE_DIR / 'quota_status.json'
SCOPES = ['https://www.googleapis.com/auth/youtube.upload', 'https://www.googleapis.com/auth/youtube.readonly']
STOP_FILE = BASE_DIR / 'STOP'
CACHE_FILE = BASE_DIR / 'yt_schedule_cache.json'
CACHE_EXPIRY_SECONDS = 3600  # 1 hora

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

config = load_config()

def get_next_publish_date(videos, video_type='video', yt_scheduled_dates=None):
    """
    Busca el primer hueco disponible para el tipo dado (short o video).
    yt_scheduled_dates: un mapping fecha -> {"videos": N, "shorts": N}
    """
    if yt_scheduled_dates is None:
        yt_scheduled_dates = {}

    tz_offset = config.get('scheduling', {}).get('colombia_time_offset', -5)
    target_hour = config.get('scheduling', {}).get('publish_hour', 17)
    target_minute = config.get('scheduling', {}).get('publish_minute', 45)
    colombia_tz = timezone(timedelta(hours=tz_offset))
    
    # Empezar a buscar desde mañana (7 de abril en este contexto)
    now_utc = datetime.now(timezone.utc)
    now_col = now_utc.astimezone(colombia_tz)
    base_date = now_col + timedelta(days=1)
    
    # Limitar búsqueda a 2 años por seguridad
    for i in range(730):
        check_date = base_date + timedelta(days=i)
        date_str = check_date.strftime("%Y-%m-%d")
        
        # Combinar datos de YouTube y datos locales (scanned_videos.json)
        local_counts = {"videos": 0, "shorts": 0}
        for v in videos:
            if v.get('uploaded') and v.get('publishAt'):
                v_date = v['publishAt'].split('T')[0]
                if v_date == date_str:
                    if v.get('type') == 'short': local_counts["shorts"] += 1
                    else: local_counts["videos"] += 1
        
        # Sumar los de YouTube recogidos en la auditoría externa si se pasan
        yt_counts = yt_scheduled_dates.get(date_str, {"videos": 0, "shorts": 0})
        
        total_v = local_counts["videos"] + yt_counts["videos"]
        total_s = local_counts["shorts"] + yt_counts["shorts"]
        
        if video_type == 'short' and total_s == 0:
            return check_date.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0).astimezone(timezone.utc)
        elif video_type == 'video' and total_v == 0:
            return check_date.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0).astimezone(timezone.utc)
            
    return base_date.astimezone(timezone.utc) # Fallback

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
            error_content = json.loads(e.content.decode('utf-8'))
            reason = error_content['error']['errors'][0]['reason']
            
            if e.resp.status in [403] and reason in ['quotaExceeded', 'rateLimitExceeded']:
                return "QUOTA_EXCEEDED"
            
            if e.resp.status == 400 and reason == 'uploadLimitExceeded':
                logging.warning(f"⚠️ Límite de subidas de YouTube alcanzado para esta cuenta/canal.")
                return "LIMIT_EXCEEDED"

            logging.error(f"Error HTTP ({e.resp.status}): {reason} - {e}")
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
    
    with open(QUOTA_STATUS_FILE, 'w', encoding='utf-8') as f:
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

def fetch_yt_schedule(youtube, force_refresh=False):
    """Obtiene el mapeo de fechas programadas actualmente en YouTube con caché."""
    if not force_refresh and CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                cache = json.load(f)
                cache_time = datetime.fromisoformat(cache.get("timestamp", "2000-01-01"))
                if (datetime.now() - cache_time).total_seconds() < CACHE_EXPIRY_SECONDS:
                    logging.info("Usando caché del calendario de YouTube (ahorro de cuota).")
                    return cache.get("schedule", {})
        except Exception as e:
            logging.warning(f"Error leyendo caché: {e}")

    logging.info("Auditando calendario completo de YouTube (esto consume cuota de lectura)...")
    schedule = {}
    try:
        channels_response = youtube.channels().list(mine=True, part="contentDetails").execute()
        uploads_playlist_id = channels_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        
        next_page_token = None
        while True:
            playlist_request = youtube.playlistItems().list(
                part="snippet",
                playlistId=uploads_playlist_id,
                maxResults=50,
                pageToken=next_page_token
            )
            playlist_response = playlist_request.execute()
            video_ids = [item['snippet']['resourceId']['videoId'] for item in playlist_response.get("items", [])]
            
            videos_response = youtube.videos().list(
                part="status,contentDetails",
                id=",".join(video_ids)
            )
            videos_response = videos_response.execute()
            
            for video in videos_response.get("items", []):
                status = video.get('status', {})
                content = video.get('contentDetails', {})
                publish_at = status.get('publishAt')
                
                if publish_at:
                    date_str = publish_at.split("T")[0]
                    if date_str not in schedule: schedule[date_str] = {"videos": 0, "shorts": 0}
                    
                    dur_str = content.get('duration', '')
                    m = re.search(r'(\d+)M', dur_str); s = re.search(r'(\d+)S', dur_str); h = re.search(r'(\d+)H', dur_str)
                    total_sec = (int(h.group(1)) if h else 0)*3600 + (int(m.group(1)) if m else 0)*60 + (int(s.group(1)) if s else 0)
                    
                    if total_sec <= 180: # Alineado con la nueva regla de 3 min
                        schedule[date_str]["shorts"] += 1
                    else:
                        schedule[date_str]["videos"] += 1
            
            next_page_token = playlist_response.get("nextPageToken")
            if not next_page_token: break
        
        # Guardar en caché
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump({"timestamp": datetime.now().isoformat(), "schedule": schedule}, f, indent=4)
            
    except Exception as e:
        logging.error(f"Error en auditoría previa: {e}")
    return schedule

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
    while current_idx < len(client_files) and not is_client_available(client_files[current_idx]):
        current_idx += 1

    if current_idx >= len(client_files):
        logging.warning("Todas las llaves están agotadas por hoy según quota_status.json.")
        return

    youtube = get_authenticated_service(
        os.path.join(CREDENTIALS_DIR, client_files[current_idx]), 
        os.path.join(CREDENTIALS_DIR, f'token_{current_idx}.json')
    )

    logging.info("Auditando calendario de YouTube antes de comenzar...")
    yt_schedule = fetch_yt_schedule(youtube)

    # Priorizar los videos más pesados primero (Heaviest first)
    pendientes.sort(key=lambda x: x.get('size_mb', 0), reverse=True)

    for video in pendientes:
        if STOP_FILE.exists():
            logging.warning("🛑 Archivo STOP detectado. Deteniendo.")
            break

        if not os.path.exists(video['path']):
            logging.warning(f"Archivo no encontrado: {video['path']}")
            continue

        v_type = video.get('type', 'video')
        date_str = video.get('creation_date', 'N/A').split(' ')[0]
        title = f"PW | {date_str} | ({Path(video['filename']).stem})"
        desc = config.get('default_metadata', {}).get('description', '')
        
        # Ajustar título según tipo
        prefix = "[SHORT] " if v_type == 'short' else ""
        # user no pidió prefijo pero ayuda a depurar. Lo omitiré para ser fiel al formato anterior.
        # title = f"{prefix}{title}" 

        next_date = get_next_publish_date(videos, v_type, yt_schedule)
        
        while True:
            result = upload_video(youtube, video['path'], title, desc, next_date)

            if result in ["QUOTA_EXCEEDED", "LIMIT_EXCEEDED"]:
                reason_msg = "Cuota agotada" if result == "QUOTA_EXCEEDED" else "Límite de subidas de YouTube"
                logging.info(f"🔄 {reason_msg} en llave {current_idx}. Rotando...")
                
                update_quota_status(client_files[current_idx]) # Marcar como usada por hoy
                current_idx += 1
                
                if current_idx < len(client_files):
                    youtube = get_authenticated_service(
                        os.path.join(CREDENTIALS_DIR, client_files[current_idx]), 
                        os.path.join(CREDENTIALS_DIR, f'token_{current_idx}.json')
                    )
                    continue # Reintentar el MISMO video con la nueva llave
                else:
                    logging.error("❌ Se agotaron todas las llaves o el canal está bloqueado por hoy.")
                    return
            
            elif result:
                video['uploaded'] = True
                video['youtube_id'] = result
                video['publishAt'] = next_date.isoformat().replace('+00:00', 'Z')
                
                # Actualizar el mapa local de schedule para el siguiente video en este loop
                d_str = next_date.strftime("%Y-%m-%d")
                if d_str not in yt_schedule: yt_schedule[d_str] = {"videos": 0, "shorts": 0}
                if v_type == 'short': yt_schedule[d_str]["shorts"] += 1
                else: yt_schedule[d_str]["videos"] += 1

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
