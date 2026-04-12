import hashlib
import json
import logging
import os
import socket
import threading
import time
from pathlib import Path

import requests
import subprocess
from requests.adapters import HTTPAdapter

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "meta_uploader.log"
FB_LOG_FILE = BASE_DIR / "meta_uploader_facebook.log"
IG_LOG_FILE = BASE_DIR / "meta_uploader_instagram.log"
FB_UPLOAD_CHECKPOINT_DIR = BASE_DIR / ".fb_upload_checkpoints"
GRAPH_API_ROOT = "https://graph.facebook.com"
GRAPH_VIDEO_ROOT = "https://graph-video.facebook.com"
REQUEST_TIMEOUT_DEFAULT = 60
IG_CONTAINER_WAIT_SECONDS = 10
IG_CONTAINER_MAX_POLLS = 30
FB_STATUS_WAIT_SECONDS = 10
FB_STATUS_MAX_POLLS = 30
UPLOAD_STALL_CHECK_SECONDS = int(os.environ.get("META_UPLOAD_STALL_CHECK_SECONDS", "10"))
UPLOAD_STALL_MAX_NO_PROGRESS_CHECKS = int(os.environ.get("META_UPLOAD_STALL_MAX_NO_PROGRESS_CHECKS", "2"))
HTTP_RETRY_ATTEMPTS = int(os.environ.get("META_HTTP_RETRY_ATTEMPTS", "3"))
HTTP_RETRY_BACKOFF_SECONDS = float(os.environ.get("META_HTTP_RETRY_BACKOFF_SECONDS", "3"))
UPLOAD_BINARY_RETRY_ATTEMPTS = int(os.environ.get("META_UPLOAD_BINARY_RETRY_ATTEMPTS", "2"))
FB_UPLOAD_CHUNK_BYTES = int(os.environ.get("META_FB_UPLOAD_CHUNK_BYTES", str(8 * 1024 * 1024)))
FB_UPLOAD_MIN_CHUNK_BYTES = int(os.environ.get("META_FB_UPLOAD_MIN_CHUNK_BYTES", str(1 * 1024 * 1024)))
HTTP_SESSION_POOL_CONNECTIONS = int(os.environ.get("META_HTTP_SESSION_POOL_CONNECTIONS", "8"))
HTTP_SESSION_POOL_MAXSIZE = int(os.environ.get("META_HTTP_SESSION_POOL_MAXSIZE", "8"))
PROGRESS_LOG_MIN_INTERVAL_SECONDS = float(os.environ.get("META_PROGRESS_LOG_MIN_INTERVAL_SECONDS", "1.5"))
PROGRESS_LOG_MIN_BYTES = int(os.environ.get("META_PROGRESS_LOG_MIN_BYTES", str(8 * 1024 * 1024)))

_LAST_OPERATION_STATUS = {
    "kind": "unknown",
    "phase": "",
    "message": "",
    "transient": False,
    "watchdog_alerted": False,
}
_HTTP_THREAD_LOCAL = threading.local()


import threading
import uuid

def _write_json_atomic(path, payload):
    temp_path = path.with_suffix(f"{path.suffix}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
        os.replace(temp_path, path)
    except PermissionError as e:
        logging.warning("No se pudo escribir el checkpoint atómico por bloqueo de permisos en %s: %s", temp_path.name, e)
        # Fallback to direct write just in case
        try:
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, ensure_ascii=False)
        except Exception:
            pass
    except Exception as e:
        logging.error("Fallo inesperado al escribir json atómico: %s", e)
        try:
            if temp_path.exists():
                temp_path.unlink()
        except:
            pass


def _fb_checkpoint_path(page_endpoint, file_path):
    FB_UPLOAD_CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    resolved = str(Path(file_path).resolve())
    hash_key = hashlib.sha1(f"{page_endpoint}|{resolved}".encode("utf-8")).hexdigest()[:12]
    endpoint_tag = page_endpoint.replace("/", "_")
    safe_name = f"{endpoint_tag}__{Path(file_path).stem}__{hash_key}.json"
    return FB_UPLOAD_CHECKPOINT_DIR / safe_name


def _load_fb_upload_checkpoint(page_endpoint, file_path, file_size):
    checkpoint_path = _fb_checkpoint_path(page_endpoint, file_path)
    if not checkpoint_path.exists():
        return None
    try:
        with open(checkpoint_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception as exc:
        logging.warning("No se pudo leer checkpoint de Facebook %s: %s", checkpoint_path.name, exc)
        return None

    if payload.get("file_path") != str(Path(file_path).resolve()):
        return None
    if int(payload.get("file_size") or 0) != int(file_size):
        return None
    if payload.get("page_endpoint") != page_endpoint:
        return None
    if not payload.get("video_id") or not payload.get("upload_session_id"):
        return None
    return payload


def _save_fb_upload_checkpoint(page_endpoint, file_path, *, file_size, video_id, upload_session_id, current_offset):
    checkpoint_path = _fb_checkpoint_path(page_endpoint, file_path)
    payload = {
        "page_endpoint": page_endpoint,
        "file_path": str(Path(file_path).resolve()),
        "file_name": Path(file_path).name,
        "file_size": int(file_size),
        "video_id": str(video_id),
        "upload_session_id": str(upload_session_id),
        "current_offset": int(current_offset),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    _write_json_atomic(checkpoint_path, payload)


def _delete_fb_upload_checkpoint(page_endpoint, file_path):
    checkpoint_path = _fb_checkpoint_path(page_endpoint, file_path)
    if checkpoint_path.exists():
        checkpoint_path.unlink()


class KeywordRoutingFilter(logging.Filter):
    def __init__(self, keywords):
        super().__init__()
        self.keywords = tuple(keyword.lower() for keyword in keywords)

    def filter(self, record):
        message = record.getMessage().lower()
        return any(keyword in message for keyword in self.keywords)


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


class RangeFile:
    def __init__(self, filename, start_offset, end_offset, callback=None):
        self._file = open(filename, "rb")
        self._file.seek(start_offset)
        self._remaining = max(0, end_offset - start_offset)
        self._seen = 0
        self._total = self._remaining
        self._callback = callback

    def read(self, n=-1):
        if self._remaining <= 0:
            return b""
        if n is None or n < 0 or n > self._remaining:
            n = self._remaining
        chunk = self._file.read(n)
        self._remaining -= len(chunk)
        self._seen += len(chunk)
        if self._callback:
            self._callback(self._seen, self._total)
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
        self._ever_alerted = False

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
                    self._ever_alerted = True

    def had_alert(self):
        with self._lock:
            return self._ever_alerted


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


def _set_operation_status(kind, phase, message, *, transient=False, watchdog_alerted=False):
    _LAST_OPERATION_STATUS.update(
        {
            "kind": kind,
            "phase": phase,
            "message": message,
            "transient": transient,
            "watchdog_alerted": watchdog_alerted,
        }
    )


def get_last_operation_status():
    return dict(_LAST_OPERATION_STATUS)


def _flatten_exception(exc):
    messages = [repr(exc)]
    current = exc.__cause__ or exc.__context__
    depth = 0
    while current and depth < 3:
        messages.append(repr(current))
        current = current.__cause__ or current.__context__
        depth += 1
    return " | ".join(messages)


def _classify_request_exception(exc):
    text = _flatten_exception(exc).lower()
    if "name resolution" in text or "getaddrinfo failed" in text:
        return "dns_resolution", True
    if "timed out" in text or "timeout" in text:
        return "timeout", True
    if (
        "connection aborted" in text
        or "connection reset" in text
        or "10054" in text
        or "remote disconnected" in text
        or "broken pipe" in text
    ):
        return "connection_reset", True
    if "invalid argument" in text or "oserror(22" in text or "[errno 22]" in text:
        return "local_socket_error", True
    if "ssl" in text or "tls" in text:
        return "ssl_error", True
    return "request_exception", True


def _should_retry_http_status(status_code):
    return status_code in {408, 409, 425, 429, 500, 502, 503, 504}


def _retry_delay_seconds(attempt_index):
    return HTTP_RETRY_BACKOFF_SECONDS * attempt_index


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


def _configure_logging():
    root = logging.getLogger()
    if getattr(root, "_meta_uploader_configured", False):
        return

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handlers = [
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ]

    fb_handler = logging.FileHandler(FB_LOG_FILE, encoding="utf-8")
    fb_handler.addFilter(
        KeywordRoutingFilter(
            (
                "facebook",
                "subiendo fb",
                " fb ",
                "fb reel",
                "facebook reel",
                "facebook transfer",
            )
        )
    )
    handlers.append(fb_handler)

    ig_handler = logging.FileHandler(IG_LOG_FILE, encoding="utf-8")
    ig_handler.addFilter(
        KeywordRoutingFilter(
            (
                "instagram",
                "contenedor ig",
                " ig ",
                "ig story",
                "ig reel",
                "ig feed",
            )
        )
    )
    handlers.append(ig_handler)

    root.setLevel(logging.INFO)
    for handler in handlers:
        handler.setFormatter(formatter)
        root.addHandler(handler)

    root._meta_uploader_configured = True


_configure_logging()


def _masked(value, visible=5):
    if not value:
        return "missing"
    if len(value) <= visible:
        return value
    return f"{value[:visible]}..."


def graph_url(path):
    return f"{GRAPH_API_ROOT}/{GRAPH_API_VERSION}/{path.lstrip('/')}"


def graph_video_url(path):
    return f"{GRAPH_VIDEO_ROOT}/{GRAPH_API_VERSION}/{path.lstrip('/')}"


def _iter_graph_collection(path_or_url, *, access_token, fields, page_size=100, max_pages=5):
    next_url = path_or_url if str(path_or_url).startswith("http") else graph_url(path_or_url)
    params = {
        "access_token": access_token,
        "fields": fields,
        "limit": str(page_size),
    }
    pages = 0

    while next_url and pages < max_pages:
        result = _request_json("GET", next_url, params=params)
        if not result:
            return

        for item in result.get("data") or []:
            yield item

        pages += 1
        next_url = (result.get("paging") or {}).get("next")
        params = None


def find_existing_facebook_video_by_caption_marker(marker, *, page_size=25, max_pages=2):
    marker = (marker or "").strip()
    if not marker or not FB_PAGE_ID or not META_FB_PAGE_TOKEN:
        return None

    for item in _iter_graph_collection(
        f"{FB_PAGE_ID}/videos",
        access_token=META_FB_PAGE_TOKEN,
        fields="id,description,created_time,published,scheduled_publish_time",
        page_size=page_size,
        max_pages=max_pages,
    ):
        description = str(item.get("description") or "")
        if marker in description:
            return {
                "id": str(item.get("id") or ""),
                "description": description,
                "created_time": item.get("created_time"),
                "published": bool(item.get("published")),
                "scheduled_publish_time": item.get("scheduled_publish_time"),
            }
    return None


def find_existing_instagram_media_by_caption_marker(marker, *, page_size=25, max_pages=2):
    marker = (marker or "").strip()
    if not marker or not IG_USER_ID or not IG_ACCESS_TOKEN:
        return None

    for item in _iter_graph_collection(
        f"{IG_USER_ID}/media",
        access_token=IG_ACCESS_TOKEN,
        fields="id,caption,timestamp,media_type,media_product_type",
        page_size=page_size,
        max_pages=max_pages,
    ):
        caption = str(item.get("caption") or "")
        if marker in caption:
            return {
                "id": str(item.get("id") or ""),
                "caption": caption,
                "timestamp": item.get("timestamp"),
                "media_type": item.get("media_type"),
                "media_product_type": item.get("media_product_type"),
            }
    return None


def get_latest_scheduled_facebook_date():
    """
    Consulta la API de Graph para obtener el timestamp ('scheduled_publish_time')
    del post programado más lejano en el tiempo de la página actual.
    Retorna un timestamp entero (ej. 1778259600) o None si no hay nada programado.
    """
    if not FB_PAGE_ID or not META_FB_PAGE_TOKEN:
        return None

    max_time = 0
    for item in _iter_graph_collection(
        f"{FB_PAGE_ID}/scheduled_posts",
        access_token=META_FB_PAGE_TOKEN,
        fields="id,scheduled_publish_time",
        page_size=50,
        max_pages=10
    ):
        st_time = item.get("scheduled_publish_time")
        if st_time:
            max_time = max(max_time, int(st_time))

    return max_time if max_time > 0 else None


def _get_http_session():
    session = getattr(_HTTP_THREAD_LOCAL, "session", None)
    if session is None:
        session = requests.Session()
        adapter = HTTPAdapter(
            pool_connections=HTTP_SESSION_POOL_CONNECTIONS,
            pool_maxsize=HTTP_SESSION_POOL_MAXSIZE,
            max_retries=0,
        )
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update({"Connection": "keep-alive"})
        _HTTP_THREAD_LOCAL.session = session
    return session


def _request_json(method, url, *, params=None, data=None, headers=None):
    for attempt in range(1, HTTP_RETRY_ATTEMPTS + 1):
        try:
            response = _get_http_session().request(
                method,
                url,
                params=params,
                data=data,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            error_kind, transient = _classify_request_exception(exc)
            if transient and attempt < HTTP_RETRY_ATTEMPTS:
                delay = _retry_delay_seconds(attempt)
                logging.warning(
                    "Error HTTP transitorio (%s) en %s %s. Reintento %s/%s en %.1fs. Detalle: %s",
                    error_kind,
                    method,
                    url,
                    attempt,
                    HTTP_RETRY_ATTEMPTS,
                    delay,
                    exc,
                )
                time.sleep(delay)
                continue

            logging.exception("Error HTTP en %s %s: %s", method, url, exc)
            _set_operation_status(error_kind, "request_json", str(exc), transient=transient)
            return None

        try:
            payload = response.json()
        except ValueError:
            payload = {"raw_text": response.text}

        if not isinstance(payload, dict):
            payload = {"data": payload}

        payload.setdefault("_http_status", response.status_code)

        if response.status_code >= 400:
            if _should_retry_http_status(response.status_code) and attempt < HTTP_RETRY_ATTEMPTS:
                delay = _retry_delay_seconds(attempt)
                logging.warning(
                    "Meta devolvio HTTP %s en %s %s. Reintento %s/%s en %.1fs.",
                    response.status_code,
                    method,
                    url,
                    attempt,
                    HTTP_RETRY_ATTEMPTS,
                    delay,
                )
                time.sleep(delay)
                continue

            logging.error(
                "Meta devolvio HTTP %s en %s %s: %s",
                response.status_code,
                method,
                url,
                json.dumps(payload, ensure_ascii=False),
            )
            _set_operation_status(
                f"http_{response.status_code}",
                "request_json",
                json.dumps(payload, ensure_ascii=False),
                transient=_should_retry_http_status(response.status_code),
            )

        return payload

    return None


def _log_progress(prefix):
    last_emit = {"seen": -PROGRESS_LOG_MIN_BYTES, "time": 0.0}

    def _safe_print(message="", *, end="\n"):
        try:
            print(message, end=end, flush=True)
        except OSError:
            return

    def callback(seen, total):
        now = time.monotonic()
        if total and seen < total:
            bytes_advanced = seen - last_emit["seen"]
            elapsed = now - last_emit["time"]
            if bytes_advanced < PROGRESS_LOG_MIN_BYTES and elapsed < PROGRESS_LOG_MIN_INTERVAL_SECONDS:
                return
        pct = (seen / total) * 100 if total else 0
        last_emit["seen"] = seen
        last_emit["time"] = now
        _safe_print(f"\r{prefix}: {pct:5.1f}% ({seen}/{total} bytes)", end="")

    return callback


def _post_binary(url, headers, file_path, progress_prefix):
    for attempt in range(1, UPLOAD_BINARY_RETRY_ATTEMPTS + 1):
        progress_callback = _log_progress(progress_prefix)
        watchdog = UploadWatchdog(progress_prefix)

        def combined_callback(seen, total):
            progress_callback(seen, total)
            watchdog.update(seen, total)

        watchdog.start()
        response = None
        try:
            with ProgressFile(file_path, "rb", callback=combined_callback) as handle:
                response = _get_http_session().post(
                    url,
                    headers=headers,
                    data=handle,
                    timeout=REQUEST_TIMEOUT,
                )
        except requests.RequestException as exc:
            try:
                print()
            except OSError:
                pass
            watchdog.stop()
            watchdog_alerted = watchdog.had_alert()
            error_kind, transient = _classify_request_exception(exc)
            if transient and attempt < UPLOAD_BINARY_RETRY_ATTEMPTS:
                delay = _retry_delay_seconds(attempt)
                logging.warning(
                    "Error transitorio subiendo binario (%s) hacia %s. Reintento %s/%s en %.1fs. Detalle: %s",
                    error_kind,
                    url,
                    attempt,
                    UPLOAD_BINARY_RETRY_ATTEMPTS,
                    delay,
                    exc,
                )
                _set_operation_status(error_kind, "binary_upload", str(exc), transient=True, watchdog_alerted=watchdog_alerted)
                time.sleep(delay)
                continue

            logging.exception("Error subiendo binario hacia %s: %s", url, exc)
            _set_operation_status(error_kind, "binary_upload", str(exc), transient=transient, watchdog_alerted=watchdog_alerted)
            return None
        finally:
            watchdog.stop()

        try:
            print()
        except OSError:
            pass

        try:
            payload = response.json()
        except ValueError:
            payload = {"raw_text": response.text}

        if response.status_code >= 400:
            if _should_retry_http_status(response.status_code) and attempt < UPLOAD_BINARY_RETRY_ATTEMPTS:
                delay = _retry_delay_seconds(attempt)
                logging.warning(
                    "Fallo subida binaria HTTP %s hacia %s. Reintento %s/%s en %.1fs.",
                    response.status_code,
                    url,
                    attempt,
                    UPLOAD_BINARY_RETRY_ATTEMPTS,
                    delay,
                )
                _set_operation_status(
                    f"http_{response.status_code}",
                    "binary_upload",
                    json.dumps(payload, ensure_ascii=False),
                    transient=True,
                    watchdog_alerted=watchdog.had_alert(),
                )
                time.sleep(delay)
                continue

            logging.error(
                "Fallo subida binaria HTTP %s hacia %s: %s",
                response.status_code,
                url,
                json.dumps(payload, ensure_ascii=False),
            )
            _set_operation_status(
                f"http_{response.status_code}",
                "binary_upload",
                json.dumps(payload, ensure_ascii=False),
                transient=_should_retry_http_status(response.status_code),
                watchdog_alerted=watchdog.had_alert(),
            )
            return None

        if not isinstance(payload, dict):
            payload = {"data": payload}
        payload.setdefault("_http_status", response.status_code)
        _set_operation_status(
            "success",
            "binary_upload",
            f"HTTP {response.status_code}",
            transient=False,
            watchdog_alerted=watchdog.had_alert(),
        )
        return payload

    return None


def _read_chunk_bytes(file_path, start_offset, end_offset, callback=None):
    size = max(0, end_offset - start_offset)
    with open(file_path, "rb") as handle:
        handle.seek(start_offset)
        chunk = handle.read(size)
    if callback:
        callback(len(chunk), size)
    return chunk, size


def _post_transfer_chunk(url, data, file_path, start_offset, end_offset, progress_prefix):
    for attempt in range(1, UPLOAD_BINARY_RETRY_ATTEMPTS + 1):
        progress_callback = _log_progress(progress_prefix)
        watchdog = UploadWatchdog(progress_prefix)

        def combined_callback(seen, total):
            progress_callback(seen, total)
            watchdog.update(seen, total)

        watchdog.start()
        response = None
        try:
            chunk, expected_size = _read_chunk_bytes(file_path, start_offset, end_offset, callback=combined_callback)
            if not chunk:
                logging.error(
                    "No se pudo leer un chunk valido para Facebook transfer en el rango %s-%s.",
                    start_offset,
                    end_offset,
                )
                _set_operation_status(
                    "empty_chunk_read",
                    "transfer_chunk",
                    f"Rango {start_offset}-{end_offset}",
                    transient=False,
                    watchdog_alerted=watchdog.had_alert(),
                )
                return None

            files = {
                "video_file_chunk": (Path(file_path).name, chunk, "video/mp4"),
            }
            response = _get_http_session().post(
                url,
                data=data,
                files=files,
                timeout=(30, REQUEST_TIMEOUT),
            )
        except requests.RequestException as exc:
            try:
                print()
            except OSError:
                pass
            watchdog.stop()
            watchdog_alerted = watchdog.had_alert()
            error_kind, transient = _classify_request_exception(exc)
            if transient and attempt < UPLOAD_BINARY_RETRY_ATTEMPTS:
                delay = _retry_delay_seconds(attempt)
                logging.warning(
                    "Error transitorio subiendo chunk (%s) hacia %s. Reintento %s/%s en %.1fs. Detalle: %s",
                    error_kind,
                    url,
                    attempt,
                    UPLOAD_BINARY_RETRY_ATTEMPTS,
                    delay,
                    exc,
                )
                _set_operation_status(
                    error_kind,
                    "transfer_chunk",
                    str(exc),
                    transient=True,
                    watchdog_alerted=watchdog_alerted,
                )
                time.sleep(delay)
                continue

            logging.exception("Error subiendo chunk hacia %s: %s", url, exc)
            _set_operation_status(
                error_kind,
                "transfer_chunk",
                str(exc),
                transient=transient,
                watchdog_alerted=watchdog_alerted,
            )
            return None
        finally:
            watchdog.stop()

        try:
            print()
        except OSError:
            pass

        try:
            payload = response.json()
        except ValueError:
            payload = {"raw_text": response.text}

        if response.status_code >= 400:
            if _should_retry_http_status(response.status_code) and attempt < UPLOAD_BINARY_RETRY_ATTEMPTS:
                delay = _retry_delay_seconds(attempt)
                logging.warning(
                    "Fallo chunk HTTP %s hacia %s. Reintento %s/%s en %.1fs.",
                    response.status_code,
                    url,
                    attempt,
                    UPLOAD_BINARY_RETRY_ATTEMPTS,
                    delay,
                )
                _set_operation_status(
                    f"http_{response.status_code}",
                    "transfer_chunk",
                    json.dumps(payload, ensure_ascii=False),
                    transient=True,
                    watchdog_alerted=watchdog.had_alert(),
                )
                time.sleep(delay)
                continue

            logging.error(
                "Fallo chunk HTTP %s hacia %s: %s",
                response.status_code,
                url,
                json.dumps(payload, ensure_ascii=False),
            )
            _set_operation_status(
                f"http_{response.status_code}",
                "transfer_chunk",
                json.dumps(payload, ensure_ascii=False),
                transient=_should_retry_http_status(response.status_code),
                watchdog_alerted=watchdog.had_alert(),
            )
            return None

        if not isinstance(payload, dict):
            payload = {"data": payload}
        payload.setdefault("_http_status", response.status_code)
        _set_operation_status(
            "success",
            "transfer_chunk",
            f"HTTP {response.status_code}",
            transient=False,
            watchdog_alerted=watchdog.had_alert(),
        )
        return payload

    return None


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


def _create_ig_video_container(media_type, caption="", share_to_feed=None):
    payload = {
        "media_type": media_type,
        "upload_type": "resumable",
        "access_token": IG_ACCESS_TOKEN,
    }
    # Estandarizacion API 2026: Tanto Feed como Reels usan el tipo REELS.
    if media_type == "REELS" and share_to_feed is not None:
        payload["share_to_feed"] = "true" if share_to_feed else "false"
    
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


def create_ig_reel_container(caption="", share_to_feed=True):
    return _create_ig_video_container("REELS", caption=caption, share_to_feed=share_to_feed)


def create_ig_story_container():
    return _create_ig_video_container("STORIES")


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


def upload_ig_story_video_resumable(video_path):
    """
    Flujo oficial resumible para video en Instagram Stories usando
    `media_type=STORIES`.
    """
    if not IG_USER_ID or not IG_ACCESS_TOKEN:
        logging.error("Faltan META_IG_USER_ID o el token de Instagram.")
        return None

    file_path = Path(video_path)
    if not file_path.exists():
        logging.error("No existe el archivo para subir Story a Instagram: %s", file_path)
        return None

    creation_id = create_ig_story_container()
    if not creation_id:
        return None

    if not upload_ig_binary(str(creation_id), str(file_path)):
        return None

    if not wait_for_ig_container(str(creation_id)):
        return None

    return publish_ig_container(str(creation_id))


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


def wait_for_fb_video_status(video_id, *, allow_scheduled=False):
    """
    Valida el estado asincrono de videos/Reels de Facebook.
    Devuelve:
    - True si Meta reporta listo/publicado
    - False si Meta reporta error terminal
    - "scheduled" si Meta confirma que el video quedo programado
    - None si la subida fue aceptada pero no se pudo confirmar antes del timeout
    """
    url = graph_url(str(video_id))
    params = {"fields": "status,published,scheduled_publish_time", "access_token": META_FB_PAGE_TOKEN}

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

        scheduled_publish_time = result.get("scheduled_publish_time")
        if allow_scheduled and scheduled_publish_time:
            logging.info(
                "Facebook confirmo el video %s como programado para %s.",
                video_id,
                scheduled_publish_time,
            )
            return "scheduled"

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


def _start_fb_upload(page_endpoint, file_size):
    return _request_json(
        "POST",
        graph_url(page_endpoint),
        data={
            "upload_phase": "start",
            "file_size": str(file_size),
            "access_token": META_FB_PAGE_TOKEN,
        },
    )


def _transfer_fb_upload(page_endpoint, upload_session_id, file_path, *, video_id, current_offset=0):
    file_size = os.path.getsize(file_path)
    target_chunk_bytes = max(FB_UPLOAD_MIN_CHUNK_BYTES, FB_UPLOAD_CHUNK_BYTES)
    chunk_bytes = target_chunk_bytes
    consecutive_successes = 0
    current_offset = max(0, min(int(current_offset), file_size))

    if current_offset:
        logging.info(
            "Reanudando transferencia de Facebook desde %s/%s bytes para %s.",
            current_offset,
            file_size,
            Path(file_path).name,
        )

    _save_fb_upload_checkpoint(
        page_endpoint,
        file_path,
        file_size=file_size,
        video_id=video_id,
        upload_session_id=upload_session_id,
        current_offset=current_offset,
    )

    while current_offset < file_size:
        end_offset = min(current_offset + chunk_bytes, file_size)
        logging.info(
            "Facebook transfer chunk %s-%s/%s para %s",
            current_offset,
            end_offset,
            file_size,
            Path(file_path).name,
        )
        started_at = time.monotonic()
        previous_offset = current_offset
        transfer_payload = {
            "upload_phase": "transfer",
            "upload_session_id": upload_session_id,
            "start_offset": str(current_offset),
            "access_token": META_FB_PAGE_TOKEN,
        }
        result = _post_transfer_chunk(
            graph_video_url(page_endpoint),
            transfer_payload,
            file_path,
            current_offset,
            end_offset,
            f"Subiendo FB {current_offset}-{end_offset}",
        )
        if not result:
            last_status = get_last_operation_status()
            if last_status.get("transient") and chunk_bytes > FB_UPLOAD_MIN_CHUNK_BYTES:
                previous_chunk = chunk_bytes
                chunk_bytes = max(FB_UPLOAD_MIN_CHUNK_BYTES, chunk_bytes // 2)
                consecutive_successes = 0
                logging.warning(
                    "Reduciendo chunk de Facebook de %s a %s bytes tras fallo transitorio (%s).",
                    previous_chunk,
                    chunk_bytes,
                    last_status.get("kind"),
                )
                continue
            return None

        next_start = result.get("start_offset")
        next_end = result.get("end_offset")
        try:
            if next_start is not None:
                current_offset = int(next_start)
            elif next_end is not None:
                current_offset = int(next_end)
            else:
                current_offset = end_offset
        except (TypeError, ValueError):
            current_offset = end_offset

        elapsed = max(time.monotonic() - started_at, 0.001)
        confirmed_bytes = max(0, current_offset - previous_offset)
        throughput_mb_s = confirmed_bytes / elapsed / (1024 * 1024)
        logging.info(
            "Facebook transfer confirmado hasta %s/%s bytes para %s en %.2fs (%.2f MB/s).",
            current_offset,
            file_size,
            Path(file_path).name,
            elapsed,
            throughput_mb_s,
        )
        _save_fb_upload_checkpoint(
            page_endpoint,
            file_path,
            file_size=file_size,
            video_id=video_id,
            upload_session_id=upload_session_id,
            current_offset=current_offset,
        )

        consecutive_successes += 1
        if chunk_bytes < target_chunk_bytes and consecutive_successes >= 3:
            increased_chunk = min(target_chunk_bytes, chunk_bytes * 2)
            if increased_chunk != chunk_bytes:
                logging.info(
                    "Aumentando chunk de Facebook de %s a %s bytes tras %s transferencias estables.",
                    chunk_bytes,
                    increased_chunk,
                    consecutive_successes,
                )
                chunk_bytes = increased_chunk
            consecutive_successes = 0

    return {"success": True, "upload_session_id": upload_session_id}


def _finish_fb_upload(endpoint, video_id, description, upload_session_id=None, publish=True, scheduled_publish_time=None):
    finish_payload = {
        "upload_phase": "finish",
        "video_id": video_id,
        "access_token": META_FB_PAGE_TOKEN,
    }
    if upload_session_id:
        finish_payload["upload_session_id"] = upload_session_id
    if description:
        finish_payload["description"] = description
    if scheduled_publish_time:
        finish_payload["scheduled_publish_time"] = str(int(scheduled_publish_time))
        if endpoint == "video_reels":
            finish_payload["video_state"] = "SCHEDULED"
        else:
            finish_payload["published"] = "false"
    elif publish:
        finish_payload["video_state"] = "PUBLISHED"
    return _finalize_facebook_upload(
        endpoint,
        finish_payload,
        str(video_id),
        allow_scheduled=bool(scheduled_publish_time),
    )


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


def _finalize_facebook_upload(endpoint, payload, video_id, *, allow_scheduled=False):
    result = _request_json("POST", graph_url(f"{FB_PAGE_ID}/{endpoint}"), data=payload)
    if not result:
        return None

    if result.get("success") or result.get("video_id") or result.get("id"):
        status_result = wait_for_fb_video_status(video_id, allow_scheduled=allow_scheduled)
        if status_result is False:
            return None
        if status_result == "scheduled":
            logging.info("Facebook confirmo la programacion del video %s.", video_id)
            _set_operation_status("scheduled_remote", "facebook_finish", str(video_id), transient=False)
            return video_id
        if status_result is None:
            logging.warning("Se devuelve el video_id %s como aceptado, pero aun sin confirmacion final.", video_id)
            _set_operation_status("accepted_without_confirmation", "facebook_finish", str(video_id), transient=False)
            return video_id

        success_msg = f"Facebook confirmo la publicacion del video {video_id}."
        if payload.get("file_name"):
            success_msg = f"Facebook confirmo la publicacion del video {video_id} para {payload['file_name']}."
            
        logging.info(success_msg)
        _set_operation_status("success", "facebook_finish", str(video_id), transient=False)
        return video_id

    logging.error("Facebook no confirmo el finish del video %s: %s", video_id, result)
    _set_operation_status("finish_not_confirmed", "facebook_finish", json.dumps(result, ensure_ascii=False), transient=False)
    return None


def upload_fb_reel(video_path, caption, scheduled_publish_time=None, _allow_fresh_retry=True, is_draft=False):
    """
    Flujo asincrono de Facebook Reels:
    1. start
    2. upload binario
    3. finish
    4. polling de estado
    """
    if not _validate_facebook_credentials():
        return None

    if is_draft:
        scheduled_publish_time = None

    file_path = Path(video_path)
    if not file_path.exists():
        logging.error("No existe el archivo para subir a Facebook Reels: %s", file_path)
        return None

    file_size = file_path.stat().st_size
    page_endpoint = f"{FB_PAGE_ID}/video_reels"
    checkpoint = _load_fb_upload_checkpoint(page_endpoint, str(file_path), file_size)
    if checkpoint:
        video_id = checkpoint["video_id"]
        upload_session_id = checkpoint["upload_session_id"]
        current_offset = int(checkpoint.get("current_offset") or 0)
        logging.info(
            "Se reutiliza checkpoint de Facebook Reel para %s con sesion %s en offset %s.",
            file_path.name,
            upload_session_id,
            current_offset,
        )
    else:
        start_result = _start_fb_upload(page_endpoint, file_size)
        if not start_result:
            return None

        video_id = start_result.get("video_id")
        if not video_id:
            logging.error("Facebook no devolvio video_id en start de Reel: %s", start_result)
            return None

        upload_session_id = start_result.get("upload_session_id")
        if not upload_session_id:
            logging.error("Facebook no devolvio upload_session_id en start de Reel: %s", start_result)
            return None
        current_offset = 0

    if not _transfer_fb_upload(
        page_endpoint,
        str(upload_session_id),
        str(file_path),
        video_id=str(video_id),
        current_offset=current_offset,
    ):
        if checkpoint and _allow_fresh_retry and not get_last_operation_status().get("transient"):
            logging.warning(
                "No se pudo reanudar el checkpoint de Facebook Reel para %s. Se reinicia una sesion nueva.",
                file_path.name,
            )
            _delete_fb_upload_checkpoint(page_endpoint, str(file_path))
            return upload_fb_reel(video_path, caption, _allow_fresh_retry=False)
        return None

    result = _finish_fb_upload(
        "video_reels",
        str(video_id),
        caption,
        str(upload_session_id),
        publish=not is_draft,
        scheduled_publish_time=scheduled_publish_time,
    )
    if result:
        _delete_fb_upload_checkpoint(page_endpoint, str(file_path))
    elif checkpoint and _allow_fresh_retry and not get_last_operation_status().get("transient"):
        logging.warning(
            "Finish rechazo la sesion de Facebook Reel reanudada de %s. Se limpia el checkpoint caducado y se reinicia.",
            file_path.name,
        )
        _delete_fb_upload_checkpoint(page_endpoint, str(file_path))
        return upload_fb_reel(video_path, caption, scheduled_publish_time=scheduled_publish_time, _allow_fresh_retry=False, is_draft=is_draft)
    return result


def upload_fb_video_standard(video_path, description, scheduled_publish_time=None, _allow_fresh_retry=True, is_draft=False):
    """
    Flujo de videos estandar de pagina usando start/upload/finish y validacion.
    """
    if not _validate_facebook_credentials():
        return None

    if is_draft:
        scheduled_publish_time = None

    file_path = Path(video_path)
    if not file_path.exists():
        logging.error("No existe el archivo para subir a videos de Facebook: %s", file_path)
        return None

    file_size = file_path.stat().st_size
    page_endpoint = f"{FB_PAGE_ID}/videos"
    checkpoint = _load_fb_upload_checkpoint(page_endpoint, str(file_path), file_size)
    if checkpoint:
        video_id = checkpoint["video_id"]
        upload_session_id = checkpoint["upload_session_id"]
        current_offset = int(checkpoint.get("current_offset") or 0)
        logging.info(
            "Se reutiliza checkpoint de Facebook Post para %s con sesion %s en offset %s.",
            file_path.name,
            upload_session_id,
            current_offset,
        )
    else:
        start_result = _start_fb_upload(page_endpoint, file_size)
        if not start_result:
            return None

        video_id = start_result.get("video_id")
        if not video_id:
            logging.error("Facebook no devolvio video_id en start de video: %s", start_result)
            return None
        upload_session_id = start_result.get("upload_session_id")
        if not upload_session_id:
            logging.error("Facebook no devolvio upload_session_id en start de video: %s", start_result)
            return None
        current_offset = 0

    if not _transfer_fb_upload(
        page_endpoint,
        str(upload_session_id),
        str(file_path),
        video_id=str(video_id),
        current_offset=current_offset,
    ):
        if checkpoint and _allow_fresh_retry and not get_last_operation_status().get("transient"):
            logging.warning(
                "No se pudo reanudar el checkpoint de Facebook Post para %s. Se reinicia una sesion nueva.",
                file_path.name,
            )
            _delete_fb_upload_checkpoint(page_endpoint, str(file_path))
            return upload_fb_video_standard(video_path, description, scheduled_publish_time=scheduled_publish_time, _allow_fresh_retry=False, is_draft=is_draft)
        return None

    result = _finish_fb_upload(
        "videos",
        str(video_id),
        description,
        str(upload_session_id),
        publish=not is_draft,
        scheduled_publish_time=scheduled_publish_time,
    )
    if result:
        _delete_fb_upload_checkpoint(page_endpoint, str(file_path))
    elif checkpoint and _allow_fresh_retry and not get_last_operation_status().get("transient"):
        logging.warning(
            "Finish rechazo la sesion de Facebook Post reanudada de %s. Se limpia el checkpoint caducado y se reinicia.",
            file_path.name,
        )
        _delete_fb_upload_checkpoint(page_endpoint, str(file_path))
        return upload_fb_video_standard(video_path, description, scheduled_publish_time=scheduled_publish_time, _allow_fresh_retry=False, is_draft=is_draft)
    return result


def upload_fb_file_handle(video_path, description, scheduled_publish_time=None, is_draft=False):
    """
    Flujo avanzado de file handle para videos grandes.
    Soporta programación si se provee scheduled_publish_time (timestamp UNIX).
    """
    if not _validate_facebook_credentials(require_app_id=True):
        return None
        
    if is_draft:
        scheduled_publish_time = None

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
    elif is_draft:
        payload_publish["published"] = "false"

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

    status_result = wait_for_fb_video_status(str(video_id), allow_scheduled=bool(scheduled_publish_time))
    if status_result is False:
        return None
    if status_result == "scheduled":
        logging.info(
            "Facebook acepto el video %s y quedo programado para %s.",
            video_id,
            scheduled_publish_time,
        )
        _set_operation_status(
            "scheduled_remote",
            "facebook_schedule",
            str(video_id),
            transient=False,
        )
        return str(video_id)
    if status_result is None:
        logging.warning("File handle aceptado para %s, pero sin confirmacion final aun.", video_id)
        return str(video_id)

    logging.info("Facebook confirmo el video %s publicado via file handle para %s.", video_id, file_path.name)
    return str(video_id)


def republish_draft_to_scheduled(video_id, scheduled_unix_time):
    """
    Toma un Borrador alojado en Facebook (Draft) y le asigna su scheduled_publish_time
    para graduarlo a Post Programado, completando la estrategia de goteo.
    """
    if not _validate_facebook_credentials():
        return False
        
    url = graph_url(str(video_id))
    payload = {
        "scheduled_publish_time": str(scheduled_unix_time),
        "access_token": META_FB_PAGE_TOKEN,
    }
    
    # Hacer request por fuera de la maquinaria de finish
    import requests
    try:
        resp = requests.post(url, data=payload, timeout=30)
        if resp.ok and resp.json().get("success"):
            _set_operation_status(
                "scheduled_remote", "facebook_republish", f"Borrador promovido exitosamente a: {scheduled_unix_time}"
            )
            return str(video_id)
        else:
            logging.error("Fallo al graduar el Borrador %s: %s", video_id, resp.text[:300])
            try:
                error_data = resp.json()
                _set_operation_status(
                    "http_400", "facebook_republish", f"Error API: {error_data.get('error', {}).get('message', 'Desconocido')}"
                )
            except Exception:
                _set_operation_status("http_500", "facebook_republish", "Respuesta irreconocible")
            return False
    except Exception as e:
        logging.error("Excepcion graduating draft %s: %s", video_id, e)
        _set_operation_status("request_exception", "facebook_republish", str(e))
        return False


def get_facebook_page_feed(limit=10, after=None):
    """
    Obtiene las publicaciones publicadas mas recientes de la pagina de Facebook.
    Soporta paginacion mediante el cursor 'after'.
    """
    if not FB_PAGE_ID or not META_FB_PAGE_TOKEN:
        logging.error("Faltan FB_PAGE_ID o META_FB_PAGE_TOKEN para leer el feed.")
        return None
    
    url = graph_url(f"{FB_PAGE_ID}/published_posts")
    params = {
        "fields": "id,message,created_time,full_picture,attachments{media,type,subattachments}",
        "limit": limit,
        "access_token": META_FB_PAGE_TOKEN
    }
    if after:
        params["after"] = after
        
    return _request_json("GET", url, params=params)


def create_ig_media_container_from_url(media_url, media_type="IMAGE", caption="", target="FEED"):
    """
    Crea un contenedor de Instagram a partir de una URL publica (Meta-a-Meta).
    Targets soportados: FEED, REELS, STORIES.
    """
    if not IG_USER_ID or not IG_ACCESS_TOKEN:
        logging.error("Faltan IG_USER_ID o token de Instagram para crear contenedor via URL.")
        return None

    payload = {
        "caption": caption,
        "access_token": IG_ACCESS_TOKEN
    }

    # Normalizacion de media_type para Meta
    is_video = media_type.upper() in {"VIDEO", "REELS"}

    if target == "REELS":
        if not is_video:
            logging.error("No se puede crear Reel desde una imagen estatica via API.")
            return None
        payload["video_url"] = media_url
        payload["media_type"] = "REELS"
        payload["share_to_feed"] = "true"
    elif target == "STORIES":
        payload["media_type"] = "STORIES"
        if is_video:
            payload["video_url"] = media_url
        else:
            payload["image_url"] = media_url
    else: # Default: FEED
        if is_video:
            payload["video_url"] = media_url
            payload["media_type"] = "REELS"
            payload["share_to_feed"] = "true"
        else:
            payload["image_url"] = media_url

    result = _request_json("POST", graph_url(f"{IG_USER_ID}/media"), data=payload)
    if not result:
        return None

    creation_id = result.get("id")
    if not creation_id:
        logging.error("No se recibio creation_id al crear contenedor IG %s via URL: %s", target, result)
        return None

    logging.info("Contenedor IG (%s) via URL creado: %s", target, creation_id)
    return creation_id


def get_instagram_user_feed(limit=25):
    """
    Obtiene las ultimas publicaciones del feed de Instagram para procesos de reconciliacion.
    """
    if not IG_USER_ID or not IG_ACCESS_TOKEN:
        logging.error("Faltan IG_USER_ID o token de Instagram para leer el feed.")
        return None
    
    url = graph_url(f"{IG_USER_ID}/media")
    params = {
        "fields": "id,caption,media_type,timestamp,permalink",
        "limit": limit,
        "access_token": IG_ACCESS_TOKEN
    }
    return _request_json("GET", url, params=params)


def ensure_ig_compatibility(file_path, max_duration=None, force_recode=False):
    """
    Optimiza el archivo para IG:
    1. Si excede 300MB -> Aplica Fast Slice (-fs 290M).
    2. Si es para Stories -> Aplica recorte de tiempo (-t 60).
    3. Si force_recode -> Transcodifica a perfil High 4.1 (Deep Clean).
    4. Por defecto -> Remuxea (-c copy) para "limpiar" el contenedor.
    """
    if not file_path or not os.path.exists(file_path):
        return file_path
    
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    needs_size_slice = file_size_mb > 300
    
    # Si el archivo ya es compatible y NO necesitamos recortar duracion ni forzar recode, saltamos.
    if "ig_compat_" in os.path.basename(file_path) and not force_recode and not max_duration:
        return file_path

    if max_duration:
        logging.info("Aplicando Recorte Temporal (Max %ss) a %s...", 
                     max_duration, os.path.basename(file_path))
    elif force_recode:
        logging.info("Aplicando Deep Clean (Transcoding) a %s para estabilidad total...", 
                     os.path.basename(file_path))
    else:
        logging.info("Aplicando Quick Clean (Remuxing) a %s para estabilidad Meta...", 
                     os.path.basename(file_path))
    
    temp_dir = Path(file_path).parent / ".ig_temp"
    temp_dir.mkdir(exist_ok=True)
    
    # Nombrado de salida evadiendo recursividad y colisiones por duracion
    duration_tag = f"_{max_duration}s" if max_duration else ""
    prefix = "slice" if max_duration else "ig_compat"
    output_path = temp_dir / f"{prefix}{duration_tag}_{os.path.basename(file_path)}"
    
    # Base del comando (SIEMPRE con faststart para streaming eficiente en Meta)
    cmd = ["ffmpeg", "-y", "-i", file_path, "-movflags", "+faststart"]
    
    if force_recode:
        # Perfil de compatibilidad maxima para Instagram (Deep Clean 2.0)
        cmd += [
            "-c:v", "libx264",
            "-preset", "veryfast",    # Mas estable que ultrafast para Meta
            "-crf", "23",             # Calidad balanceada
            "-profile:v", "high",
            "-level:v", "4.1",
            "-pix_fmt", "yuv420p",    # Vital para IG
            "-bf", "2",               # B-frames controlados para streaming
            "-flags", "+cgop",        # Closed GOP (vital para Meta)
            "-g", "60",               # Keyframes frecuentes para estabilidad
            "-color_range", "tv",     # Rango de color estandar
            "-c:a", "aac",
            "-b:a", "128k",
            "-ac", "2",
            "-ar", "44100"
        ]
    else:
        # Copia directa (Quick Clean)
        cmd += ["-c", "copy"]

    
    if max_duration:
        cmd += ["-t", str(max_duration)]
    if needs_size_slice:
        cmd += ["-fs", "290M"]
        
    cmd.append(str(output_path))
    
    try:
        # Capturamos stderr para diagnostico real
        proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
        logging.info("Fast Slice completado: %s (%.2f MB)", 
                     output_path.name, os.path.getsize(output_path)/(1024*1024))
        return str(output_path)
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr or str(e)
        logging.error("Fallo ffmpeg Fast Slice: %s. Se intentara subir original.", error_msg.strip())
        return file_path
    except Exception as e:
        logging.error("Fallo inesperado en Fast Slice: %s", e)
        return file_path

def probe_video(video_path):
    """
    Inspecciona metadatos tecnicos de un video usando ffprobe.
    """
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,duration,codec_name,avg_frame_rate,pix_fmt,bit_rate",
        "-of", "json",
        video_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        stream = (data.get("streams") or [{}])[0]
        return {
            "path": video_path,
            "filename": Path(video_path).name,
            "size_bytes": Path(video_path).stat().st_size,
            "duration_seconds": float(stream.get("duration") or 0),
            "width": int(stream.get("width") or 0),
            "height": int(stream.get("height") or 0),
            "codec_name": (stream.get("codec_name") or "").lower(),
            "avg_frame_rate": stream.get("avg_frame_rate") or "0/0",
            "pix_fmt": stream.get("pix_fmt") or "",
            "bit_rate": int(stream.get("bit_rate") or 0),
        }
    except Exception as exc:
        logging.error("No se pudo inspeccionar %s: %s", video_path, exc)
        return {
            "path": video_path,
            "filename": Path(video_path).name,
            "size_bytes": Path(video_path).stat().st_size if Path(video_path).exists() else 0,
            "duration_seconds": 0,
            "width": 0,
            "height": 0,
            "codec_name": "",
            "avg_frame_rate": "0/0",
            "pix_fmt": "",
            "bit_rate": 0,
        }





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
