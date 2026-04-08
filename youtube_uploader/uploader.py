import json
import logging
import shutil
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httplib2
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from video_helpers import build_upload_metadata
from video_helpers import enrich_video_record
from video_helpers import load_config
from video_helpers import save_json_file

UPLOAD_STALL_CHECK_SECONDS = 10
UPLOAD_STALL_MAX_NO_PROGRESS_CHECKS = 2

BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "uploader.log"
JSON_DB = BASE_DIR / "scanned_videos.json"
CREDENTIALS_DIR = BASE_DIR / "credentials"
CONFIG_FILE = BASE_DIR / "config.json"
QUOTA_STATUS_FILE = BASE_DIR / "quota_status.json"
STOP_FILE = BASE_DIR / "STOP"
CACHE_FILE = BASE_DIR / "yt_schedule_cache.json"
CACHE_EXPIRY_SECONDS = 3600
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)

config = load_config(BASE_DIR)


class UploadWatchdog:
    def __init__(self, label):
        self.label = label
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = None
        self._started_at = time.monotonic()
        self._last_change_at = self._started_at
        self._last_seen = 0
        self._last_total = 0
        self._no_progress_checks = 0
        self._alerted = False

    def start(self):
        self._thread = threading.Thread(target=self._run, name=f"watchdog-{self.label}", daemon=True)
        self._thread.start()

    def update(self, seen, total):
        with self._lock:
            if seen > self._last_seen:
                recovered = self._alerted
                self._last_seen = seen
                self._last_total = total
                self._last_change_at = time.monotonic()
                self._no_progress_checks = 0
                self._alerted = False
            else:
                recovered = False

        if recovered:
            logging.info(
                "%s reanudo avance despues del bloqueo temporal. Progreso actual: %s/%s bytes.",
                self.label,
                seen,
                total or "?",
            )

    def stop(self):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)

    def _run(self):
        while not self._stop_event.wait(UPLOAD_STALL_CHECK_SECONDS):
            with self._lock:
                now = time.monotonic()
                stalled_seconds = int(now - self._last_change_at)
                total_runtime = int(now - self._started_at)
                has_progress = self._last_seen > 0

                if has_progress:
                    self._no_progress_checks = self._no_progress_checks + 1 if stalled_seconds >= UPLOAD_STALL_CHECK_SECONDS else 0
                else:
                    self._no_progress_checks = self._no_progress_checks + 1 if total_runtime >= UPLOAD_STALL_CHECK_SECONDS else 0

                should_alert = self._no_progress_checks >= UPLOAD_STALL_MAX_NO_PROGRESS_CHECKS and not self._alerted
                seen = self._last_seen
                total = self._last_total

            if should_alert:
                if has_progress:
                    logging.warning(
                        "%s parece detenida: sin avance en %ss (%s verificaciones de %ss). Ultimo progreso: %s/%s bytes.",
                        self.label,
                        stalled_seconds,
                        self._no_progress_checks,
                        UPLOAD_STALL_CHECK_SECONDS,
                        seen,
                        total or "?",
                    )
                else:
                    logging.warning(
                        "%s parece detenida en el inicio (%ss sin emitir el primer chunk).",
                        self.label,
                        total_runtime,
                    )
                self._alerted = True


def get_next_publish_date(videos, video_type="video", yt_scheduled_dates=None):
    if yt_scheduled_dates is None:
        yt_scheduled_dates = {}

    tz_offset = config.get("scheduling", {}).get("colombia_time_offset", -5)
    target_hour = config.get("scheduling", {}).get("publish_hour", 17)
    target_minute = config.get("scheduling", {}).get("publish_minute", 45)
    colombia_tz = timezone(timedelta(hours=tz_offset))

    now_utc = datetime.now(timezone.utc)
    now_col = now_utc.astimezone(colombia_tz)
    base_date = now_col + timedelta(days=1)

    for offset in range(730):
        check_date = base_date + timedelta(days=offset)
        date_str = check_date.strftime("%Y-%m-%d")

        local_counts = {"videos": 0, "shorts": 0}
        for video in videos:
            if not (video.get("uploaded") and video.get("publishAt")):
                continue
            publish_date = video["publishAt"].split("T")[0]
            if publish_date != date_str:
                continue
            if video.get("type") == "short":
                local_counts["shorts"] += 1
            else:
                local_counts["videos"] += 1

        yt_counts = yt_scheduled_dates.get(date_str, {"videos": 0, "shorts": 0})
        total_videos = local_counts["videos"] + yt_counts["videos"]
        total_shorts = local_counts["shorts"] + yt_counts["shorts"]

        if video_type == "short" and total_shorts == 0:
            return check_date.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0).astimezone(timezone.utc)
        if video_type != "short" and total_videos == 0:
            return check_date.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0).astimezone(timezone.utc)

    return base_date.astimezone(timezone.utc)


def get_authenticated_service(client_secret_file, creds_cache_file):
    client_secret_file = Path(client_secret_file)
    creds_cache_file = Path(creds_cache_file)

    creds = None
    if creds_cache_file.exists():
        creds = Credentials.from_authorized_user_file(str(creds_cache_file), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_file), SCOPES)
            creds = flow.run_local_server(port=0)
        creds_cache_file.write_text(creds.to_json(), encoding="utf-8")

    return build("youtube", "v3", credentials=creds)


def extract_http_error_reason(error):
    try:
        payload = json.loads(error.content.decode("utf-8"))
        return payload["error"]["errors"][0]["reason"]
    except Exception:
        return str(error)


def upload_video(youtube, file_path, upload_metadata, publish_at_dt):
    publish_at_str = publish_at_dt.isoformat().replace("+00:00", "Z")
    audience = config.get("audience_settings", {"selfDeclaredMadeForKids": False})

    body = {
        "snippet": {
            "title": upload_metadata["title"],
            "description": upload_metadata["description"],
            "tags": upload_metadata["tags"],
            "categoryId": upload_metadata["categoryId"],
        },
        "status": {
            "privacyStatus": upload_metadata["privacyStatus"],
            "publishAt": publish_at_str,
            "selfDeclaredMadeForKids": audience.get("selfDeclaredMadeForKids", False),
            "hasAlteredContentDisclosure": audience.get("hasAlteredContentDisclosure", False),
            "license": upload_metadata["license"],
        },
    }

    media = MediaFileUpload(str(file_path), chunksize=1024 * 1024 * 10, resumable=True)
    insert_request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    logging.info("Iniciando subida: %s (%s)", title, file_path)
    logging.info("Programado para: %s (MadeForKids: %s)", publish_at_str, body["status"]["selfDeclaredMadeForKids"])

    response = None
    retry_count = 0
    max_retries = 5
    total_size = media.size() if callable(getattr(media, "size", None)) else 0
    watchdog = UploadWatchdog(Path(file_path).name)
    watchdog.start()

    try:
        while response is None:
            try:
                status, response = insert_request.next_chunk()
                if not status:
                    continue

                progress_bytes = int(getattr(status, "resumable_progress", 0) or 0)
                total_bytes = int(getattr(status, "total_size", total_size) or total_size or 0)
                watchdog.update(progress_bytes, total_bytes)
                logging.info("Progreso: %s%%", int(status.progress() * 100))
                retry_count = 0
            except (httplib2.HttpLib2Error, ConnectionError, TimeoutError) as exc:
                retry_count += 1
                if retry_count > max_retries:
                    logging.error("Fallo critico tras %s reintentos de red: %s", max_retries, exc)
                    return None

                wait_time = retry_count * 5
                logging.warning(
                    "Error de red (%s). Reintentando en %ss... (Intento %s/%s)",
                    exc,
                    wait_time,
                    retry_count,
                    max_retries,
                )
                time.sleep(wait_time)
            except HttpError as exc:
                reason = extract_http_error_reason(exc)
                if exc.resp.status == 403 and reason in {"quotaExceeded", "rateLimitExceeded"}:
                    return "QUOTA_EXCEEDED"
                if exc.resp.status == 400 and reason == "uploadLimitExceeded":
                    logging.warning("Limite de subidas de YouTube alcanzado para esta cuenta o canal.")
                    return "LIMIT_EXCEEDED"

                logging.error("Error HTTP (%s): %s - %s", exc.resp.status, reason, exc)
                return None
            except Exception as exc:
                logging.error("Error inesperado: %s", exc)
                return None
    finally:
        watchdog.stop()

    if not response or "id" not in response:
        logging.error("La API no devolvio un id de video para %s.", file_path)
        return None

    logging.info("Subida completada. Video ID: %s", response["id"])
    return response["id"]


def update_quota_status(client_name):
    status = {}
    if QUOTA_STATUS_FILE.exists():
        try:
            status = json.loads(QUOTA_STATUS_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logging.warning("quota_status.json estaba corrupto; se reescribira.")

    status[client_name] = {
        "last_quota_exceeded": datetime.now().isoformat(),
        "date": datetime.now().strftime("%Y-%m-%d"),
    }
    QUOTA_STATUS_FILE.write_text(json.dumps(status, indent=4), encoding="utf-8")


def is_client_available(client_name):
    if not QUOTA_STATUS_FILE.exists():
        return True
    try:
        status = json.loads(QUOTA_STATUS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return True

    entry = status.get(client_name)
    if entry and entry.get("date") == datetime.now().strftime("%Y-%m-%d"):
        return False
    return True


def fetch_yt_schedule(youtube, force_refresh=False):
    if not force_refresh and CACHE_FILE.exists():
        try:
            cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            cache_time = datetime.fromisoformat(cache.get("timestamp", "2000-01-01"))
            if (datetime.now() - cache_time).total_seconds() < CACHE_EXPIRY_SECONDS:
                logging.info("Usando cache del calendario de YouTube.")
                return cache.get("schedule", {})
        except Exception as exc:
            logging.warning("Error leyendo cache: %s", exc)

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
                pageToken=next_page_token,
            )
            playlist_response = playlist_request.execute()
            video_ids = [item["snippet"]["resourceId"]["videoId"] for item in playlist_response.get("items", [])]
            if not video_ids:
                next_page_token = playlist_response.get("nextPageToken")
                if not next_page_token:
                    break
                continue

            videos_response = youtube.videos().list(part="status,contentDetails", id=",".join(video_ids)).execute()

            for video in videos_response.get("items", []):
                status = video.get("status", {})
                content = video.get("contentDetails", {})
                publish_at = status.get("publishAt")
                if not publish_at:
                    continue

                date_str = publish_at.split("T")[0]
                if date_str not in schedule:
                    schedule[date_str] = {"videos": 0, "shorts": 0}

                duration_string = content.get("duration", "")
                hours = re_search_duration(duration_string, "H")
                minutes = re_search_duration(duration_string, "M")
                seconds = re_search_duration(duration_string, "S")
                total_seconds = hours * 3600 + minutes * 60 + seconds

                if total_seconds <= 180:
                    schedule[date_str]["shorts"] += 1
                else:
                    schedule[date_str]["videos"] += 1

            next_page_token = playlist_response.get("nextPageToken")
            if not next_page_token:
                break

        CACHE_FILE.write_text(
            json.dumps({"timestamp": datetime.now().isoformat(), "schedule": schedule}, indent=4),
            encoding="utf-8",
        )
    except Exception as exc:
        logging.error("Error en auditoria previa: %s", exc)

    return schedule


def re_search_duration(duration_string, suffix):
    import re

    match = re.search(rf"(\d+){suffix}", duration_string)
    return int(match.group(1)) if match else 0


def enrich_pending_videos(videos):
    changed = False
    for video in videos:
        if video.get("uploaded"):
            continue
        if enrich_video_record(video, include_probe=True):
            changed = True
    return changed


def main():
    if not CONFIG_FILE.exists():
        logging.error("Falta config.json. Copia config.example.json y ajusta tu configuracion local.")
        return

    CREDENTIALS_DIR.mkdir(exist_ok=True)

    client_files = sorted(path.name for path in CREDENTIALS_DIR.glob("client_secret*.json"))
    if not client_files:
        logging.error("No hay client_secret_X.json en credentials/.")
        return

    if not JSON_DB.exists():
        logging.error("Falta scanned_videos.json. Ejecuta video_scanner.py primero.")
        return

    videos = json.loads(JSON_DB.read_text(encoding="utf-8"))
    if enrich_pending_videos(videos):
        save_json_file(JSON_DB, videos)

    pendientes = [video for video in videos if not video.get("uploaded", False)]
    logging.info("Videos pendientes: %s", len(pendientes))
    if not pendientes:
        return

    current_idx = 0
    while current_idx < len(client_files) and not is_client_available(client_files[current_idx]):
        current_idx += 1

    if current_idx >= len(client_files):
        logging.warning("Todas las llaves estan agotadas por hoy segun quota_status.json.")
        return

    youtube = get_authenticated_service(
        CREDENTIALS_DIR / client_files[current_idx],
        CREDENTIALS_DIR / f"token_{current_idx}.json",
    )

    logging.info("Auditando calendario de YouTube antes de comenzar...")
    yt_schedule = fetch_yt_schedule(youtube)
    pendientes.sort(key=lambda item: item.get("size_mb", 0), reverse=True)

    for video in pendientes:
        if STOP_FILE.exists():
            logging.warning("Archivo STOP detectado. Deteniendo.")
            break

        file_path = Path(video["path"])
        if not file_path.exists():
            logging.warning("Archivo no encontrado: %s", file_path)
            continue

        if enrich_video_record(video, include_probe=True):
            save_json_file(JSON_DB, videos)

        video_type = video.get("type", "video")
        upload_metadata = build_upload_metadata(video, config)
        next_date = get_next_publish_date(videos, video_type, yt_schedule)

        while True:
            result = upload_video(youtube, file_path, upload_metadata, next_date)

            if result in {"QUOTA_EXCEEDED", "LIMIT_EXCEEDED"}:
                reason_label = "Cuota agotada" if result == "QUOTA_EXCEEDED" else "Limite de subidas de YouTube"
                logging.info("%s en llave %s. Rotando...", reason_label, current_idx)

                update_quota_status(client_files[current_idx])
                current_idx += 1
                if current_idx >= len(client_files):
                    logging.error("Se agotaron todas las llaves o el canal esta bloqueado por hoy.")
                    return

                youtube = get_authenticated_service(
                    CREDENTIALS_DIR / client_files[current_idx],
                    CREDENTIALS_DIR / f"token_{current_idx}.json",
                )
                continue

            if not result:
                break

            video["uploaded"] = True
            video["youtube_id"] = result
            video["publishAt"] = next_date.isoformat().replace("+00:00", "Z")

            date_key = next_date.strftime("%Y-%m-%d")
            if date_key not in yt_schedule:
                yt_schedule[date_key] = {"videos": 0, "shorts": 0}
            if video_type == "short":
                yt_schedule[date_key]["shorts"] += 1
            else:
                yt_schedule[date_key]["videos"] += 1

            try:
                success_folder = file_path.parent / "videos subidos exitosamente"
                success_folder.mkdir(exist_ok=True)
                new_path = success_folder / file_path.name
                shutil.move(str(file_path), str(new_path))
                video["path"] = str(new_path)
                file_path = new_path
            except Exception as exc:
                logging.error("Error moviendo archivo: %s", exc)

            save_json_file(JSON_DB, videos)
            break


if __name__ == "__main__":
    main()
