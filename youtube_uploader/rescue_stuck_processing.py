"""
Rescata videos atascados en YouTube sin borrar objetos del canal.

Estrategia:
1. Detecta videos con uploadStatus != processed.
2. Busca una copia hermana ya procesada con el mismo stem canonical.
3. Si existe, repara metadata/status de la copia buena cuando haga falta.
4. Si no existe, hace un metadata touch no destructivo sobre el video atascado.
"""
import json
import logging
import time
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from video_helpers import extract_video_stem

BASE_DIR = Path(__file__).resolve().parent
CREDENTIALS_DIR = BASE_DIR / "credentials"
REPORT_FILE = BASE_DIR / "processing_rescue_report.json"
SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(BASE_DIR / "rescue_stuck_processing.log", encoding="utf-8"),
    ],
)


def get_authenticated_service():
    client_files = sorted(path.name for path in CREDENTIALS_DIR.glob("client_secret*.json"))
    if not client_files:
        logging.error("No hay client_secret_X.json disponibles.")
        return None

    client_secret_path = CREDENTIALS_DIR / client_files[0]
    creds_cache_file = CREDENTIALS_DIR / "token_admin.json"
    creds = None
    if creds_cache_file.exists():
        creds = Credentials.from_authorized_user_file(str(creds_cache_file), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                logging.warning("Token admin expirado; se solicitara autenticacion manual.")
                flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), SCOPES)
                creds = flow.run_local_server(port=0)
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), SCOPES)
            creds = flow.run_local_server(port=0)
        creds_cache_file.write_text(creds.to_json(), encoding="utf-8")

    return build("youtube", "v3", credentials=creds)


def fetch_channel_videos(youtube):
    channels_response = youtube.channels().list(mine=True, part="contentDetails").execute()
    uploads_playlist_id = channels_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    playlist_items = []
    next_page_token = None
    while True:
        playlist_response = youtube.playlistItems().list(
            part="snippet",
            playlistId=uploads_playlist_id,
            maxResults=50,
            pageToken=next_page_token,
        ).execute()
        playlist_items.extend(playlist_response.get("items", []))
        next_page_token = playlist_response.get("nextPageToken")
        if not next_page_token:
            break

    all_ids = [item["snippet"]["resourceId"]["videoId"] for item in playlist_items]
    video_rows = []
    for index in range(0, len(all_ids), 50):
        batch_ids = all_ids[index:index + 50]
        response = youtube.videos().list(
            part="snippet,status,processingDetails",
            id=",".join(batch_ids),
        ).execute()
        video_rows.extend(response.get("items", []))

    return video_rows


def summarize_video(video):
    status = video.get("status", {})
    processing = video.get("processingDetails", {})
    snippet = video.get("snippet", {})
    return {
        "id": video["id"],
        "title": snippet.get("title", ""),
        "stem": extract_video_stem(snippet.get("title", "")),
        "uploadStatus": status.get("uploadStatus", "unknown"),
        "privacyStatus": status.get("privacyStatus", "unknown"),
        "publishAt": status.get("publishAt", ""),
        "processingStatus": processing.get("processingStatus", "unknown"),
    }


def choose_best_processed_sibling(stuck_video, candidates):
    stuck_title = stuck_video.get("snippet", {}).get("title", "")
    preferred = []
    fallback = []

    for candidate in candidates:
        candidate_title = candidate.get("snippet", {}).get("title", "")
        if candidate_title == stuck_title:
            preferred.append(candidate)
        else:
            fallback.append(candidate)

    if preferred:
        return preferred[0]
    if fallback:
        return sorted(
            fallback,
            key=lambda item: (".faststart.tmp" in item.get("snippet", {}).get("title", "").lower(), item["id"]),
        )[0]
    return None


def build_snippet_update(target_video, source_video):
    target_snippet = dict(target_video.get("snippet", {}))
    source_snippet = source_video.get("snippet", {})

    mutable_keys = ("title", "description", "tags", "categoryId", "defaultLanguage")
    changed = False
    for key in mutable_keys:
        source_value = source_snippet.get(key)
        target_value = target_snippet.get(key)
        if source_value != target_value and source_value not in (None, ""):
            target_snippet[key] = source_value
            changed = True

    if not changed:
        return None

    payload = {}
    for key in mutable_keys:
        value = target_snippet.get(key)
        if value not in (None, "", []):
            payload[key] = value
    return payload


def build_status_update(target_video, source_video):
    target_status = dict(target_video.get("status", {}))
    source_status = source_video.get("status", {})
    payload = {}
    changed = False

    for key in ("privacyStatus", "license", "embeddable", "publicStatsViewable", "selfDeclaredMadeForKids"):
        if key in source_status and source_status.get(key) != target_status.get(key):
            payload[key] = source_status.get(key)
            changed = True
        elif key in target_status:
            payload[key] = target_status.get(key)

    if source_status.get("privacyStatus") == "private" and source_status.get("publishAt"):
        if source_status.get("publishAt") != target_status.get("publishAt"):
            changed = True
        payload["publishAt"] = source_status.get("publishAt")

    if not changed:
        return None
    return payload


def repair_processed_copy(youtube, target_video, source_video):
    actions = []
    snippet_body = build_snippet_update(target_video, source_video)
    if snippet_body:
        youtube.videos().update(part="snippet", body={"id": target_video["id"], "snippet": snippet_body}).execute()
        actions.append("snippet")

    status_body = build_status_update(target_video, source_video)
    if status_body:
        try:
            youtube.videos().update(part="status", body={"id": target_video["id"], "status": status_body}).execute()
            actions.append("status")
        except HttpError as exc:
            if exc.resp.status == 400 and "invalidPublishAt" in str(exc):
                logging.warning(
                    "Se omitio la sincronizacion de status para %s porque YouTube rechazo publishAt. "
                    "La copia procesada ya existe y se conserva tal cual.",
                    target_video["id"],
                )
                actions.append("status_skipped_invalid_publishAt")
            else:
                raise

    return actions


def touch_video(youtube, video):
    snippet = video.get("snippet", {})
    status = video.get("status", {})
    description = snippet.get("description", "")
    if description.endswith("\u200b"):
        new_description = description.rstrip("\u200b")
    else:
        new_description = description + "\u200b"

    snippet_body = {
        "id": video["id"],
        "snippet": {
            "title": snippet.get("title", ""),
            "description": new_description,
            "categoryId": snippet.get("categoryId", "22"),
        },
    }
    if snippet.get("tags"):
        snippet_body["snippet"]["tags"] = snippet.get("tags")
    if snippet.get("defaultLanguage"):
        snippet_body["snippet"]["defaultLanguage"] = snippet.get("defaultLanguage")

    youtube.videos().update(part="snippet", body=snippet_body).execute()

    status_body = {
        "id": video["id"],
        "status": {
            "privacyStatus": status.get("privacyStatus", "private"),
            "license": status.get("license", "youtube"),
            "embeddable": status.get("embeddable", True),
            "publicStatsViewable": status.get("publicStatsViewable", True),
            "selfDeclaredMadeForKids": status.get("selfDeclaredMadeForKids", False),
        },
    }
    if status.get("privacyStatus") == "private" and status.get("publishAt"):
        status_body["status"]["publishAt"] = status.get("publishAt")
    youtube.videos().update(part="status", body=status_body).execute()


def main():
    youtube = get_authenticated_service()
    if not youtube:
        return

    videos = fetch_channel_videos(youtube)
    by_stem = {}
    for video in videos:
        stem = extract_video_stem(video.get("snippet", {}).get("title", ""))
        if not stem:
            continue
        by_stem.setdefault(stem, []).append(video)

    problematic = [
        video for video in videos
        if video.get("status", {}).get("uploadStatus") != "processed"
    ]
    logging.info("Videos problematicos detectados: %s", len(problematic))

    rescued = []
    unresolved = []
    touched = []

    for stuck_video in problematic:
        stem = extract_video_stem(stuck_video.get("snippet", {}).get("title", ""))
        siblings = by_stem.get(stem, [])
        processed_siblings = [
            sibling for sibling in siblings
            if sibling["id"] != stuck_video["id"] and sibling.get("status", {}).get("uploadStatus") == "processed"
        ]

        if processed_siblings:
            target = choose_best_processed_sibling(stuck_video, processed_siblings)
            try:
                actions = repair_processed_copy(youtube, target, stuck_video)
            except HttpError as exc:
                logging.error("No se pudo reparar copia procesada %s usando %s: %s", target["id"], stuck_video["id"], exc)
                unresolved.append({
                    "stuck": summarize_video(stuck_video),
                    "reason": f"repair_error:{exc.resp.status}",
                })
                continue

            rescued.append({
                "stuck": summarize_video(stuck_video),
                "processed_copy": summarize_video(target),
                "actions": actions,
            })
            if actions:
                logging.info(
                    "RESCATE OK: %s -> %s (%s)",
                    stuck_video["id"],
                    target["id"],
                    ",".join(actions),
                )
            else:
                logging.info("RESCATE OK: %s ya tenia copia buena %s", stuck_video["id"], target["id"])
            continue

        unresolved.append({"stuck": summarize_video(stuck_video), "reason": "no_processed_sibling"})

    for item in unresolved:
        stuck_id = item["stuck"]["id"]
        source_video = next((video for video in problematic if video["id"] == stuck_id), None)
        if not source_video:
            continue
        try:
            touch_video(youtube, source_video)
            touched.append(stuck_id)
            logging.info("NUDGE REFORZADO aplicado a %s", stuck_id)
            time.sleep(1)
        except HttpError as exc:
            logging.error("No se pudo aplicar nudge reforzado a %s: %s", stuck_id, exc)
            item["touchError"] = f"http:{exc.resp.status}"
        except Exception as exc:
            logging.error("No se pudo aplicar nudge reforzado a %s: %s", stuck_id, exc)
            item["touchError"] = str(exc)

    report = {
        "problematic_total": len(problematic),
        "rescued_by_processed_copy": len(rescued),
        "unresolved_total": len(unresolved),
        "touched_unresolved": touched,
        "rescued": rescued,
        "unresolved": unresolved,
    }
    REPORT_FILE.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n" + "=" * 72)
    print("RESCATE DE VIDEOS ATASCADOS")
    print("=" * 72)
    print(f"Problemas detectados:      {len(problematic)}")
    print(f"Rescatados por copia OK:   {len(rescued)}")
    print(f"Sin copia procesada:       {len(unresolved)}")
    print(f"Nudge reforzado aplicado:  {len(touched)}")
    print(f"Reporte: {REPORT_FILE}")
    print("=" * 72)


if __name__ == "__main__":
    main()
