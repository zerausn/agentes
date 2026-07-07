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
from datetime import datetime, timezone
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# ─── Rutas ────────────────────────────────────────────────────────────────────
BASE_DIR        = Path("/root/agentes/youtube_uploader")
REPO_DIR        = Path("/root/agentes")
CREDENTIALS_DIR = BASE_DIR / "credentials"
REGISTRY_FILE   = BASE_DIR / "yt_lotes_registro_sin_limite.json"
LOG_FILE        = BASE_DIR / "yt_lotes_sin_limite.log"
DEST_DIR        = Path("/sdcard/Antigravity/crudos")
TEMP_DIR        = BASE_DIR / "yt_temp_dl"

# ─── Configuración ────────────────────────────────────────────────────────────
# SIN TARGET_DATE: se descargan TODOS los videos públicos del canal.
SCOPES        = ["https://www.googleapis.com/auth/youtube.readonly"]
YTDLP_BIN     = shutil.which("yt-dlp") or "/usr/local/bin/yt-dlp"
FFMPEG_PRESET = os.getenv("AGENTES_FFMPEG_PRESET", "fast")
FFMPEG_CRF    = os.getenv("AGENTES_FFMPEG_CRF", "20")
FFMPEG_AUDIO  = os.getenv("AGENTES_FFMPEG_AUDIO_BITRATE", "192k")

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


def sync_pull():
    """
    Hace git pull antes de empezar para obtener el registro más reciente
    de cualquier otro dispositivo. Loguea el resultado pero no interrumpe.
    """
    print()
    print("[SYNC] Descargando registro actualizado desde GitHub...")
    log.info("[SYNC] git pull origin linux-arm64")

    # Primero el fetch para ver si hay algo nuevo
    ok, out = _git("fetch", "origin", "linux-arm64", "--quiet", capture=True)
    if not ok:
        log.warning("[SYNC] ⚠️  git fetch falló (sin conexión?): %s", out)
        print("[SYNC] ⚠️  No se pudo conectar con GitHub. Se usará el registro local.")
        return

    # Verificar si el remoto tiene commits nuevos
    ok2, local  = _git("rev-parse", "HEAD", capture=True)
    ok3, remote = _git("rev-parse", "origin/linux-arm64", capture=True)
    local  = local.strip()
    remote = remote.strip()

    if local == remote:
        print("[SYNC] ✅ Registro ya está al día (sin cambios remotos).")
        log.info("[SYNC] Sin cambios remotos (HEAD=%s).", local[:7])
        return

    # Hay cambios: hacer pull
    ok4, out4 = _git("pull", "--ff-only", "origin", "linux-arm64", capture=True)
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
        log.warning("[SYNC] ⚠️  git pull falló: %s", out4)
        print(f"[SYNC] ⚠️  git pull falló (se continúa con registro local): {out4[:120]}")


def sync_push(month: str, count: int):
    """
    Hace git add + commit + push del registro tras una descarga exitosa.
    No interrumpe el flujo si falla.
    """
    print()
    print("[SYNC] Subiendo registro actualizado a GitHub...")
    log.info("[SYNC] Intentando git push (después de descargar %d videos de %s).", count, month)

    rel_registry = REGISTRY_FILE.relative_to(REPO_DIR)

    # Solo agregar el archivo de registro, no otros cambios
    ok1, _ = _git("add", str(rel_registry), capture=True)
    if not ok1:
        log.warning("[SYNC] ⚠️  git add falló.")
        print("[SYNC] ⚠️  git add falló. Se omite el push.")
        return

    # Verificar si hay algo para commitear
    ok2, status = _git("status", "--porcelain", str(rel_registry), capture=True)
    if not status.strip():
        print("[SYNC] ✅ Sin cambios que subir (registro ya está sincronizado).")
        log.info("[SYNC] Nada para commit (registro sin cambios).")
        return

    commit_msg = f"sync: {DEVICE_NAME} descargó {count} videos ({month})"
    ok3, out3 = _git("commit", "-m", commit_msg, capture=True)
    if not ok3:
        log.warning("[SYNC] ⚠️  git commit falló: %s", out3)
        print(f"[SYNC] ⚠️  git commit falló: {out3[:120]}")
        return

    ok4, out4 = _git("push", "origin", "linux-arm64", capture=True)
    if ok4:
        ok5, sha = _git("rev-parse", "--short", "HEAD", capture=True)
        sha_str = sha.strip() if ok5 else "?"
        log.info("[SYNC] ✅ Registro subido a GitHub (commit %s): %s", sha_str, commit_msg)
        print(f"[SYNC] ✅ Registro sincronizado en GitHub (commit {sha_str})")
    else:
        log.warning("[SYNC] ⚠️  git push falló: %s", out4)
        print(f"[SYNC] ⚠️  git push falló (el registro local está actualizado, se intentará en la próxima sesión): {out4[:120]}")


# ═══════════════════════════════════════════════════════════════════════════════
# AUTENTICACIÓN
# ═══════════════════════════════════════════════════════════════════════════════

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

def fetch_all_public_videos(youtube) -> list:
    """
    Descarga la lista COMPLETA de videos públicos del canal.
    SIN restricción de fecha. Videos privados/ocultos/unlisted son ignorados.
    """
    log.info("Escaneando canal de YouTube (TODOS los videos públicos)...")
    channels_resp = youtube.channels().list(mine=True, part="contentDetails").execute()
    uploads_id = channels_resp["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    videos = []
    seen = set()
    next_page = None

    while True:
        resp = youtube.playlistItems().list(
            playlistId=uploads_id,
            part="snippet,status",
            maxResults=50,
            pageToken=next_page,
        ).execute()

        for item in resp.get("items", []):
            vid_id = item["snippet"]["resourceId"]["videoId"]
            if vid_id in seen:
                continue
            seen.add(vid_id)

            # ── FILTRO DE PRIVACIDAD ─────────────────────────────────────────
            # Solo se incluyen videos públicos. Los privados, ocultos (unlisted)
            # o no listados son ignorados completamente.
            if item.get("status", {}).get("privacyStatus") != "public":
                continue
            # ── FIN FILTRO PRIVACIDAD ────────────────────────────────────────

            pub_str = item["snippet"]["publishedAt"]
            pub = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
            month = pub.strftime("%Y-%m")
            videos.append({
                "id":          vid_id,
                "title":       item["snippet"]["title"],
                "publishedAt": pub_str,
                "month":       month,
            })

        next_page = resp.get("nextPageToken")
        if not next_page:
            break

    log.info("  → %s videos públicos encontrados en total.", len(videos))
    return videos


def sync_registry_with_channel(registry: dict, channel_videos: list) -> dict:
    """Añade al registro los videos nuevos (sin borrar los ya descargados)."""
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
    save_registry(registry)
    return registry


# ═══════════════════════════════════════════════════════════════════════════════
# DESCARGA
# ═══════════════════════════════════════════════════════════════════════════════

def sanitize(title: str) -> str:
    return re.sub(r'[\\/*?"<>|]', "", str(title or "")).strip()[:80] or "video_sin_titulo"


def download_video(vid_id: str, title: str) -> str | None:
    """Descarga un video en 4K y lo transcoda a MP4. Retorna la ruta final o None."""
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    DEST_DIR.mkdir(parents=True, exist_ok=True)

    safe_title = sanitize(title)
    final_path = DEST_DIR / f"{safe_title}.mp4"
    url = f"https://www.youtube.com/watch?v={vid_id}"
    stub = TEMP_DIR / f"dl_{vid_id}"
    mkv_tmp = TEMP_DIR / f"dl_{vid_id}.mkv"
    mp4_tmp = TEMP_DIR / f"dl_{vid_id}.mp4"

    if final_path.exists() and final_path.stat().st_size > 1024 * 1024:
        log.info("  Ya existe en destino, se omite: %s", final_path.name)
        return str(final_path)

    # ── Paso 1: Descarga con yt-dlp ──────────────────────────────────────────
    log.info("  [1/2] Descargando en 4K: %s", title)
    ytdlp_cmd_base = [
        "/usr/bin/python3", YTDLP_BIN,
        "--js-runtimes", "node",
        "--force-ipv4",
        "--no-part",
        "--merge-output-format", "mkv",
        "-o", str(stub) + ".%(ext)s",
    ]

    downloaded_path = None
    for selector in [
        "bestvideo[height>=2160]+bestaudio[ext=m4a]/bestvideo[height>=2160]+bestaudio/best[height>=2160]/bestvideo+bestaudio/best",
        "bestvideo+bestaudio/best",
        "best",
    ]:
        for f in [mkv_tmp, mp4_tmp]:
            if f.exists():
                f.unlink(missing_ok=True)
        try:
            subprocess.run([*ytdlp_cmd_base, "-f", selector, url], check=True)
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
        downloaded_path.rename(final_path)
        return str(final_path)

    # ── Paso 2: Transcodificación a MP4 ──────────────────────────────────────
    log.info("  [2/2] Transcodificando a MP4...")
    prog_file = TEMP_DIR / f"ffprog_{vid_id}.txt"
    try:
        dur_out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(downloaded_path)],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        total_dur = float(dur_out)
    except Exception:
        total_dur = 0

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

        # ── Descargar el lote seleccionado ──────────────────────────────────
        month, vids_to_download = pending_months[choice - 1]
        print(f"\n{'='*58}")
        print(f"  Descargando lote: {month} ({len(vids_to_download)} videos)")
        print(f"  Dispositivo     : {DEVICE_NAME}")
        print(f"  Destino         : {DEST_DIR}")
        print(f"{'='*58}\n")

        ok_count = 0
        fail_count = 0
        for i, (vid_id, info) in enumerate(vids_to_download, start=1):
            print(f"\n[{i}/{len(vids_to_download)}] {info['title']}")
            result = download_video(vid_id, info["title"])
            if result:
                mark_video(registry, month, vid_id, "descargado", result)
                ok_count += 1
            else:
                mark_video(registry, month, vid_id, "fallido")
                fail_count += 1
            time.sleep(2)

        print()
        print(f"{'='*58}")
        print(f"  Lote {month} terminado. ✅ {ok_count}  ❌ {fail_count}")
        print(f"{'='*58}")

        # ── Sincronizar registro con GitHub tras el lote ─────────────────
        if ok_count > 0:
            sync_push(month, ok_count)

        input("\nPresiona Enter para volver al menú...")
        registry = load_registry()  # recargar por si algo cambió


if __name__ == "__main__":
    main()
