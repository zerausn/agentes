"""
cleanup_zombies.py - Elimina los videos marcados como 'zombis' (duplicados de copias ya procesadas).
Este script lee 'processing_diagnostic.json' y procede a borrar los IDs confirmados por el usuario.
"""
import json
import logging
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

BASE_DIR = Path(__file__).resolve().parent
CREDENTIALS_DIR = BASE_DIR / "credentials"
DIAGNOSTIC_FILE = BASE_DIR / "processing_diagnostic.json"
SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(BASE_DIR / "cleanup_zombies.log", encoding="utf-8"),
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


def main():
    if not DIAGNOSTIC_FILE.exists():
        logging.error("No se encontro 'processing_diagnostic.json'. Ejecuta 'diagnose_processing.py' primero.")
        return

    with DIAGNOSTIC_FILE.open("r", encoding="utf-8") as f:
        diagnostic = json.load(f)

    zombies = [
        v for v in diagnostic.get("problematic_videos", [])
        if v.get("hasProcessedSibling")
    ]

    if not zombies:
        logging.info("No se detectaron videos zombis (duplicados con copia buena) para borrar.")
        return

    logging.info("Se han detectado %d videos zombis para borrar.", len(zombies))
    
    youtube = get_authenticated_service()
    if not youtube:
        return

    deleted_count = 0
    failed_count = 0

    for video in zombies:
        vid = video["id"]
        title = video.get("title", "Sin titulo")
        logging.info("Borrando zombi: [%s] %s", vid, title)
        try:
            youtube.videos().delete(id=vid).execute()
            logging.info("BORRADO OK: %s", vid)
            deleted_count += 1
        except HttpError as e:
            logging.error("Error al borrar %s: %s", vid, e)
            failed_count += 1
        except Exception as e:
            logging.error("Error inesperado al borrar %s: %s", vid, e)
            failed_count += 1

    logging.info("Limpieza completada: %d borrados, %d fallidos.", deleted_count, failed_count)
    print("\n" + "=" * 60)
    print("RESUMEN DE LIMPIEZA")
    print("=" * 60)
    print(f"Zombis detectados: {len(zombies)}")
    print(f"Borrados:          {deleted_count}")
    print(f"Fallos:            {failed_count}")
    print("=" * 60)


if __name__ == "__main__":
    main()
