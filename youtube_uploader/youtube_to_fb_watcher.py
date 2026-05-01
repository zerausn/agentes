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

# Configuracion basica
BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "youtube_to_fb_sync.log"
CREDENTIALS_DIR = BASE_DIR / "credentials"
HISTORY_FILE = BASE_DIR / "sync_history.json"

SYNC_DEST_CANDIDATES = [
    Path("/media/zerausn/D69493CF9493B08B/Users/ZN-/Documents/ADM/Carpeta 1/videos subidos exitosamente"),
    Path("/home/zerausn/Documents/ADM/Carpeta 1/videos subidos exitosamente"),
]

# Filtros
TARGET_DATE = datetime(2026, 3, 1, tzinfo=timezone.utc)
BATCH_SIZE = 20

SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]
YT_DLP_BIN = str((BASE_DIR.parents[1] / ".venv_parrot_sync" / "bin" / "yt-dlp").resolve())
YTDLP_BASE_ARGS = [
    YT_DLP_BIN if Path(YT_DLP_BIN).exists() else "yt-dlp",
    "--js-runtimes",
    "node",
    "--force-ipv4",
    "--concurrent-fragments",
    "1",
    "--no-part",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()],
)


def get_authenticated_service(client_secret_file, key_idx):
    """Obtiene el servicio de YouTube v3 usando una llave especifica."""
    token_file = CREDENTIALS_DIR / f"token_sync_{key_idx}.json"

    creds = None
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_file), SCOPES)
            creds = flow.run_local_server(port=0)

        token_file.write_text(creds.to_json(), encoding="utf-8")

    return build("youtube", "v3", credentials=creds)


def load_history():
    if not HISTORY_FILE.exists():
        return set()
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        return set(data)
    except Exception:
        return set()


def save_history(history):
    HISTORY_FILE.write_text(json.dumps(list(history), indent=2), encoding="utf-8")


def resolve_destination_dir():
    for candidate in SYNC_DEST_CANDIDATES:
        if candidate.exists():
            return candidate
    return SYNC_DEST_CANDIDATES[0]


DEST_DIR = resolve_destination_dir()


def sanitize_title_for_filename(title):
    sanitized = re.sub(r'[\\/*?:"<>|]', "", str(title or "")).strip()
    sanitized = re.sub(r"\s+", " ", sanitized)
    return sanitized or "video_sin_titulo"


def final_destination_path(dest_dir, title):
    base_name = sanitize_title_for_filename(title)
    return dest_dir / f"{base_name}.mp4"


def legacy_destination_path(dest_dir, title, video_id):
    base_name = sanitize_title_for_filename(title)
    return dest_dir / f"{base_name}_{video_id}.mp4"


def adopt_legacy_named_file(dest_dir, title, video_id):
    final_path = final_destination_path(dest_dir, title)
    legacy_path = legacy_destination_path(dest_dir, title, video_id)

    if final_path.exists():
        return final_path

    if legacy_path.exists():
        try:
            os.rename(legacy_path, final_path)
            logging.info("  Archivo legado renombrado a nombre canonico: %s", final_path.name)
            return final_path
        except OSError as exc:
            logging.warning("  No se pudo renombrar archivo legado %s: %s", legacy_path.name, exc)

    return final_path


def get_public_videos(youtube, history, limit=100):
    """Obtiene videos publicos antiguos, deteniendose al alcanzar el limite."""
    logging.info("Buscando videos publicos no sincronizados...")

    channels_resp = youtube.channels().list(mine=True, part="contentDetails").execute()
    uploads_playlist_id = channels_resp["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    videos = []
    seen_ids = set()
    next_page_token = None

    while True:
        playlist_items_resp = youtube.playlistItems().list(
            playlistId=uploads_playlist_id,
            part="snippet,status",
            maxResults=50,
            pageToken=next_page_token,
        ).execute()

        for item in playlist_items_resp.get("items", []):
            video_id = item["snippet"]["resourceId"]["videoId"]
            if video_id in seen_ids:
                continue
            seen_ids.add(video_id)

            if video_id in history:
                continue

            status = item.get("status", {}).get("privacyStatus")
            if status != "public":
                continue

            published_at_str = item["snippet"]["publishedAt"]
            published_at = datetime.fromisoformat(published_at_str.replace("Z", "+00:00"))

            if published_at < TARGET_DATE:
                videos.append(
                    {
                        "id": video_id,
                        "title": item["snippet"]["title"],
                        "publishedAt": published_at_str,
                    }
                )

            if len(videos) >= limit:
                break

        if len(videos) >= limit:
            break

        next_page_token = playlist_items_resp.get("nextPageToken")
        if not next_page_token:
            break

    return videos


def download_video(video_id, title):
    """Descarga en maxima calidad priorizando 4K y usando EJS+Node para recuperar DASH reales."""
    final_path = adopt_legacy_named_file(DEST_DIR, title, video_id)
    url = f"https://www.youtube.com/watch?v={video_id}"
    download_stub = DEST_DIR / f"dl_{video_id}_merged"
    merged_mp4_tmp = DEST_DIR / f"dl_{video_id}_merged.mp4"
    merged_mkv_tmp = DEST_DIR / f"dl_{video_id}_merged.mkv"
    merged_webm_tmp = DEST_DIR / f"dl_{video_id}_merged.webm"

    logging.info("Descargando [%s] (%s) en 4K...", title, video_id)

    try:
        if final_path.exists() and final_path.stat().st_size > 1024 * 1024:
            logging.info("  Ya existe archivo canonico, se reutiliza sin renombrar: %s", final_path.name)
            return True

        logging.info("  Paso 1/2: Descargando video+audio en maxima calidad...")
        format_candidates = [
            "bestvideo[height>=2160]+bestaudio[ext=m4a]/bestvideo[height>=2160]+bestaudio/best[height>=2160]/bestvideo+bestaudio/best",
            "bestvideo+bestaudio/best",
        ]
        downloaded_path = None

        for selector in format_candidates:
            logging.info("    Intentando selector combinado: %s", selector)
            _cleanup_temps(merged_mp4_tmp, merged_mkv_tmp, merged_webm_tmp)
            cmd_download = [
                *YTDLP_BASE_ARGS,
                "-f",
                selector,
                "-o",
                str(download_stub) + ".%(ext)s",
                "--merge-output-format",
                "mkv",
                url,
            ]
            try:
                subprocess.run(cmd_download, check=True)
                result_returncode = 0
            except subprocess.CalledProcessError as exc:
                result_returncode = exc.returncode

            for candidate in [merged_mkv_tmp, merged_mp4_tmp, merged_webm_tmp]:
                if candidate.exists() and candidate.stat().st_size > 1024 * 1024:
                    downloaded_path = candidate
                    break

            if result_returncode == 0 and downloaded_path is not None:
                logging.info("    Descarga OK con selector '%s': %.1f MB", selector, downloaded_path.stat().st_size / (1024 * 1024))
                break

            downloaded_path = None
            logging.warning("    Selector combinado '%s' fallo, probando siguiente...", selector)

        if downloaded_path is None:
            logging.error("  No se pudo descargar el asset 4K con audio.")
            _cleanup_temps(merged_mp4_tmp, merged_mkv_tmp, merged_webm_tmp)
            return False

        if downloaded_path.suffix.lower() == ".mp4":
            os.rename(downloaded_path, final_path)
            logging.info("  Descarga final MP4 OK: %s", final_path.name)
            return True

        logging.info("  Paso 2/2: Transcodificando a MP4 compatible manteniendo maxima calidad...")
        transcode_cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(downloaded_path),
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(final_path),
        ]
        subprocess.run(transcode_cmd, check=True, capture_output=True)
        _cleanup_temps(downloaded_path)

        if final_path.exists() and final_path.stat().st_size > 1024 * 1024:
            logging.info("  Descarga final transcodificada OK: %s (%.1f MB)", final_path.name, final_path.stat().st_size / (1024 * 1024))
            return True

        logging.error("  La transcodificacion a MP4 fallo para %s", video_id)
        return False

    except subprocess.CalledProcessError as exc:
        logging.error("Fallo la descarga de %s: %s", video_id, exc)
        _cleanup_temps(merged_mp4_tmp, merged_mkv_tmp, merged_webm_tmp)
        return False


def _cleanup_temps(*paths):
    """Elimina archivos temporales de descarga."""
    for path in paths:
        if path and path.exists():
            try:
                path.unlink()
            except Exception:
                pass


def generate_checklist(videos, history):
    """Genera un archivo Markdown con el listado de videos y su estado."""
    checklist_path = BASE_DIR / "checklist_sincronizacion.md"
    lines = [
        "# Checklist de Sincronizacion YouTube -> Facebook\n",
        f"Generado el: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
        "Estado: [x] Sincronizado | [ ] Pendiente\n\n",
    ]

    for video in videos:
        status = "[x]" if video["id"] in history else "[ ]"
        lines.append(f"- {status} {video['publishedAt'][:10]} | {video['title']} (ID: {video['id']})\n")

    checklist_path.write_text("".join(lines), encoding="utf-8")
    logging.info("Checklist generado en: %s", checklist_path)


def main():
    parser = argparse.ArgumentParser(description="YouTube to Meta Video Sync Watcher")
    parser.add_argument("--dry-run", action="store_true", help="Solo listar videos encontrados sin descargar.")
    parser.add_argument("--limit", type=int, default=BATCH_SIZE, help="Cantidad maxima de videos a descargar en este lote.")
    parser.add_argument("--generate-checklist", action="store_true", help="Generar checklist.md con todos los videos compatibles.")
    args = parser.parse_args()

    client_secrets = sorted(list(CREDENTIALS_DIR.glob("client_secret_*.json")))
    if not client_secrets:
        logging.error("No se encontraron archivos client_secret_*.json en credentials/")
        return

    history = load_history()
    all_videos = []

    search_limit = 5000 if args.generate_checklist else args.limit + 50

    for idx, secret_file in enumerate(client_secrets):
        try:
            logging.info("Probando llave %s (%s)...", idx, secret_file.name)
            youtube = get_authenticated_service(secret_file, idx)
            all_videos = get_public_videos(youtube, history, limit=search_limit)
            break
        except HttpError as exc:
            if exc.resp.status == 430 or "quota" in str(exc).lower():
                logging.warning("Cuota excedida en llave %s. Intentando con la siguiente...", idx)
                continue
            raise
        except Exception as exc:
            logging.error("Error inesperado con llave %s: %s", idx, exc)
            continue

    if not all_videos:
        logging.info("No se encontraron videos pendientes (o se agotaron las cuotas de listado).")
        return

    if args.generate_checklist:
        generate_checklist(all_videos, history)
        if not args.dry_run and not args.limit:
            return

    to_sync = [video for video in all_videos if video["id"] not in history]

    if args.dry_run:
        logging.info("MODO DRY-RUN: Los siguientes %s videos se descargarian:", len(to_sync[:args.limit]))
        for video in to_sync[:args.limit]:
            logging.info("- [%s] %s (ID: %s)", video["publishedAt"], video["title"], video["id"])
        return

    if not DEST_DIR.exists():
        logging.error("Directorio de destino no encontrado: %s", DEST_DIR)
        return

    success_count = 0
    batch = to_sync[:args.limit]
    for video in batch:
        if download_video(video["id"], video["title"]):
            history.add(video["id"])
            success_count += 1
            save_history(history)
            logging.info("Esperando 5 segundos antes de la siguiente descarga para evitar bloqueos...")
            time.sleep(5)

    logging.info("Sincronizacion finalizada: %s videos descargados.", success_count)


if __name__ == "__main__":
    main()
