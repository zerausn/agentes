"""
Diagnostico de videos con procesamiento pendiente/fallido en YouTube.
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

from video_helpers import extract_video_stem

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
            all_video_ids.append(
                {
                    "id": item["snippet"]["resourceId"]["videoId"],
                    "title": item["snippet"]["title"],
                }
            )

        next_page_token = playlist_response.get("nextPageToken")
        if not next_page_token:
            break

    logging.info("Total de videos en el canal: %s", len(all_video_ids))

    problematic = []
    processed_count = 0
    all_summaries = []

    for index in range(0, len(all_video_ids), 50):
        batch = all_video_ids[index:index + 50]
        ids_str = ",".join(video["id"] for video in batch)

        videos_response = youtube.videos().list(
            part="status,processingDetails,contentDetails",
            id=ids_str,
        ).execute()

        title_map = {video["id"]: video["title"] for video in batch}

        for video in videos_response.get("items", []):
            vid = video["id"]
            status = video.get("status", {})
            processing = video.get("processingDetails", {})
            upload_status = status.get("uploadStatus", "unknown")
            privacy = status.get("privacyStatus", "unknown")
            publish_at = status.get("publishAt", "")
            title = title_map.get(vid, "?")

            summary = {
                "id": vid,
                "title": title,
                "stem": extract_video_stem(title),
                "uploadStatus": upload_status,
                "privacyStatus": privacy,
                "publishAt": publish_at,
                "processingStatus": processing.get("processingStatus", "unknown"),
                "processingProgress": processing.get("processingProgress", {}),
                "failureReason": status.get("failureReason", ""),
                "rejectionReason": status.get("rejectionReason", ""),
            }
            all_summaries.append(summary)

            if upload_status != "processed":
                problematic.append(summary)
            else:
                processed_count += 1

    processed_by_stem = {}
    for item in all_summaries:
        if item["uploadStatus"] != "processed" or not item["stem"]:
            continue
        processed_by_stem.setdefault(item["stem"], []).append(item["id"])

    for item in problematic:
        sibling_ids = [video_id for video_id in processed_by_stem.get(item["stem"], []) if video_id != item["id"]]
        item["processedSiblingIds"] = sibling_ids
        item["hasProcessedSibling"] = bool(sibling_ids)

    return all_video_ids, problematic, processed_count


def main():
    youtube = get_authenticated_service()
    if not youtube:
        return

    logging.info("Consultando estado de procesamiento de todos los videos...")
    all_videos, problematic, processed = diagnose_all_videos(youtube)

    rescued = sum(1 for item in problematic if item.get("hasProcessedSibling"))
    unresolved = len(problematic) - rescued

    print("\n" + "=" * 80)
    print("DIAGNOSTICO DE PROCESAMIENTO DE YOUTUBE")
    print("=" * 80)
    print(f"Total de videos en el canal: {len(all_videos)}")
    print(f"Procesados correctamente:    {processed}")
    print(f"Con problemas:               {len(problematic)}")
    print(f"Con copia procesada:         {rescued}")
    print(f"Sin copia procesada:         {unresolved}")
    print("=" * 80)

    if problematic:
        by_status = {}
        for video in problematic:
            by_status.setdefault(video["uploadStatus"], []).append(video)

        for status_name, videos in by_status.items():
            print(f"\n--- Estado: {status_name} ({len(videos)} videos) ---")
            for video in videos:
                reason = video.get("failureReason") or video.get("rejectionReason") or ""
                reason_str = f" | Razon: {reason}" if reason else ""
                rescue_str = " | copia OK existente" if video.get("hasProcessedSibling") else " | sin copia OK"
                print(f"  [{video['id']}] {video['title'][:60]}{reason_str}{rescue_str}")

        report_path = BASE_DIR / "processing_diagnostic.json"
        with report_path.open("w", encoding="utf-8") as handle:
            json.dump(
                {
                    "total_videos": len(all_videos),
                    "processed_ok": processed,
                    "problematic_count": len(problematic),
                    "problematic_with_processed_copy": rescued,
                    "problematic_without_processed_copy": unresolved,
                    "by_status": {key: len(value) for key, value in by_status.items()},
                    "problematic_videos": problematic,
                },
                handle,
                indent=2,
                ensure_ascii=False,
            )
        print(f"\nReporte guardado en: {report_path}")
    else:
        print("\nTodos los videos estan procesados correctamente.")


if __name__ == "__main__":
    main()
