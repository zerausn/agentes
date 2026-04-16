"""
nudge_stuck_videos.py - Intenta reactivar el procesamiento de videos atascados
haciendo un metadata touch (actualización menor de descripción) vía videos.update.

Según reportes de la comunidad, actualizar metadata puede forzar a YouTube
a re-evaluar el pipeline de procesamiento de un video atascado.
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

BASE_DIR = Path(__file__).resolve().parent
CREDENTIALS_DIR = BASE_DIR / "credentials"
SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(BASE_DIR / "nudge_stuck_videos.log", encoding="utf-8"),
    ],
)


def get_authenticated_service():
    client_files = sorted(path.name for path in CREDENTIALS_DIR.glob("client_secret*.json"))
    if not client_files:
        logging.error("No hay client_secret_X.json disponibles.")
        return None

    client_secret_path = CREDENTIALS_DIR / client_files[0]
    # Usar un token separado para no interferir con el uploader
    creds_cache_file = CREDENTIALS_DIR / "token_admin.json"
    creds = None
    if creds_cache_file.exists():
        creds = Credentials.from_authorized_user_file(str(creds_cache_file), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                logging.warning("Token expirado, solicitando nueva autenticacion...")
                flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), SCOPES)
                creds = flow.run_local_server(port=0)
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), SCOPES)
            creds = flow.run_local_server(port=0)
        creds_cache_file.write_text(creds.to_json(), encoding="utf-8")

    return build("youtube", "v3", credentials=creds)


def nudge_video(youtube, video_id, heavy=False):
    """
    Hace un metadata touch: lee la descripción actual y la reescribe.
    Si heavy=True, también cambia la categoría y altera ligeramente el título.
    """
    try:
        # Leer metadata actual
        result = youtube.videos().list(
            part="snippet,status",
            id=video_id,
        ).execute()

        items = result.get("items", [])
        if not items:
            logging.warning("Video %s no encontrado en la API.", video_id)
            return False

        video = items[0]
        snippet = video["snippet"]
        status = video["status"]
        current_title = snippet.get("title", "")
        current_desc = snippet.get("description", "")
        current_cat = snippet.get("categoryId", "22")

        # Touch: añadir o quitar un espacio Unicode invisible al final
        if current_desc.endswith("\u200B"):
            new_desc = current_desc.rstrip("\u200B")
        else:
            new_desc = current_desc + "\u200B"

        new_title = current_title
        new_cat = current_cat

        if heavy:
            logging.info("Aplicando HEAVY NUDGE a %s", video_id)
            # Alterar titulo ligeramente
            if " " in current_title:
                if current_title.endswith(" "):
                    new_title = current_title.rstrip(" ")
                else:
                    new_title = current_title + " "
            
            # Cambiar categoria (si es 24 poner 22, si es otra poner 24)
            new_cat = "22" if current_cat == "24" else "24"

        # Actualizar snippet
        update_body = {
            "id": video_id,
            "snippet": {
                "title": new_title,
                "description": new_desc,
                "categoryId": new_cat,
            },
        }
        if snippet.get("tags"):
            update_body["snippet"]["tags"] = snippet["tags"]
        if snippet.get("defaultLanguage"):
            update_body["snippet"]["defaultLanguage"] = snippet["defaultLanguage"]

        youtube.videos().update(part="snippet", body=update_body).execute()

        # Si es heavy, intentar alternar privacidad de private a public y viceversa (si es posible)
        if heavy:
            current_privacy = status.get("privacyStatus", "private")
            # No lo hacemos a public por riesgo de notificaciones, pero podemos cambiarlo a unlisted y luego private
            # O simplemente dejar el cambio de categoria/titulo como trigger suficiente.
            pass

        logging.info("NUDGE OK: [%s] %s", video_id, new_title[:60])
        return True

    except HttpError as exc:
        logging.error("Error haciendo nudge a %s: %s", video_id, exc)
        return False
    except Exception as exc:
        logging.error("Error inesperado en nudge de %s: %s", video_id, exc)
        return False


def check_processing_status(youtube, video_ids):
    """Verifica el estado actual de procesamiento de una lista de videos."""
    results = {}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i + 50]
        ids_str = ",".join(batch)
        response = youtube.videos().list(
            part="status,processingDetails",
            id=ids_str,
        ).execute()
        for video in response.get("items", []):
            vid = video["id"]
            status = video.get("status", {})
            processing = video.get("processingDetails", {})
            results[vid] = {
                "uploadStatus": status.get("uploadStatus", "unknown"),
                "processingStatus": processing.get("processingStatus", "unknown"),
            }
    return results


def main():
    # Cargar lista de videos atascados
    diag_file = BASE_DIR / "processing_diagnostic.json"
    rescue_file = BASE_DIR / "processing_rescue_report.json"
    if not diag_file.exists():
        logging.error("Ejecuta diagnose_processing.py primero.")
        return

    diag = json.loads(diag_file.read_text(encoding="utf-8"))
    stuck_videos = diag.get("problematic_videos", [])

    unresolved_ids = []
    if rescue_file.exists():
        rescue_report = json.loads(rescue_file.read_text(encoding="utf-8"))
        unresolved_data = [item.get("stuck", {}) for item in rescue_report.get("unresolved", []) if item.get("stuck", {}).get("id")]
        if unresolved_data:
            stuck_videos = unresolved_data
            unresolved_ids = [v["id"] for v in unresolved_data]
            logging.info("Usando solo videos sin copia procesada segun processing_rescue_report.json.")

    if not stuck_videos:
        logging.info("No hay videos atascados.")
        return

    logging.info("Se intentara reactivar %s videos atascados.", len(stuck_videos))

    youtube = get_authenticated_service()
    if not youtube:
        return

    # Fase 1: Nudge todos los videos
    success_count = 0
    failed_ids = []
    for v in stuck_videos:
        vid = v["id"]
        # Si es un video sin copia procesada, aplicar Heavy Nudge
        is_orphan = v.get("id") in unresolved_ids
        ok = nudge_video(youtube, vid, heavy=is_orphan)
        if ok:
            success_count += 1
        else:
            failed_ids.append(vid)
        time.sleep(1)  # Evitar rate limiting

    logging.info(
        "Nudge completado: %s exitosos, %s fallidos.",
        success_count, len(failed_ids),
    )

    if failed_ids:
        logging.warning("Videos que no se pudieron tocar: %s", failed_ids)

    # Fase 2: Esperar 60 segundos y verificar si alguno cambió
    logging.info("Esperando 60s para verificar si el nudge activo el procesamiento...")
    time.sleep(60)

    all_ids = [v["id"] for v in stuck_videos]
    post_status = check_processing_status(youtube, all_ids)

    fixed = 0
    still_stuck = 0
    for vid, status in post_status.items():
        if status["uploadStatus"] == "processed":
            logging.info("RECUPERADO: %s ahora esta procesado.", vid)
            fixed += 1
        else:
            still_stuck += 1

    print(f"\n{'='*60}")
    print(f"RESULTADO DEL NUDGE")
    print(f"{'='*60}")
    print(f"Videos tocados:      {success_count}")
    print(f"Recuperados:         {fixed}")
    print(f"Aun atascados:       {still_stuck}")
    print(f"Fallos de nudge:     {len(failed_ids)}")
    print(f"{'='*60}")

    if still_stuck > 0:
        print(
            "\nNOTA: Los videos que siguen atascados pueden necesitar mas tiempo.\n"
            "YouTube puede tardar hasta 24h en re-procesar tras un nudge.\n"
            "Ejecuta diagnose_processing.py manana para verificar."
        )


if __name__ == "__main__":
    main()
