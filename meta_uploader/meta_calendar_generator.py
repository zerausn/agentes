import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from meta_uploader import get_latest_scheduled_facebook_date

BASE_DIR = Path(__file__).resolve().parent
LOG_FILE = BASE_DIR / "calendar.log"
REELS_FILE = BASE_DIR / "pendientes_reels.json"
POSTS_FILE = BASE_DIR / "pendientes_posts.json"
CALENDAR_FILE = BASE_DIR / "meta_calendar.json"

# Configuración Gold Slots
HORIZON_DAYS = 29
GOLD_SLOTS = [
    "07:00:00",  # Slot A (Global Morning)
    "18:30:00",  # Slot B (Local Prime)
    "10:00:00",  # Slot C (Global Mid-day)
    "21:00:00",  # Slot D (Late Night)
    "12:00:00",  # Slot E
    "15:00:00",  # Slot F
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()],
)

def load_queue(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return []

def generate_calendar(start_date=None):
    if start_date is None:
        # Nota: Para el sistema de apilamiento en 29 dias, siempre empezamos desde hoy
        # para asegurar vaciar el disco rapido, ignorando lo que ya este en Meta si queremos "apilar".
        start_date = datetime.now()
        logging.info("Iniciando ciclo de apilamiento desde hoy: %s", start_date.strftime("%Y-%m-%d"))

    reels = load_queue(REELS_FILE)
    posts = load_queue(POSTS_FILE)
    total_reels = len(reels)
    total_posts = len(posts)
    
    max_items = max(total_reels, total_posts)
    logging.info("Generando calendario de APILAMIENTO para %s items en ventana de %s dias...", max_items, HORIZON_DAYS)

    calendar = []
    
    # Mapeamos cada item a un slot ciclico
    for i in range(max_items):
        day_offset = i % HORIZON_DAYS
        slot_index = (i // HORIZON_DAYS) % len(GOLD_SLOTS)
        
        current_date = start_date + timedelta(days=day_offset)
        date_str = current_date.strftime("%Y-%m-%d")
        time_str = GOLD_SLOTS[slot_index]
        
        # Cada item tiene su propia entrada para no mezclar en el mismo slot
        # Pero el usuario menciono "Video 1 Slot A, Video 2 Slot B..."
        # Asi que distribuiremos Reels y Posts en los mismos slots.
        
        entry = {
            "fecha": date_str,
            "summary": {"status": "pending"},
            "reel": reels[i] if i < total_reels else None,
            "reel_time": f"{date_str}T{time_str}",
            "post": posts[i] if i < total_posts else None,
            "post_time": f"{date_str}T{time_str}",
        }
        calendar.append(entry)

    # Ordenar por fecha y hora para que el scheduler vaya en orden cronologico
    calendar.sort(key=lambda x: (x["fecha"], x["reel_time"] if x["reel"] else x["post_time"]))

    with open(CALENDAR_FILE, "w", encoding="utf-8") as handle:
        json.dump(calendar, handle, indent=2, ensure_ascii=False)

    logging.info("Calendario APILADO generado en %s con %s entradas en 29 dias.", CALENDAR_FILE.name, len(calendar))

if __name__ == "__main__":
    generate_calendar()
