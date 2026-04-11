"""
Actualiza la hora de publicación de todos los videos programados en la página de Facebook
de 12:00 (hora vieja) a 18:30 (hora Colombia - hora óptima de audiencia).

USO:
    python meta_uploader/reschedule_to_1830.py --dry-run   # Solo muestra qué cambiaría
    python meta_uploader/reschedule_to_1830.py             # Aplica los cambios en Meta
"""
import argparse
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

from meta_uploader import _iter_graph_collection, FB_PAGE_ID, META_FB_PAGE_TOKEN
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

BOGOTA_TZ = ZoneInfo("America/Bogota")
TARGET_HOUR = 18
TARGET_MINUTE = 30
GRAPH_URL = "https://graph.facebook.com/v19.0"


def get_new_slot_unix(fecha_str: str) -> int:
    """Dado '2026-04-11', devuelve el unix timestamp para las 18:30 Bogotá de ese día."""
    dt = datetime.strptime(fecha_str, "%Y-%m-%d").replace(
        hour=TARGET_HOUR,
        minute=TARGET_MINUTE,
        second=0,
        microsecond=0,
        tzinfo=BOGOTA_TZ,
    )
    return int(dt.astimezone(timezone.utc).timestamp())


def reschedule_video(video_id: str, new_unix: int, dry_run: bool) -> bool:
    """Llama a la API de Meta para actualizar el scheduled_publish_time del video."""
    if dry_run:
        logging.info("  [DRY-RUN] Se actualizaría video %s -> unix %s", video_id, new_unix)
        return True

    url = f"{GRAPH_URL}/{video_id}"
    resp = requests.post(url, data={
        "scheduled_publish_time": new_unix,
        "access_token": META_FB_PAGE_TOKEN,
    }, timeout=30)

    if resp.ok and resp.json().get("success"):
        logging.info("  ✅ Video %s reprogramado correctamente.", video_id)
        return True
    else:
        logging.error("  ❌ Error reprogramando %s: %s", video_id, resp.text[:300])
        return False


def main(dry_run: bool):
    if not FB_PAGE_ID or not META_FB_PAGE_TOKEN:
        logging.error("Faltan credenciales (FB_PAGE_ID / META_FB_PAGE_TOKEN) en .env")
        sys.exit(1)

    logging.info("Consultando videos programados en Facebook (pagina %s)...", FB_PAGE_ID)

    total = 0
    updated = 0
    skipped = 0
    failed = 0

    def iter_scheduled_videos():
        """Itera los posts programados de la página."""
        url = f"{GRAPH_URL}/{FB_PAGE_ID}/scheduled_posts"
        params = {
            "access_token": META_FB_PAGE_TOKEN,
            "fields": "id,scheduled_publish_time",
            "limit": "50",
        }
        pages = 0
        while url and pages < 20:
            resp = requests.get(url, params=params, timeout=30)
            if not resp.ok:
                logging.error("Error consultando scheduled_posts: %s", resp.text[:300])
                break
            data = resp.json()
            for item in data.get("data", []):
                yield item
            paging = data.get("paging", {})
            url = paging.get("next")
            params = {}  # next URL ya trae todos los params
            pages += 1

    for item in iter_scheduled_videos():
        video_id = str(item.get("id", ""))
        current_unix = item.get("scheduled_publish_time")
        if not video_id or not current_unix:
            continue

        current_unix = int(current_unix)
        current_dt = datetime.fromtimestamp(current_unix, tz=BOGOTA_TZ)
        fecha_str = current_dt.strftime("%Y-%m-%d")
        current_time_str = current_dt.strftime("%H:%M")
        total += 1

        # Solo actualizar si NO son las 18:30
        if current_dt.hour == TARGET_HOUR and current_dt.minute == TARGET_MINUTE:
            logging.info("  [OK] %s | %s ya está a las 18:30 - sin cambio.", video_id, fecha_str)
            skipped += 1
            continue

        new_unix = get_new_slot_unix(fecha_str)
        now_unix = int(datetime.now(timezone.utc).timestamp())

        # No podemos programar en el pasado (mínimo 15 min en el futuro)
        if new_unix <= now_unix + 900:
            logging.warning(
                "  [SKIP] %s | %s 18:30 ya pasó o es muy próximo. Se deja en %s.",
                video_id, fecha_str, current_time_str
            )
            skipped += 1
            continue

        logging.info(
            "  [UPDATE] %s | %s %s → 18:30 (unix %s → %s)",
            video_id, fecha_str, current_time_str, current_unix, new_unix
        )
        ok = reschedule_video(video_id, new_unix, dry_run)
        if ok:
            updated += 1
        else:
            failed += 1

        # Pausa pequeña para no saturar la API
        time.sleep(0.5)

    logging.info(
        "\n=== RESUMEN ===\nTotal encontrados: %s | Actualizados: %s | Ya correctos: %s | Fallidos: %s",
        total, updated, skipped, failed
    )
    if dry_run:
        logging.info("(Modo DRY-RUN: no se hizo ningún cambio real en Meta)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reprograma todos los scheduled_posts de Meta a las 18:30 hora Colombia.")
    parser.add_argument("--dry-run", action="store_true", help="Solo muestra qué cambiaría sin modificar Meta.")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
