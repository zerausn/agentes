import json
import logging
import os
import socket
import threading
import time
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "meta_uploader.log"
GRAPH_API_ROOT = "https://graph.facebook.com"
REQUEST_TIMEOUT_DEFAULT = 60
IG_CONTAINER_WAIT_SECONDS = 10
IG_CONTAINER_MAX_POLLS = 30
FB_STATUS_WAIT_SECONDS = 10
FB_STATUS_MAX_POLLS = 30
UPLOAD_STALL_CHECK_SECONDS = int(os.environ.get("META_UPLOAD_STALL_CHECK_SECONDS", "10"))
UPLOAD_STALL_MAX_NO_PROGRESS_CHECKS = int(os.environ.get("META_UPLOAD_STALL_MAX_NO_PROGRESS_CHECKS", "2"))


class ProgressFile:
    def __init__(self, filename, mode, callback=None):
        self._file = open(filename, mode)
        self._size = os.path.getsize(filename)
        self._seen = 0
        self._callback = callback

    def __len__(self):
        return self._size

    def read(self, n=-1):
        chunk = self._file.read(n)
        self._seen += len(chunk)
        if self._callback:
            self._callback(self._seen, self._size)
        return chunk

    def close(self):
        self._file.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __getattr__(self, name):
        return getattr(self._file, name)


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
                total,
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
                    if stalled_seconds >= UPLOAD_STALL_CHECK_SECONDS:
                        self._no_progress_checks += 1
                    else:
                        self._no_progress_checks = 0
                else:
                    if total_runtime >= UPLOAD_STALL_CHECK_SECONDS:
                        self._no_progress_checks += 1
                    else:
                        self._no_progress_checks = 0

                should_alert = (
                    self._no_progress_checks >= UPLOAD_STALL_MAX_NO_PROGRESS_CHECKS and not self._alerted
                )
                seen = self._last_seen
                total = self._last_total

            if should_alert:
                diagnostics = diagnose_meta_connectivity()
                status_line = diagnostics["summary"]
                if has_progress:
                    logging.warning(
                        "%s parece detenida: sin avance en %ss (%s verificaciones de 10s). "
                        "Ultimo progreso: %s/%s bytes. %s",
                        self.label,
                        stalled_seconds,
                        self._no_progress_checks,
                        seen,
                        total or "?",
                        status_line,
                    )
                else:
                    logging.warning(
                        "%s parece detenida: no inicio transferencia visible en %ss "
                        "(%s verificaciones de 10s). %s",
                        self.label,
                        total_runtime,
                        self._no_progress_checks,
                        status_line,
                    )

                with self._lock:
                    self._alerted = True


def _socket_probe(host, port, timeout=5):
    started = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            elapsed_ms = int((time.monotonic() - started) * 1000)
            return True, elapsed_ms, None
    except OSError as exc:
        return False, None, str(exc)


def diagnose_meta_connectivity():
    internet_ok, internet_ms, internet_error = _socket_probe("8.8.8.8", 53)
    meta_ok, meta_ms, meta_error = _socket_probe("graph.facebook.com", 443)

    if internet_ok and meta_ok:
        summary = (
            "No parece una caida total de wifi/internet; la red sigue viva y Meta responde "
            f"a nivel de socket (internet={internet_ms}ms, meta={meta_ms}ms)."
        )
    elif internet_ok and not meta_ok:
        summary = (
            "Hay conectividad general, pero el socket hacia Meta no respondio. "
            f"Error Meta: {meta_error}."
        )
    elif not internet_ok and meta_ok:
        summary = (
            "La conectividad general luce inestable, aunque Meta responde por socket. "
            f"Internet error: {internet_error}; Meta={meta_ms}ms."
        )
    else:
        summary = (
            "Parece una caida o degradacion fuerte de conectividad local: "
            f"internet error={internet_error}; meta error={meta_error}."
        )

    return {
        "internet_ok": internet_ok,
        "internet_ms": internet_ms,
        "internet_error": internet_error,
        "meta_ok": meta_ok,
        "meta_ms": meta_ms,
        "meta_error": meta_error,
        "summary": summary,
    }


def _strip_quotes(value):
    return value.strip().strip('"').strip("'")


def manual_load_env():
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    with open(env_path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key and key not in os.environ:
                os.environ[key] = _strip_quotes(value)


if load_dotenv:
    load_dotenv(BASE_DIR / ".env")

manual_load_env()

GRAPH_API_VERSION = os.environ.get("META_GRAPH_API_VERSION", "v19.0").strip() or "v19.0"
REQUEST_TIMEOUT = int(os.environ.get("META_REQUEST_TIMEOUT", REQUEST_TIMEOUT_DEFAULT))
META_PAGE_TOKEN = os.environ.get("META_PAGE_TOKEN", "")
IG_ACCESS_TOKEN = os.environ.get("META_IG_USER_TOKEN", "") or META_PAGE_TOKEN
META_FB_PAGE_TOKEN = os.environ.get("META_FB_PAGE_TOKEN", "")
FB_APP_ID = os.environ.get("META_APP_ID", "")
IG_USER_ID = os.environ.get("META_IG_USER_ID", "")
FB_PAGE_ID = os.environ.get("META_FB_PAGE_ID", "")


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()],
)


def _masked(value, visible=5):
    if not value:
        return "missing"
    if len(value) <= visible:
        return value
    return f"{value[:visible]}..."


def graph_url(path):
    return f"{GRAPH_API_ROOT}/{GRAPH_API_VERSION}/{path.lstrip('/')}"


def _request_json(method, url, *, params=None, data=None, headers=None):
    try:
        response = requests.request(
            method,
            url,
            params=params,
            data=data,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        logging.error("Error HTTP en %s %s: %s", method, url, exc)
        return None

    try:
        payload = response.json()
    except ValueError:
        payload = {"raw_text": response.text}

    if not isinstance(payload, dict):
        payload = {"data": payload}

    payload.setdefault("_http_status", response.status_code)

    if response.status_code >= 400:
        logging.error(
            "Meta devolvio HTTP %s en %s %s: %s",
            response.status_code,
            method,
            url,
            json.dumps(payload, ensure_ascii=False),
        )

    return payload


def _log_progress(prefix):
    def callback(seen, total):
        pct = (seen / total) * 100 if total else 0
        print(f"\r{prefix}: {pct:5.1f}% ({seen}/{total} bytes)", end="", flush=True)

    return callback


def _post_binary(url, headers, file_path, progress_prefix):
    progress_callback = _log_progress(progress_prefix)
    watchdog = UploadWatchdog(progress_prefix)

    def combined_callback(seen, total):
        progress_callback(seen, total)
        watchdog.update(seen, total)

    watchdog.start()
    with ProgressFile(file_path, "rb", callback=combined_callback) as handle:
        try:
            response = requests.post(url, headers=headers, data=handle, timeout=REQUEST_TIMEOUT)
        except requests.RequestException as exc:
            print()
            logging.error("Error subiendo binario hacia %s: %s", url, exc)
            watchdog.stop()
            return None

    watchdog.stop()
    print()

    try:
        payload = response.json()
    except ValueError:
        payload = {"raw_text": response.text}

    if response.status_code >= 400:
        logging.error(
            "Fallo subida binaria HTTP %s hacia %s: %s",
            response.status_code,
            url,
            json.dumps(payload, ensure_ascii=False),
        )
        return None

    if not isinstance(payload, dict):
        payload = {"data": payload}
    payload.setdefault("_http_status", response.status_code)
    return payload


def check_ig_publish_limit():
    """
    Consulta el limite real reportado por Meta para no depender de un numero fijo.
    """
    if not IG_USER_ID or not IG_ACCESS_TOKEN:
        logging.warning("No hay credenciales suficientes para consultar el limite de IG.")
        return True

    payload = _request_json(
        "GET",
        graph_url(f"{IG_USER_ID}/content_publishing_limit"),
        params={"fields": "config,quota_usage", "access_token": IG_ACCESS_TOKEN},
    )
    if not payload:
        return True

    rows = payload.get("data") or []
    if not rows:
        logging.warning("Meta no devolvio datos de quota_usage para Instagram.")
        return True

    row = rows[0]
    usage = int(row.get("quota_usage", 0))
    config = row.get("config") or {}
    quota_total = None
    if isinstance(config, dict):
        for candidate in ("quota_total", "max_quota", "limit"):
            value = config.get(candidate)
            if isinstance(value, int):
                quota_total = value
                break

    if quota_total is None:
        logging.info(
            "Uso actual de Instagram: %s publicaciones API en la ventana movil. "
            "Meta no devolvio un total numerico claro; se conserva el fallback preventivo.",
            usage,
        )
        return usage < 99

    logging.info("Uso actual de Instagram: %s/%s publicaciones API.", usage, quota_total)
    return usage < quota_total


def create_ig_reel_container(caption="", share_to_feed=True):
    payload = {
        "media_type": "REELS",
        "upload_type": "resumable",
        "access_token": IG_ACCESS_TOKEN,
        "share_to_feed": "true" if share_to_feed else "false",
    }
    if caption:
        payload["caption"] = caption

    result = _request_json("POST", graph_url(f"{IG_USER_ID}/media"), data=payload)
    if not result:
        return None

    creation_id = result.get("id")
    if not creation_id:
        logging.error("No se recibio creation_id al crear el contenedor de IG: %s", result)
        return None

    logging.info("Contenedor de Instagram creado: %s", creation_id)
    return creation_id


def upload_ig_binary(creation_id, video_path):
    file_size = os.path.getsize(video_path)
    rupload_url = f"https://rupload.facebook.com/ig-api-upload/{GRAPH_API_VERSION}/{creation_id}"
    headers = {
        "Authorization": f"OAuth {IG_ACCESS_TOKEN}",
        "offset": "0",
        "file_size": str(file_size),
        "Content-Type": "application/octet-stream",
    }
    result = _post_binary(rupload_url, headers, video_path, "Subiendo IG")
    return result is not None


def wait_for_ig_container(creation_id):
    """
    Polling del contenedor de Instagram hasta que quede listo para publicar.
    """
    url = graph_url(str(creation_id))
    params = {"fields": "status_code,status", "access_token": IG_ACCESS_TOKEN}

    for _ in range(IG_CONTAINER_MAX_POLLS):
        result = _request_json("GET", url, params=params)
        if not result:
            time.sleep(IG_CONTAINER_WAIT_SECONDS)
            continue

        status_code = (result.get("status_code") or "").upper()
        if status_code in {"FINISHED", "PUBLISHED"}:
            logging.info("Contenedor IG %s listo para publicar.", creation_id)
            return True
        if status_code in {"ERROR", "EXPIRED"}:
            logging.error("Contenedor IG %s fallo con estado %s.", creation_id, status_code)
            return False

        logging.info("Contenedor IG %s aun procesando: %s", creation_id, status_code or "UNKNOWN")
        time.sleep(IG_CONTAINER_WAIT_SECONDS)

    logging.error("Timeout esperando el contenedor IG %s.", creation_id)
    return False


def publish_ig_container(creation_id):
    """
    Publica un contenedor ya procesado en Instagram.
    """
    payload = {"creation_id": creation_id, "access_token": IG_ACCESS_TOKEN}
    result = _request_json("POST", graph_url(f"{IG_USER_ID}/media_publish"), data=payload)
    if not result:
        return None

    media_id = result.get("id")
    if media_id:
        logging.info("Instagram acepto la publicacion. Media ID: %s", media_id)
        return media_id

    logging.error("Meta no devolvio id al publicar el contenedor de IG: %s", result)
    return None


def upload_ig_reel_resumable(video_path, caption, *, share_to_feed=True):
    """
    Flujo oficial resumible para video en Instagram usando `media_type=REELS`.
    Segun la documentacion oficial y los errores actuales de Meta, el valor
    `VIDEO` ya no debe usarse para publicar video en el feed; por eso este
    helper cubre tanto Reel como video compartido al feed segun `share_to_feed`.

    1. Crear contenedor
    2. Subir binario
    3. Esperar FINISHED
    4. Publicar con media_publish
    """
    if not IG_USER_ID or not IG_ACCESS_TOKEN:
        logging.error("Faltan META_IG_USER_ID o el token de Instagram.")
        return None

    file_path = Path(video_path)
    if not file_path.exists():
        logging.error("No existe el archivo para subir a Instagram: %s", file_path)
        return None

    creation_id = create_ig_reel_container(caption, share_to_feed=share_to_feed)
    if not creation_id:
        return None

    if not upload_ig_binary(str(creation_id), str(file_path)):
        return None

    if not wait_for_ig_container(str(creation_id)):
        return None

    return publish_ig_container(str(creation_id))


def upload_ig_feed_video_resumable(video_path, caption):
    """
    Publica un video de Instagram compartido al feed usando el mismo flujo
    documentado de `REELS` con `share_to_feed=true`.
    """
    return upload_ig_reel_resumable(video_path, caption, share_to_feed=True)


def _normalize_fb_status(status_blob):
    if not isinstance(status_blob, dict):
        return "", "", ""

    video_status = str(status_blob.get("video_status", "")).lower()
    uploading_phase = status_blob.get("uploading_phase") or {}
    processing_phase = status_blob.get("processing_phase") or {}
    publishing_phase = status_blob.get("publishing_phase") or {}

    processing_state = str(processing_phase.get("status", "")).lower()
    publishing_state = str(publishing_phase.get("status", "")).lower()
    uploading_state = str(uploading_phase.get("status", "")).lower()

    return video_status, processing_state or uploading_state, publishing_state


def wait_for_fb_video_status(video_id):
    """
    Valida el estado asincrono de videos/Reels de Facebook.
    Devuelve:
    - True si Meta reporta listo/publicado
    - False si Meta reporta error terminal
    - None si la subida fue aceptada pero no se pudo confirmar antes del timeout
    """
    url = graph_url(str(video_id))
    params = {"fields": "status", "access_token": META_FB_PAGE_TOKEN}

    for _ in range(FB_STATUS_MAX_POLLS):
        result = _request_json("GET", url, params=params)
        if not result:
            time.sleep(FB_STATUS_WAIT_SECONDS)
            continue

        status_blob = result.get("status") or {}
        video_status, processing_state, publishing_state = _normalize_fb_status(status_blob)
        compact_status = {
            "video_status": video_status,
            "processing": processing_state,
            "publishing": publishing_state,
        }

        if video_status in {"ready", "published", "complete"} or publishing_state in {"complete", "published"}:
            logging.info("Facebook confirmo el video %s: %s", video_id, compact_status)
            return True

        if any(state in {"error", "failed"} for state in compact_status.values() if state):
            logging.error("Facebook reporto error terminal en %s: %s", video_id, compact_status)
            return False

        logging.info("Facebook aun procesa %s: %s", video_id, compact_status)
        time.sleep(FB_STATUS_WAIT_SECONDS)

    logging.warning("Facebook acepto la subida %s, pero no se pudo confirmar estado final a tiempo.", video_id)
    return None


def _validate_facebook_credentials(require_app_id=False):
    if not FB_PAGE_ID or not META_FB_PAGE_TOKEN:
        logging.error("Faltan META_FB_PAGE_ID o META_FB_PAGE_TOKEN.")
        return False
    if require_app_id and not FB_APP_ID:
        logging.error("Falta META_APP_ID para el flujo de file handles.")
        return False
    return True


def _upload_facebook_video_binary(video_id, video_path):
    file_size = os.path.getsize(video_path)
    rupload_url = f"https://rupload.facebook.com/video-upload/{GRAPH_API_VERSION}/{video_id}"
    headers = {
        "Authorization": f"OAuth {META_FB_PAGE_TOKEN}",
        "offset": "0",
        "file_offset": "0",
        "file_size": str(file_size),
        "Content-Type": "application/octet-stream",
    }
    result = _post_binary(rupload_url, headers, video_path, "Subiendo FB")
    return result is not None


def _finalize_facebook_upload(endpoint, payload, video_id):
    result = _request_json("POST", graph_url(f"{FB_PAGE_ID}/{endpoint}"), data=payload)
    if not result:
        return None

    if result.get("success") or result.get("video_id") or result.get("id"):
        status_result = wait_for_fb_video_status(video_id)
        if status_result is False:
            return None
        if status_result is None:
            logging.warning("Se devuelve el video_id %s como aceptado, pero aun sin confirmacion final.", video_id)
            return video_id

        logging.info("Facebook confirmo la publicacion del video %s.", video_id)
        return video_id

    logging.error("Facebook no confirmo el finish del video %s: %s", video_id, result)
    return None


def upload_fb_reel(video_path, caption):
    """
    Flujo asincrono de Facebook Reels:
    1. start
    2. upload binario
    3. finish
    4. polling de estado
    """
    if not _validate_facebook_credentials():
        return None

    file_path = Path(video_path)
    if not file_path.exists():
        logging.error("No existe el archivo para subir a Facebook Reels: %s", file_path)
        return None

    start_result = _request_json(
        "POST",
        graph_url(f"{FB_PAGE_ID}/video_reels"),
        data={"upload_phase": "start", "access_token": META_FB_PAGE_TOKEN},
    )
    if not start_result:
        return None

    video_id = start_result.get("video_id")
    if not video_id:
        logging.error("Facebook no devolvio video_id en start de Reel: %s", start_result)
        return None

    if not _upload_facebook_video_binary(str(video_id), str(file_path)):
        return None

    finish_payload = {
        "upload_phase": "finish",
        "video_id": video_id,
        "video_state": "PUBLISHED",
        "access_token": META_FB_PAGE_TOKEN,
    }
    if caption:
        finish_payload["description"] = caption

    return _finalize_facebook_upload("video_reels", finish_payload, str(video_id))


def upload_fb_video_standard(video_path, description):
    """
    Flujo de videos estandar de pagina usando start/upload/finish y validacion.
    """
    if not _validate_facebook_credentials():
        return None

    file_path = Path(video_path)
    if not file_path.exists():
        logging.error("No existe el archivo para subir a videos de Facebook: %s", file_path)
        return None

    start_result = _request_json(
        "POST",
        graph_url(f"{FB_PAGE_ID}/videos"),
        data={"upload_phase": "start", "access_token": META_FB_PAGE_TOKEN},
    )
    if not start_result:
        return None

    video_id = start_result.get("video_id")
    if not video_id:
        logging.error("Facebook no devolvio video_id en start de video: %s", start_result)
        return None

    if not _upload_facebook_video_binary(str(video_id), str(file_path)):
        return None

    finish_payload = {
        "upload_phase": "finish",
        "video_id": video_id,
        "access_token": META_FB_PAGE_TOKEN,
    }
    if description:
        finish_payload["description"] = description

    return _finalize_facebook_upload("videos", finish_payload, str(video_id))


def upload_fb_file_handle(video_path, description, scheduled_publish_time=None):
    """
    Flujo avanzado de file handle para videos grandes.
    Soporta programación si se provee scheduled_publish_time (timestamp UNIX).
    """
    if not _validate_facebook_credentials(require_app_id=True):

        return None

    file_path = Path(video_path)
    if not file_path.exists():
        logging.error("No existe el archivo para subir por file handle: %s", file_path)
        return None

    file_size = file_path.stat().st_size
    init_result = _request_json(
        "POST",
        graph_url(f"{FB_APP_ID}/uploads"),
        data={
            "file_name": file_path.name,
            "file_length": file_size,
            "access_token": META_FB_PAGE_TOKEN,
        },
    )
    if not init_result:
        return None

    upload_id = init_result.get("id")
    if not upload_id:
        logging.error("Meta no devolvio upload_id para file handle: %s", init_result)
        return None

    headers = {"Authorization": f"OAuth {META_FB_PAGE_TOKEN}", "offset": "0"}
    upload_result = _post_binary(graph_url(str(upload_id)), headers, str(file_path), "Subiendo FB handle")
    if not upload_result:
        return None

    file_handle = upload_result.get("h")
    if not file_handle:
        logging.error("Meta no devolvio el handle de archivo esperado: %s", upload_result)
        return None

    payload_publish = {
        "fbuploader_video_file_chunk": file_handle,
        "description": description,
        "access_token": META_FB_PAGE_TOKEN,
    }
    if scheduled_publish_time:
        payload_publish["published"] = "false"
        payload_publish["scheduled_publish_time"] = str(scheduled_publish_time)

    publish_result = _request_json(
        "POST",
        graph_url(f"{FB_PAGE_ID}/videos"),
        data=payload_publish,
    )
    if not publish_result:
        return None

    video_id = publish_result.get("id")
    if not video_id:
        logging.error("Facebook acepto el handle pero no devolvio id final: %s", publish_result)
        return None

    status_result = wait_for_fb_video_status(str(video_id))
    if status_result is False:
        return None
    if status_result is None:
        logging.warning("File handle aceptado para %s, pero sin confirmacion final aun.", video_id)
        return str(video_id)

    logging.info("Facebook confirmo el video publicado via file handle: %s", video_id)
    return str(video_id)


def main():
    logging.info(
        "Meta uploader listo. FB page=%s | IG user=%s | IG token=%s | API=%s",
        _masked(FB_PAGE_ID),
        _masked(IG_USER_ID),
        "user" if os.environ.get("META_IG_USER_TOKEN") else "fallback_page",
        GRAPH_API_VERSION,
    )

    if not META_PAGE_TOKEN and not os.environ.get("META_IG_USER_TOKEN"):
        logging.error("Falta token para Instagram. Configura META_IG_USER_TOKEN o META_PAGE_TOKEN.")
        return

    if not check_ig_publish_limit():
        logging.error("Meta reporta que el limite actual de Instagram ya fue alcanzado.")
        return

    logging.info(
        "El agente base no auto-publica por si solo. Usa los scripts de cola o integra "
        "meta_calendar.json cuando el flujo completo quede cerrado."
    )


if __name__ == "__main__":
    main()
