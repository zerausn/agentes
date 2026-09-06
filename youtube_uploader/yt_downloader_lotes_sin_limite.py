"""
yt_downloader_lotes_sin_limite.py
Descargador de YouTube por lotes SIN LÍMITE DE FECHA para Termux/proot-Debian.

- Lista TODOS los videos PÚBLICOS del canal (sin restricción de fecha).
- Videos privados, ocultos o unlisted son ignorados.
- Muestra menú interactivo de lotes (agrupados por mes).
- Lleva registro en yt_lotes_registro_sin_limite.json de descargados/pendientes/fallidos.
- Guarda los archivos en /sdcard/Antigravity/crudos/
- Sincroniza el registro automáticamente con GitHub (git pull al inicio, git push tras cada descarga).
"""

import json
import logging
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime, timezone
from pathlib import Path

import httplib2
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# ─── Rutas ────────────────────────────────────────────────────────────────────
BASE_DIR        = Path(__file__).resolve().parent
REPO_DIR        = BASE_DIR.parent
CREDENTIALS_DIR = BASE_DIR / "credentials"
REGISTRY_FILE   = BASE_DIR / "yt_lotes_registro_sin_limite.json"
LOG_FILE        = BASE_DIR / "yt_lotes_sin_limite.log"
if Path("/mnt/Videos").exists():
    DEST_DIR = Path("/mnt/Videos/antigravity/crudos")
else:
    DEST_DIR = Path("/sdcard/Antigravity/crudos")
TEMP_DIR        = BASE_DIR / "yt_temp_dl"
BRANCH_NAME     = "linux-arm64"

# ─── Configuración ────────────────────────────────────────────────────────────
# SIN TARGET_DATE: se descargan TODOS los videos públicos del canal.
SCOPES        = ["https://www.googleapis.com/auth/youtube.readonly"]
YTDLP_BIN     = shutil.which("yt-dlp") or "/usr/local/bin/yt-dlp"
FFMPEG_PRESET = os.getenv("AGENTES_FFMPEG_PRESET", "ultrafast")
FFMPEG_CRF    = os.getenv("AGENTES_FFMPEG_CRF", "20")
FFMPEG_AUDIO  = os.getenv("AGENTES_FFMPEG_AUDIO_BITRATE", "192k")

# Cookies de YouTube: una sesión anónima nunca recibe la oferta de 2160p
# (confirmado en docs/CAPTURA_4K_MITMPROXY_NAVEGADOR.md — máximo 1080p60 sin
# login). Se prioriza el perfil real de Firefox con sesión logueada que ya usa
# la captura 4K por navegador (mismo login, un solo lugar que mantener); si no
# existe, se cae al cookies.txt clásico (bot-check / age-restricted).
_FIREFOX_PROFILE_CANDIDATES = [
    Path("/root/captura_firefox_profile"),
]
def _check_firefox_profile(p: Path) -> bool:
    try:
        return (p / "cookies.sqlite").exists()
    except PermissionError:
        return False

FIREFOX_COOKIES_PROFILE = next(
    (p for p in _FIREFOX_PROFILE_CANDIDATES if _check_firefox_profile(p)), None
)

_COOKIE_CANDIDATES = [
    Path("/sdcard/Antigravity/cookies.txt"),
    CREDENTIALS_DIR / "cookies.txt",
]
COOKIES_FILE = next((c for c in _COOKIE_CANDIDATES if c.exists()), None)
if FIREFOX_COOKIES_PROFILE:
    logging.getLogger(__name__).info(
        "[COOKIES] yt-dlp usará sesión logueada de Firefox: %s", FIREFOX_COOKIES_PROFILE
    )
elif COOKIES_FILE:
    logging.getLogger(__name__).info("[COOKIES] yt-dlp usará cookies de: %s", COOKIES_FILE)

# Nombre del dispositivo actual (para el registro de quién descargó qué).
# Se puede configurar en ~/.agentes_termux_env como:
#   export AGENTES_DEVICE_NAME="S24"
DEVICE_NAME = os.getenv("AGENTES_DEVICE_NAME") or socket.gethostname() or "desconocido"

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════════════
# SINCRONIZACIÓN GIST (REEMPLAZO DE GIT)
# ═══════════════════════════════════════════════════════════════════════════════

import urllib.request
import urllib.error

GIST_TOKEN_FILE = CREDENTIALS_DIR / "github_gist_token.txt"
GIST_ID_FILE = CREDENTIALS_DIR / "github_gist_id.txt"

def _get_gist_api_headers() -> dict:
    if not GIST_TOKEN_FILE.exists():
        return None
    token = GIST_TOKEN_FILE.read_text(encoding="utf-8").strip()
    if not token:
        return None
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28"
    }

def _get_gist_id() -> str:
    if not GIST_ID_FILE.exists():
        return None
    return GIST_ID_FILE.read_text(encoding="utf-8").strip()

def sync_pull():
    print()
    print("[SYNC] Descargando registro actualizado desde GitHub Gists...")
    headers = _get_gist_api_headers()
    gist_id = _get_gist_id()
    if not headers or not gist_id:
        print("[SYNC] ⚠️ Faltan credenciales o Gist ID en credentials/. Se usará el registro local.")
        log.warning("[SYNC] Faltan github_gist_token.txt o github_gist_id.txt")
        return

    try:
        req = urllib.request.Request(f"https://api.github.com/gists/{gist_id}", headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            if response.status == 200:
                gist_data = json.loads(response.read().decode("utf-8"))
                file_obj = gist_data.get("files", {}).get("yt_lotes_registro_sin_limite.json")
                if file_obj:
                    content = file_obj.get("content", "{}")
                    remote_registry = json.loads(content)
                    local_registry = load_registry()
                    
                    merged_count = 0
                    for month, videos in remote_registry.items():
                        if month not in local_registry:
                            local_registry[month] = videos
                            merged_count += len(videos)
                        else:
                            for vid_id, vid_info in videos.items():
                                if vid_info.get("status") == "descargado":
                                    local_registry[month][vid_id] = vid_info
                                    merged_count += 1
                    save_registry(local_registry)
                    print("[SYNC] ✅ Registro actualizado desde GitHub Gists.")
                    log.info("[SYNC] Pull Gist OK. Mezclados: %d", merged_count)
                else:
                    print("[SYNC] ⚠️ Archivo JSON no encontrado en el Gist.")
            else:
                print(f"[SYNC] ⚠️ Falló la conexión al Gist: {response.status}")
    except Exception as e:
        print(f"[SYNC] ⚠️ Error al descargar el registro del Gist: {e}")
        log.error("[SYNC] Error Gist Pull: %s", e)

def sync_push(commit_msg: str):
    print()
    print("[SYNC] Subiendo registro actualizado a GitHub Gists...")
    headers = _get_gist_api_headers()
    gist_id = _get_gist_id()
    if not headers or not gist_id:
        print("[SYNC] ⚠️ Faltan credenciales o Gist ID. Se omite subida a la nube.")
        log.warning("[SYNC] Faltan credenciales para push Gist.")
        return

    try:
        sync_pull()
        local_registry = load_registry()
        payload = json.dumps({
            "description": commit_msg,
            "files": {
                "yt_lotes_registro_sin_limite.json": {
                    "content": json.dumps(local_registry, indent=2, ensure_ascii=False)
                }
            }
        }).encode("utf-8")
        
        req_headers = headers.copy()
        req_headers["Content-Type"] = "application/json"
        req = urllib.request.Request(f"https://api.github.com/gists/{gist_id}", data=payload, headers=req_headers, method="PATCH")
        
        with urllib.request.urlopen(req, timeout=15) as response:
            if response.status == 200:
                print("[SYNC] ✅ Registro sincronizado en GitHub Gists exitosamente.")
                log.info("[SYNC] Push Gist OK.")
            else:
                print(f"[SYNC] ⚠️ Falló la subida al Gist: {response.status}")
    except Exception as e:
        print(f"[SYNC] ⚠️ Error al subir el registro al Gist: {e}")
        log.error("[SYNC] Error Gist Push: %s", e)

# ═══════════════════════════════════════════════════════════════════════════════
# AUTENTICACIÓN
# ═══════════════════════════════════════════════════════════════════════════════

# Timeout en segundos para cada llamada a la API de YouTube.
# Si la red está lenta o cortada, no se bloquea indefinidamente.
API_TIMEOUT = 45


def get_youtube_service():
    """Intenta autenticarse con los tokens disponibles en orden."""
    token_candidates = sorted(CREDENTIALS_DIR.glob("token_*.json"))
    if not token_candidates:
        log.error("No se encontraron archivos token_*.json en %s", CREDENTIALS_DIR)
        return None

    for token_file in token_candidates:
        try:
            creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                token_file.write_text(creds.to_json(), encoding="utf-8")
            if creds.valid:
                log.info("Autenticado con: %s", token_file.name)
                return build("youtube", "v3", credentials=creds)
        except Exception as e:
            log.warning("Token %s no válido: %s", token_file.name, e)

    log.error("No se pudo autenticar con ningún token. Ejecuta el widget 0_RENOVAR_TOKEN_YT para generar nuevos tokens.")
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# REGISTRO
# ═══════════════════════════════════════════════════════════════════════════════

def load_registry() -> dict:
    if REGISTRY_FILE.exists():
        try:
            return json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_registry(registry: dict):
    REGISTRY_FILE.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")


def mark_video(registry: dict, month: str, vid_id: str, status: str, filepath: str = None):
    if month not in registry:
        registry[month] = {}
    entry = registry[month].get(vid_id, {})
    entry["status"] = status
    if status == "descargado":
        entry["downloaded_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry["downloaded_by"] = DEVICE_NAME
    if filepath:
        entry["file"] = filepath
    registry[month][vid_id] = entry
    save_registry(registry)


# ═══════════════════════════════════════════════════════════════════════════════
# ESCANEO DE YOUTUBE
# ═══════════════════════════════════════════════════════════════════════════════

def _api_call_with_timeout(request, timeout: int = API_TIMEOUT):
    """
    Ejecuta una solicitud de la Google API con timeout.
    Lanza TimeoutError si la API no responde en `timeout` segundos.
    """
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(request.execute)
        try:
            return future.result(timeout=timeout)
        except FuturesTimeoutError:
            raise TimeoutError(
                f"La API de YouTube no respondió en {timeout}s. "
                "Comprueba la conexión a internet."
            )


def fetch_all_public_videos(youtube) -> list:
    """
    Descarga la lista COMPLETA de videos públicos del canal.
    SIN restricción de fecha.
    - Videos privados, ocultos o unlisted son ignorados.
    - Videos con "teaser" en el título son ignorados: son clips recortados
      de ~16 segundos, NO son crudos.
    - Cada llamada a la API tiene un timeout de API_TIMEOUT segundos para
      evitar bloqueos indefinidos cuando hay problemas de red.
    """
    log.info("Escaneando canal de YouTube (TODOS los crudos públicos, sin teasers)...")
    try:
        channels_resp = _api_call_with_timeout(
            youtube.channels().list(mine=True, part="contentDetails")
        )
    except TimeoutError as e:
        log.error("[API] %s", e)
        print(f"\n[ERROR] {e}")
        return []
    except Exception as e:
        log.error("[API] Error obteniendo canal: %s", e)
        print(f"\n[ERROR] No se pudo obtener información del canal: {e}")
        return []

    uploads_id = channels_resp["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    videos = []
    seen = set()
    skipped_private = 0
    skipped_teaser  = 0
    next_page = None
    page_num = 0

    while True:
        page_num += 1
        try:
            resp = _api_call_with_timeout(
                youtube.playlistItems().list(
                    playlistId=uploads_id,
                    part="snippet,status",
                    maxResults=50,
                    pageToken=next_page,
                )
            )
        except TimeoutError as e:
            log.error("[API] Timeout en página %d: %s", page_num, e)
            print(f"\n[ERROR] {e}")
            break
        except Exception as e:
            log.error("[API] Error en página %d: %s", page_num, e)
            print(f"\n[ERROR] Error inesperado en página {page_num}: {e}")
            break

        for item in resp.get("items", []):
            vid_id = item["snippet"]["resourceId"]["videoId"]
            if vid_id in seen:
                continue
            seen.add(vid_id)

            # ── FILTRO DE PRIVACIDAD ─────────────────────────────────────────
            # Solo se incluyen videos públicos. Los privados, ocultos (unlisted)
            # o no listados son ignorados completamente.
            if item.get("status", {}).get("privacyStatus") != "public":
                skipped_private += 1
                continue
            # ── FIN FILTRO PRIVACIDAD ────────────────────────────────────────

            title = item["snippet"]["title"]

            # ── FILTRO DE TEASERS ────────────────────────────────────────────
            # Los teasers son clips recortados de ~16 segundos generados
            # automáticamente. Se identifican porque su título contiene
            # la palabra "teaser" (sin importar mayúsculas/minúsculas).
            # NO son crudos y no deben descargarse aquí.
            if "teaser" in title.lower():
                skipped_teaser += 1
                continue
            # ── FIN FILTRO TEASERS ───────────────────────────────────────────

            pub_str = item["snippet"]["publishedAt"]
            pub = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
            month = pub.strftime("%Y-%m")
            videos.append({
                "id":          vid_id,
                "title":       title,
                "publishedAt": pub_str,
                "month":       month,
            })

        next_page = resp.get("nextPageToken")
        if not next_page:
            break

    log.info(
        "  → %s crudos públicos encontrados. Ignorados: %s privados/ocultos, %s teasers.",
        len(videos), skipped_private, skipped_teaser,
    )
    return videos


def sync_registry_with_channel(registry: dict, channel_videos: list) -> dict:
    """
    Sincroniza el registro con la lista filtrada del canal:
    1. Agrega videos nuevos que no estaban en el registro.
    2. Elimina del registro entradas que ya no pasan los filtros
       (teasers, privados, ocultos) — EXCEPTO los ya descargados,
       cuyo historial se preserva.
    """
    # Conjunto de IDs válidos según los filtros actuales
    valid_ids: set[str] = {v["id"] for v in channel_videos}

    # ── Agregar videos nuevos ────────────────────────────────────────────────
    for v in channel_videos:
        month = v["month"]
        if month not in registry:
            registry[month] = {}
        if v["id"] not in registry[month]:
            registry[month][v["id"]] = {
                "title":         v["title"],
                "publishedAt":   v["publishedAt"],
                "status":        "pendiente",
                "file":          None,
                "downloaded_at": None,
                "downloaded_by": None,
            }

    # ── Limpiar entradas obsoletas (teasers / privados / ocultos) ───────────
    # Solo se eliminan los que están pendientes o fallidos.
    # Los ya descargados se conservan para no perder el historial.
    pruned = 0
    for month in list(registry.keys()):
        for vid_id in list(registry[month].keys()):
            if vid_id not in valid_ids:
                if registry[month][vid_id].get("status") != "descargado":
                    del registry[month][vid_id]
                    pruned += 1
        # Eliminar meses que quedaron vacíos
        if not registry[month]:
            del registry[month]

    if pruned > 0:
        log.info(
            "  → %s entradas eliminadas del registro (teasers/privados que "
            "ya no pasan los filtros).",
            pruned,
        )

    save_registry(registry)
    return registry


# ═══════════════════════════════════════════════════════════════════════════════
# DESCARGA
# ═══════════════════════════════════════════════════════════════════════════════

def sanitize(title: str) -> str:
    return re.sub(r'[\\/*?"<>|]', "", str(title or "")).strip()[:80] or "video_sin_titulo"


# Sentinel para indicar que el video ya existía y fue omitido (no recién descargado)
_SKIPPED = "__SKIPPED__"


def download_video(vid_id: str, title: str) -> str | None:
    """
    Descarga un video en 4K y lo transcoda a MP4.
    Retorna:
      - La ruta final del .mp4 si se descargó/transcodificó en esta ejecución.
      - _SKIPPED si el archivo ya existía y fue omitido.
      - None si falló.
    """
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    DEST_DIR.mkdir(parents=True, exist_ok=True)

    safe_title = sanitize(title)
    final_path = DEST_DIR / f"{safe_title}.mp4"
    url = f"https://www.youtube.com/watch?v={vid_id}"
    stub = TEMP_DIR / f"dl_{vid_id}"
    mkv_tmp = TEMP_DIR / f"dl_{vid_id}.mkv"
    mp4_tmp = TEMP_DIR / f"dl_{vid_id}.mp4"

    if final_path.exists() and final_path.stat().st_size > 1024 * 1024:
        # Verificar con ffprobe que el archivo final no está corrupto antes de omitirlo
        try:
            subprocess.check_output(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(final_path)],
                stderr=subprocess.DEVNULL, timeout=5
            )
            log.info("  Ya existe en destino (ffprobe OK), se omite: %s", final_path.name)
            return _SKIPPED
        except Exception:
            log.warning("  Archivo final corrupto o ilegible, se eliminará y re-descargará: %s", final_path.name)
            print(f"  ⚠️  Archivo corrupto detectado, eliminando para re-descargar: {final_path.name}")
            final_path.unlink(missing_ok=True)

    downloaded_path = None

    # ── Revisar si el archivo crudo temporal ya fue descargado previamente ──
    for candidate in [mkv_tmp, mp4_tmp]:
        if candidate.exists() and candidate.stat().st_size > 1024 * 1024:
            # Comprobar rápido con ffprobe que el archivo no está corrupto
            try:
                subprocess.check_output(
                    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", str(candidate)],
                    stderr=subprocess.DEVNULL, timeout=2
                )
                log.info("  [1/2] Archivo crudo ya existe, saltando descarga yt-dlp: %s", candidate.name)
                downloaded_path = candidate
                break
            except Exception:
                # Si está corrupto, lo borramos y descargamos de nuevo
                candidate.unlink(missing_ok=True)

    if not downloaded_path:
        # ── Paso 1: Descarga con yt-dlp ──────────────────────────────────────────
        log.info("  [1/2] Descargando en 4K: %s", title)
        ytdlp_cmd_base = [
            sys.executable, "-m", "yt_dlp",
            "--js-runtimes", "node",
            "--no-part",
            "--merge-output-format", "mkv",
            "--newline", "--quiet", "--no-warnings", "--progress",
            "-o", str(stub) + ".%(ext)s",
        ]
        # IMPORTANTE: Se omiten las cookies intencionalmente para evadir el experimento "SABR streaming"
        # que fuerza HLS a 1080p máximo en cuentas logueadas, perdiéndose el 4K DASH original.
        # El PO Token (bgutil) provee acceso anónimo seguro sorteando el error 403.
        # if FIREFOX_COOKIES_PROFILE:
        #     ytdlp_cmd_base += ["--cookies-from-browser", f"firefox:{FIREFOX_COOKIES_PROFILE}"]
        # elif COOKIES_FILE:
        #     ytdlp_cmd_base += ["--cookies", str(COOKIES_FILE)]
        
        ytdlp_cmd_base += ["--remote-components", "ejs:github"]

        for selector in [
            "bestvideo[height>=2160]+bestaudio[ext=m4a]/bestvideo[height>=2160]+bestaudio/best[height>=2160]/bestvideo+bestaudio/best",
            "bestvideo+bestaudio/best",
            "best",
        ]:
            for f in [mkv_tmp, mp4_tmp]:
                if f.exists():
                    f.unlink(missing_ok=True)
            try:
                cmd = [*ytdlp_cmd_base, "-f", selector, url]
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                for line in proc.stdout:
                    if "[download]" in line and "%" in line and "Destination" not in line:
                        cleaned = line.replace("[download]", "").strip()
                        print(f"\r  ⬇️  {cleaned}   ", end="", flush=True)
                proc.wait()
                print()  # Salto de línea al terminar
                if proc.returncode != 0:
                    raise subprocess.CalledProcessError(proc.returncode, cmd)
            except subprocess.CalledProcessError:
                pass
            for candidate in [mkv_tmp, mp4_tmp]:
                if candidate.exists() and candidate.stat().st_size > 512 * 1024:
                    downloaded_path = candidate
                    break
            if downloaded_path:
                log.info("  Descarga OK (%.1f MB) | selector: %s",
                         downloaded_path.stat().st_size / (1024 * 1024), selector[:40])
                break

    if not downloaded_path:
        log.error("  Falló la descarga de: %s (%s)", title, vid_id)
        return None

    # Si ya es MP4 limpio, moverlo directo
    if downloaded_path.suffix.lower() == ".mp4":
        shutil.move(str(downloaded_path), str(final_path))
        return str(final_path)

    # Detectar codec del video descargado — si es H.264 se copia sin re-encodar (instantáneo)
    prog_file = TEMP_DIR / f"ffprog_{vid_id}.txt"
    try:
        probe_out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=codec_name",
             "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(downloaded_path)],
            stderr=subprocess.DEVNULL,
        ).decode().strip().splitlines()
        codec_out = next((l for l in probe_out if l not in ("", "N/A") and not l.replace(".","").isdigit()), "")
        dur_vals = [l for l in probe_out if l.replace(".","").isdigit()]
        total_dur = float(dur_vals[0]) if dur_vals else 0
    except Exception:
        codec_out = ""
        total_dur = 0

    if codec_out.lower() in ("h264", "avc"):
        # ✅ Ya es H.264 → remux directo (copiar streams, sin re-encodar)
        log.info("  [2/2] Remuxeando a MP4 (H.264 detectado, sin re-encodar)...")
        print("  ⚡ Codec H.264 detectado — remux instantáneo, sin transcodificación.")
        transcode_cmd = [
            "ffmpeg", "-y", "-i", str(downloaded_path),
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", FFMPEG_AUDIO,
            "-movflags", "+faststart",
            "-progress", str(prog_file),
            str(final_path),
        ]
    else:
        # ⚙️ VP9 / AV1 / otro → re-encodar con libx264
        log.info("  [2/2] Transcodificando a MP4 (codec: %s → H.264)...", codec_out or "desconocido")
        transcode_cmd = [
            "ffmpeg", "-y", "-i", str(downloaded_path),
            "-c:v", "libx264", "-preset", FFMPEG_PRESET, "-crf", FFMPEG_CRF,
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", FFMPEG_AUDIO,
            "-movflags", "+faststart",
            "-progress", str(prog_file),
            str(final_path),
        ]
    proc = subprocess.Popen(transcode_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    while proc.poll() is None:
        if prog_file.exists() and total_dur > 0:
            try:
                content = prog_file.read_text()
                times = re.findall(r"out_time_us=(\d+)", content)
                speeds = re.findall(r"speed=\s*([\d.]+)x", content)
                if times:
                    cur_s = int(times[-1]) / 1_000_000
                    pct = min((cur_s / total_dur) * 100, 100)
                    spd = float(speeds[-1]) if speeds else 0
                    eta = f"{int((total_dur-cur_s)/spd//60)}m{int((total_dur-cur_s)/spd%60)}s" if spd > 0 else "--"
                    print(f"\r  📊 {pct:.1f}% | ETA: {eta} | {spd:.2f}x   ", end="", flush=True)
            except Exception:
                pass
        time.sleep(2)
    print()

    # Limpieza de temporales
    for f in [downloaded_path, prog_file]:
        try:
            f.unlink(missing_ok=True)
        except Exception:
            pass

    if final_path.exists() and final_path.stat().st_size > 512 * 1024:
        log.info("  ✅ Guardado: %s (%.1f MB)", final_path.name, final_path.stat().st_size / (1024 * 1024))
        return str(final_path)

    log.error("  Transcodificación falló: %s", title)
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# PENDIENTES DE SESIÓN ANTERIOR
# ═══════════════════════════════════════════════════════════════════════════════

def _find_vid_in_registry(vid_id: str, registry: dict) -> tuple[str, str, str] | None:
    """Busca un vid_id en el registro. Retorna (month, title, status) o None."""
    for month, videos in registry.items():
        if vid_id in videos:
            info = videos[vid_id]
            return month, info.get("title", vid_id), info.get("status", "pendiente")
    return None


def finish_pending_transcodes(registry: dict) -> dict:
    """
    Antes de arrancar el lote seleccionado, barre la carpeta temporal en
    busca de archivos .mkv que se descargaron completamente en una sesión
    anterior pero cuya transcodificación fue interrumpida.

    Si los encuentra:
      - Los transcodifica a .mp4.
      - Los marca como descargados en el registro (puede ser de otro lote).
      - Hace git push inmediato para que los demás celulares se enteren.
    """
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    pending_mkv = sorted(TEMP_DIR.glob("dl_*.mkv"))
    if not pending_mkv:
        return registry

    print()
    print("═" * 58)
    print(f"  ⚠️  Se encontraron {len(pending_mkv)} archivo(s) pendiente(s) de sesión anterior.")
    print("  Terminando transcodificaciones antes de arrancar el lote...")
    print("═" * 58)

    for mkv_path in pending_mkv:
        # Extraer vid_id del nombre del archivo: dl_{vid_id}.mkv
        vid_id = mkv_path.stem.replace("dl_", "", 1)

        # Validar que el mkv esté completo con ffprobe
        try:
            subprocess.check_output(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(mkv_path)],
                stderr=subprocess.DEVNULL, timeout=5
            )
        except Exception:
            log.warning("  ⚠️  Archivo temporal corrupto o incompleto, se elimina: %s", mkv_path.name)
            mkv_path.unlink(missing_ok=True)
            continue

        # Buscar el video en el registro para saber a qué lote pertenece
        info = _find_vid_in_registry(vid_id, registry)
        if info:
            month, title, status = info
        else:
            # No está en el registro; usar el vid_id como título
            month, title, status = "desconocido", vid_id, "pendiente"

        # Si ya fue marcado como descargado y el .mp4 final existe, solo limpiar el mkv
        safe_title = sanitize(title)
        final_path = DEST_DIR / f"{safe_title}.mp4"
        if status == "descargado" and final_path.exists() and final_path.stat().st_size > 512 * 1024:
            log.info("  Limpiando residuo temporal ya transcodificado: %s", mkv_path.name)
            mkv_path.unlink(missing_ok=True)
            continue

        print()
        print(f"  ⏭️  Pendiente de lote [{month}]: {title}")
        log.info("  Retomando transcodificación de pendiente [%s]: %s", month, title)

        # Transcodificar
        # Llamamos directamente a la lógica de transcodificación
        prog_file = TEMP_DIR / f"ffprog_{vid_id}.txt"
        try:
            dur_out = subprocess.check_output(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(mkv_path)],
                stderr=subprocess.DEVNULL,
            ).decode().strip()
            total_dur = float(dur_out)
        except Exception:
            total_dur = 0

        transcode_cmd = [
            "ffmpeg", "-y", "-i", str(mkv_path),
            "-c:v", "libx264", "-preset", FFMPEG_PRESET, "-crf", FFMPEG_CRF,
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", FFMPEG_AUDIO,
            "-movflags", "+faststart",
            "-progress", str(prog_file),
            str(final_path),
        ]
        proc = subprocess.Popen(transcode_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log.info("  [2/2] Transcodificando a MP4...")
        while proc.poll() is None:
            if prog_file.exists() and total_dur > 0:
                try:
                    content = prog_file.read_text()
                    times = re.findall(r"out_time_us=(\d+)", content)
                    speeds = re.findall(r"speed=\s*([\d.]+)x", content)
                    if times:
                        cur_s = int(times[-1]) / 1_000_000
                        pct = min((cur_s / total_dur) * 100, 100)
                        spd = float(speeds[-1]) if speeds else 0
                        eta = f"{int((total_dur-cur_s)/spd//60)}m{int((total_dur-cur_s)/spd%60)}s" if spd > 0 else "--"
                        print(f"\r  📊 {pct:.1f}% | ETA: {eta} | {spd:.2f}x   ", end="", flush=True)
                except Exception:
                    pass
            time.sleep(2)
        print()

        # Limpiar temporales
        for f in [mkv_path, prog_file]:
            try:
                f.unlink(missing_ok=True)
            except Exception:
                pass

        if final_path.exists() and final_path.stat().st_size > 512 * 1024:
            log.info("  ✅ Pendiente terminado [lote %s]: %s (%.1f MB)",
                     month, final_path.name, final_path.stat().st_size / (1024 * 1024))
            print(f"  ✅ Guardado [lote {month}]: {final_path.name}")
            if month != "desconocido":
                mark_video(registry, month, vid_id, "descargado", str(final_path))
                sync_push(f"sync: {DEVICE_NAME} completó pendiente {vid_id} ({month})")
        else:
            log.error("  ❌ Transcodificación fallida en pendiente: %s", title)
            print(f"  ❌ Falló la transcodificación del pendiente: {title}")

    print()
    print("═" * 58)
    print("  Pendientes anteriores procesados. Arrancando lote seleccionado...")
    print("═" * 58)
    return registry


# ═══════════════════════════════════════════════════════════════════════════════
# MENÚ INTERACTIVO
# ═══════════════════════════════════════════════════════════════════════════════

def print_header():
    print()
    print("=" * 58)
    print("  5_BAJAR_YOUTUBE_SIN_LIMITE — Descargador por Lotes")
    print("  (Incluye TODOS los crudos públicos, sin límite de fecha)")
    print("=" * 58)


def print_status(registry: dict):
    total = sum(len(vids) for vids in registry.values())
    descargados = sum(
        1 for vids in registry.values()
        for v in vids.values() if v["status"] == "descargado"
    )
    fallidos = sum(
        1 for vids in registry.values()
        for v in vids.values() if v["status"] == "fallido"
    )
    pendientes = total - descargados - fallidos

    print()
    print(f"  Dispositivo actual : {DEVICE_NAME}")
    print()
    print("ESTADO GENERAL:")
    print(f"  Total videos públicos : {total}")
    print(f"  Ya descargados        : {descargados}  ✅")
    print(f"  Pendientes            : {pendientes}  ⏳")
    print(f"  Fallidos              : {fallidos}  ❌")


def get_pending_months(registry: dict) -> list[tuple[str, list]]:
    """Retorna lista de (mes, [video_ids pendientes]) ordenados cronológicamente."""
    pending = []
    for month in sorted(registry.keys()):
        vids = [
            (vid_id, info)
            for vid_id, info in registry[month].items()
            if info["status"] in ("pendiente", "fallido")
        ]
        if vids:
            pending.append((month, vids))
    return pending


def get_completed_months(registry: dict) -> list[tuple[str, str, str]]:
    """
    Retorna lista de meses completamente descargados con info del último dispositivo.
    Cada elemento: (mes, device_name, downloaded_at)
    """
    completed = []
    for month in sorted(registry.keys()):
        vids = registry[month]
        if not vids:
            continue
        all_done = all(v["status"] == "descargado" for v in vids.values())
        if all_done:
            # Tomar el más reciente downloaded_at del mes
            last = max(
                vids.values(),
                key=lambda v: v.get("downloaded_at") or "0000-00-00 00:00",
            )
            completed.append((
                month,
                last.get("downloaded_by") or "?",
                last.get("downloaded_at") or "?",
            ))
    return completed


def print_menu(pending_months: list, completed_months: list) -> int:
    print()

    # ── Lotes completados ────────────────────────────────────────────────────
    if completed_months:
        print("LOTES COMPLETADOS:")
        for month, device, at in completed_months:
            print(f"  ✅  {month}  →  descargado por {device} el {at}")
        print()

    # ── Lotes pendientes ─────────────────────────────────────────────────────
    if not pending_months:
        print("  ¡No hay lotes pendientes! Todo ha sido descargado. ✅")
        return 0

    print("LOTES DISPONIBLES (pendientes por mes):")
    for i, (month, vids) in enumerate(pending_months, start=1):
        failed = sum(1 for _, info in vids if info["status"] == "fallido")
        tag = f"  ({failed} fallidos)" if failed else ""
        print(f"  [{i:2d}]  {month}  →  {len(vids)} videos{tag}")

    print()
    print("  [ 0]  Salir")
    print()

    while True:
        try:
            choice = input("Selecciona un lote (número) o 0 para salir: ").strip()
            n = int(choice)
            if 0 <= n <= len(pending_months):
                return n
            print(f"  Por favor escribe un número entre 0 y {len(pending_months)}.")
        except (ValueError, EOFError):
            print("  Entrada inválida. Escribe un número.")


# ═══════════════════════════════════════════════════════════════════════════════
# BARRIDO INICIAL DE CARPETA DESTINO
# ═══════════════════════════════════════════════════════════════════════════════

def scan_and_report_existing_downloads(registry: dict, channel_videos: list) -> dict:
    """
    Escanea toda la carpeta destino (/sdcard/Antigravity/crudos/) al inicio.
    Para cada .mp4 encontrado:
      1. Lo cruza contra la lista de videos del canal para identificar su ID.
      2. Si ya está en el registro como 'descargado', lo salta.
      3. Si no está reportado: lo valida con ffprobe.
         - Pasa: lo marca como 'descargado' en el registro.
         - Falla: lo ignora (archivo corrupto, no se toca).
    Al final, si hubo nuevos archivos confirmados, hace un único git push.
    """
    if not DEST_DIR.exists():
        return registry

    mp4_files = sorted(DEST_DIR.glob("*.mp4"))
    if not mp4_files:
        return registry

    # Construir lookup: título sanitizado → info del video
    title_to_vid = {sanitize(v["title"]): v for v in channel_videos}

    print()
    print("─" * 58)
    print(f"  [BARRIDO] Revisando {len(mp4_files)} archivo(s) en disco...")

    nuevos = 0
    corruptos = 0

    for mp4_file in mp4_files:
        stem = mp4_file.stem
        vid_info = title_to_vid.get(stem)
        if not vid_info:
            # No coincide con ningún video del canal (otro script, teaser, etc.)
            continue

        vid_id = vid_info["id"]
        month  = vid_info["month"]

        # Si ya está reportado como descargado en el registro de GitHub, saltar
        if registry.get(month, {}).get(vid_id, {}).get("status") == "descargado":
            continue

        # Validar integridad con ffprobe
        try:
            subprocess.check_output(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(mp4_file)],
                stderr=subprocess.DEVNULL, timeout=5
            )
        except Exception:
            log.warning("  [BARRIDO] Archivo corrupto, se omite (no se borra): %s", mp4_file.name)
            corruptos += 1
            continue

        # Marcar como descargado
        mark_video(registry, month, vid_id, "descargado", str(mp4_file))
        log.info("  [BARRIDO] Confirmado y registrado: %s (%s)", mp4_file.name, month)
        nuevos += 1

    if nuevos > 0:
        print(f"  [BARRIDO] {nuevos} archivo(s) nuevo(s) confirmados con ffprobe.")
        if corruptos > 0:
            print(f"  [BARRIDO] {corruptos} archivo(s) corrupto(s) encontrados (ignorados).")
        sync_push(f"sync: {DEVICE_NAME} barrido inicial — {nuevos} archivos existentes registrados")
    else:
        print("  [BARRIDO] Todo ya estaba sincronizado con GitHub. Sin cambios.")

    print("─" * 58)
    return registry


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print_header()

    # ── Sincronizar registro desde GitHub ────────────────────────────────────
    sync_pull()

    # ── Autenticar ──────────────────────────────────────────────────────────
    print("\nConectando con YouTube API...")
    youtube = get_youtube_service()
    if not youtube:
        print("\n[ERROR] No se pudo autenticar con YouTube. Revisa los tokens en credentials/")
        input("Presiona Enter para salir...")
        sys.exit(1)

    # ── Escanear canal y actualizar registro ────────────────────────────────
    print("Escaneando canal (puede tardar unos segundos)...")
    channel_videos = fetch_all_public_videos(youtube)
    registry = load_registry()
    registry = sync_registry_with_channel(registry, channel_videos)

    # ── Barrido inicial: reportar a GitHub todos los archivos ya en disco ────
    registry = scan_and_report_existing_downloads(registry, channel_videos)

    # ── Menú principal ──────────────────────────────────────────────────────
    while True:
        print_header()
        print_status(registry)
        pending_months = get_pending_months(registry)
        completed_months = get_completed_months(registry)
        choice = print_menu(pending_months, completed_months)

        if choice == 0:
            print("\nSaliendo. ¡Hasta luego!")
            break

        # ── Antes de arrancar: terminar transcodificaciones pendientes ─────────
        registry = finish_pending_transcodes(registry)

        # ── Descargar el lote seleccionado ──────────────────────────────────
        month, vids_to_download = pending_months[choice - 1]
        print(f"\n{'='*58}")
        print(f"  Descargando lote: {month} ({len(vids_to_download)} videos)")
        print(f"  Dispositivo     : {DEVICE_NAME}")
        print(f"  Destino         : {DEST_DIR}")
        print(f"{'='*58}\n")

        ok_count = 0
        skip_count = 0
        fail_count = 0
        for i, (vid_id, info) in enumerate(vids_to_download, start=1):
            print(f"\n[{i}/{len(vids_to_download)}] {info['title']}")
            result = download_video(vid_id, info["title"])
            if result == _SKIPPED:
                # Ya existía: marcar como descargado en el registro sin hacer push
                mark_video(registry, month, vid_id, "descargado", None)
                skip_count += 1
            elif result:
                # Recién descargado y transcodificado: marcar y sincronizar GitHub
                mark_video(registry, month, vid_id, "descargado", result)
                ok_count += 1
                sync_push(f"sync: {DEVICE_NAME} bajó {vid_id} ({month})")
            else:
                mark_video(registry, month, vid_id, "fallido")
                fail_count += 1
            time.sleep(2)

        print()
        print(f"{'='*58}")
        print(f"  Lote {month} terminado. ✅ {ok_count} nuevos  ⏭️  {skip_count} omitidos  ❌ {fail_count}")
        print(f"{'='*58}")

        if skip_count > 0:
            sync_push(f"sync: {DEVICE_NAME} registró {skip_count} videos ya existentes en {month}")

        input("\nPresiona Enter para volver al menú...")
        registry = load_registry()  # recargar por si algo cambió


if __name__ == "__main__":
    # Arrancar el servidor bgutil en segundo plano para el PO Token de yt-dlp
    bgutil_proc = None
    bgutil_paths = [
        Path("/root/bgutil-ytdlp-pot-provider/server/build/main.js"), # S24 Proot
        Path.home() / "bgutil-ytdlp-pot-provider/server/build/main.js" # PC
    ]
    
    def _check_bgutil_path(p: Path) -> bool:
        try:
            return p.exists()
        except PermissionError:
            return False

    server_path = next((p for p in bgutil_paths if _check_bgutil_path(p)), None)
    
    if server_path:
        log.info("Arrancando bgutil HTTP server para PO Token...")
        bgutil_proc = subprocess.Popen(
            ["node", str(server_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        import time
        time.sleep(2) # Darle tiempo a arrancar
        
    try:
        main()
    finally:
        if bgutil_proc:
            bgutil_proc.terminate()
            bgutil_proc.wait()
