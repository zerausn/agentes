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

# Configuración básica
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()],
)

def get_authenticated_service(client_secret_file, key_idx):
    """Obtiene el servicio de YouTube v3 usando una llave específica."""
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


def unique_destination_path(dest_dir, title, video_id):
    base_name = sanitize_title_for_filename(title)
    candidate = dest_dir / f"{base_name}.mp4"
    if not candidate.exists():
        return candidate
    return dest_dir / f"{base_name}_{video_id}.mp4"


def get_public_videos(youtube, history, limit=100):
    """Obtiene videos públicos antiguos, deteniéndose al alcanzar el límite."""
    logging.info("Buscando videos públicos no sincronizados...")
    
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
            pageToken=next_page_token
        ).execute()
        
        for item in playlist_items_resp.get("items", []):
            video_id = item["snippet"]["resourceId"]["videoId"]
            if video_id in seen_ids:
                continue
            seen_ids.add(video_id)

            # Ignorar si ya está en el historial
            if video_id in history:
                continue
                
            status = item.get("status", {}).get("privacyStatus")
            if status != "public":
                continue
                
            published_at_str = item["snippet"]["publishedAt"]
            published_at = datetime.fromisoformat(published_at_str.replace("Z", "+00:00"))
            
            if published_at < TARGET_DATE:
                videos.append({
                    "id": video_id,
                    "title": item["snippet"]["title"],
                    "publishedAt": published_at_str
                })
            
            if len(videos) >= limit:
                break
        
        if len(videos) >= limit:
            break
            
        next_page_token = playlist_items_resp.get("nextPageToken")
        if not next_page_token:
            break
            
    return videos

def download_video(video_id, title):
    """Descarga un video en 4K usando estrategia de 2 pasos para evitar 403 en audio."""
    final_path = unique_destination_path(DEST_DIR, title, video_id)

    url = f"https://www.youtube.com/watch?v={video_id}"
    EDGE_PROFILE = "/home/zerausn/.var/app/com.microsoft.Edge/config/microsoft-edge"
    
    video_tmp = DEST_DIR / f"dl_{video_id}_video.mp4"
    audio_tmp = DEST_DIR / f"dl_{video_id}_audio.m4a"
    merged_tmp = DEST_DIR / f"dl_{video_id}_merged.mp4"

    video_args = [
        "--extractor-args", "youtube:player_client=ios",
        "--force-ipv4",
        "--concurrent-fragments", "1",
        "--no-part",
    ]

    # Args para AUDIO: web CON cookies (para autenticación, evita restricciones)
    audio_args_base = [
        "--cookies-from-browser", f"edge:{EDGE_PROFILE}",
        "--force-ipv4",
        "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
        "--referer", "https://www.youtube.com/",
        "--concurrent-fragments", "1",
        "--sleep-requests", "1",
        "--retry-sleep", "10",
        "--no-part",
    ]
    
    logging.info(f"Descargando [{title}] ({video_id}) en 4K...")
    
    try:
        # PASO 1: Descargar solo VIDEO en máxima calidad
        logging.info(f"  Paso 1/3: Descargando video 4K...")
        video_ok = False
        for client in ["ios", "tv", "web"]:
            logging.info(f"    Intentando cliente para video: {client}")
            # iOS/TV sin cookies para máxima velocidad, web con cookies por si acaso
            client_video_args = [] if client in ["ios", "tv"] else ["--cookies-from-browser", f"edge:{EDGE_PROFILE}"]
            cmd_video = [
                "yt-dlp", "-f", "bestvideo",
                "--extractor-args", f"youtube:player_client={client}",
                "-o", str(video_tmp),
                *client_video_args,
                "--force-ipv4", "--concurrent-fragments", "1", "--no-part",
                url
            ]
            try:
                # Removemos capture_output para que el progreso se vea en el terminal 
                subprocess.run(cmd_video, check=True)
                result_returncode = 0
            except subprocess.CalledProcessError as e:
                result_returncode = e.returncode
                
            if result_returncode == 0 and video_tmp.exists() and video_tmp.stat().st_size > 1024 * 1024:
                video_ok = True
                logging.info(f"    Video OK con cliente '{client}': {video_tmp.stat().st_size / (1024*1024):.1f} MB")
                break
            else:
                if video_tmp.exists(): video_tmp.unlink()
                logging.warning(f"    Cliente video '{client}' falló, probando siguiente...")

        if not video_ok:
            logging.error(f"  No se pudo descargar video 4K con ningún cliente.")
            _cleanup_temps(video_tmp, audio_tmp, merged_tmp)
            return False
        
        # PASO 2: Descargar solo AUDIO con múltiples estrategias
        logging.info(f"  Paso 2/3: Descargando audio...")
        audio_ok = False
        
        # Probar múltiples clientes para obtener el audio
        for client in ["ios", "tv", "web", "mweb"]:
            logging.info(f"    Intentando cliente: {client}")
            # iOS no soporta cookies, los demás sí
            client_cookies = [] if client == "ios" else ["--cookies-from-browser", f"edge:{EDGE_PROFILE}"]
            cmd_audio = [
                "yt-dlp", "-f", "bestaudio",
                "--extractor-args", f"youtube:player_client={client}",
                "-o", str(audio_tmp),
                *client_cookies,
                "--force-ipv4", "--concurrent-fragments", "1", "--no-part",
                url
            ]
            try:
                subprocess.run(cmd_audio, check=True)
                audio_returncode = 0
            except subprocess.CalledProcessError as e:
                audio_returncode = e.returncode
                
            if audio_returncode == 0 and audio_tmp.exists() and audio_tmp.stat().st_size > 10000:
                audio_ok = True
                logging.info(f"    Audio OK con cliente '{client}': {audio_tmp.stat().st_size / 1024:.1f} KB")
                break
            else:
                # Limpiar intento fallido
                if audio_tmp.exists():
                    audio_tmp.unlink()
                logging.warning(f"    Cliente '{client}' falló para audio, probando siguiente...")
        
        if not audio_ok:
            logging.warning(f"  No se pudo descargar audio por separado. Intentando formato combinado...")
            combined_ok = False
            combined_candidates = [
                ("bv*+ba/b", ["--extractor-args", "youtube:player_client=ios"]),
                (
                    "bestvideo*+bestaudio/best",
                    [
                        "--cookies-from-browser", f"edge:{EDGE_PROFILE}",
                        "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
                        "--referer", "https://www.youtube.com/",
                    ],
                ),
            ]

            for format_selector, extra_args in combined_candidates:
                logging.info("    Intentando fallback combinado con formato: %s", format_selector)
                cmd_combined = [
                    "yt-dlp",
                    "-f",
                    format_selector,
                    "-o",
                    str(merged_tmp),
                    "--merge-output-format",
                    "mp4",
                    "--force-ipv4",
                    "--concurrent-fragments",
                    "1",
                    "--no-part",
                    *extra_args,
                    url,
                ]
                try:
                    subprocess.run(cmd_combined, check=True)
                    combined_returncode = 0
                except subprocess.CalledProcessError as e:
                    combined_returncode = e.returncode

                if combined_returncode == 0 and merged_tmp.exists() and merged_tmp.stat().st_size > 1024 * 1024:
                    combined_ok = True
                    break
                if merged_tmp.exists():
                    merged_tmp.unlink()

            if combined_ok:
                os.rename(merged_tmp, final_path)
                _cleanup_temps(video_tmp, audio_tmp, None)
                logging.info(f"  Descarga combinada exitosa: {final_path.name}")
                return True

            logging.error(f"  Todas las estrategias de audio fallaron para {video_id}")
            _cleanup_temps(video_tmp, audio_tmp, merged_tmp)
            return False
        
        # PASO 3: Mezclar video + audio con ffmpeg
        logging.info(f"  Paso 3/3: Mezclando video + audio con ffmpeg...")
        cmd_merge = [
            "ffmpeg", "-y",
            "-i", str(video_tmp),
            "-i", str(audio_tmp),
            "-c", "copy",
            "-movflags", "+faststart",
            str(merged_tmp)
        ]
        subprocess.run(cmd_merge, check=True, capture_output=True)
        
        if merged_tmp.exists() and merged_tmp.stat().st_size > 1024 * 1024:
            os.rename(merged_tmp, final_path)
            _cleanup_temps(video_tmp, audio_tmp, None)
            logging.info(f"  ✅ Descarga exitosa: {final_path.name} ({final_path.stat().st_size / (1024*1024):.1f} MB)")
            return True
        else:
            logging.error(f"  Merge falló para {video_id}")
            _cleanup_temps(video_tmp, audio_tmp, merged_tmp)
            return False
            
    except subprocess.CalledProcessError as e:
        logging.error(f"Fallo la descarga de {video_id}: {e}")
        _cleanup_temps(video_tmp, audio_tmp, merged_tmp)
        return False

def _cleanup_temps(*paths):
    """Elimina archivos temporales de descarga."""
    for p in paths:
        if p and p.exists():
            try:
                p.unlink()
            except Exception:
                pass


def generate_checklist(videos, history):
    """Genera un archivo Markdown con el listado de videos y su estado."""
    checklist_path = BASE_DIR / "checklist_sincronizacion.md"
    lines = ["# Checklist de Sincronización YouTube -> Facebook\n", 
             f"Generado el: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n",
             "Estado: [x] Sincronizado | [ ] Pendiente\n\n"]
    
    for v in videos:
        status = "[x]" if v["id"] in history else "[ ]"
        lines.append(f"- {status} {v['publishedAt'][:10]} | {v['title']} (ID: {v['id']})\n")
    
    checklist_path.write_text("".join(lines), encoding="utf-8")
    logging.info(f"Checklist generado en: {checklist_path}")

def main():
    parser = argparse.ArgumentParser(description="YouTube to Meta Video Sync Watcher")
    parser.add_argument("--dry-run", action="store_true", help="Solo listar videos encontrados sin descargar.")
    parser.add_argument("--limit", type=int, default=BATCH_SIZE, help="Cantidad máxima de videos a descargar en este lote.")
    parser.add_argument("--generate-checklist", action="store_true", help="Generar checklist.md con todos los videos compatibles.")
    args = parser.parse_args()

    client_secrets = sorted(list(CREDENTIALS_DIR.glob("client_secret_*.json")))
    if not client_secrets:
        logging.error("No se encontraron archivos client_secret_*.json en credentials/")
        return

    history = load_history()
    all_videos = []
    
    # Intentar con llaves rotativas hasta conseguir la lista de videos
    # Para el checklist listamos TODO (limite alto), para descarga solo el lote
    search_limit = 5000 if args.generate_checklist else args.limit + 50
    
    for idx, secret_file in enumerate(client_secrets):
        try:
            logging.info(f"Probando llave {idx} ({secret_file.name})...")
            youtube = get_authenticated_service(secret_file, idx)
            all_videos = get_public_videos(youtube, history, limit=search_limit)
            break
        except HttpError as e:
            if e.resp.status == 430 or "quota" in str(e).lower():
                logging.warning(f"Cuota excedida en llave {idx}. Intentando con la siguiente...")
                continue
            raise
        except Exception as e:
            logging.error(f"Error inesperado con llave {idx}: {e}")
            continue

    if not all_videos:
        logging.info("No se encontraron videos pendientes (o se agotaron las cuotas de listado).")
        return

    if args.generate_checklist:
        generate_checklist(all_videos, history)
        if not args.dry_run and not args.limit:
            return

    to_sync = [v for v in all_videos if v["id"] not in history]

    if args.dry_run:
        logging.info(f"MODO DRY-RUN: Los siguientes {len(to_sync[:args.limit])} videos se descargarían:")
        for v in to_sync[:args.limit]:
            logging.info(f"- [{v['publishedAt']}] {v['title']} (ID: {v['id']})")
        return

    if not DEST_DIR.exists():
        logging.error(f"Directorio de destino no encontrado: {DEST_DIR}")
        return

    # Procesar descargas
    success_count = 0
    batch = to_sync[:args.limit]
    for video in batch:
        if download_video(video["id"], video["title"]):
            history.add(video["id"])
            success_count += 1
            save_history(history)
            logging.info("Esperando 5 segundos antes de la siguiente descarga para evitar bloqueos...")
            time.sleep(5)
            
    logging.info(f"Sincronización finalizada: {success_count} videos descargados.")

if __name__ == "__main__":
    main()
