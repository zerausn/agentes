import os
import json
import time
import requests
import logging
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

# Configuraciones de entorno
BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "meta_uploader.log"

if load_dotenv:
    load_dotenv(BASE_DIR / ".env")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)

# TODO: Reemplazar con tokens ambientales locales
PAGE_ACCESS_TOKEN = os.environ.get("META_PAGE_TOKEN", "")
IG_USER_ID = os.environ.get("META_IG_USER_ID", "")
FB_PAGE_ID = os.environ.get("META_FB_PAGE_ID", "")

def check_ig_publish_limit():
    """Consulta la API de Meta para asegurar que no excedamos los 100 Reels/día en IG."""
    if not IG_USER_ID or not PAGE_ACCESS_TOKEN:
        return True # Fallback

    url = f"https://graph.facebook.com/v19.0/{IG_USER_ID}/content_publishing_limit"
    params = {
        "fields": "config,quota_usage",
        "access_token": PAGE_ACCESS_TOKEN
    }
    try:
        req = requests.get(url, params=params)
        data = req.json()
        if 'data' in data and len(data['data']) > 0:
            usage = data['data'][0]['quota_usage']
            logging.info(f"Uso actual de IG Limit: {usage}/100")
            if usage >= 99:
                return False
    except Exception as e:
        logging.error(f"Error consultando límite IG: {e}")
    return True

def upload_ig_reel(video_url, caption):
    """
    Subida asíncrona de Reels a Instagram.
    Fase 1: Subir contenedor y recibir IG Container ID.
    """
    url = f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media"
    payload = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": PAGE_ACCESS_TOKEN
    }
    
    logging.info("Enviando orden a Meta para crear contenedor IG Reel...")
    req = requests.post(url, data=payload)
    result = req.json()
    
    if "id" in result:
        return result["id"]
    else:
        logging.error(f"Fallo en Fase 1 IG Reel: {result}")
        return None

def wait_for_ig_container(creation_id):
    """
    Fase 1.5: Hacer polling del estado del contenedor hasta que diga FINISHED.
    """
    url = f"https://graph.facebook.com/v19.0/{creation_id}"
    params = {
        "fields": "status_code",
        "access_token": PAGE_ACCESS_TOKEN
    }
    
    max_retries = 30
    delay = 10
    for _ in range(max_retries):
        try:
            req = requests.get(url, params=params)
            data = req.json()
            status = data.get("status_code", "")
            logging.info(f"Container IG {creation_id} status: {status}")
            
            if status == "FINISHED":
                return True
            if status in ["ERROR", "EXPIRED"]:
                logging.error(f"Container IG {creation_id} falló con estado: {status}")
                return False
        except Exception as e:
            logging.error(f"Error consultando contenedor IG {creation_id}: {e}")
            
        time.sleep(delay)
        
    logging.error(f"Container IG {creation_id} timeout excedido.")
    return False

def upload_fb_reel(video_path, caption):
    """
    Subida asíncrona de Reels a la página de FB (3 Fases).
    """
    if not FB_PAGE_ID or not PAGE_ACCESS_TOKEN:
        logging.error("Faltan credenciales FB_PAGE_ID o Token")
        return None
        
    logging.info("Iniciando Phase 1 de FB Reel (START)...")
    url_start = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/video_reels"
    payload_start = {"upload_phase": "start", "access_token": PAGE_ACCESS_TOKEN}
    
    res_start = requests.post(url_start, data=payload_start).json()
    video_id = res_start.get("video_id")
    if not video_id:
        logging.error(f"Error Phase 1 FB Reel: {res_start}")
        return None
        
    logging.info(f"Phase 1 FB Reel exitoso. Video ID: {video_id}")
    
    logging.info("Iniciando Phase 2 FB Reel (UPLOAD) a rupload.facebook.com...")
    rupload_url = f"https://rupload.facebook.com/video-upload/v19.0/{video_id}"
    headers = {
        "Authorization": f"OAuth {PAGE_ACCESS_TOKEN}",
        "offset": "0", "file_offset": "0",
        "Content-Type": "application/octet-stream"
    }
    
    try:
        with open(video_path, "rb") as f:
            res_upload = requests.post(rupload_url, headers=headers, data=f)
        if res_upload.status_code != 200:
            logging.error(f"Error Phase 2 FB Reel ({res_upload.status_code}): {res_upload.text}")
            return None
    except Exception as e:
        logging.error(f"Expresión leyendo binario de video: {e}")
        return None
        
    logging.info("Phase 2 FB Reel exitoso.")
    
    logging.info("Iniciando Phase 3 FB Reel (FINISH)...")
    url_finish = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/video_reels"
    payload_finish = {
        "upload_phase": "finish", "video_id": video_id,
        "video_state": "PUBLISHED", "description": caption,
        "access_token": PAGE_ACCESS_TOKEN
    }
    res_finish = requests.post(url_finish, data=payload_finish).json()
    if res_finish.get("success"):
        logging.info(f"✅ ¡Éxito! FB Reel publicado. Video ID: {video_id}")
        return video_id
    else:
        logging.error(f"Error Phase 3 FB Reel: {res_finish}")
        return None

def publish_ig_container(creation_id):
    """
    Fase 2: Publicar el contenedor una vez terminado de procesar en Meta.
    """
    url = f"https://graph.facebook.com/v19.0/{IG_USER_ID}/media_publish"
    payload = {
        "creation_id": creation_id,
        "access_token": PAGE_ACCESS_TOKEN
    }
    logging.info(f"Publicando Reel desde el contenedor {creation_id}...")
    req = requests.post(url, data=payload)
    result = req.json()
    if "id" in result:
        logging.info(f"✅ ¡Éxito! IG Reel publicado. ID: {result['id']}")
        return result['id']
    else:
        logging.error(f"Fallo en Fase 2 IG Reel: {result}")
        return None

def main():
    logging.info("INICIANDO META UPLOADER AGENT...")
    if not PAGE_ACCESS_TOKEN:
        logging.error("Faltan las credenciales. Configura .env o exporta las variables de entorno.")
        return

    # Comprobar Circuit Breaker (Límite 100/día IG)
    if not check_ig_publish_limit():
        logging.error("🔴 Límite diario de IG alcanzado (100). Parando.")
        return

    # Aquí iría el bucle de procesamiento y subidas en base al meta_calendar.json
    
if __name__ == "__main__":
    main()
