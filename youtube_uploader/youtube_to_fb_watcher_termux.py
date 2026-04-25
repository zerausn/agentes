import argparse
import json
import logging
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ─── Rutas Termux ────────────────────────────────────────────────────────────
BASE_DIR = Path("/data/data/com.termux/files/home/agentes/youtube_uploader")
LOG_FILE = BASE_DIR / "youtube_to_fb_sync.log"
CREDENTIALS_DIR = BASE_DIR / "credentials"
HISTORY_FILE = BASE_DIR / "history.json"          # nombre correcto en el celular
DEST_DIR = BASE_DIR / "downloads"                 # ruta local en el celular
PUBLIC_DIR = Path("/sdcard/Download/Agentes_YouTube_4K")  # para la Galeria

TARGET_DATE = datetime(2026, 3, 1, tzinfo=timezone.utc)
BATCH_SIZE = 5
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]
YTDLP_BASE_ARGS = [
    "/usr/bin/python3", "/usr/local/bin/yt-dlp",
    "--js-runtimes", "node", "--force-ipv4",
    "--concurrent-fragments", "1", "--no-part",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()],
)


def get_authenticated_service(client_secret_file, key_idx):
    # El celular tiene los tokens como token_0.json, token_1.json, etc.
    token_file = CREDENTIALS_DIR / f"token_{key_idx}.json"
    creds = None
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            token_file.write_text(creds.to_json(), encoding="utf-8")
        else:
            logging.error("Token expirado y sin refresh_token para llave %s. Reautenticar manualmente.", key_idx)
            raise Exception("Token invalido")
    return build("youtube", "v3", credentials=creds)


def load_history():
    if not HISTORY_FILE.exists():
        return set()
    try:
        return set(json.loads(HISTORY_FILE.read_text(encoding="utf-8")))
    except Exception:
        return set()


def save_history(history):
    HISTORY_FILE.write_text(json.dumps(list(history), indent=2), encoding="utf-8")


def sanitize(title):
    return re.sub(r'[\\/*?:"<>|]', "", str(title or "")).strip() or "video_sin_titulo"


def get_public_videos(youtube, history, limit=100):
    logging.info("Buscando videos publicos anteriores al 1-Mar-2026...")
    channels_resp = youtube.channels().list(mine=True, part="contentDetails").execute()
    uploads_id = channels_resp["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    videos, seen, next_page = [], set(), None
    while True:
        resp = youtube.playlistItems().list(
            playlistId=uploads_id, part="snippet,status",
            maxResults=50, pageToken=next_page
        ).execute()
        for item in resp.get("items", []):
            vid_id = item["snippet"]["resourceId"]["videoId"]
            if vid_id in seen or vid_id in history:
                continue
            seen.add(vid_id)
            if item.get("status", {}).get("privacyStatus") != "public":
                continue
            pub = datetime.fromisoformat(item["snippet"]["publishedAt"].replace("Z", "+00:00"))
            if pub < TARGET_DATE:
                videos.append({"id": vid_id, "title": item["snippet"]["title"], "publishedAt": item["snippet"]["publishedAt"]})
            if len(videos) >= limit:
                break
        if len(videos) >= limit:
            break
        next_page = resp.get("nextPageToken")
        if not next_page:
            break
    logging.info("  Encontrados %s videos pendientes.", len(videos))
    return videos


def download_video(video_id, title):
    final_path = DEST_DIR / f"{sanitize(title)}.mp4"
    url = f"https://www.youtube.com/watch?v={video_id}"
    stub = DEST_DIR / f"dl_{video_id}_merged"
    mkv_tmp = DEST_DIR / f"dl_{video_id}_merged.mkv"
    mp4_tmp = DEST_DIR / f"dl_{video_id}_merged.mp4"

    logging.info("Descargando [%s] (%s)...", title, video_id)

    if final_path.exists() and final_path.stat().st_size > 1024 * 1024:
        logging.info("  Ya existe, se omite.")
        return True

    # Paso 1: Descarga
    logging.info("  Paso 1/2: Descargando en 4K...")
    downloaded_path = None
    for selector in [
        "bestvideo[height>=2160]+bestaudio[ext=m4a]/bestvideo[height>=2160]+bestaudio/best[height>=2160]/bestvideo+bestaudio/best",
        "bestvideo+bestaudio/best",
        "best",
    ]:
        for f in [mkv_tmp, mp4_tmp]:
            if f.exists(): f.unlink(missing_ok=True)
        cmd = [*YTDLP_BASE_ARGS, "-f", selector, "-o", str(stub) + ".%(ext)s", "--merge-output-format", "mkv", url]
        try:
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError:
            pass
        for c in [mkv_tmp, mp4_tmp]:
            if c.exists() and c.stat().st_size > 1024 * 1024:
                downloaded_path = c
                break
        if downloaded_path:
            logging.info("  Descarga OK (%.1f MB) con selector: %s", downloaded_path.stat().st_size / (1024 * 1024), selector)
            break

    if not downloaded_path:
        logging.error("  Fallo la descarga.")
        return False

    if downloaded_path.suffix.lower() == ".mp4":
        os.rename(downloaded_path, final_path)
        _copy_to_public(final_path)
        return True

    # Paso 2: Transcode con progreso INLINE
    logging.info("  Paso 2/2: Transcodificando a MP4... (progreso en pantalla)")
    dur_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=noprint_wrappers=1:nokey=1", str(downloaded_path)]
    try:
        total_dur = float(subprocess.check_output(dur_cmd).decode().strip())
    except Exception:
        total_dur = 0

    prog_file = BASE_DIR / "ffmpeg_progress.txt"
    transcode_cmd = [
        "ffmpeg", "-y", "-i", str(downloaded_path),
        "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
        "-progress", str(prog_file),
        str(final_path),
    ]
    process = subprocess.Popen(transcode_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    while process.poll() is None:
        if prog_file.exists() and total_dur > 0:
            try:
                content = prog_file.read_text()
                times = re.findall(r"out_time_us=(\d+)", content)
                speeds = re.findall(r"speed=\s*([\d.]+)x", content)
                if times:
                    cur_s = int(times[-1]) / 1_000_000
                    pct = min((cur_s / total_dur) * 100, 100)
                    spd = float(speeds[-1]) if speeds else 0
                    eta = f"{int((total_dur - cur_s) / spd // 60)}m {int((total_dur - cur_s) / spd % 60)}s" if spd > 0 else "--"
                    print(f"\r  📊 {pct:.1f}% | ETA: {eta} | Vel: {spd:.2f}x   ", end="", flush=True)
            except Exception:
                pass
        time.sleep(2)
    print()

    if downloaded_path.exists():
        downloaded_path.unlink(missing_ok=True)

    if final_path.exists() and final_path.stat().st_size > 1024 * 1024:
        logging.info("  ✅ Listo: %s (%.1f MB)", final_path.name, final_path.stat().st_size / (1024 * 1024))
        _copy_to_public(final_path)
        return True

    logging.error("  Transcodificacion fallo.")
    return False


def _copy_to_public(path):
    try:
        PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
        dest = PUBLIC_DIR / path.name
        if not dest.exists():
            subprocess.run(["cp", str(path), str(dest)], check=True)
            logging.info("  Copiado a Downloads: %s", dest.name)
    except Exception as e:
        logging.warning("  No se pudo copiar a Downloads: %s", e)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=BATCH_SIZE)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    DEST_DIR.mkdir(parents=True, exist_ok=True)
    client_secrets = sorted(CREDENTIALS_DIR.glob("client_secret_*.json"))
    if not client_secrets:
        logging.error("No se encontraron client_secret_*.json")
        return

    history = load_history()
    youtube = None
    for idx, secret in enumerate(client_secrets):
        try:
            logging.info("Probando llave %s...", idx)
            youtube = get_authenticated_service(secret, idx)
            break
        except Exception as exc:
            logging.warning("Llave %s fallo: %s", idx, exc)

    if not youtube:
        logging.error("No se pudo autenticar con ninguna llave.")
        return

    videos = get_public_videos(youtube, history, limit=args.limit + 50)
    to_sync = [v for v in videos if v["id"] not in history]

    if not to_sync:
        logging.info("No hay videos pendientes de sincronizar.")
        return

    if args.dry_run:
        for v in to_sync[:args.limit]:
            logging.info("[DRY] %s - %s", v["publishedAt"][:10], v["title"])
        return

    ok = 0
    for v in to_sync[:args.limit]:
        if download_video(v["id"], v["title"]):
            history.add(v["id"])
            save_history(history)
            ok += 1
            time.sleep(5)

    logging.info("Finalizacion: %s/%s videos descargados.", ok, min(len(to_sync), args.limit))


if __name__ == "__main__":
    main()
