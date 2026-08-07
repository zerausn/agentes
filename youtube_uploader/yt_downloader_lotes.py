"""
yt_downloader_lotes.py
Descargador de YouTube por lotes mensuales para Termux/proot-Debian.

- Lista todos los videos PUBLICOS del canal anteriores a TARGET_DATE (2026-04-27).
- Muestra menú interactivo de lotes (agrupados por mes).
- Lleva registro en yt_lotes_registro.json de descargados/pendientes/fallidos.
- Guarda los archivos en /sdcard/Antigravity/crudos/
"""

import json
import logging
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

# ─── Rutas ────────────────────────────────────────────────────────────────────
BASE_DIR       = Path("/root/agentes/youtube_uploader")
CREDENTIALS_DIR = BASE_DIR / "credentials"
REGISTRY_FILE  = BASE_DIR / "yt_lotes_registro.json"
LOG_FILE       = BASE_DIR / "yt_lotes_downloader.log"
DEST_DIR       = Path("/sdcard/Antigravity/crudos")
TEMP_DIR       = BASE_DIR / "yt_temp_dl"

# ─── Configuración ────────────────────────────────────────────────────────────
TARGET_DATE   = datetime(2026, 4, 27, tzinfo=timezone.utc)   # solo videos ANTES de esta fecha
SCOPES        = ["https://www.googleapis.com/auth/youtube.readonly"]
YTDLP_BIN     = shutil.which("yt-dlp") or "/usr/local/bin/yt-dlp"
FFMPEG_PRESET = os.getenv("AGENTES_FFMPEG_PRESET", "fast")
FFMPEG_CRF    = os.getenv("AGENTES_FFMPEG_CRF", "20")
FFMPEG_AUDIO  = os.getenv("AGENTES_FFMPEG_AUDIO_BITRATE", "192k")

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
    registry[month][vid_id]["status"] = status
    registry[month][vid_id]["downloaded_at"] = datetime.now().strftime("%Y-%m-%d %H:%M") if status == "descargado" else registry[month][vid_id].get("downloaded_at")
    if filepath:
        registry[month][vid_id]["file"] = filepath
    save_registry(registry)


# ═══════════════════════════════════════════════════════════════════════════════
# ESCANEO DE YOUTUBE
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_all_public_videos(youtube) -> list:
    """Descarga la lista completa de videos públicos anteriores a TARGET_DATE."""
    log.info("Escaneando canal de YouTube (videos públicos < %s)...", TARGET_DATE.date())
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

            if item.get("status", {}).get("privacyStatus") != "public":
                continue

            pub_str = item["snippet"]["publishedAt"]
            pub = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
            if pub >= TARGET_DATE:
                continue

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

    log.info("  → %s videos públicos encontrados antes de %s", len(videos), TARGET_DATE.date())
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
            }
    save_registry(registry)
    return registry


# ═══════════════════════════════════════════════════════════════════════════════
# DESCARGA
# ═══════════════════════════════════════════════════════════════════════════════

def sanitize(title: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", str(title or "")).strip()[:80] or "video_sin_titulo"


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
    print("=" * 54)
    print("  5_BAJAR_YOUTUBE — Descargador por Lotes")
    print("=" * 54)


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
    print("ESTADO GENERAL:")
    print(f"  Total videos públicos (< 2026-04-27): {total}")
    print(f"  Ya descargados : {descargados}  ✅")
    print(f"  Pendientes     : {pendientes}  ⏳")
    print(f"  Fallidos       : {fallidos}  ❌")


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


def print_menu(pending_months: list) -> int:
    print()
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
        choice = print_menu(pending_months)

        if choice == 0:
            print("\nSaliendo. ¡Hasta luego!")
            break

        # ── Descargar el lote seleccionado ──────────────────────────────────
        month, vids_to_download = pending_months[choice - 1]
        print(f"\n{'='*54}")
        print(f"  Descargando lote: {month} ({len(vids_to_download)} videos)")
        print(f"  Destino: {DEST_DIR}")
        print(f"{'='*54}\n")

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
        print(f"{'='*54}")
        print(f"  Lote {month} terminado. ✅ {ok_count}  ❌ {fail_count}")
        print(f"{'='*54}")
        input("\nPresiona Enter para volver al menú...")
        registry = load_registry()  # recargar por si algo cambió


if __name__ == "__main__":
    main()
