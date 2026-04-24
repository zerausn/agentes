import json
import logging
import time
import argparse
import re
from pathlib import Path
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.errors import HttpError

# Import normalized logic from video_helpers
from video_helpers import normalize_video_stem, SLICE_CLEAN_RE, MANAGED_STEM_RE

# Configuration
BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "fix_titles.log"
CREDENTIALS_DIR = BASE_DIR / "credentials"
SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.readonly",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)

def get_authenticated_service(client_secret_file, current_idx):
    import subprocess
    client_secret_file = Path(client_secret_file)
    
    # Intentar varios nombres de tokens existentes para evitar pedir login
    token_candidates = [
        CREDENTIALS_DIR / f"token_fix_titles_{current_idx}.json",
        CREDENTIALS_DIR / f"token_{current_idx}.json",
        CREDENTIALS_DIR / f"token_playlist_{current_idx}.json"
    ]
    
    creds = None
    token_file = token_candidates[0] # Por defecto guardaremos en el nuevo si no existe ninguno
    
    for candidate in token_candidates:
        if candidate.exists():
            creds = Credentials.from_authorized_user_file(str(candidate), SCOPES)
            token_file = candidate
            logging.info(f"Reutilizando token existente: {candidate.name}")
            break
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                logging.warning(f"Error refrescando token: {e}. Forzando re-login.")
                creds = None
        
        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_file), SCOPES)
            # Imprimir URL y tratar de abrir Edge como pidió el usuario
            auth_url, _ = flow.authorization_url(prompt='consent')
            logging.info(f"POR FAVOR, AUTORIZA AQUÍ: {auth_url}")
            
            # Intentar abrir en Edge (Linux/Parrot usa microsoft-edge o microsoft-edge-stable)
            try:
                logging.info("Intentando abrir Microsoft Edge...")
                subprocess.Popen(["microsoft-edge", auth_url], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
            except Exception:
                try:
                    subprocess.Popen(["microsoft-edge-stable", auth_url], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
                except Exception:
                    logging.info("No se pudo abrir Edge automáticamente. Abre la URL de arriba manualmente.")
            
            creds = flow.run_local_server(port=0, open_browser=False)
            token_file.write_text(creds.to_json(), encoding="utf-8")
    
    return build("youtube", "v3", credentials=creds)

def clean_youtube_title(title):
    """
    Lógica mejorada para limpiar un título existente en YouTube sin perder etiquetas.
    """
    # 1. Limpiar el prefijo si existe
    clean_base = title.replace("PW | ", "").strip()
    
    # 2. Eliminar la fecha del formato antiguo si existe: YYYY-MM-DD |
    clean_base = re.sub(r"\d{4}-\d{2}-\d{2}[ |]*", "", clean_base).strip()
    
    # 3. Quitar paréntesis exteriores si el título los tiene (ej. (nombre) #Teaser)
    # pero queremos quedarnos con todo el contenido.
    # Usamos un truco: quitamos los paréntesis abiertos y cerrados y luego normalizamos.
    clean_base = clean_base.replace("(", " ").replace(")", " ").strip()
    
    # 4. Limpiar usando la lógica centralizada (slice 60, ig_compat, etc)
    # normalize_video_stem ya maneja múltiples espacios y limpieza de slice_60
    clean_name = normalize_video_stem(clean_base)
    
    # 5. Reconstruir el título asegurando que no quede vacío
    if not clean_name:
        return title # Si por alguna razón queda vacío, no tocar
        
    return f"PW | ({clean_name})"

def main():
    parser = argparse.ArgumentParser(description="Fix existing YouTube video titles.")
    parser.add_argument("--execute", action="store_true", help="Apply changes to YouTube.")
    parser.add_argument("--limit", type=int, default=100, help="Max videos to process.")
    args = parser.parse_args()

    client_files = sorted(Path(CREDENTIALS_DIR).glob("client_secret*.json"))
    if not client_files:
        logging.error("No se encontraron client_secret_X.json en credentials/")
        return
        
    current_key_idx = 0
    executed_count = 0
    skipped_count = 0
    
    while current_key_idx < len(client_files) and executed_count < args.limit:
        client_secret = client_files[current_key_idx]
        
        logging.info(f"--- Usando Llave {current_key_idx + 1}: {client_secret.name} ---")
        
        try:
            youtube = get_authenticated_service(client_secret, current_key_idx)
            
            # Obtener lista de subidas
            channels_res = youtube.channels().list(mine=True, part="contentDetails").execute()
            uploads_id = channels_res["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
            
            next_page_token = None
            finished = False
            
            while not finished and executed_count < args.limit:
                items_res = youtube.playlistItems().list(
                    part="snippet",
                    playlistId=uploads_id,
                    maxResults=50,
                    pageToken=next_page_token
                ).execute()
                
                for item in items_res.get("items", []):
                    video_id = item["snippet"]["resourceId"]["videoId"]
                    old_title = item["snippet"]["title"]
                    
                    # Verificar si el título necesita limpieza
                    # Necesita limpieza si: 
                    # - Contiene 'slice' o '60s'
                    # - Tiene una fecha YYYY-MM-DD
                    # - No sigue el formato exacto 'PW | (nombre)' sin fecha
                    
                    new_title = clean_youtube_title(old_title)
                    
                    if old_title != new_title:
                        logging.info(f"ID: {video_id} | ORIGINAL: '{old_title}' -> NUEVO: '{new_title}'")
                        
                        if args.execute:
                            try:
                                youtube.videos().update(
                                    part="snippet",
                                    body={
                                        "id": video_id,
                                        "snippet": {
                                            "title": new_title,
                                            "categoryId": "24" # Valor por defecto seguro (Entertainment)
                                        }
                                    }
                                ).execute()
                                logging.info(f"  [OK] Titulo actualizado.")
                                time.sleep(1) # Pequeña pausa para evitar rate limits
                            except HttpError as e:
                                if "quotaExceeded" in str(e):
                                    logging.warning("Cuota agotada al actualizar. Rotando llave...")
                                    current_key_idx += 1
                                    break # Forzamos salida del loop interno
                                raise e
                        
                        executed_count += 1
                        if executed_count >= args.limit:
                            finished = True
                            break
                    else:
                        skipped_count += 1

                next_page_token = items_res.get("nextPageToken")
                if not next_page_token:
                    finished = True
            
            if finished:
                break # Salimos del loop de llaves si terminamos
                
        except Exception as e:
            if "quotaExceeded" in str(e):
                current_key_idx += 1
                continue
            logging.error(f"Error inesperado: {e}")
            current_key_idx += 1
            time.sleep(2)
            
    logging.info(f"Proceso finalizado. Videos detectados/corregidos: {executed_count}, Omitidos: {skipped_count}")

if __name__ == "__main__":
    main()
