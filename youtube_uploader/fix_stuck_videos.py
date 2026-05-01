"""
fix_stuck_videos.py - Recuperación de videos YouTube atascados en uploadStatus='uploaded'.

Flujo:
1. Consulta todos los videos del canal
2. Identifica los que tienen uploadStatus != 'processed'
3. Para videos atascados >24h: los elimina y los marca para re-subida
4. Para videos atascados <24h: solo reporta (YouTube puede estar procesando)

Requiere: google-api-python-client, google-auth-oauthlib
"""
import json
import logging
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

BASE_DIR = Path(__file__).resolve().parent
CREDENTIALS_DIR = BASE_DIR / "credentials"
JSON_DB = BASE_DIR / "scanned_videos.json"
SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(BASE_DIR / "fix_stuck_videos.log", encoding="utf-8"),
    ],
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
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), SCOPES)
            creds = flow.run_local_server(port=0)
        creds_cache_file.write_text(creds.to_json(), encoding="utf-8")

    return build("youtube", "v3", credentials=creds)


def fetch_stuck_videos(youtube):
    """Obtiene todos los videos del canal y filtra los que no están 'processed'."""
    channels_response = youtube.channels().list(mine=True, part="contentDetails").execute()
    uploads_playlist_id = channels_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    all_video_ids = []
    next_page_token = None
    while True:
        playlist_response = youtube.playlistItems().list(
            part="snippet",
            playlistId=uploads_playlist_id,
            maxResults=50,
            pageToken=next_page_token,
        ).execute()

        for item in playlist_response.get("items", []):
            all_video_ids.append({
                "id": item["snippet"]["resourceId"]["videoId"],
                "title": item["snippet"]["title"],
                "publishedAt": item["snippet"].get("publishedAt", ""),
            })

        next_page_token = playlist_response.get("nextPageToken")
        if not next_page_token:
            break

    logging.info("Total de videos en el canal: %s", len(all_video_ids))

    stuck = []
    for i in range(0, len(all_video_ids), 50):
        batch = all_video_ids[i:i + 50]
        ids_str = ",".join(v["id"] for v in batch)

        videos_response = youtube.videos().list(
            part="status,processingDetails,snippet",
            id=ids_str,
        ).execute()

        title_map = {v["id"]: v for v in batch}

        for video in videos_response.get("items", []):
            vid = video["id"]
            status = video.get("status", {})
            upload_status = status.get("uploadStatus", "unknown")

            if upload_status != "processed":
                published_at = title_map.get(vid, {}).get("publishedAt", "")
                stuck.append({
                    "id": vid,
                    "title": video.get("snippet", {}).get("title", "?"),
                    "uploadStatus": upload_status,
                    "publishedAt": published_at,
                    "privacyStatus": status.get("privacyStatus", "unknown"),
                    "publishAt": status.get("publishAt", ""),
                    "failureReason": status.get("failureReason", ""),
                })

    return stuck


def load_local_db():
    if not JSON_DB.exists():
        return []
    return json.loads(JSON_DB.read_text(encoding="utf-8"))


def save_local_db(videos):
    JSON_DB.write_text(json.dumps(videos, indent=2, ensure_ascii=False), encoding="utf-8")


def find_local_video_by_youtube_id(local_videos, yt_id):
    for v in local_videos:
        if v.get("youtube_id") == yt_id:
            return v
    return None


def delete_and_mark_for_reupload(youtube, video_info, local_videos):
    """Elimina el video de YouTube y lo marca para re-subida en scanned_videos.json."""
    vid = video_info["id"]
    title = video_info["title"]

    try:
        youtube.videos().delete(id=vid).execute()
        logging.info("ELIMINADO de YouTube: [%s] %s", vid, title)
    except HttpError as exc:
        logging.error("Error eliminando video %s: %s", vid, exc)
        return False

    # Buscar en la base local y desmarcar
    local = find_local_video_by_youtube_id(local_videos, vid)
    if local:
        local["uploaded"] = False
        local.pop("youtube_id", None)
        local.pop("publishAt", None)
        logging.info("Video %s desmarcado en scanned_videos.json para re-subida.", title)
    else:
        logging.warning("Video %s no encontrado en scanned_videos.json (puede requerir re-scan).", title)

    return True


def main():
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        logging.info("MODO DRY-RUN: No se eliminará ni modificará nada.")

    youtube = get_authenticated_service()
    if not youtube:
        return

    logging.info("Buscando videos atascados...")
    stuck = fetch_stuck_videos(youtube)

    if not stuck:
        logging.info("No hay videos atascados. Todo procesado correctamente.")
        return

    logging.info("Se encontraron %s videos atascados.", len(stuck))
    local_videos = load_local_db()
    now = datetime.now(timezone.utc)

    old_stuck = []
    recent_stuck = []

    for v in stuck:
        published = v.get("publishedAt", "")
        if published:
            try:
                pub_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                age = now - pub_dt
                if age > timedelta(hours=24):
                    old_stuck.append(v)
                else:
                    recent_stuck.append(v)
                continue
            except (ValueError, TypeError):
                pass
        old_stuck.append(v)

    logging.info("Videos atascados >24h (candidatos a eliminación): %s", len(old_stuck))
    logging.info("Videos atascados <24h (esperar procesamiento): %s", len(recent_stuck))

    if recent_stuck:
        print("\n--- Videos recientes (<24h), se deja que YouTube los procese ---")
        for v in recent_stuck:
            print(f"  [{v['id']}] {v['title']}")

    deleted_count = 0
    if old_stuck:
        print(f"\n--- Videos antiguos (>24h), {'SIMULANDO' if dry_run else 'ELIMINANDO'} para re-subida ---")
        for v in old_stuck:
            print(f"  [{v['id']}] {v['title']} | status={v['uploadStatus']}")
            if not dry_run:
                if delete_and_mark_for_reupload(youtube, v, local_videos):
                    deleted_count += 1
                time.sleep(1)  # Evitar rate limiting

    if not dry_run and deleted_count > 0:
        save_local_db(local_videos)
        logging.info("Base de datos local actualizada. %s videos marcados para re-subida.", deleted_count)

    print(f"\n{'='*60}")
    print(f"Resumen: {deleted_count} eliminados, {len(recent_stuck)} en espera.")
    if dry_run:
        print("(Modo dry-run, nada fue modificado. Ejecuta sin --dry-run para aplicar.)")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
