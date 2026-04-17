import logging
import shutil
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from video_helpers import EXCLUDED_DIR_NAME
from video_helpers import infer_library_root_from_path
from video_helpers import load_json_file
from video_helpers import save_json_file

BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "check_videos.log"
JSON_DB = BASE_DIR / "scanned_videos.json"
CREDENTIALS_DIR = BASE_DIR / "credentials"
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(LOG_FILE)],
)


def get_authenticated_service():
    client_files = sorted(path.name for path in CREDENTIALS_DIR.glob("client_secret*.json"))
    if not client_files:
        logging.error("No hay client_secret_X.json disponibles.")
        return None

    client_secret_path = CREDENTIALS_DIR / client_files[0]
    creds_cache_file = CREDENTIALS_DIR / "token_0.json"
    creds = None
    if creds_cache_file.exists():
        creds = Credentials.from_authorized_user_file(str(creds_cache_file), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                logging.warning("Fallo el refresco, solicitando nueva autenticacion...")
                flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), SCOPES)
                creds = flow.run_local_server(port=0)
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), SCOPES)
            creds = flow.run_local_server(port=0)

        creds_cache_file.write_text(creds.to_json(), encoding="utf-8")

    return build("youtube", "v3", credentials=creds)


def fetch_all_channel_videos(youtube):
    videos = []
    try:
        channels_response = youtube.channels().list(mine=True, part="contentDetails").execute()
        if not channels_response.get("items"):
            logging.error("No se encontro el canal.")
            return []

        uploads_playlist_id = channels_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        logging.info("Obteniendo videos de la lista de reproduccion: %s", uploads_playlist_id)

        next_page_token = None
        while True:
            playlist_response = youtube.playlistItems().list(
                part="snippet",
                playlistId=uploads_playlist_id,
                maxResults=50,
                pageToken=next_page_token,
            ).execute()

            for item in playlist_response.get("items", []):
                videos.append(
                    {
                        "id": item["snippet"]["resourceId"]["videoId"],
                        "title": item["snippet"]["title"],
                    }
                )

            next_page_token = playlist_response.get("nextPageToken")
            if not next_page_token:
                break
    except Exception as exc:
        logging.error("Error consultando videos del canal: %s", exc)
    return videos


def normalize(value):
    return (value or "").replace("_", "").replace(" ", "").replace("-", "").lower().strip()


def build_channel_title_index(yt_videos):
    import re

    stems = set()
    for video in yt_videos:
        title = video["title"]
        match = re.search(r"\((.*?)\)", title)
        if match:
            stems.add(match.group(1).strip())
        stems.add(title.strip())
    return {normalize(stem) for stem in stems}


def move_duplicates(local_videos, channel_index):
    moved_count = 0
    updated = False

    for video in local_videos:
        if video.get("uploaded"):
            continue

        file_path = Path(video["path"])
        if not file_path.exists():
            continue

        stem = normalize(file_path.stem)
        if stem not in channel_index:
            continue

        root_dir = infer_library_root_from_path(file_path)
        exclude_folder = root_dir / EXCLUDED_DIR_NAME
        exclude_folder.mkdir(exist_ok=True)
        destination = exclude_folder / file_path.name

        logging.info("Moviendo duplicado ya presente en YouTube: %s", file_path.name)
        try:
            shutil.move(str(file_path), str(destination))
        except Exception as exc:
            logging.error("Error moviendo %s: %s", file_path.name, exc)
            continue

        video["uploaded"] = True
        video["path"] = str(destination)
        moved_count += 1
        updated = True

    return moved_count, updated


def main():
    if not JSON_DB.exists():
        logging.error("No se encontro scanned_videos.json. Ejecuta video_scanner.py primero.")
        return

    youtube = get_authenticated_service()
    if not youtube:
        return

    logging.info("Buscando videos en el canal de YouTube...")
    yt_videos = fetch_all_channel_videos(youtube)
    logging.info("Se encontraron %s videos en YouTube.", len(yt_videos))

    local_videos = load_json_file(JSON_DB, [])
    channel_index = build_channel_title_index(yt_videos)
    moved_count, updated = move_duplicates(local_videos, channel_index)

    logging.info("Proceso finalizado. Se movieron %s archivos.", moved_count)
    if updated:
        save_json_file(JSON_DB, local_videos)
        logging.info("scanned_videos.json actualizado con las nuevas ubicaciones.")


if __name__ == "__main__":
    main()
