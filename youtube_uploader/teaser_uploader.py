import json
import os
import logging
import shutil
import threading
import time
import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httplib2
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from video_helpers import apply_faststart
from video_helpers import build_teaser_sort_key
from video_helpers import build_upload_metadata
from video_helpers import enrich_video_record
from video_helpers import extract_teaser_sequence
from video_helpers import load_config

# ─── CONFIGURACION PRINCIPAL ──────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "teaser_uploader.log"
CREDENTIALS_DIR = BASE_DIR / "credentials"
CONFIG_FILE = BASE_DIR / "config.json"
QUOTA_STATUS_FILE = BASE_DIR / "quota_status.json"
STOP_FILE = BASE_DIR / "STOP_TEASER"
CACHE_FILE = BASE_DIR / "yt_schedule_cache.json"

STORAGE_ROOT = Path(os.environ.get("AGENTES_STORAGE_ROOT", "/sdcard/Antigravity"))
if STORAGE_ROOT.exists():
    INPUT_DIR = STORAGE_ROOT / "teasers_pendientes"
    OUTPUT_DIR = STORAGE_ROOT / "videos subidos exitosamente"
else:
    INPUT_DIR = Path("/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents/ADM/Carpeta 1/teasers_pendientes")
    OUTPUT_DIR = Path("/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents/ADM/Carpeta 1/videos subidos exitosamente")
SUPPORTED_EXTS = {".mp4", ".mov", ".mkv"}

UPLOAD_STALL_CHECK_SECONDS = 30
UPLOAD_STALL_MAX_NO_PROGRESS_CHECKS = 2
CACHE_EXPIRY_SECONDS = 3600
STRICT_TEASER_PUBLISH_HOUR = 17
STRICT_TEASER_PUBLISH_MINUTE = 45
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


def _read_client_id(json_file):
    try:
        payload = json.loads(Path(json_file).read_text(encoding="utf-8"))
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None

    for section in ("installed", "web"):
        client_id = payload.get(section, {}).get("client_id")
        if client_id:
            return client_id

    return payload.get("client_id")


def _extract_numeric_suffix(path_like, prefix):
    stem = Path(path_like).stem
    if not stem.startswith(prefix):
        return None

    suffix = stem[len(prefix):].lstrip("_")
    return int(suffix) if suffix.isdigit() else None


def _credential_sort_key(path_like, prefix):
    path = Path(path_like)
    suffix = _extract_numeric_suffix(path, prefix)
    if suffix is None:
        return (1, path.name.lower())
    return (0, suffix)


def _list_client_secret_files():
    return sorted(
        (path for path in CREDENTIALS_DIR.glob("client_secret*.json") if path.suffix.lower() == ".json"),
        key=lambda path: _credential_sort_key(path, "client_secret"),
    )


def _list_token_files():
    return sorted(
        (
            token_file
            for token_file in CREDENTIALS_DIR.glob("token_*.json")
            if _extract_numeric_suffix(token_file, "token") is not None
        ),
        key=lambda path: _credential_sort_key(path, "token"),
    )


def _default_token_cache_file(client_secret_file, fallback_index=None):
    client_number = _extract_numeric_suffix(client_secret_file, "client_secret")
    if client_number is not None:
        return CREDENTIALS_DIR / f"token_{max(client_number - 1, 0)}.json"

    if fallback_index is not None:
        return CREDENTIALS_DIR / f"token_{fallback_index}.json"

    return CREDENTIALS_DIR / "token_0.json"


def _read_token_scopes(json_file):
    try:
        payload = json.loads(Path(json_file).read_text(encoding="utf-8"))
    except Exception:
        return set()

    scopes = payload.get("scopes") or []
    return set(scopes) if isinstance(scopes, list) else set()


def resolve_token_cache_file(client_secret_file, key_index=0):
    client_secret_file = Path(client_secret_file)
    preferred_cache_file = _default_token_cache_file(client_secret_file, fallback_index=key_index)
    required_scopes = set(SCOPES)
    client_id = _read_client_id(client_secret_file)
    ordered_candidates = [preferred_cache_file]
    ordered_candidates.extend(
        token_file for token_file in _list_token_files() if token_file != preferred_cache_file
    )

    for token_file in ordered_candidates:
        if not token_file.exists():
            continue

        if not required_scopes.issubset(_read_token_scopes(token_file)):
            continue

        if client_id:
            if _read_client_id(token_file) != client_id:
                continue
            if token_file != preferred_cache_file:
                logging.info(
                    "Usando %s para %s (client_id coincidente).",
                    token_file.name,
                    client_secret_file.name,
                )
            return token_file

        if token_file == preferred_cache_file:
            return token_file

    fallback_token = preferred_cache_file
    logging.warning(
        "No se encontro token compatible para %s. Se intentara crear %s si hace falta relogin.",
        client_secret_file.name,
        fallback_token.name,
    )
    return fallback_token


def _build_credential_pool():
    slots = []
    for legacy_index, client_secret_file in enumerate(_list_client_secret_files()):
        token_file = resolve_token_cache_file(client_secret_file, key_index=legacy_index)
        if not token_file.exists():
            logging.warning(
                "Saltando %s: no hay token OAuth compatible presente en credentials/.",
                client_secret_file.name,
            )
            continue

        client_id = _read_client_id(client_secret_file)
        token_client_id = _read_client_id(token_file)
        if client_id and token_client_id != client_id:
            logging.warning(
                "Saltando %s: %s pertenece a otra app OAuth (%s).",
                client_secret_file.name,
                token_file.name,
                token_client_id or "sin client_id",
            )
            continue

        slots.append(
            {
                "legacy_index": legacy_index,
                "client_name": client_secret_file.name,
            }
        )

    return slots


def get_authenticated_service(key_index=0):
    from google.auth.exceptions import RefreshError
    client_secret_files = _list_client_secret_files()
    if key_index < 0 or key_index >= len(client_secret_files):
        logging.error("Indice de credencial fuera de rango: %s", key_index)
        return None

    client_secret_file = client_secret_files[key_index]
    creds_cache_file = resolve_token_cache_file(client_secret_file, key_index)
    
    if not client_secret_file.exists():
        logging.error(f"No se encuentra el secreto de cliente: {client_secret_file}")
        return None

    scopes = SCOPES
    creds = None
    if creds_cache_file.exists():
        creds = Credentials.from_authorized_user_file(str(creds_cache_file), scopes)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError as e:
                logging.warning("Token revocado o fallido (%s). Borrando %s y relogueando...", e, creds_cache_file.name)
                creds_cache_file.unlink(missing_ok=True)
                flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_file), scopes)
                creds = flow.run_local_server(port=0, open_browser=False, timeout_seconds=300)
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_file), scopes)
            creds = flow.run_local_server(port=0, open_browser=False, timeout_seconds=300)
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

def move_file_to_success(file_path):
    try:
        if not OUTPUT_DIR.exists():
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        new_path = OUTPUT_DIR / file_path.name
        if new_path.exists():
            logging.info("Destino ya existe, eliminando fuente: %s", file_path.name)
            file_path.unlink()
        elif file_path.exists():
            shutil.move(str(file_path), str(new_path))
            logging.info("Teaser movido con exito a exito: %s", file_path.name)
        else:
            logging.warning("Fuente no encontrada para mover: %s", file_path)
    except Exception as exc:
        logging.warning("No se pudo mover el video %s tras verificacion: %s", file_path.name, exc)

def start_processing_verifier(video_id, key_index, file_path):
    def bg_verify():
        try:
            verifier = get_authenticated_service(key_index)
            success = wait_for_processing(verifier, video_id)
            if success:
                move_file_to_success(Path(file_path))
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


def get_next_publish_date(yt_schedule, now_utc=None):
    tz_offset = config.get("scheduling", {}).get("colombia_time_offset", -5)
    colombia_tz = timezone(timedelta(hours=tz_offset))

    if now_utc is None:
        now_utc = datetime.now(timezone.utc)
    now_col = now_utc.astimezone(colombia_tz)
    base_date = now_col + timedelta(days=1)

    for offset in range(730):
        check_date = base_date + timedelta(days=offset)
        date_str = check_date.strftime("%Y-%m-%d")

        yt_counts = yt_schedule.get(date_str, {"videos": 0, "shorts": 0})

        if yt_counts["shorts"] == 0:
            return check_date.replace(
                hour=STRICT_TEASER_PUBLISH_HOUR,
                minute=STRICT_TEASER_PUBLISH_MINUTE,
                second=0,
                microsecond=0,
            ).astimezone(timezone.utc)

    return base_date.replace(
        hour=STRICT_TEASER_PUBLISH_HOUR,
        minute=STRICT_TEASER_PUBLISH_MINUTE,
        second=0,
        microsecond=0,
    ).astimezone(timezone.utc)


def list_pending_teasers(source_video_stem=None):
    if not INPUT_DIR.exists():
        return []
    
    pending = []
    # Solo procesar archivos que tengan 'teaser' en el nombre
    for f in INPUT_DIR.glob("*"):
        name_lower = f.name.lower()
        if f.suffix.lower() in SUPPORTED_EXTS and "teaser" in name_lower:
            # Si hay filtro por video origen, validamos el prefijo
            if source_video_stem and not name_lower.startswith(source_video_stem.lower()):
                continue
            pending.append(f)
    
    # Ordenar por el patrón de teaser (opcional pero ayuda a la coherencia)
    pending.sort(key=lambda path: build_teaser_sort_key(path.name))
    return pending


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
def upload_video(youtube, file_path, upload_metadata, publish_at_dt, key_index, is_publish_now):
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
    verifier_thread = start_processing_verifier(video_id, key_index, file_path)
    
    return video_id, verifier_thread


# ─── AGENTE PRINCIPAL ─────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="YouTube Teaser Uploader Granular")
    parser.add_argument("--source-video", help="Nombre (sin extension) del video original para filtrar sus teasers.")
    parser.add_argument("--from-orchestrator", action="store_true", help="Saltar bloqueo de instancia (.lock).")
    parser.add_argument("--key", type=int, default=0, help="Indice del token a usar (0, 1, 2, 3)")
    parser.add_argument("--single-file", help="Subir un solo archivo (ruta completa). Ignora --source-video y list_pending_teasers.")
    parser.add_argument("--state-dir", default="/sdcard/Antigravity/.state", help="Directorio para markers de estado.")
    args = parser.parse_args()

    print("=" * 60)
    print("   YOUTUBE TEASER UPLOADER (RECICLAJE IG -> YT)  ")
    print("=" * 60)

    if not CONFIG_FILE.exists():
        logging.error("Falta config.json. Copia config.example.json y ajusta tu configuracion local.")
        return

    # Lock de instancia (Solo si no viene del orquestador)
    lock_file = BASE_DIR / "teaser_uploader.lock"
    if not args.from_orchestrator:
        if lock_file.exists():
            logging.warning("Ya hay una instancia de teaser_uploader corriendo o el lock quedo huerfano. Saliendo.")
            return
        lock_file.write_text(str(os.getpid()))
    else:
        logging.info("Modo Orquestador: Omitiendo verificacion de lock (.lock)")
    
    try:
        CREDENTIALS_DIR.mkdir(exist_ok=True)
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        client_secret_files = _list_client_secret_files()
        if not client_secret_files:
            logging.error("No hay client_secret en credentials/.")
            return
        credential_slots = _build_credential_pool()
        if not credential_slots:
            logging.error(
                "No hay llaves con token OAuth compatible en credentials/. "
                "Renueva o genera tokens antes de reintentar."
            )
            return

        # --- MODO SINGLE FILE ---
        if args.single_file:
            single_path = Path(args.single_file)
            if not single_path.exists():
                logging.error("Archivo --single-file no existe: %s", args.single_file)
                return
            pending = [single_path]
            logging.info("Modo single-file: %s", single_path.name)
        else:
            pending = list_pending_teasers(source_video_stem=args.source_video)
            if not pending:
                msg = f"No hay teasers pendientes para procesar{f' (filtro: {args.source_video})' if args.source_video else ''}."
                logging.info(msg)
                return

        logging.info("Se encontraron %s videos de descarte para procesar como Teasers.", len(pending))

        # Seleccionar credenciales disponibles con Quota
        current_idx = 0
        while current_idx < len(credential_slots):
            current_slot = credential_slots[current_idx]
            if current_slot["legacy_index"] < args.key:
                current_idx += 1
                continue
            if not is_client_available(current_slot["client_name"]):
                current_idx += 1
                continue
            break

        if current_idx >= len(credential_slots):
            logging.warning("Todas las llaves con token compatible estan agotadas por hoy (QUOTA).")
            return

        current_slot = credential_slots[current_idx]
        youtube = get_authenticated_service(current_slot["legacy_index"])

        yt_schedule = fetch_yt_schedule(youtube)
        active_threads = []

        for file_path in pending:
            if STOP_FILE.exists():
                logging.warning("Archivo STOP_TEASER detectado. Deteniendo.")
                break

            logging.info("-" * 40)
            
            clean_name, teaser_num = extract_teaser_sequence(file_path.name)
            if not clean_name:
                clean_name = file_path.stem
            logging.info("Serie teaser detectada: %s -> teaser #%s", clean_name, teaser_num)
                
            # Emular estructura base de uploader e inyectar el override puro
            video_record = {
                "path": str(file_path), 
                "filename": file_path.name,
                "title_override": f"{clean_name} #PW #teaser #{teaser_num}"
            }
            enrich_video_record(video_record, include_probe=True)
            
            # Generalmente, los Slices de IG duran menos de 60s, serán "short"
            v_type = "short" if video_record.get("type") == "short" else "video"
            next_date = get_next_publish_date(yt_schedule)

            # Optimizacion faststart nativa
            apply_faststart(file_path)

            upload_metadata = build_upload_metadata(video_record, config)

            result = None
            verifier_thread = None
            while True:
                ret_val = upload_video(
                    youtube, file_path, upload_metadata, next_date, current_slot["legacy_index"], True
                )
                
                if ret_val == "QUOTA_EXCEEDED":
                    logging.info("Cuota agotada en %s. Rotando...", current_slot["client_name"])
                    update_quota_status(current_slot["client_name"])
                    current_idx += 1
                    while current_idx < len(credential_slots) and not is_client_available(credential_slots[current_idx]["client_name"]):
                        current_idx += 1
                    if current_idx >= len(credential_slots):
                        logging.error("Se agotaron todas las llaves con token compatible por hoy.")
                        return
                    current_slot = credential_slots[current_idx]
                    youtube = get_authenticated_service(current_slot["legacy_index"])
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

                # Marker inmediato de subida completada (no espera processing de YT)
                if args.single_file:
                    marker_path = Path(args.state_dir) / f"{file_path.name}.uploaded"
                    marker_path.parent.mkdir(parents=True, exist_ok=True)
                    marker_path.write_text(datetime.now().isoformat())

                date_key = next_date.strftime("%Y-%m-%d")
                if date_key not in yt_schedule:
                    yt_schedule[date_key] = {"videos": 0, "shorts": 0}
                if v_type == "short": yt_schedule[date_key]["shorts"] += 1
                else: yt_schedule[date_key]["videos"] += 1
            else:
                logging.error("Fallo en la subida de %s, se omitira por hoy.", file_path.name)

        logging.info("Ciclo de Teasers de subida completado.")
        if active_threads:
            logging.info("Esperando que las %s tareas criticas en paralelo terminen de confirmar el procesamiento HD en Youtube...", len(active_threads))
            for t in active_threads:
                t.join()
            logging.info("Todas las confirmaciones paralelas terminaron y se evacuo la carpeta.")

    finally:
        # Solo limpiar el lock si nosotros lo creamos
        if not args.from_orchestrator:
            if lock_file.exists():
                lock_file.unlink()

if __name__ == "__main__":
    main()
