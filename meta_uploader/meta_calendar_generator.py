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

# Configuración Gold Slots Concentrados
HORIZON_DAYS = 28
GOLD_SLOTS = [
    "07:00:00",  # Slot A (Mañana)
    "18:30:00",  # Slot B (Tarde)
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
        start_date = datetime.now()
        logging.info("Iniciando ciclo de apilamiento concentrado desde hoy: %s", start_date.strftime("%Y-%m-%d"))

    reels = load_queue(REELS_FILE)
    posts = load_queue(POSTS_FILE)
    total_reels = len(reels)
    total_posts = len(posts)
    
    max_items = max(total_reels, total_posts)
    logging.info("Generando calendario de APILAMIENTO CONCENTRADO para %s items en ventana de 28 dias...", max_items)

    calendar = []
    
    for i in range(max_items):
        # Lógica de vueltas (Laps)
        # Cada vuelta llena 28 días x 2 slots = 56 videos
        lap_size = HORIZON_DAYS * len(GOLD_SLOTS)
        lap_index = i // lap_size
        slot_index = (i // HORIZON_DAYS) % len(GOLD_SLOTS)
        day_offset = (i % HORIZON_DAYS) + 1  # Empezamos mañana (Día 1 offset)
        
        current_date_base = start_date + timedelta(days=day_offset)
        date_str = current_date_base.strftime("%Y-%m-%d")
        
        # Calculamos la hora final sumando el offset de minutos por vuelta
        time_base_str = GOLD_SLOTS[slot_index]
        time_obj = datetime.strptime(time_base_str, "%H:%M:%S")
        final_time_obj = time_obj + timedelta(minutes=lap_index)
        final_time_str = final_time_obj.strftime("%H:%M:%S")
        
        entry = {
            "fecha": date_str,
            "summary": {"status": "pending"},
            "reel": reels[i] if i < total_reels else None,
            "reel_time": f"{date_str}T{final_time_str}",
            "post": posts[i] if i < total_posts else None,
            "post_time": f"{date_str}T{final_time_str}",
        }
        calendar.append(entry)

    # Ordenar cronológicamente
    calendar.sort(key=lambda x: (x["fecha"], x["post_time"]))

    with open(CALENDAR_FILE, "w", encoding="utf-8") as handle:
        json.dump(calendar, handle, indent=2, ensure_ascii=False)

    logging.info("Calendario CONCENTRADO generado en %s con %s entradas en ventana de %s dias.", CALENDAR_FILE.name, len(calendar), HORIZON_DAYS)

if __name__ == "__main__":
    generate_calendar()
