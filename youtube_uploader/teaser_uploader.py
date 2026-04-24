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

from video_helpers import build_upload_metadata, enrich_video_record, load_config, apply_faststart

# ─── CONFIGURACION PRINCIPAL ──────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "teaser_uploader.log"
CREDENTIALS_DIR = BASE_DIR / "credentials"
CONFIG_FILE = BASE_DIR / "config.json"
QUOTA_STATUS_FILE = BASE_DIR / "quota_status.json"
STOP_FILE = BASE_DIR / "STOP_TEASER"
CACHE_FILE = BASE_DIR / "yt_schedule_cache.json"

INPUT_DIR = Path("/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents/ADM/Carpeta 1/ya_subidos_ig_temp")
OUTPUT_DIR = Path("/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents/ADM/Carpeta 1/teaser youtube subidos")
SUPPORTED_EXTS = {".mp4", ".mov", ".mkv"}

UPLOAD_STALL_CHECK_SECONDS = 30
UPLOAD_STALL_MAX_NO_PROGRESS_CHECKS = 2
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


# ─── CLASES Y HELPERS ─────────────────────────────────────────────────────────
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
            logging.info("%s reanudo avance. Progreso: %s/%s bytes.", self.label, seen, total or "?")

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
                    self._no_progress_checks += 1 if stalled_seconds >= UPLOAD_STALL_CHECK_SECONDS else 0
                else:
                    self._no_progress_checks += 1 if total_runtime >= UPLOAD_STALL_CHECK_SECONDS else 0

                should_alert = self._no_progress_checks >= UPLOAD_STALL_MAX_NO_PROGRESS_CHECKS and not self._alerted
                seen = self._last_seen
                total = self._last_total

            if should_alert:
                if has_progress:
                    logging.warning("%s detenida: sin avance en %ss. Ultimo: %s/%s bytes.", self.label, stalled_seconds, seen, total or "?")
                else:
                    logging.warning("%s detenida en inicio (%ss sin chunks).", self.label, total_runtime)
                self._alerted = True


def get_authenticated_service(client_secret_file, creds_cache_file, scopes=None):
    from google.auth.exceptions import RefreshError
    client_secret_file = Path(client_secret_file)
    creds_cache_file = Path(creds_cache_file)
    scopes = scopes or SCOPES

    creds = None
    if creds_cache_file.exists():
        creds = Credentials.from_authorized_user_file(str(creds_cache_file), scopes)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError as e:
                logging.warning("Token revocado. Borrando %s y relogueando...", creds_cache_file.name)
                creds_cache_file.unlink(missing_ok=True)
                flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_file), scopes)
                creds = flow.run_local_server(port=0)
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_file), scopes)
            creds = flow.run_local_server(port=0)
        creds_cache_file.write_text(creds.to_json(), encoding="utf-8")

    return build("youtube", "v3", credentials=creds)


def extract_http_error_reason(error):
    try:
        payload = json.loads(error.content.decode("utf-8"))
        return payload["error"]["errors"][0]["reason"]
    except Exception:
        return str(error)


def wait_for_processing(youtube, video_id):
    """Espera activamente a que YouTube procese el Reel/Teaser para evitar videos zombies."""
    logging.info("Vigilando en SEGUNDO PLANO que YouTube termine de procesar el video %s...", video_id)
    for poll in range(1, 21): # 20 * 30s = 10 mins
        time.sleep(30)
        try:
            result = youtube.videos().list(part="status,processingDetails", id=video_id).execute()
            items = result.get("items", [])
            if not items: continue

            video = items[0]
            status = video.get("status", {})
            upload_status = status.get("uploadStatus", "unknown")
            if upload_status == "processed": 
                logging.info("YouTube reporta el procesamiento como FINALIZADO OK para %s.", video_id)
                return True
            if upload_status in {"failed", "rejected", "deleted"}: 
                logging.error("Atencion: YouTube fallo procesando el video %s. Ha quedado en estado Zombie/Rechazado.", video_id)
                return False
        except HttpError:
            pass
        except Exception:
            pass
    
    logging.warning("El video procesando demoro demasiado (%s polls). Validar manualmente %s", poll, video_id)
    return None

def start_processing_verifier(video_id, client_secret_file, creds_cache_file):
    def bg_verify():
        try:
            verifier = get_authenticated_service(client_secret_file, creds_cache_file)
            wait_for_processing(verifier, video_id)
        except Exception as exc:
            logging.error("Error en verificador aislado para %s: %s", video_id, exc)
    
    t = threading.Thread(target=bg_verify, name=f"Verify-{video_id}")
    t.start()
    return t


def fetch_yt_schedule(youtube, force_refresh=False):
    if not force_refresh and CACHE_FILE.exists():
        try:
            cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            cache_time = datetime.fromisoformat(cache.get("timestamp", "2000-01-01"))
            if (datetime.now() - cache_time).total_seconds() < CACHE_EXPIRY_SECONDS:
                return cache.get("schedule", {})
        except Exception:
            pass

    logging.info("Auditando calendario completo de YouTube...")
    schedule = {}
    try:
        channels_response = youtube.channels().list(mine=True, part="contentDetails").execute()
        uploads_playlist_id = channels_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

        next_page_token = None
        while True:
            playlist_request = youtube.playlistItems().list(
                part="snippet", playlistId=uploads_playlist_id, maxResults=50, pageToken=next_page_token
            )
            playlist_response = playlist_request.execute()
            video_ids = [item["snippet"]["resourceId"]["videoId"] for item in playlist_response.get("items", [])]
            if not video_ids: break

            videos_response = youtube.videos().list(part="status,contentDetails", id=",".join(video_ids)).execute()

            for video in videos_response.get("items", []):
                publish_at = video.get("status", {}).get("publishAt")
                if not publish_at: continue

                date_str = publish_at.split("T")[0]
                if date_str not in schedule: schedule[date_str] = {"videos": 0, "shorts": 0}

                dur = video.get("contentDetails", {}).get("duration", "")
                import re
                h = int(re.search(r"(\d+)H", dur).group(1)) if re.search(r"(\d+)H", dur) else 0
                m = int(re.search(r"(\d+)M", dur).group(1)) if re.search(r"(\d+)M", dur) else 0
                s = int(re.search(r"(\d+)S", dur).group(1)) if re.search(r"(\d+)S", dur) else 0
                
                if (h*3600 + m*60 + s) <= 180:
                    schedule[date_str]["shorts"] += 1
                else:
                    schedule[date_str]["videos"] += 1

            next_page_token = playlist_response.get("nextPageToken")
            if not next_page_token: break

        CACHE_FILE.write_text(
            json.dumps({"timestamp": datetime.now().isoformat(), "schedule": schedule}, indent=4),
            encoding="utf-8",
        )
    except Exception as exc:
        logging.error("Error auditando: %s", exc)

    return schedule


def get_next_publish_date(video_type, yt_schedule):
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

        yt_counts = yt_schedule.get(date_str, {"videos": 0, "shorts": 0})

        if video_type == "short" and yt_counts["shorts"] == 0:
            return check_date.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0).astimezone(timezone.utc)
        if video_type != "short" and yt_counts["videos"] == 0:
            return check_date.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0).astimezone(timezone.utc)

    return base_date.astimezone(timezone.utc)


def update_quota_status(client_name):
    status = {}
    if QUOTA_STATUS_FILE.exists():
        try: status = json.loads(QUOTA_STATUS_FILE.read_text(encoding="utf-8"))
        except: pass

    status[client_name] = {
        "last_quota_exceeded": datetime.now().isoformat(),
        "date": datetime.now().strftime("%Y-%m-%d"),
    }
    QUOTA_STATUS_FILE.write_text(json.dumps(status, indent=4), encoding="utf-8")


def is_client_available(client_name):
    if not QUOTA_STATUS_FILE.exists(): return True
    try: status = json.loads(QUOTA_STATUS_FILE.read_text(encoding="utf-8"))
    except: return True

    entry = status.get(client_name)
    if entry and entry.get("date") == datetime.now().strftime("%Y-%m-%d"):
        return False
    return True


# ─── CORE UPLOAD FUNCTION ─────────────────────────────────────────────────────
def upload_video(youtube, file_path, upload_metadata, publish_at_dt, current_client_secret, current_token_file, is_publish_now):
    import re
    publish_at_str = publish_at_dt.isoformat().replace("+00:00", "Z")
    audience = config.get("audience_settings", {"selfDeclaredMadeForKids": False})
    
    # LA LIMPIEZA DE TITULO AHORA SE HACE EN MAIN VIA TITLE_OVERRIDE
    title = upload_metadata["title"]

    body = {
        "snippet": {
            "title": title,
            "description": upload_metadata["description"],
            "tags": upload_metadata["tags"],
            "categoryId": upload_metadata["categoryId"],
        },
        "status": {
            "selfDeclaredMadeForKids": audience.get("selfDeclaredMadeForKids", False),
            "hasAlteredContentDisclosure": audience.get("hasAlteredContentDisclosure", False),
            "license": upload_metadata["license"],
        },
    }

    if is_publish_now:
        body["status"]["privacyStatus"] = "public"
        logging.info("Iniciando subida Teaser: %s (PUBLICAR AHORA MISMO)", title)
    else:
        body["status"]["privacyStatus"] = "private"  # Requiere ser private para agendar
        body["status"]["publishAt"] = publish_at_str
        logging.info("Iniciando subida Teaser: %s (Programado para: %s)", title, publish_at_str)

    media = MediaFileUpload(str(file_path), chunksize=1024 * 1024 * 10, resumable=True)
    insert_request = youtube.videos().insert(
        part="snippet,status", body=body, media_body=media, notifySubscribers=False
    )

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
                if not status: continue

                progress_bytes = int(getattr(status, "resumable_progress", 0) or 0)
                total_bytes = int(getattr(status, "total_size", total_size) or total_size or 0)
                watchdog.update(progress_bytes, total_bytes)
                retry_count = 0
            except (httplib2.HttpLib2Error, ConnectionError, TimeoutError) as exc:
                retry_count += 1
                if retry_count > max_retries:
                    logging.error("Fallo de red tras %s reintentos: %s", max_retries, exc)
                    return None
                time.sleep(retry_count * 5)
            except HttpError as exc:
                reason = extract_http_error_reason(exc)
                if exc.resp.status == 403 and reason in {"quotaExceeded", "rateLimitExceeded"}:
                    return "QUOTA_EXCEEDED"
                if exc.resp.status == 400 and reason == "uploadLimitExceeded":
                    return "LIMIT_EXCEEDED"
                logging.error("Error HTTP (%s): %s", exc.resp.status, reason)
                return None
            except Exception as exc:
                logging.error("Error inesperado: %s", exc)
                return None
    finally:
        watchdog.stop()
        if hasattr(media, "_fd") and media._fd:
            try: media._fd.close()
            except: pass

    if not response or "id" not in response:
        return None

    video_id = response["id"]
    logging.info("Subida Teaser completada. Video ID: %s.", video_id)
    
    # Iniciar verificación en paralelo sin frenar la cola principal
    verifier_thread = start_processing_verifier(video_id, current_client_secret, current_token_file)
    
    return video_id, verifier_thread


# ─── AGENTE PRINCIPAL ─────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("   YOUTUBE TEASER UPLOADER (RECICLAJE IG -> YT)  ")
    print("=" * 60)

    if not CONFIG_FILE.exists():
        logging.error("Falta config.json en youtube_uploader.")
        return

    CREDENTIALS_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    client_files = sorted(path.name for path in CREDENTIALS_DIR.glob("client_secret*.json"))
    if not client_files:
        logging.error("No hay client_secret en credentials/.")
        return

    if not INPUT_DIR.exists():
        logging.error("Carpeta %s no existe.", INPUT_DIR)
        return

    # Buscar videos disponibles
    videos_pendientes = [
        p for p in INPUT_DIR.glob("*.*") if p.suffix.lower() in SUPPORTED_EXTS
    ]
    videos_pendientes.sort(key=lambda p: p.stat().st_size, reverse=True)

    if not videos_pendientes:
        logging.info("No hay videos en la carpeta temporal de IG.")
        return

    logging.info("Se encontraron %s videos de descarte para procesar como Teasers.", len(videos_pendientes))

    # Seleccionar credenciales disponibles con Quota
    current_idx = 0
    while current_idx < len(client_files) and not is_client_available(client_files[current_idx]):
        current_idx += 1

    if current_idx >= len(client_files):
        logging.warning("Todas las llaves estan agotadas por hoy (QUOTA).")
        return

    current_client_secret = CREDENTIALS_DIR / client_files[current_idx]
    current_token_file = CREDENTIALS_DIR / f"token_{current_idx}.json"
    youtube = get_authenticated_service(current_client_secret, current_token_file)

    yt_schedule = fetch_yt_schedule(youtube)
    upload_counter = 0
    active_threads = []

    for file_path in videos_pendientes:
        if STOP_FILE.exists():
            logging.warning("Archivo STOP_TEASER detectado. Deteniendo.")
            break

        logging.info("-" * 40)
        
        from video_helpers import normalize_video_stem
        clean_name = normalize_video_stem(file_path.stem)
        
        # Emular estructura base de uploader e inyectar el override puro
        video_record = {
            "path": str(file_path), 
            "filename": file_path.name,
            "title_override": f"{clean_name} #PW #Teaser"
        }
        enrich_video_record(video_record, include_probe=True)
        
        # Decidir si publicar ahora (Patron 1 ahora, 3 futuros)
        upload_counter += 1
        is_publish_now = (upload_counter % 4 == 1)
        
        # Generalmente, los Slices de IG duran menos de 60s, serán "short"
        v_type = "short" if video_record.get("type") == "short" else "video"
        
        if is_publish_now:
            next_date = datetime.now(timezone.utc)
        else:
            next_date = get_next_publish_date(v_type, yt_schedule)

        # Optimizacion faststart nativa
        apply_faststart(file_path)

        upload_metadata = build_upload_metadata(video_record, config)

        result = None
        verifier_thread = None
        while True:
            ret_val = upload_video(
                youtube, file_path, upload_metadata, next_date, current_client_secret, current_token_file, is_publish_now
            )
            
            if ret_val == "QUOTA_EXCEEDED":
                logging.info("Cuota agotada en %s. Rotando...", client_files[current_idx])
                update_quota_status(client_files[current_idx])
                current_idx += 1
                if current_idx >= len(client_files):
                    logging.error("Se agotaron todas las llaves por hoy.")
                    return
                current_client_secret = CREDENTIALS_DIR / client_files[current_idx]
                current_token_file = CREDENTIALS_DIR / f"token_{current_idx}.json"
                youtube = get_authenticated_service(current_client_secret, current_token_file)
                continue

            if ret_val == "LIMIT_EXCEEDED":
                logging.error("Canal alcanzo limite de uploads por HOY.")
                return

            if ret_val is not None and isinstance(ret_val, tuple):
                result, verifier_thread = ret_val
            break

        if result:
            if verifier_thread:
                active_threads.append(verifier_thread)

            date_key = next_date.strftime("%Y-%m-%d")
            if date_key not in yt_schedule:
                yt_schedule[date_key] = {"videos": 0, "shorts": 0}
            if v_type == "short": yt_schedule[date_key]["shorts"] += 1
            else: yt_schedule[date_key]["videos"] += 1

            # Mover a la carpeta especial
            try:
                if not OUTPUT_DIR.exists():
                    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                
                new_path = OUTPUT_DIR / file_path.name
                if new_path.exists():
                    logging.info("Destino ya existe, eliminando fuente: %s", file_path.name)
                    file_path.unlink()
                elif file_path.exists():
                    shutil.move(str(file_path), str(new_path))
                    logging.info("Video movido con exito a: %s", OUTPUT_DIR.name)
                else:
                    logging.warning("Fuente no encontrada para mover: %s", file_path)
            except Exception as exc:
                logging.warning("No se pudo mover el video %s: %s", file_path.name, exc)
        else:
            logging.error("Fallo en la subida de %s, se omitira por hoy.", file_path.name)

    logging.info("Ciclo de Teasers de subida completado.")
    if active_threads:
        logging.info("Esperando que las %s tareas criticas en paralelo terminen de confirmar el procesamiento HD en Youtube...", len(active_threads))
        for t in active_threads:
            t.join()
        logging.info("Todas las confirmaciones paralelas fueron exitosas y terminaron.")

if __name__ == "__main__":
    main()
