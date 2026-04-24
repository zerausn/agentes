import logging
import sys
import os
import time
import subprocess
from pathlib import Path
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.errors import HttpError

# Configuración de rutas y logs
BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "manage_playlist.log"
CREDENTIALS_DIR = BASE_DIR / "credentials"
# Scopes requeridos para gestionar playlists
SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.readonly",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)

def get_authenticated_service(client_secret_file, token_file):
    creds = None
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                logging.warning(f"Error refrescando token: {e}. Forzando re-login.")
                creds = None
        
        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_file), SCOPES)
            # Imprimimos la URL y la abrimos en Edge según instrucción del usuario
            auth_url, _ = flow.authorization_url(prompt='consent')
            logging.info(f"URL de autorización: {auth_url}")
            logging.info("Abriendo URL en Microsoft Edge...")
            try:
                subprocess.run(["start", "msedge", f'"{auth_url}"'], shell=True)
            except Exception as e:
                logging.error(f"No se pudo abrir Edge: {e}. Abre la URL manualmente.")
            
            creds = flow.run_local_server(port=0)
            token_file.write_text(creds.to_json(), encoding="utf-8")
    
    return build("youtube", "v3", credentials=creds)

def find_or_create_playlist(youtube, title, description):
    logging.info(f"Buscando playlist: '{title}'...")
    next_page_token = None
    while True:
        try:
            response = youtube.playlists().list(
                part="snippet,status",
                mine=True,
                maxResults=50,
                pageToken=next_page_token
            ).execute()
            
            for item in response.get("items", []):
                if item["snippet"]["title"] == title:
                    playlist_id = item["id"]
                    logging.info(f"Playlist encontrada: {playlist_id}")
                    
                    # Verificamos si la privacidad es la correcta
                    if item["status"]["privacyStatus"] != "public":
                        logging.info("La playlist no es pública. Actualizando a 'public'...")
                        item["status"]["privacyStatus"] = "public"
                        youtube.playlists().update(
                            part="status,snippet",
                            body={
                                "id": playlist_id,
                                "snippet": item["snippet"],
                                "status": {"privacyStatus": "public"}
                            }
                        ).execute()
                    return playlist_id
            
            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break
        except HttpError as e:
            if any(reason in str(e).lower() for reason in ["quotaexceeded", "ratelimitexceeded", "exhausted"]):
                return "QUOTA_EXCEEDED"
            raise e
            
    logging.info(f"Playlist no encontrada. Creándola...")
    body = {
        "snippet": {
            "title": title,
            "description": description
        },
        "status": {
            "privacyStatus": "public"
        }
    }
    try:
        response = youtube.playlists().insert(part="snippet,status", body=body).execute()
        logging.info(f"Playlist creada con ID: {response['id']}")
        return response["id"]
    except HttpError as e:
        if any(reason in str(e).lower() for reason in ["quotaexceeded", "ratelimitexceeded", "exhausted"]):
            return "QUOTA_EXCEEDED"
        raise e

def fetch_all_eligible_videos(youtube):
    logging.info("Escaneando videos del canal (Públicos + Programados)...")
    eligible_videos = []
    
    # Obtenemos el ID de la lista de subidass (Uploads)
    channels_res = youtube.channels().list(mine=True, part="contentDetails").execute()
    uploads_id = channels_res["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    
    next_page_token = None
    while True:
        # Obtenemos items de la playlist de subidas
        items_res = youtube.playlistItems().list(
            part="snippet,status",
            playlistId=uploads_id,
            maxResults=50,
            pageToken=next_page_token
        ).execute()
        
        video_ids = [item["snippet"]["resourceId"]["videoId"] for item in items_res.get("items", [])]
        if not video_ids:
            break
            
        # Consultamos el estado real del video (privacyStatus, publishAt)
        videos_res = youtube.videos().list(
            part="status,snippet",
            id=",".join(video_ids)
        ).execute()
        
        for video in videos_res.get("items", []):
            status = video["status"]
            privacy = status["privacyStatus"]
            publish_at = status.get("publishAt")
            
            # REGLAS DEL USUARIO (Stricto Sensu):
            # - SI Públicos (privacy == 'public')
            # - SI Programados (privacy == 'private' Y publishAt != None)
            # - NO Privados (privacy == 'private' Y publishAt == None)
            # - NO Ocultos (privacy == 'unlisted')
            
            is_public = (privacy == "public")
            is_scheduled = (privacy == "private" and publish_at is not None)
            
            if is_public or is_scheduled:
                eligible_videos.append({
                    "id": video["id"],
                    "title": video["snippet"]["title"]
                })
        
        next_page_token = items_res.get("nextPageToken")
        if not next_page_token:
            break
            
    logging.info(f"Se encontraron {len(eligible_videos)} videos elegibles.")
    return eligible_videos

def get_playlist_items(youtube, playlist_id):
    logging.info("Obteniendo videos actuales de la playlist...")
    existing_ids = set()
    next_page_token = None
    while True:
        response = youtube.playlistItems().list(
            part="snippet",
            playlistId=playlist_id,
            maxResults=50,
            pageToken=next_page_token
        ).execute()
        
        for item in response.get("items", []):
            existing_ids.add(item["snippet"]["resourceId"]["videoId"])
            
        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break
    return existing_ids

def sync_playlist(youtube, playlist_id, eligible_videos):
    existing_ids = get_playlist_items(youtube, playlist_id)
    added_count = 0
    total_eligible = len(eligible_videos)
    
    logging.info(f"Sincronizando {total_eligible} videos posibles...")
    for i, video in enumerate(eligible_videos, 1):
        if video["id"] in existing_ids:
            continue
            
        try:
            youtube.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {
                            "kind": "youtube#video",
                            "videoId": video["id"]
                        }
                    }
                }
            ).execute()
            added_count += 1
            if i % 10 == 0:
                logging.info(f"Progreso: {i}/{total_eligible} | Aadidos: {added_count}")
        except HttpError as e:
            if any(reason in str(e).lower() for reason in ["quotaexceeded", "ratelimitexceeded", "exhausted"]):
                logging.error("CUOTA AGOTADA durante inserción.")
                return "QUOTA_EXCEEDED"
            logging.error(f"Error aadiendo video {video['id']}: {e}")
            
    logging.info(f"Sincronizacin terminada satisfactoriamente. Aadidos: {added_count}")
    return "OK"

def main():
    client_files = sorted(Path(CREDENTIALS_DIR).glob("client_secret*.json"))
    if not client_files:
        logging.error("No se encontraron client_secret_X.json")
        return
        
    current_key_idx = 0
    
    while current_key_idx < len(client_files):
        client_secret = client_files[current_key_idx]
        token_file = CREDENTIALS_DIR / f"token_playlist_{current_key_idx}.json"
        
        logging.info(f"--- Intentando con Llave {current_key_idx + 1}: {client_secret.name} ---")
        
        try:
            youtube = get_authenticated_service(client_secret, token_file)
            
            playlist_title = "#PW #Siguenos en #FB e #IG"
            playlist_desc = "Siguenos en nuestras redes sociales: linktr.ee/performaticwritingscali"
            
            # 1. Buscar o crear playlist
            playlist_id = find_or_create_playlist(youtube, playlist_title, playlist_desc)
            if playlist_id == "QUOTA_EXCEEDED":
                logging.warning("Cuota agotada al buscar/crear playlist. Rotando llave...")
                current_key_idx += 1
                continue
            
            # 2. Obtener videos elegibles
            try:
                eligible_videos = fetch_all_eligible_videos(youtube)
            except HttpError as e:
                if "quotaExceeded" in str(e):
                    logging.warning("Cuota agotada al listar videos. Rotando llave...")
                    current_key_idx += 1
                    continue
                raise e
            
            # 3. Sincronizar
            result = sync_playlist(youtube, playlist_id, eligible_videos)
            if result == "QUOTA_EXCEEDED":
                logging.warning("Cuota agotada durante la sincronizacin. Rotando llave...")
                current_key_idx += 1
                continue
                
            logging.info("### PROCESO COMPLETADO EXITOSAMENTE ###")
            break
            
        except Exception as e:
            logging.error(f"Error inesperado: {e}")
            current_key_idx += 1
            time.sleep(2)
            
    if current_key_idx >= len(client_files):
        logging.error("Se agotaron todas las llaves disponibles.")

if __name__ == "__main__":
    main()
