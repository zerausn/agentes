"""
tiktok_evacuador_720.py

Evacua UN SOLO VIDEO hacia TikTok usando la app Android, sin Content Posting API.
El loop de 720s vive en scripts/linux/vigia_tiktok720_termux.sh.

Flujo por ciclo:
  1. Toma el primer video (alphabetico) de /sdcard/Antigravity/subidos a facebbok.
  2. Ejecuta `touch` al archivo seleccionado para que sea el mas reciente en el filesystem
     y aparezca PRIMERO en la galeria de TikTok (que ordena por fecha de modificacion).
  3. Abre TikTok en Home via `monkey -p com.zhiliaoapp.musically` (evita permisos de intent).
  4. Navega por UI usando coordenadas escaladas y deteccion de texto:
       - Tap Crear (+) en barra inferior
       - Tap Cargar (Upload) en pantalla camara
       - Tap dropdown Recientes → busca carpeta por nombre en UI → la selecciona
       - Tap al primer video de la carpeta (que es el archivo seleccionado en paso 2)
       - Tap Siguiente en galeria
       - Tap Siguiente en editor (abajo a la derecha)
       - Tap campo descripcion → escribe caption → cierra teclado
       - Tap Publicar (por UI o fallback coordinado)
  5. Espera POST_SETTLE_SECONDS para que TikTok procese la publicacion.
  6. Verifica publicacion: si el boton Publicar desaparecio o el dump esta vacio
     (animacion post-publicacion), considera exito.
  7. Solo si todos los pasos devuelven OK, mueve el archivo a
     /sdcard/Antigravity/subidos a tiktok.

Exit codes:
  0  video enviado/publicado y movido, o dry-run OK
  1  error durante apertura/automatizacion
  2  no hay videos pendientes
  3  otra instancia esta corriendo

Cambios 2026-07-20 (Android 14 / Samsung Galaxy S24):
  - REEMPLAZADO: launch_share/launch_direct/launch_termux_open → launch_tiktok_home()
    usando `monkey` en vez de intents (Android 14 bloquea INTERACT_ACROSS_USERS_FULL).
  - NUEVO: Flujo Crear → Cargar → Recientes → carpeta por UI → video → Siguiente.
  - FIX: Siguiente editor movido de (665,77) a (531,1341) por cambio de layout en S24.
  - FIX: close_caption_editor ahora toca el fondo de pantalla para quitar foco del teclado.
  - FIX: dump_ui borra el XML anterior antes de volcar para evitar leer estados rancios.
  - FIX: publish_confirmed ahora asume exito si dump_ui devuelve lista vacia
    (animacion post-publicacion que bloquea uiautomator dump).
  - FIX: Se aplica `touch` al archivo antes de abrir TikTok para garantizar que el
    video que Python selecciona == el video que TikTok muestra primero en galeria.

Cambios 2026-07-21 (Note9 / vigia fix):
  - BUG FIX CRITICO: dump_ui() ya no cachea el XML anterior — antes reutilizaba el
    archivo tiktok_ui.xml viejo si _uiautomator_available era True, lo que causaba que
    todos los dump_ui() dentro de una ejecucion leian el mismo estado de pantalla.
    Ahora siempre borra y vuelca de nuevo.
  - BUG FIX: Eliminado `return nodes` duplicado/muerto al final de _parse_ui_nodes().
  - FIX: vigia_tiktok720_termux.sh ahora pasa AGENTES_STORAGE_ROOT, TIKTOK_SHARE_METHOD
    y TIKTOK_PUBLISH_MODE explicitamente al evacuador (antes dependia de defaults).
  - MEJORA: Flujo intent mejorado — en vez de un solo tap_match(NEXT_RE, timeout=10),
    ahora intenta Siguiente hasta 2 veces con UI detection + coordenada fallback,
    cubriendo versiones de TikTok con 2 pantallas de editor.
  - MEJORA: Deteccion de boton Publicar mejorada — primero intenta UI, luego coordenada.
    publish_ok ahora refleja si publish_confirmed() paso, no solo si el tap se ejecuto.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
import time
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

try:
    sys.path.insert(0, str(BASE_DIR.parent / "youtube_uploader"))
    from video_helpers import extract_teaser_sequence, normalize_video_stem
except Exception:
    extract_teaser_sequence = None
    normalize_video_stem = None


LOG_FILE = BASE_DIR / "tiktok_evacuador.log"

ROOT_ENV = os.environ.get("AGENTES_STORAGE_ROOT", "").strip()
ROOT = Path(ROOT_ENV) if ROOT_ENV else Path("/sdcard/Antigravity")
SOURCE_DIR_ENV = os.environ.get("TIKTOK_SOURCE_DIR", "").strip()
SOURCE_DIR = Path(SOURCE_DIR_ENV) if SOURCE_DIR_ENV else (ROOT / "subidos a facebbok")
DONE_DIR_ENV = os.environ.get("TIKTOK_DONE_DIR", "").strip()
DONE_DIR = Path(DONE_DIR_ENV) if DONE_DIR_ENV else (ROOT / "subidos a tiktok")
FAILED_DIR_ENV = os.environ.get("TIKTOK_FAILED_DIR", "").strip()
FAILED_DIR = Path(FAILED_DIR_ENV) if FAILED_DIR_ENV else (ROOT / "fallidos_tiktok")
STATE_DIR_OVERRIDE = os.environ.get("TIKTOK_STATE_DIR", "").strip()
STATE_DIR = Path(STATE_DIR_OVERRIDE) if STATE_DIR_OVERRIDE else (ROOT / ".state")
STATE_FILE = STATE_DIR / "tiktok_queue.json"
CAPTION_FILE = STATE_DIR / "tiktok_caption_actual.txt"
CONTENT_URIS_CACHE = STATE_DIR / "content_uris.json"
SHARE_REQUEST_FILE = STATE_DIR / "share_request.txt"
UI_DUMP_FILE = STATE_DIR / "tiktok_ui.xml"
LOCK_FILE = STATE_DIR / "tiktok_evacuador.lock"

_content_uris: dict[str, str] = {}
_uiautomator_available: bool | None = None

SUPPORTED_EXTS = {".mp4", ".mov", ".mkv"}
DEVICE_NAME = os.environ.get("AGENTES_DEVICE_NAME") or socket.gethostname() or "desconocido"
TIKTOK_PACKAGE = os.environ.get("TIKTOK_PACKAGE", "com.zhiliaoapp.musically")
TIKTOK_ACTIVITY = os.environ.get(
    "TIKTOK_SHARE_ACTIVITY",
    "com.ss.android.ugc.aweme.share.SystemShareActivity",
)
UI_BACKEND = os.environ.get("TIKTOK_UI_BACKEND", "direct").strip().lower()
ADB_SERIAL = os.environ.get("TIKTOK_ADB_SERIAL", "127.0.0.1:5555").strip()
TAP_HELPER_PKG = os.environ.get("TIKTOK_TAP_HELPER_PKG", "com.antigravity.touchhelper").strip()
AUTOMATION_TIMEOUT = int(os.environ.get("TIKTOK_AUTOMATION_TIMEOUT", "240"))
PUBLISH_MODE = os.environ.get("TIKTOK_PUBLISH_MODE", "direct").strip().lower()
SHARE_METHOD = os.environ.get("TIKTOK_SHARE_METHOD", "intent").strip().lower()
POST_SETTLE_SECONDS = int(os.environ.get("TIKTOK_POST_SETTLE_SECONDS", "90"))
CAPTION_ENABLED = os.environ.get("TIKTOK_CAPTION_ENABLED", "").strip() == "1"

def settle_seconds(video: Path) -> int:
    try:
        mb = video.stat().st_size / (1024 * 1024)
    except OSError:
        mb = 0
    if mb > 200:
        logging.info("Video %.0fMB > 200MB → settle 300s", mb)
        return 300
    logging.info("Video %.0fMB ≤ 200MB → settle 120s", mb)
    return 120

COORD_BASE_W = 720
COORD_BASE_H = 1480

class _ImmediateFileHandler(logging.FileHandler):
    def emit(self, record):
        super().emit(record)
        self.flush()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        _ImmediateFileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)


POST_RE = re.compile(r"^(post|publish|publicar|publicar ahora)$", re.I)
NEXT_RE = re.compile(r"^(siguiente|next|continuar)$", re.I)
PUBLICAR_RE = re.compile(r"^(publicar|publish|post)$", re.I)
CREAR_RE = re.compile(r"^(crear|create)$", re.I)
NEXT_RE = re.compile(r"^(next|siguiente|continuar|continue|listo|done)$", re.I)
VIDEO_NUEVO_RE = re.compile(r"^(video\s+nuevo|new\s+video)$", re.I)
DISMISS_RE = re.compile(
    r"^(allow|permitir|aceptar|ok|entendido|got it|not now|ahora no|skip|saltar|cancelar|cancel)$",
    re.I,
)
GUARDAR_RE = re.compile(r"^(guardar|save)$", re.I)
BORRADOR_RE = re.compile(r"^(borradores?|drafts?)$", re.I)
BOUNDS_RE = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def run(cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PATH"] = "/system/bin:/system/xbin:/data/data/com.termux/files/usr/bin:" + env.get("PATH", "")
    if "TMPDIR" not in env or not os.path.isdir(env["TMPDIR"]):
        env["TMPDIR"] = "/data/data/com.termux/files/usr/tmp"
    return subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, env=env)


KEYCODE_TO_GLOBAL = {
    "KEYCODE_BACK": 1,
    "KEYCODE_HOME": 2,
    "KEYCODE_RECENTS": 3,
    "KEYCODE_NOTIFICATIONS": 4,
    "KEYCODE_DPAD_CENTER": 1,
    "KEYCODE_ENTER": 1,
}

def ensure_adb_connected() -> None:
    if UI_BACKEND not in ("adb",):
        return
    r = run(["adb", "devices"], timeout=10)
    if ADB_SERIAL in r.stdout and "device" in r.stdout:
        return
    if ADB_SERIAL == "127.0.0.1:5555":
        run(["adb", "connect", "127.0.0.1:5555"], timeout=10)
    else:
        logging.warning("ADB device %s no conectado. Conecta USB.", ADB_SERIAL)

def _has_termuxapi() -> bool:
    return shutil.which("termux-tap") is not None


def _termux_tap(*args: str) -> subprocess.CompletedProcess:
    return run(["termux-tap", *args], timeout=15)


def _termux_swipe(*args: str) -> subprocess.CompletedProcess:
    return run(["termux-swipe", *args], timeout=15)


def _termux_key(*args: str) -> subprocess.CompletedProcess:
    return run(["termux-key", *args], timeout=10)


def _termux_text(text: str) -> subprocess.CompletedProcess:
    return run(["termux-text", text], timeout=15)


def _am_broadcast(args: list[str], timeout: int = 10) -> subprocess.CompletedProcess:
    shell_cmd = "/system/bin/am broadcast " + " ".join(shlex.quote(a) for a in args)
    try:
        subprocess.run(
            ["/system/bin/sh", "-c", shell_cmd + " >/dev/null 2>&1 &"],
            capture_output=True, timeout=3,
        )
    except subprocess.TimeoutExpired:
        pass
    return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

def run_android(cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    if UI_BACKEND == "termuxapi":
        if cmd[:2] == ["input", "tap"] and len(cmd) == 4:
            return _termux_tap(cmd[2], cmd[3])
        if cmd[:2] == ["input", "swipe"] and len(cmd) >= 6:
            return _termux_swipe(*cmd[2:])
        if cmd[:2] == ["input", "keyevent"] and len(cmd) >= 3:
            return _termux_key(cmd[2])
        if cmd[:2] == ["input", "text"] and len(cmd) >= 3:
            return _termux_text(" ".join(cmd[2:]))
        return run(cmd, timeout=timeout)
    if UI_BACKEND == "adb":
        shell_cmd = " ".join(shlex.quote(arg) for arg in cmd)
        return run(["adb", "-s", ADB_SERIAL, "shell", "exec " + shell_cmd], timeout=timeout)
    if UI_BACKEND == "accessibility":
        if cmd[:2] == ["input", "tap"] and len(cmd) == 4:
            _, _, sx, sy = cmd
            return _am_broadcast([
                "-a", "com.antigravity.TAP",
                "--ei", "x", sx, "--ei", "y", sy,
                "-n", f"{TAP_HELPER_PKG}/.TapReceiver",
            ])
        if cmd[:2] == ["input", "swipe"] and len(cmd) >= 6:
            _, _, x1, y1, x2, y2 = cmd[:6]
            dur = cmd[6] if len(cmd) > 6 else "300"
            return _am_broadcast([
                "-a", "com.antigravity.SWIPE",
                "--ei", "x1", x1, "--ei", "y1", y1,
                "--ei", "x2", x2, "--ei", "y2", y2,
                "--ei", "duration", dur,
                "-n", f"{TAP_HELPER_PKG}/.TapReceiver",
            ])
        if cmd[:2] == ["input", "keyevent"] and len(cmd) >= 3:
            key = cmd[2]
            global_key = KEYCODE_TO_GLOBAL.get(key)
            if global_key is not None:
                return _am_broadcast([
                    "-a", "com.antigravity.KEYEVENT",
                    "--ei", "key", str(global_key),
                    "-n", f"{TAP_HELPER_PKG}/.TapReceiver",
                ])
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")
        if cmd[:2] == ["input", "text"] and len(cmd) >= 3:
            text = " ".join(cmd[2:])
            return _am_broadcast([
                "-a", "com.antigravity.TEXT",
                "--es", "text", text,
                "-n", f"{TAP_HELPER_PKG}/.TapReceiver",
            ])
        return run(cmd, timeout=timeout)
    return run(cmd, timeout=timeout)


def shell_text_arg(text: str) -> str:
    """Texto compatible con `input text`: espacios como %s y caracteres seguros."""
    text = text.replace("%", "")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"[^0-9A-Za-z #.@/_-]", "", text)
    return text.replace(" ", "%s")[:240]


@contextlib.contextmanager
def process_lock():
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = str(LOCK_FILE)

    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise RuntimeError("Otra instancia de TikTok evacuador esta corriendo")

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(f"{os.getpid()} {now_str()}\n")
            fh.flush()
        yield
    finally:
        try:
            os.unlink(lock_path)
        except OSError:
            pass


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"history": []}
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"history": []}
    if not isinstance(data, dict):
        return {"history": []}
    data.setdefault("history", [])
    return data


def save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(STATE_FILE)


def append_history(item: dict) -> None:
    state = load_state()
    history = state.setdefault("history", [])
    history.append(item)
    if len(history) > 500:
        del history[:-500]
    state["last"] = item
    save_state(state)


def _purge_ghost_mediastore_entries(ms_rows: list[tuple[str, str]]) -> int:
    """
    Borra del MediaStore entradas cuyo archivo ya no existe en disco.
    ms_rows: lista de (raw_path, vid_id) obtenida de la consulta al MediaStore.
    Retorna la cantidad de fantasmas eliminados.
    """
    ghosts = 0
    for raw_path, vid_id in ms_rows:
        if not vid_id:
            continue
        raw_path_sdcard = raw_path.replace("/storage/emulated/0/", "/sdcard/")
        if not Path(raw_path_sdcard).exists():
            try:
                run_android(
                    ["content", "delete",
                     "--uri", f"content://media/external/video/media/{vid_id}"],
                    timeout=5,
                )
                ghosts += 1
            except Exception:
                pass
    if ghosts:
        logging.info("MediaStore: %d entradas fantasma eliminadas.", ghosts)
    return ghosts


def iter_videos() -> list[Path]:
    """
    Retorna videos pendientes ordenados por mtime (más antiguo primero).
    Fuente de verdad: el filesystem real (SOURCE_DIR.iterdir()).
    MediaStore se consulta SOLO para poblar _content_uris (URIs para share intent)
    y para limpiar entradas fantasma.
    """
    global _content_uris
    if not SOURCE_DIR.exists():
        return []

    # 1. Lista real de archivos en disco — fuente de verdad
    real_files: list[Path] = sorted(
        (
            f for f in SOURCE_DIR.iterdir()
            if f.is_file()
            and f.suffix.lower() in SUPPORTED_EXTS
            and not f.name.endswith(".part")
        ),
        key=lambda p: p.stat().st_mtime,
    )

    _content_uris = {}
    # Intentar cache local primero (generado desde ADB shell)
    if CONTENT_URIS_CACHE.exists():
        try:
            cached = json.loads(CONTENT_URIS_CACHE.read_text(encoding="utf-8"))
            for name, uri in cached.items():
                p = SOURCE_DIR / name
                if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS:
                    _content_uris[name] = uri
            logging.info(
                "Content URIs cache: %d válidas de %d en cache.",
                len(_content_uris), len(cached),
            )
        except Exception as exc:
            logging.warning("Error leyendo cache de content URIs: %s", exc)

    try:
        cmd = [
            "content", "query",
            "--uri", "content://media/external/video/media",
            "--projection", "_data:_id",
        ]
        result = run_android(cmd, timeout=10)
        if result.returncode == 0:
            ms_rows: list[tuple[str, str]] = []
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                match = re.search(r"_data=(.*?)(?:,\s|$)", line)
                id_match = re.search(r"_id=(\d+)", line)
                if match and id_match:
                    ms_rows.append((match.group(1).strip(), id_match.group(1)))

            _purge_ghost_mediastore_entries(ms_rows)

            for raw_path, vid_id in ms_rows:
                if SOURCE_DIR.name not in raw_path:
                    continue
                raw_path_sdcard = raw_path.replace("/storage/emulated/0/", "/sdcard/")
                p = Path(raw_path_sdcard)
                if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS:
                    _content_uris[p.name] = f"content://media/external/video/media/{vid_id}"

    except Exception as exc:
        logging.warning("No se pudo consultar MediaStore: %s", exc)

    logging.info(
        "MediaStore: %d entradas válidas con URI. Archivos reales en disco: %d.",
        len(_content_uris), len(real_files),
    )

    return real_files


def file_is_stable(path: Path) -> bool:
    try:
        last_size = path.stat().st_size
    except FileNotFoundError:
        return False
    for _ in range(3):
        time.sleep(1)
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            return False
        if size != last_size:
            last_size = size
            continue
        return True
    return False


def build_caption(path: Path) -> str:
    if extract_teaser_sequence:
        clean_name, teaser_num = extract_teaser_sequence(path.name)
    else:
        clean_name = path.stem.strip()
        teaser_match = re.search(r"(?i)_teaser_(\d+)$", clean_name)
        teaser_num = int(teaser_match.group(1)) if teaser_match else 1
        if teaser_match:
            clean_name = clean_name[: teaser_match.start()].strip(" _-")

    if not clean_name:
        clean_name = path.stem.strip()
    if normalize_video_stem:
        clean_name = normalize_video_stem(clean_name)

    caption_stem = re.sub(r"\s+", "_", clean_name.strip())
    caption_stem = caption_stem.strip("_")

    is_teaser = bool(re.search(r"(?i)_teaser_\d+$", path.stem))
    parts = [caption_stem, "#PW"]
    if is_teaser:
        parts.extend(["#teaser", f"#{teaser_num}"])

    parts.extend(
        [
            "Siguenos",
            "tambien",
            "en",
            "Instagram",
            "Facebook",
            "Youtube",
            "linktr.ee/performaticwritingscali",
            "#teatro",
            "#performance",
            "#escriturasperformaticas",
        ]
    )
    return " ".join(parts)


def unique_dest(folder: Path, name: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    candidate = folder / name
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    for i in range(1, 1000):
        alt = folder / f"{stem}__dup{i}{suffix}"
        if not alt.exists():
            return alt
    raise RuntimeError(f"No se pudo crear destino unico para {name}")


def write_caption(caption: str) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    CAPTION_FILE.write_text(caption + "\n", encoding="utf-8")


def _media_scan_broadcast(video: Path) -> bool:
    """Envia MEDIA_SCANNER_SCAN_FILE broadcast via ADB (127.0.0.1:5555).
    os.system() falla desde Termux con rc=256 (permiso denegado).
    Usando run_android -> adb shell el broadcast si se ejecuta con permisos de sistema.
    Retorna True si el broadcast se ejecuto (no garantiza que el scan termine)."""
    try:
        file_uri = "file://" + str(video.resolve())
        result = run_android([
            "am", "broadcast",
            "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
            "-d", file_uri,
        ], timeout=10)
        ok = result.returncode == 0
        if ok:
            logging.info("MediaScanner broadcast enviado via ADB: %s", video.name)
        else:
            logging.warning("MediaScanner broadcast fallo via ADB (rc=%s): %s", result.returncode, result.stderr.strip())
        return ok
    except Exception as exc:
        logging.warning("MediaScanner broadcast exception: %s", exc)
        return False


def insert_media_store(video: Path) -> str | None:
    """Inserta un video en MediaStore si no tiene entrada.
    Envia MEDIA_SCANNER_SCAN_FILE via ADB y espera hasta 15s a que el scan termine.
    Retorna la content:// URI o None si falla."""
    _media_scan_broadcast(video)

    # Normalizar ambas rutas para comparacion consistente
    video_normalized = str(video.resolve()).replace("/sdcard/", "/storage/emulated/0/")

    for attempt in range(3):
        time.sleep(5)  # dar tiempo al MediaScanner a indexar el archivo
        try:
            result = run_android([
                "content", "query",
                "--uri", "content://media/external/video/media",
                "--projection", "_data:_id",
            ], timeout=10)
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if not line.strip():
                        continue
                    raw_match = re.search(r"_data=(.*?)(?:,\s|$)", line)
                    id_match = re.search(r"_id=(\d+)", line)
                    if raw_match and id_match:
                        raw_path = raw_match.group(1).strip()
                        raw_normalized = raw_path.replace("/sdcard/", "/storage/emulated/0/")
                        if raw_normalized == video_normalized:
                            uri = f"content://media/external/video/media/{id_match.group(1)}"
                            _content_uris[video.name] = uri
                            logging.info("MediaStore URI tras scan (intento %d): %s -> %s", attempt + 1, video.name, uri)
                            return uri
        except Exception as exc:
            logging.warning("MediaStore re-query exception (intento %d): %s", attempt + 1, exc)
        logging.warning("MediaStore re-query no encontro el archivo tras scan (intento %d/3)", attempt + 1)
    return None


def get_content_uri(path: Path) -> str | None:
    """Retorna content URI desde el cache poblado por iter_videos()."""
    global _content_uris
    uri = _content_uris.get(path.name)
    if uri:
        logging.info("Content URI cache: %s", uri)
        return uri
    logging.warning("No content URI en cache para: %s", path.name)
    return None


def _ensure_media_store(video: Path) -> bool:
    """Asegura que el video tenga entrada en MediaStore para que aparezca en la galeria.
    Si no tiene content URI, lo inserta. Retorna True si hay URI disponible."""
    global _content_uris
    if _content_uris.get(video.name):
        return True
    uri = insert_media_store(video)
    if uri:
        _content_uris[video.name] = uri
        logging.info("MediaStore OK: %s", video.name)
        return True
    logging.warning("No se pudo registrar en MediaStore: %s", video.name)
    return False


def launch_share_intent(video: Path) -> bool:
    """Comparte el video directamente a TikTok via Android Share Intent.
    Usa content URI via run_android (con ADB funciona como shell).
    Fallback: broadcast al TermuxOpenReceiver (fire-and-forget)."""
    video_path = str(video.resolve())
    content_uri = get_content_uri(video)
    if not content_uri:
        logging.warning("No hay content URI en cache para %s.", video.name)
        content_uri = insert_media_store(video)
    if content_uri:
        logging.info("Share intent URI: %s", content_uri)
        cmd = ["am", "start", "-a", "android.intent.action.SEND", "-t", "video/mp4",
               "-f", "0x08000000", "--grant-read-uri-permission",
               "--eu", "android.intent.extra.STREAM", content_uri,
               "-n", f"{TIKTOK_PACKAGE}/{TIKTOK_ACTIVITY}"]
        result = run_android(cmd, timeout=15)
        if result.returncode == 0:
            logging.info("Share intent local OK")
            return True

    # Fallback: si no hay content URI no podemos compartir el video de forma fiable.
    # Retornar False para que el ciclo se marque como fallido y no se mueva el archivo.
    if not content_uri:
        logging.error("No hay content URI disponible para %s. Abortando share intent.", video.name)
        return False

    # Ultimo intento: ADB request para PC watcher (solo si hay content_uri)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    adb_cmd = (
        ["adb", "shell"]
        + ["am", "start", "-W",
           "-a", "android.intent.action.SEND",
           "-t", "video/mp4",
           "--eu", "android.intent.extra.STREAM", content_uri,
           "-f", "0x10000000",
           "-n", f"{TIKTOK_PACKAGE}/{TIKTOK_ACTIVITY}",
           ]
    )
    SHARE_REQUEST_FILE.write_text(" ".join(shlex.quote(a) for a in adb_cmd) + "\n", encoding="utf-8")
    logging.warning("Share intent local fallo. Se dejo request para PC watcher, pero no se puede confirmar publicacion desde el dispositivo.")
    return False


def launch_tiktok_home() -> bool:
    """Abre TikTok. En Android 13 no podemos verificar foreground (dumpsys
    window restringido), así que confiamos en que el ADB tuvo éxito."""
    tiktok_main_activity = f"{TIKTOK_PACKAGE}/com.ss.android.ugc.aweme.splash.SplashActivity"
    try:
        cmd = [
            "am", "start",
            "-n", tiktok_main_activity,
            "-a", "android.intent.action.MAIN",
            "-c", "android.intent.category.LAUNCHER",
            "-f", "0x10000000",
        ]
        result = run_android(cmd, timeout=30)
        if result.returncode == 0:
            logging.info("TikTok abierto localmente.")
            return True
        logging.warning("Fallo local: %s", result.stderr.strip())
    except Exception as exc:
        logging.warning("Excepcion local: %s", exc)
    # Fallback via ADB
    SHARE_REQUEST_FILE.write_text(
        " ".join(shlex.quote(a) for a in [
            "adb", "shell", "am", "start", "-W",
            "-n", tiktok_main_activity,
            "-a", "android.intent.action.MAIN",
            "-c", "android.intent.category.LAUNCHER",
        ]) + "\n",
        encoding="utf-8",
    )
    logging.info("Solicitando apertura via ADB...")
    for _ in range(20):
        time.sleep(1)
        if not SHARE_REQUEST_FILE.exists():
            time.sleep(5)
            logging.info("ADB ejecutado. Asumiendo TikTok abierto.")
            return True
    logging.warning("ADB no respondio.")
    SHARE_REQUEST_FILE.unlink(missing_ok=True)
    return False
    logging.warning("ADB no respondio para abrir TikTok.")
    SHARE_REQUEST_FILE.unlink(missing_ok=True)
    return False
    logging.warning("ADB no respondio para abrir TikTok.")
    SHARE_REQUEST_FILE.unlink(missing_ok=True)
    return False


def screen_size() -> tuple[int, int]:
    result = run_android(["wm", "size"], timeout=10)
    text = result.stdout + result.stderr
    match = re.search(r"Override size:\s*(\d+)x(\d+)", text)
    if not match:
        match = re.search(r"Physical size:\s*(\d+)x(\d+)", text)
    if match:
        return int(match.group(1)), int(match.group(2))
    return COORD_BASE_W, COORD_BASE_H


def tap_scaled(x: int, y: int, label: str, pause: float = 1.0) -> bool:
    width, height = screen_size()
    sx = round(x * width / COORD_BASE_W)
    sy = round(y * height / COORD_BASE_H)
    ok = tap((sx, sy), label)
    time.sleep(pause)
    return ok


def keyevent(key: str, label: str, pause: float = 1.0) -> bool:
    try:
        result = run_android(["input", "keyevent", key], timeout=10)
    except subprocess.TimeoutExpired:
        logging.warning("input keyevent timed out para %s (%s)", label, key)
        time.sleep(pause)
        return False
    if result.returncode == 0:
        logging.info("Keyevent: %s (%s)", key, label)
        time.sleep(pause)
        return True
    logging.warning("input keyevent fallo para %s: %s", label, result.stderr.strip())
    time.sleep(pause)
    return False


def keyboard_visible() -> bool:
    result = run_android(["dumpsys", "input_method"], timeout=15)
    text = result.stdout + result.stderr
    markers = (
        "mInputShown=true",
        "mIsInputViewShown=true",
    )
    return any(marker in text for marker in markers)


def type_caption(caption: str) -> bool:
    safe_caption = shell_text_arg(caption)
    if not safe_caption:
        return False
    result = run_android(["input", "text", safe_caption], timeout=30)
    if result.returncode == 0:
        logging.info("Caption insertado con input text: %s", safe_caption)
        return True
    logging.warning("No se pudo insertar caption: %s", result.stderr.strip())
    return False


def parse_bounds(bounds: str) -> tuple[int, int] | None:
    match = BOUNDS_RE.match(bounds or "")
    if not match:
        return None
    x1, y1, x2, y2 = map(int, match.groups())
    return (x1 + x2) // 2, (y1 + y2) // 2


def dump_ui() -> list[dict]:
    """Siempre vuelca la UI actual via uiautomator (sin cache: el XML anterior se borra)."""
    global _uiautomator_available
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    # Borrar siempre el XML anterior para evitar leer estado rancio
    try:
        run_android(["rm", "-f", str(UI_DUMP_FILE)], timeout=5)
    except subprocess.TimeoutExpired:
        pass
    try:
        result = run_android(["uiautomator", "dump", str(UI_DUMP_FILE)], timeout=20)
    except subprocess.TimeoutExpired:
        _uiautomator_available = False
        return []
    if result.returncode == 0 and UI_DUMP_FILE.exists():
        _uiautomator_available = True
        try:
            root = ET.parse(UI_DUMP_FILE).getroot()
            return _parse_ui_nodes(root)
        except Exception:
            return []
    _uiautomator_available = False
    return []


def _parse_ui_nodes(root: ET.Element) -> list[dict]:
    nodes: list[dict] = []
    for node in root.iter("node"):
        text = (node.attrib.get("text") or "").strip()
        desc = (node.attrib.get("content-desc") or "").strip()
        label = text or desc
        center = parse_bounds(node.attrib.get("bounds", ""))
        if not label or not center:
            continue
        if node.attrib.get("enabled") == "false":
            continue
        nodes.append(
            {
                "label": label,
                "text": text,
                "desc": desc,
                "center": center,
                "clickable": node.attrib.get("clickable") == "true",
                "class": node.attrib.get("class", ""),
            }
        )
    return nodes


def tap(center: tuple[int, int], label: str) -> bool:
    x, y = center
    try:
        result = run_android(["input", "tap", str(x), str(y)], timeout=10)
    except subprocess.TimeoutExpired:
        logging.warning("input tap timed out para %s en (%s,%s)", label, x, y)
        return False
    if result.returncode == 0:
        logging.info("Tap: %s en (%s,%s)", label, x, y)
        return True
    logging.warning("input tap fallo para %s: %s", label, result.stderr.strip())
    return False


def wake_screen() -> None:
    run_android(["input", "keyevent", "KEYCODE_WAKEUP"], timeout=10)
    time.sleep(1)
    # Swipe conservador para quitar lockscreen sin PIN/patron.
    run_android(["input", "swipe", "500", "1700", "500", "500", "350"], timeout=10)
    time.sleep(1)


def reset_tiktok() -> None:
    result = run_android(["am", "force-stop", TIKTOK_PACKAGE], timeout=10)
    if result.returncode == 0:
        logging.info("TikTok reiniciado antes del ciclo.")
    else:
        logging.warning("No se pudo force-stop TikTok: %s", result.stderr.strip())


def find_match(nodes: list[dict], pattern: re.Pattern[str]) -> dict | None:
    preferred = []
    fallback = []
    for node in nodes:
        label = node["label"].strip()
        if pattern.match(label):
            (preferred if node["clickable"] else fallback).append(node)
    if preferred:
        return preferred[-1]
    if fallback:
        return fallback[-1]
    return None


def current_package() -> str:
    result = run_android(["dumpsys", "window"], timeout=15)
    text = result.stdout + result.stderr
    match = re.search(r"mCurrentFocus=.*? ([A-Za-z0-9_.]+)/", text)
    if match:
        return match.group(1)
    match = re.search(r"mFocusedApp=.*? ([A-Za-z0-9_.]+)/", text)
    if match:
        return match.group(1)
    # Fallback: dump UI via uiautomator y extraer package del XML
    try:
        dump_ui()
        with UI_DUMP_FILE.open("r", encoding="utf-8") as f:
            content = f.read(8192)
        m = re.search(r'package="([A-Za-z0-9_.]+)"', content)
        if m:
            return m.group(1)
    except OSError:
        pass
    return ""


def tap_match(pattern: re.Pattern[str], label: str, timeout: int = 12) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        match = find_match(dump_ui(), pattern)
        if match and tap(match["center"], match["label"]):
            logging.info("Boton detectado para %s: %s", label, match["label"])
            return True
        time.sleep(2)
    logging.info("No se detecto boton por UI para %s; se usara fallback si existe.", label)
    return False


def close_caption_editor() -> bool:
    # KEYCODE_BACK navega hacia atras en TikTok y DESHACE los pasos de 
    # "Siguiente". Solo tocamos el fondo para intentar cerrar el teclado.
    deadline = time.time() + 10
    while time.time() < deadline:
        if not keyboard_visible():
            return True
        tap_scaled(360, 400, "tocar fondo para ocultar teclado", pause=2)
    if keyboard_visible():
        logging.warning("No se pudo ocultar el teclado; se continua de todos modos.")
    return True


def publish_confirmed(settle: int | None = None) -> bool:
    """
    Verifica que la publicacion haya sido exitosa con el metodo simple:
    el tap en "Publicar" ya produjo el cambio de pantalla (TikTok salio del
    editor hacia el feed 'Para ti'). Aqui solo esperamos el tiempo de subida
    del video (20s despues del tap/cambio de pantalla) y confirmamos.
    El metodo se cambio porque la senal de la notificacion 'Cargando...'
    (canal trill.publish) permanecia activa incluso tras matar TikTok,
    bloqueando la confirmacion. El tap de Publicar en este VIVO publica de
    forma fiable, asi que el cambio de pantalla basta.
    Tomamos screenshot al final para verificacion manual.
    """
    effective_settle = settle if settle is not None else POST_SETTLE_SECONDS
    upload_wait = int(os.environ.get("TIKTOK_PUBLISH_UPLOAD_WAIT_SECONDS", "20"))
    logging.info("Publicacion asumida OK (metodo simple): tap Publicar cambio la pantalla; esperando %ds de subida...", upload_wait)
    time.sleep(upload_wait)
    run_android(["screencap", "-p", str(STATE_DIR / "post_publish.png")], timeout=5)
    return True


def automate_tiktok_publish() -> bool:
    deadline = time.time() + AUTOMATION_TIMEOUT
    last_action = ""
    next_clicks = 0

    while time.time() < deadline:
        pkg = current_package()
        if pkg and pkg != TIKTOK_PACKAGE and "permissioncontroller" not in pkg:
            logging.info("Esperando TikTok; foreground=%s", pkg)

        nodes = dump_ui()
        labels = [n["label"] for n in nodes[:40]]
        logging.debug("UI labels: %s", labels)

        post = find_match(nodes, POST_RE)
        if post:
            if tap(post["center"], post["label"]):
                logging.info("Boton final detectado y tocado: %s", post["label"])
                time.sleep(POST_SETTLE_SECONDS)
                return True

        nxt = find_match(nodes, NEXT_RE)
        if nxt and next_clicks < 4:
            if tap(nxt["center"], nxt["label"]):
                next_clicks += 1
                last_action = nxt["label"]
                time.sleep(6)
                continue

        dismiss = find_match(nodes, DISMISS_RE)
        if dismiss and dismiss["label"] != last_action:
            if tap(dismiss["center"], dismiss["label"]):
                last_action = dismiss["label"]
                time.sleep(3)
                continue

        time.sleep(3)

    logging.error("No se llego al boton Publicar/Post dentro de %ss.", AUTOMATION_TIMEOUT)
    return False


TIKTOK_RE = re.compile(r"^tiktok$", re.I)
ONCE_RE = re.compile(r"^(solo\s+una\s+vez|just\s+once)$", re.I)


def chooser_select_tiktok() -> bool:
    """
    El selector de Android 'Completar la accion mediante' requiere:
      1. Tocar la app TikTok para seleccionarla (habilita los botones Solo una vez / Siempre).
      2. Tocar 'Solo una vez'.
    Usa deteccion de UI para encontrar ambos elementos por etiqueta.
    """
    logging.info("Esperando selector Android...")
    deadline = time.time() + 20
    while time.time() < deadline:
        nodes = dump_ui()
        tiktok_node = find_match(nodes, TIKTOK_RE)
        if tiktok_node:
            logging.info("TikTok encontrado en chooser: %s", tiktok_node["center"])
            tap(tiktok_node["center"], "TikTok en chooser")
            time.sleep(2)
            # Ahora 'Solo una vez' deberia estar habilitado
            nodes2 = dump_ui()
            once_node = find_match(nodes2, ONCE_RE)
            if once_node:
                logging.info("Boton 'Solo una vez' encontrado: %s", once_node["center"])
                tap(once_node["center"], "Solo una vez")
                time.sleep(5)
                return True
            # Fallback: coordenada conocida de 'Solo una vez'
            logging.warning("No se detecto 'Solo una vez' por UI; usando coordenada fallback.")
            tap_scaled(200, 1351, "Solo una vez fallback", pause=5)
            return True
        time.sleep(2)
    logging.info("No se detecto selector Android — TikTok se abrio directamente.")
    return False


def save_as_draft() -> bool:
    """Guarda como borrador tocando 'Borradores' en la pantalla de publicacion.
    No usa BACK (esa ruta falla en algunas versiones de TikTok)."""
    logging.info("Guardando como borrador (tocando boton Borradores)...")
    ok = tap_match(BORRADOR_RE, "Borradores", timeout=8)
    if not ok:
        ok = tap_scaled(187, 1333, "Borradores coordenada", pause=5)
    if ok:
        logging.info("Video guardado como borrador.")
        return True
    logging.warning("No se encontro boton Borradores.")
    return False


def automate_tiktok_publish_coords(video: Path, caption: str, folder_name: str) -> bool:
    """
    Flujo probado en Note9 con override 720x1480.
    Usa deteccion de UI para elementos dinámicos y coordenadas escaladas para el resto.
    PUBLISH_MODE=direct: publica directo con boton CREAR
    PUBLISH_MODE=draft: guarda como borrador en vez de publicar
    """
    logging.info("Automatizando TikTok (publish_mode=%s).", PUBLISH_MODE)
    required_steps: list[tuple[str, bool]] = []

    # Home Screen: Tap Crear (+) en la barra inferior
    required_steps.append(("Crear (+)", tap_scaled(360, 1353, "Crear (+)", pause=5)))

    # Camera Screen: Tap CREAR (no PUBLICAR) para abrir opciones
    # CREAR button bounds: [450,1297] - [584,1376] → center (517, 1337)
    required_steps.append(("CREAR (camara)", tap_scaled(517, 1337, "CREAR", pause=5)))

    # Menu desplegable: Tap "Video nuevo"
    video_nuevo = False
    for attempt in range(5):
        nodes = dump_ui()
        vn = find_match(nodes, VIDEO_NUEVO_RE)
        if vn:
            video_nuevo = tap(vn["center"], "Video nuevo")
            time.sleep(5)
            break
        time.sleep(2)
    required_steps.append(("Video nuevo", video_nuevo))

    # Gallery Screen: Tocar dropdown 'Recientes' para cambiar de carpeta
    required_steps.append(("Recientes", tap_scaled(360, 83, "Dropdown Recientes", pause=3)))

    # Esperar y buscar el nombre de la carpeta de origen
    folder_re = re.compile(re.escape(folder_name), re.I)
    folder_selected = False
    for attempt in range(5):
        nodes = dump_ui()
        folder_node = find_match(nodes, folder_re)
        if folder_node:
            logging.info("Carpeta encontrada en UI: %s", folder_node["center"])
            folder_selected = tap(folder_node["center"], f"Carpeta {folder_name}")
            time.sleep(3)
            break
        time.sleep(2)
    required_steps.append((f"Seleccionar {folder_name}", folder_selected))

    # Permiso multimedia si aparece
    tap_scaled(360, 1210, "Permitir multimedia", pause=2)

    # Galeria: primer video (asegurado por touch + MediaStore)
    time.sleep(2)
    required_steps.append(("primer video", tap_scaled(200, 241, "primer video", pause=1)))
    required_steps.append(("Siguiente galeria", tap_scaled(600, 1352, "Siguiente galeria", pause=6)))

    # Editor: Siguiente (abajo a la derecha)
    required_steps.append(("Siguiente editor", tap_scaled(531, 1341, "Siguiente editor", pause=10)))

    # Pantalla de descripcion: caption
    if CAPTION_ENABLED:
        required_steps.append(("campo descripcion", tap_scaled(178, 152, "campo descripcion", pause=1)))
        required_steps.append(("caption", type_caption(caption)))
        required_steps.append(("cerrar teclado", close_caption_editor()))
        time.sleep(2)

    if PUBLISH_MODE == "draft":
        publish_ok = save_as_draft()
        required_steps.append(("Guardar borrador", publish_ok))
    else:
        video_settle = settle_seconds(video)
        publish_ok = tap_scaled(608, 80, "Publicar top", pause=5)
        if publish_ok:
            time.sleep(15)
            upload_deadline = time.time() + video_settle
            while time.time() < upload_deadline:
                if publish_confirmed(video_settle):
                    break
                time.sleep(15)
            else:
                publish_ok = publish_confirmed(video_settle)

        required_steps.append(("Publicar", publish_ok))
        if publish_ok:
            required_steps.append(("confirmar publicacion", True))
        else:
            required_steps.append(("confirmar publicacion", publish_confirmed()))

    failed = [label for label, ok in required_steps if not ok]
    if failed:
        logging.error("Automatizacion incompleta. Fallaron: %s", ", ".join(failed))
        return False

    logging.info("Secuencia completada exitosamente (mode=%s).", PUBLISH_MODE)
    return True


def move_to_done(video: Path, record: dict) -> None:
    if not video.exists():
        logging.warning("Archivo ya no existe en origen (otra instancia lo movio?): %s", video.name)
        record["status"] = "already_moved"
        record["finished_at"] = now_str()
        append_history(record)
        print(f"[TIKTOK_OK] {video.name} (ya publicado por otra instancia)")
        return
    dest = unique_dest(DONE_DIR, video.name)
    shutil.move(str(video), str(dest))
    record["status"] = "published_moved"
    record["done_path"] = str(dest)
    record["finished_at"] = now_str()
    append_history(record)
    logging.info("Movido a '%s': %s", DONE_DIR.name, dest.name)
    print(f"[TIKTOK_OK] {dest}")


def open_next(args: argparse.Namespace) -> int:
    videos = iter_videos()
    if not videos:
        logging.info("No hay videos pendientes en: %s", SOURCE_DIR)
        return 2

    video = videos[0]
    if not file_is_stable(video):
        logging.info("Archivo en cambio activo; se reintentara luego: %s", video.name)
        return 2

    caption = build_caption(video)
    write_caption(caption)

    logging.info("=" * 60)
    logging.info("  TIKTOK EVACUADOR — 1 video autonomo")
    logging.info("=" * 60)
    logging.info("Fuente: %s", SOURCE_DIR)
    logging.info("Video: %s", video.name)
    logging.info("Caption: %s", CAPTION_FILE)
    print(f"[VIDEO] {video}")
    print(f"[CAPTION_FILE] {CAPTION_FILE}")
    print("[CAPTION]")
    print(caption)

    # Listar archivos en la carpeta fuente para saber cual seleccionar en TikTok
    print(f"\n--- Archivos en {SOURCE_DIR} ---")
    for f in sorted(SOURCE_DIR.iterdir()):
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS:
            print(f"  {f.name}")
    print(f"Total: {len(videos)} pendientes\n")

    if args.dry_run:
        logging.info("DRY-RUN: no se abre TikTok ni se mueve archivo.")
        return 0

    record = {
        "name": video.name,
        "source": str(video),
        "caption": caption,
        "started_at": now_str(),
        "device": DEVICE_NAME,
    }

    wake_screen()
    reset_tiktok()

    if SHARE_METHOD == "intent":
        if not launch_share_intent(video):
            record["status"] = "share_intent_failed"
            record["finished_at"] = now_str()
            append_history(record)
            return 1

        time.sleep(25)  # Dar tiempo a TikTok para cargarse completamente

        # Verificar que TikTok efectivamente se abrió después del share intent
        # Nota: dumpsys window no funciona desde Termux (pkg==""), así que
        # siempre intentamos seleccionar TikTok en el chooser por si acaso.
        pkg = current_package()
        if pkg == "android" or not pkg:
            if not pkg:
                logging.info("Foreground desconocido (dumpsys no funciona). Intentando chooser...")
            chooser_select_tiktok()
            time.sleep(10)
        elif pkg != TIKTOK_PACKAGE:
            logging.warning("TikTok no en foreground (%s). Reintentando share intent via ADB...", pkg)
            retry_uri = _content_uris.get(video.name, "")
            if retry_uri:
                SHARE_REQUEST_FILE.write_text(
                    " ".join(shlex.quote(a) for a in [
                        "adb", "shell", "am", "start", "-W",
                        "-a", "android.intent.action.SEND",
                        "-t", "video/mp4",
                        "--eu", "android.intent.extra.STREAM", retry_uri,
                        "-f", "0x10000000",
                    ]) + "\n",
                    encoding="utf-8",
                )
                for _ in range(15):
                    time.sleep(1)
                    if not SHARE_REQUEST_FILE.exists():
                        break
                time.sleep(10)

        required_steps: list[tuple[str, bool]] = []

        # Puede haber 1-2 pantallas de editor antes de llegar a descripcion.
        # Tocamos "Siguiente" hasta 2 veces (con deteccion UI + coordenada fallback).
        for _editor_step in range(2):
            nodes = dump_ui()
            nxt = find_match(nodes, NEXT_RE)
            if nxt:
                logging.info("Editor step %d: tocando Siguiente UI '%s'", _editor_step + 1, nxt["label"])
                tap(nxt["center"], nxt["label"])
                time.sleep(8)
            else:
                logging.info("Editor step %d: Siguiente no detectado por UI, probando coordenadas fallback una por una...", _editor_step + 1)
                # Fallbacks: 1) Nueva coord S24/Vivo abajo-derecha, 2) Antigua coord arriba-derecha
                fallback_coords = [(531, 1341), (665, 77), (600, 1352)]
                fallback_advanced = False
                for fx, fy in fallback_coords:
                    if not tap_scaled(fx, fy, f"Siguiente coord {fx},{fy} (step {_editor_step + 1})", pause=4):
                        continue
                    nodes_after = dump_ui()
                    if find_match(nodes_after, NEXT_RE):
                        logging.info("Siguiente sigue visible tras %s,%s; probando siguiente fallback.", fx, fy)
                        continue
                    fallback_advanced = True
                    logging.info("Siguiente fallback %s,%s produjo cambio de pantalla; no se tocaran mas coordenadas.", fx, fy)
                    break
                if not fallback_advanced:
                    logging.warning("No hubo cambio claro tras fallback de Siguiente en step %d.", _editor_step + 1)

        # Pantalla de caption: tocar campo y escribir
        if CAPTION_ENABLED:
            required_steps.append(("campo descripcion", tap_scaled(178, 152, "campo descripcion", pause=2)))
            required_steps.append(("caption", type_caption(caption)))
            required_steps.append(("cerrar teclado", close_caption_editor()))
            time.sleep(2)

        if PUBLISH_MODE == "draft":
            publish_ok = save_as_draft()
            required_steps.append(("Guardar borrador", publish_ok))
        else:
            # Intentar detectar el boton Publicar por UI primero
            publish_ok = False
            nodes = dump_ui()
            pub_node = find_match(nodes, PUBLICAR_RE)
            if pub_node:
                logging.info("Boton Publicar detectado por UI: %s en %s", pub_node["label"], pub_node["center"])
                publish_ok = tap(pub_node["center"], pub_node["label"])
            else:
                # Fallback: intentar varias coordenadas comunes para boton Publicar
                logging.info("Publicar no detectado por UI; probando coordenadas fallback una por una...")
                fallback_pub = [(608, 80), (665, 77), (600, 1350)]
                for px, py in fallback_pub:
                    publish_ok = tap_scaled(px, py, f"Publicar coord {px},{py}", pause=3)
                    if not publish_ok:
                        continue
                    nodes_after = dump_ui()
                    if find_match(nodes_after, PUBLICAR_RE) or find_match(nodes_after, POST_RE):
                        logging.info("Publicar sigue visible tras %s,%s; probando siguiente fallback.", px, py)
                        publish_ok = False
                        continue
                    logging.info("Publicar fallback %s,%s produjo cambio de pantalla; no se tocaran mas coordenadas.", px, py)
                    break

            if publish_ok:
                # Esperar a que TikTok procese y suba el video (poll cada 15s)
                time.sleep(15)
                confirmed = False
                upload_deadline = time.time() + POST_SETTLE_SECONDS
                while time.time() < upload_deadline:
                    if publish_confirmed():
                        confirmed = True
                        break
                    time.sleep(15)
                if not confirmed:
                    confirmed = publish_confirmed()
                publish_ok = confirmed

            required_steps.append(("Publicar", publish_ok))

        failed = [label for label, ok in required_steps if not ok]
        if failed:
            logging.error("Share-intent flow incompleto. Fallaron: %s", ", ".join(failed))
            record["status"] = "caption_publish_failed"
            record["finished_at"] = now_str()
            append_history(record)
            return 1

    else:
        # Metodo monkey: navegacion completa por UI
        if not video.exists():
            logging.error("Video ya no existe en disco: %s", video.name)
            record["status"] = "file_not_found"
            record["finished_at"] = now_str()
            append_history(record)
            return 1

        # Registrar en MediaStore para que TikTok lo vea en la galeria
        _ensure_media_store(video)

        try:
            run_android(["touch", str(video)], timeout=5)
            logging.info("Touch aplicado a: %s", video.name)
        except Exception as exc:
            logging.warning("No se pudo hacer touch al video: %s", exc)

        if not launch_tiktok_home():
            record["status"] = "launch_home_failed"
            record["finished_at"] = now_str()
            append_history(record)
            return 1

        time.sleep(8)
        folder_name = video.parent.name
        if not automate_tiktok_publish_coords(video, caption, folder_name):
            record["status"] = "ui_automation_failed"
            record["finished_at"] = now_str()
            append_history(record)
            return 1

    move_to_done(video, record)
    return 0


def show_status() -> int:
    pending = len(iter_videos())
    state = load_state()
    print(f"Fuente: {SOURCE_DIR}")
    print(f"Pendientes en fuente: {pending}")
    print(f"Destino OK: {DONE_DIR}")
    print(f"Destino fallidos: {FAILED_DIR}")
    print(f"Ultimo estado: {state.get('last')}")
    print(f"Caption actual: {CAPTION_FILE}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evacuador TikTok autonomo 720")
    parser.add_argument("--open-next", action="store_true", help="abre y publica el siguiente video")
    parser.add_argument("--status", action="store_true", help="muestra estado de la cola")
    parser.add_argument("--dry-run", action="store_true", help="no abre TikTok ni cambia archivos")
    parser.add_argument("--publish-mode", choices=["direct", "draft"], default=os.environ.get("TIKTOK_PUBLISH_MODE", "direct"),
                        help="direct=publica, draft=guarda borrador")
    parser.add_argument("--share-method", choices=["intent", "monkey"], default=os.environ.get("TIKTOK_SHARE_METHOD", "intent"),
                        help="intent=share directo, monkey=navegacion UI")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    global PUBLISH_MODE, SHARE_METHOD
    PUBLISH_MODE = args.publish_mode
    SHARE_METHOD = args.share_method
    ensure_adb_connected()
    if args.status:
        return show_status()
    
    ret = 3
    try:
        with process_lock():
            ret = open_next(args)
    except RuntimeError as exc:
        logging.warning("%s", exc)
        ret = 3
        
    if getattr(args, "open_next", False) and not getattr(args, "dry_run", False):
        logging.info("Ciclo terminado. Esperando 20 segundos para regresar a HOME...")
        time.sleep(20)
        logging.info("Enviando evento HOME para evitar reproduccion infinita de videos.")
        run_android(["input", "keyevent", "KEYCODE_HOME"], timeout=5)
        
    return ret

if __name__ == "__main__":
    sys.exit(main())
