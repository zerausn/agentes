"""
schedule_drafts.py
==================
Toma todos los videos en estado 'privado' (borradores programados o sin fecha)
del canal de YouTube y les asigna una fecha de publicación escalonada:
  - Un video por día
  - A las 17:45 hora Colombia (UTC-5)
  - Empezando desde mañana si no hay fecha previa, o desde el último video ya programado + 1 día.

REQUISITOS:
  - Haber autorizado credentials/token_0.json con scopes youtube.upload + youtube.readonly
  - pip install google-api-python-client google-auth-oauthlib
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

BASE_DIR = Path(__file__).parent.absolute()
CREDENTIALS_DIR = BASE_DIR / 'credentials'
SCOPES = [
    'https://www.googleapis.com/auth/youtube.upload',
    'https://www.googleapis.com/auth/youtube.readonly',
    'https://www.googleapis.com/auth/youtube.force-ssl'
]

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(BASE_DIR / 'schedule_drafts.log', encoding='utf-8')
    ]
)

COLOMBIA_UTC_OFFSET = -5
TARGET_HOUR = 17
TARGET_MINUTE = 45

def get_all_authenticated_services():
    """Retorna una lista de todos los servicios de YouTube autenticados disponibles."""
    client_files = sorted([f for f in os.listdir(CREDENTIALS_DIR) if f.startswith('client_secret') and f.endswith('.json')])
    services = []
    for idx, client_file in enumerate(client_files):
        creds_cache = CREDENTIALS_DIR / f'token_{idx}.json'
        creds = None
        if creds_cache.exists():
            creds = Credentials.from_authorized_user_file(str(creds_cache), SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    with open(creds_cache, 'w') as f:
                        f.write(creds.to_json())
                except Exception:
                    pass
            else:
                logging.info(f"Abriendo navegador para autorizar {client_file}...")
                flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_DIR / client_file), SCOPES)
                creds = flow.run_local_server(port=0)
                with open(creds_cache, 'w') as f:
                    f.write(creds.to_json())
        if creds and creds.valid:
            services.append((client_file, build('youtube', 'v3', credentials=creds)))
    return services

class YouTubeServicePool:
    def __init__(self, services):
        self.services = services  # Lista de (nombre, servicio)
        self.current_idx = 0

    def get_service(self):
        if self.current_idx >= len(self.services):
            return None, None
        return self.services[self.current_idx][1], self.services[self.current_idx][0]

    def rotate(self):
        self.current_idx += 1
        if self.current_idx >= len(self.services):
            return False
        logging.info(f"🔄 Rotando a credencial: {self.services[self.current_idx][0]}")
        return True

    def execute(self, func):
        """Ejecuta una función que recibe el objeto 'youtube' y rota si hay quotaExceeded."""
        while True:
            youtube, name = self.get_service()
            if not youtube:
                raise Exception("Todas las credenciales agotadas.")
            try:
                return func(youtube)
            except Exception as e:
                if 'quotaExceeded' in str(e):
                    logging.warning(f"⚠️ Cuota agotada en {name}. Rotando...")
                    if self.rotate():
                        continue
                raise e

def fetch_all_private_videos(pool):
    """Obtiene todos los videos del canal usando el pool para rotar si es necesario."""
    video_ids = []
    
    def get_search_results(youtube):
        ids = []
        req = youtube.search().list(
            part="id",
            forMine=True,
            type="video",
            maxResults=50,
            order="date"
        )
        while req:
            resp = req.execute()
            for item in resp.get('items', []):
                ids.append(item['id']['videoId'])
            req = youtube.search().list_next(req, resp)
        return ids

    try:
        video_ids = pool.execute(get_search_results)
    except Exception as e:
        logging.error(f"Error fatal en búsqueda: {e}")
        return []

    if not video_ids:
        logging.warning("No se encontraron vídeos (canal vacío).")
        return []

    logging.info(f"IDs encontrados: {len(video_ids)}. Obteniendo detalles...")

    videos = []
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i+50]
        def get_details(youtube):
            return youtube.videos().list(part="snippet,status", id=','.join(batch)).execute()
        
        try:
            resp = pool.execute(get_details)
            for item in resp.get('items', []):
                if item.get('status', {}).get('privacyStatus') in ['private', 'unlisted']:
                    videos.append(item)
        except Exception as e:
            logging.error(f"Error obteniendo detalles del lote: {e}")

    return videos

def get_last_scheduled_date(videos_details):
    """Encuentra la última fecha de publicación programada entre todos los videos."""
    max_date = None
    for v in videos_details:
        publish_at = v.get('status', {}).get('publishAt')
        if publish_at:
            try:
                dt = datetime.fromisoformat(publish_at.replace('Z', '+00:00'))
                if max_date is None or dt > max_date:
                    max_date = dt
            except Exception:
                pass
    return max_date

def main():
    services = get_all_authenticated_services()
    if not services:
        logging.error("No hay credenciales disponibles.")
        return
    
    pool = YouTubeServicePool(services)

    logging.info("🚀 Iniciando proceso de programación de borradores...")
    videos = fetch_all_private_videos(pool)
    logging.info(f"Total de videos privados/borrador encontrados: {len(videos)}")

    if not videos:
        logging.info("No hay videos para procesar.")
        return

    # Separar los que ya tienen fecha de los que no
    with_date = [v for v in videos if v.get('status', {}).get('publishAt')]
    
    # IMPORTANTE: Solo tomamos como "Borradores" los que:
    # 1. No tienen fecha de publicación.
    # 2. Coinciden con nuestro patrón de título (ej: "Performatic Writings" o el formato de fecha "2025...")
    def is_our_draft(v):
        if v.get('status', {}).get('publishAt'): return False
        title = v.get('snippet', {}).get('title', '')
        # Patrón 1: Títulos creados por nuestro uploader
        if "Performatic Writings" in title: return True
        # Patrón 2: Títulos por defecto de archivos (ej: 20250310_191216.mp4)
        import re
        if re.search(r'\d{8}_\d{6}', title): return True
        return False

    without_date = [v for v in videos if is_our_draft(v)]
    intentional_private = [v for v in videos if not v.get('status', {}).get('publishAt') and not is_our_draft(v)]

    logging.info(f"  Programados: {len(with_date)}")
    logging.info(f"  Borradores (a programar): {len(without_date)}")
    logging.info(f"  Privados intencionales (ignorados): {len(intentional_private)}")

    # Calcular próxima fecha disponible
    colombia_tz = timezone(timedelta(hours=COLOMBIA_UTC_OFFSET))
    last_date = get_last_scheduled_date(with_date)

    if last_date:
        next_slot = last_date.astimezone(colombia_tz) + timedelta(days=1)
    else:
        next_slot = datetime.now(colombia_tz) + timedelta(days=1)

    next_slot = next_slot.replace(hour=TARGET_HOUR, minute=TARGET_MINUTE, second=0, microsecond=0)

    logging.info(f"📅 Iniciando desde: {next_slot.strftime('%Y-%m-%d %H:%M')} (Col)")

    scheduled_count = 0
    for video in without_date:
        vid_id = video['id']
        title = video.get('snippet', {}).get('title', 'Sin título')[:50]
        publish_str = next_slot.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

        def do_update(youtube):
            return youtube.videos().update(
                part="status",
                body={"id": vid_id, "status": {"privacyStatus": "private", "publishAt": publish_str}}
            ).execute()

        try:
            pool.execute(do_update)
            logging.info(f"  [OK] {title}... -> {publish_str}")
            scheduled_count += 1
            next_slot += timedelta(days=1)
            next_slot = next_slot.replace(hour=TARGET_HOUR, minute=TARGET_MINUTE, second=0, microsecond=0)
        except Exception as e:
            if 'uploadLimitExceeded' in str(e):
                logging.error(f"🛑 Límite de subidas del CANAL alcanzado. YouTube no permite programar más por hoy.")
                break
            logging.error(f"❌ Error en {vid_id}: {e}")

    logging.info(f"\nRESUMEN: {scheduled_count} videos programados.")
    if scheduled_count < len(without_date):
        logging.info(f"Quedaron {len(without_date) - scheduled_count} videos sin programar (posiblemente por límite del canal).")

if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()
