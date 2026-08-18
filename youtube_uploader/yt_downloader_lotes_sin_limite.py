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
DEST_DIR        = Path("/sdcard/Antigravity/crudos")
TEMP_DIR        = BASE_DIR / "yt_temp_dl"
BRANCH_NAME     = "linux-arm64"

# ─── Configuración ────────────────────────────────────────────────────────────
# SIN TARGET_DATE: se descargan TODOS los videos públicos del canal.
SCOPES        = ["https://www.googleapis.com/auth/youtube.readonly"]
YTDLP_BIN     = shutil.which("yt-dlp") or "/usr/local/bin/yt-dlp"
FFMPEG_PRESET = os.getenv("AGENTES_FFMPEG_PRESET", "ultrafast")
FFMPEG_CRF    = os.getenv("AGENTES_FFMPEG_CRF", "20")
FFMPEG_AUDIO  = os.getenv("AGENTES_FFMPEG_AUDIO_BITRATE", "192k")

# Cookies de YouTube (opcional): si hay una sesión iniciada en cookies.txt,
# se pasa a yt-dlp para evitar el bot-check 403 y los videos age-restricted.
_COOKIE_CANDIDATES = [
    Path("/sdcard/Antigravity/cookies.txt"),
    CREDENTIALS_DIR / "cookies.txt",
]
COOKIES_FILE = next((c for c in _COOKIE_CANDIDATES if c.exists()), None)
if COOKIES_FILE:
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
# SINCRONIZACIÓN GIT
# ═══════════════════════════════════════════════════════════════════════════════

def _git(*args, capture=False):
    """Ejecuta un comando git en el directorio del repo. Retorna (ok, output)."""
    cmd = ["git", "-C", str(REPO_DIR)] + list(args)
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            timeout=60,
        )
        output = (result.stdout + result.stderr).strip() if capture else ""
        return result.returncode == 0, output
    except Exception as e:
        return False, str(e)


def _rebase_in_progress() -> bool:
    git_dir = REPO_DIR / ".git"
    return (git_dir / "rebase-merge").exists() or (git_dir / "rebase-apply").exists()


def _ensure_git_branch(context: str) -> bool:
    """Garantiza que Git esté en la rama esperada antes de sincronizar."""
    if _rebase_in_progress():
        log.warning("[SYNC] Rebase activo detectado antes de %s; abortando rebase pendiente.", context)
        ok_abort, out_abort = _git("rebase", "--abort", capture=True)
        if not ok_abort:
            log.warning("[SYNC] No se pudo abortar el rebase pendiente: %s", out_abort)
            print("[SYNC] ⚠️  Hay un rebase pendiente. Ejecuta reparación Git antes de sincronizar.")
            return False
        print("[SYNC] ⚠️  Rebase pendiente abortado para evitar commits en detached HEAD.")

    ok_branch, branch = _git("branch", "--show-current", capture=True)
    current_branch = branch.strip() if ok_branch else ""
    if current_branch == BRANCH_NAME:
        return True

    if current_branch:
        log.warning("[SYNC] Rama actual inesperada antes de %s: %s", context, current_branch)
    else:
        log.warning("[SYNC] HEAD detached antes de %s; intentando volver a %s.", context, BRANCH_NAME)

    ok_checkout, out_checkout = _git("checkout", BRANCH_NAME, capture=True)
    if ok_checkout:
        return True

    log.warning("[SYNC] No se pudo cambiar a %s: %s", BRANCH_NAME, out_checkout)
    print(f"[SYNC] ⚠️  Git no está en {BRANCH_NAME}. Se omite sincronización para no perder registro.")
    return False


def _load_registry_from_git(ref: str) -> dict:
    """Carga el registro JSON desde un ref de Git, por ejemplo origin/linux-arm64."""
    rel_registry = REGISTRY_FILE.relative_to(REPO_DIR).as_posix()
    ok, content = _git("show", f"{ref}:{rel_registry}", capture=True)
    if not ok or not content.strip():
        return {}
    try:
        return json.loads(content)
    except Exception as e:
        log.warning("[SYNC] No se pudo leer registro desde %s: %s", ref, e)
        return {}


def _index_registry(registry: dict) -> dict:
    index = {}
    for month, videos in registry.items():
        if not isinstance(videos, dict):
            continue
        for vid_id, entry in videos.items():
            if isinstance(entry, dict):
                index[vid_id] = (month, entry)
    return index


def _merge_downloaded_entries(target: dict, source: dict) -> int:
    """
    Conserva en target cualquier video que source ya tenga como descargado.
    El estado descargado es monotónico: ningún nodo debe degradarlo a pendiente.
    """
    merged = 0
    target_index = _index_registry(target)

    for source_month, videos in source.items():
        if not isinstance(videos, dict):
            continue
        for vid_id, source_entry in videos.items():
            if not isinstance(source_entry, dict):
                continue
            if source_entry.get("status") != "descargado":
                continue

            target_month, target_entry = target_index.get(vid_id, (source_month, None))
            if target_entry is None:
                target.setdefault(source_month, {})[vid_id] = dict(source_entry)
                target_index[vid_id] = (source_month, target[source_month][vid_id])
                merged += 1
                continue

            if target_entry.get("status") == "descargado":
                continue

            target_entry["status"] = "descargado"
            for field in ("file", "downloaded_at", "downloaded_by"):
                target_entry[field] = source_entry.get(field)
            target.setdefault(target_month, {})[vid_id] = target_entry
            merged += 1

    return merged


def _preserve_remote_downloads(context: str) -> int:
    """
    Antes de publicar, mezcla los descargados remotos en el registro local.
    Evita que un celular con un JSON viejo vuelva a marcar como pendiente
    un video que otro nodo ya informó como descargado.
    """
    ok_fetch, out_fetch = _git("fetch", "origin", BRANCH_NAME, "--quiet", capture=True)
    if not ok_fetch:
        log.warning("[SYNC] No se pudo refrescar remoto antes de %s: %s", context, out_fetch)
        return 0

    local_data = load_registry()
    remote_data = _load_registry_from_git(f"origin/{BRANCH_NAME}")
    if not local_data or not remote_data:
        return 0

    merged = _merge_downloaded_entries(local_data, remote_data)
    if merged:
        save_registry(local_data)
        log.info("[SYNC] Preservados %d descargados remotos antes de %s.", merged, context)
        print(f"[SYNC] ✅ Preservados {merged} descargado(s) remotos ya informados por otros nodos.")
    return merged


def sync_pull():
    """
    Hace git pull antes de empezar para obtener el registro más reciente
    de cualquier otro dispositivo. Loguea el resultado pero no interrumpe.
    """
    print()
    print("[SYNC] Descargando registro actualizado desde GitHub...")
    log.info("[SYNC] git pull origin %s", BRANCH_NAME)

    if not _ensure_git_branch("sync_pull"):
        return

    # Primero el fetch para ver si hay algo nuevo
    ok, out = _git("fetch", "origin", BRANCH_NAME, "--quiet", capture=True)
    if not ok:
        log.warning("[SYNC] ⚠️  git fetch falló (sin conexión?): %s", out)
        print("[SYNC] ⚠️  No se pudo conectar con GitHub. Se usará el registro local.")
        return

    # Verificar si el remoto tiene commits nuevos
    ok2, local  = _git("rev-parse", "HEAD", capture=True)
    ok3, remote = _git("rev-parse", f"origin/{BRANCH_NAME}", capture=True)
    local  = local.strip()
    remote = remote.strip()

    if local == remote:
        print("[SYNC] ✅ Registro ya está al día (sin cambios remotos).")
        log.info("[SYNC] Sin cambios remotos (HEAD=%s).", local[:7])
        return

    # Hay cambios: hacer pull
    ok4, out4 = _git("pull", "--ff-only", "origin", BRANCH_NAME, capture=True)
    if ok4:
        # Obtener autor y tiempo del commit más reciente
        ok5, meta = _git(
            "log", "-1", "--pretty=format:%an | hace %cr",
            capture=True,
        )
        meta_str = meta.strip() if ok5 else ""
        log.info("[SYNC] ✅ Registro actualizado desde GitHub: %s -> %s. %s",
                 local[:7], remote[:7], meta_str)
        print(f"[SYNC] ✅ Registro actualizado (commit {remote[:7]}) — {meta_str}")
    else:
        log.warning("[SYNC] ⚠️  git pull falló (ramas divergentes): %s", out4)
        print("[SYNC] ⚠️  Ramas desviadas. Iniciando auto-reparación de registro...")

        # 1. Respaldar datos locales en memoria
        try:
            with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
                local_data = json.load(f)
        except Exception:
            local_data = {}

        # 2. Forzar alineación de Git con la nube, borrando el commit local conflictivo
        _git("reset", "--hard", f"origin/{BRANCH_NAME}")

        # 3. Cargar datos remotos limpios
        try:
            with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
                remote_data = json.load(f)
        except Exception:
            remote_data = {}

        # 4. Mezclar inteligentemente: conservar lo remoto e inyectar lo local que falte
        merged_count = 0
        for month, videos in local_data.items():
            if month not in remote_data:
                remote_data[month] = videos
                merged_count += len(videos)
            else:
                for vid_id, vid_info in videos.items():
                    if vid_id not in remote_data[month]:
                        remote_data[month][vid_id] = vid_info
                        merged_count += 1

        # 5. Guardar la mezcla en el archivo y subirlo
        if merged_count > 0:
            with open(REGISTRY_FILE, "w", encoding="utf-8") as f:
                json.dump(remote_data, f, indent=4, ensure_ascii=False)
            
            print(f"[SYNC] ✅ Auto-merge completado: {merged_count} registros locales rescatados.")
            log.info("[SYNC] Auto-reparación finalizada. Subiendo mezcla a GitHub.")
            
            # Subir explícitamente usando sync_push
            sync_push("sync: auto-merge de ramas divergentes")
        else:
            print("[SYNC] ✅ Auto-merge completado: no había diferencias locales.")
            log.info("[SYNC] Auto-reparación: registro remoto intacto, sin pérdida local.")


def sync_push(commit_msg: str):
    """
    Hace git add + commit + push del registro tras una actualización.
    No interrumpe el flujo si falla.
    """
    print()
    print("[SYNC] Subiendo registro actualizado a GitHub...")
    log.info("[SYNC] Intentando git push: %s", commit_msg)

    if not _ensure_git_branch("sync_push"):
        return

    rel_registry = REGISTRY_FILE.relative_to(REPO_DIR)

    _preserve_remote_downloads("crear commit")

    # Solo agregar el archivo de registro, forzando porque *.json suele estar en .gitignore
    ok1, out1 = _git("add", "-f", str(rel_registry), capture=True)
    if not ok1:
        log.warning("[SYNC] ⚠️  git add falló: %s", out1)
        print(f"[SYNC] ⚠️  git add falló: {out1[:120]}. Se omite el push.")
        return

    # Verificar si hay algo para commitear
    ok2, status = _git("status", "--porcelain", str(rel_registry), capture=True)
    if not status.strip():
        print("[SYNC] ✅ Sin cambios que subir (registro ya está sincronizado).")
        log.info("[SYNC] Nada para commit (registro sin cambios).")
        return

    # Asegurar identidad de Git antes de commitear (por si es un entorno Debian limpio)
    _, _email = _git("config", "--global", "user.email", capture=True)
    if not _email.strip():
        _git("config", "--global", "user.email", "zerausn@gmail.com")
        _git("config", "--global", "user.name", "zerausn")
        log.info("[SYNC] Identidad de Git configurada automáticamente.")

    ok3, out3 = _git("commit", "-m", commit_msg, capture=True)
    if not ok3:
        log.warning("[SYNC] ⚠️  git commit falló: %s", out3)
        print(f"[SYNC] ⚠️  git commit falló: {out3[:120]}")
        return

    # Hacer pull con rebase ANTES del push para incorporar cambios de otros celulares.
    # --autostash evita que cambios locales no relacionados (por ejemplo TikTok)
    # bloqueen la publicacion del registro compartido de descargas.
    log.info("[SYNC] Sincronizando cambios remotos (pull --rebase --autostash) antes del push...")
    ok_pull, out_pull = _git("pull", "--rebase", "--autostash", "origin", BRANCH_NAME, capture=True)
    if not ok_pull:
        log.warning("[SYNC] ⚠️  git pull --rebase --autostash falló antes del push: %s", out_pull)
        print(f"[SYNC] ⚠️  git pull --rebase --autostash falló. Se conserva el commit local y no se empuja: {out_pull[:120]}")
        _git("rebase", "--abort", capture=True)
        _ensure_git_branch("sync_push post-rebase-fallido")
        return

    if not _ensure_git_branch("sync_push post-rebase"):
        return

    preserved_after_rebase = _preserve_remote_downloads("push")
    if preserved_after_rebase:
        ok_add2, out_add2 = _git("add", "-f", str(rel_registry), capture=True)
        if not ok_add2:
            log.warning("[SYNC] ⚠️  git add falló tras preservar descargados remotos: %s", out_add2)
            print(f"[SYNC] ⚠️  git add falló tras preservar descargados remotos: {out_add2[:120]}. Se omite el push.")
            return
        ok_amend, out_amend = _git("commit", "--amend", "--no-edit", capture=True)
        if not ok_amend:
            log.warning("[SYNC] ⚠️  git commit --amend falló tras preservar remotos: %s", out_amend)
            print(f"[SYNC] ⚠️  git commit --amend falló tras preservar remotos: {out_amend[:120]}")
            return

    # Reintentos para el push (por si hay microcortes o lentitud de red)
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        ok4, out4 = _git("push", "origin", f"HEAD:{BRANCH_NAME}", capture=True)
        if ok4:
            ok_head, head = _git("rev-parse", "HEAD", capture=True)
            head_full = head.strip() if ok_head else ""
            ok_remote, remote_ref = _git("ls-remote", "origin", f"refs/heads/{BRANCH_NAME}", capture=True)
            remote_sha = remote_ref.split()[0] if ok_remote and remote_ref.strip() else ""
            if head_full and remote_sha and remote_sha != head_full:
                log.warning("[SYNC] Push reportó OK, pero remoto quedó en %s y HEAD es %s", remote_sha[:7], head_full[:7])
                if attempt < max_retries:
                    print(f"[SYNC] ⚠️  GitHub no quedó en el commit local; reintentando ({attempt}/{max_retries})...")
                    time.sleep(3)
                else:
                    print("[SYNC] ⚠️  GitHub no quedó en el commit local; se intentará de nuevo después.")
                continue
            ok5, sha = _git("rev-parse", "--short", "HEAD", capture=True)
            sha_str = sha.strip() if ok5 else "?"
            log.info("[SYNC] ✅ Registro subido a GitHub (commit %s) [Intento %d]: %s", sha_str, attempt, commit_msg)
            print(f"[SYNC] ✅ Registro sincronizado en GitHub (commit {sha_str})")
            break
        else:
            log.warning("[SYNC] ⚠️  git push falló (Intento %d/%d): %s", attempt, max_retries, out4)
            if attempt < max_retries:
                print(f"[SYNC] ⚠️  Reintentando subida ({attempt}/{max_retries})...")
                import time
                time.sleep(3)
            else:
                print(f"[SYNC] ⚠️  git push falló (el registro local está actualizado, se intentará en la próxima sesión): {out4[:120]}")


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
            "/usr/bin/python3", YTDLP_BIN,
            "--js-runtimes", "node",
            "--no-part",
            "--merge-output-format", "mkv",
            "--newline", "--quiet", "--no-warnings", "--progress",
            "-o", str(stub) + ".%(ext)s",
        ]
        if COOKIES_FILE:
            ytdlp_cmd_base += ["--cookies", str(COOKIES_FILE)]

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
    main()
