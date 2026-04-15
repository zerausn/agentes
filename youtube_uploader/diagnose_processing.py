"""
Diagnóstico de videos con procesamiento pendiente/fallido en YouTube.
Consulta la API de YouTube Data v3 para listar videos que no han completado
su procesamiento interno (uploadStatus != 'processed').
"""
import json
import logging
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

BASE_DIR = Path(__file__).resolve().parent
CREDENTIALS_DIR = BASE_DIR / "credentials"
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def get_authenticated_service():
    client_files = sorted(path.name for path in CREDENTIALS_DIR.glob("client_secret*.json"))
    if not client_files:
        logging.error("No hay client_secret_X.json disponibles.")
        return None

    client_secret_path = CREDENTIALS_DIR / client_files[0]
    creds_cache_file = CREDENTIALS_DIR / "token_0.json"
    creds = None
    if creds_cache_file.exists():
        creds = Credentials.from_authorized_user_file(str(creds_cache_file), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), SCOPES)
            creds = flow.run_local_server(port=0)
        creds_cache_file.write_text(creds.to_json(), encoding="utf-8")

    return build("youtube", "v3", credentials=creds)


def diagnose_all_videos(youtube):
    channels_response = youtube.channels().list(mine=True, part="contentDetails").execute()
    uploads_playlist_id = channels_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    
    all_video_ids = []
    next_page_token = None
    while True:
        playlist_response = youtube.playlistItems().list(
            part="snippet",
            playlistId=uploads_playlist_id,
            maxResults=50,
            pageToken=next_page_token,
        ).execute()
        
        for item in playlist_response.get("items", []):
            all_video_ids.append({
                "id": item["snippet"]["resourceId"]["videoId"],
                "title": item["snippet"]["title"],
            })
        
        next_page_token = playlist_response.get("nextPageToken")
        if not next_page_token:
            break
    
    logging.info("Total de videos en el canal: %s", len(all_video_ids))
    
    # Consultar de 50 en 50 el estado de procesamiento
    problematic = []
    processed_count = 0
    
    for i in range(0, len(all_video_ids), 50):
        batch = all_video_ids[i:i+50]
        ids_str = ",".join(v["id"] for v in batch)
        
        videos_response = youtube.videos().list(
            part="status,processingDetails,contentDetails",
            id=ids_str,
        ).execute()
        
        title_map = {v["id"]: v["title"] for v in batch}
        
        for video in videos_response.get("items", []):
            vid = video["id"]
            status = video.get("status", {})
            processing = video.get("processingDetails", {})
            upload_status = status.get("uploadStatus", "unknown")
            privacy = status.get("privacyStatus", "unknown")
            publish_at = status.get("publishAt", "")
            
            proc_status = processing.get("processingStatus", "unknown")
            proc_progress = processing.get("processingProgress", {})
            failure_reason = status.get("failureReason", "")
            rejection_reason = status.get("rejectionReason", "")
            
            if upload_status != "processed":
                problematic.append({
                    "id": vid,
                    "title": title_map.get(vid, "?"),
                    "uploadStatus": upload_status,
                    "privacyStatus": privacy,
                    "publishAt": publish_at,
                    "processingStatus": proc_status,
                    "processingProgress": proc_progress,
                    "failureReason": failure_reason,
                    "rejectionReason": rejection_reason,
                })
            else:
                processed_count += 1
    
    return all_video_ids, problematic, processed_count


def main():
    youtube = get_authenticated_service()
    if not youtube:
        return
    
    logging.info("Consultando estado de procesamiento de todos los videos...")
    all_videos, problematic, processed = diagnose_all_videos(youtube)
    
    print("\n" + "=" * 80)
    print(f"DIAGNÓSTICO DE PROCESAMIENTO DE YOUTUBE")
    print(f"=" * 80)
    print(f"Total de videos en el canal: {len(all_videos)}")
    print(f"Procesados correctamente:    {processed}")
    print(f"Con problemas:               {len(problematic)}")
    print(f"=" * 80)
    
    if problematic:
        # Agrupar por estado
        by_status = {}
        for v in problematic:
            key = v["uploadStatus"]
            if key not in by_status:
                by_status[key] = []
            by_status[key].append(v)
        
        for status_name, videos in by_status.items():
            print(f"\n--- Estado: {status_name} ({len(videos)} videos) ---")
            for v in videos:
                reason = v.get("failureReason") or v.get("rejectionReason") or ""
                reason_str = f" | Razón: {reason}" if reason else ""
                print(f"  [{v['id']}] {v['title'][:60]}{reason_str}")
        
        # Guardar reporte
        report_path = BASE_DIR / "processing_diagnostic.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump({
                "total_videos": len(all_videos),
                "processed_ok": processed,
                "problematic_count": len(problematic),
                "by_status": {k: len(v) for k, v in by_status.items()},
                "problematic_videos": problematic,
            }, f, indent=2, ensure_ascii=False)
        print(f"\nReporte guardado en: {report_path}")
    else:
        print("\n✅ Todos los videos están procesados correctamente.")


if __name__ == "__main__":
    main()
