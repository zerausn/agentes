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
    
    # Mapeamos cada item a un slot diferenciado
    # Slot 0 = 07:00:00 (Reels)
    # Slot 1 = 18:30:00 (Feed)
    for i in range(max_items):
        day_offset = i % HORIZON_DAYS
        
        current_date = start_date + timedelta(days=day_offset)
        date_str = current_date.strftime("%Y-%m-%d")
        
        reel_time_str = GOLD_SLOTS[0]
        post_time_str = GOLD_SLOTS[1]
        
        # Inteligencia anti-publicacion inmediata: 
        # Si el slot de hoy ya paso, lo movemos al dia siguiente (o al proximo disponible)
        now = datetime.now()
        
        def adjust_if_past(d_str, t_str):
            dt = datetime.strptime(f"{d_str}T{t_str}", "%Y-%m-%dT%H:%M:%S")
            if dt < now:
                # Si ya paso hoy, lo movemos al dia 30 (fuera de la ventana critica) o simplemente +1 dia
                dt += timedelta(days=1)
            return dt.strftime("%Y-%m-%dT%H:%M:%S")

        entry_reel_time = adjust_if_past(date_str, reel_time_str)
        entry_post_time = adjust_if_past(date_str, post_time_str)

        entry = {
            "fecha": date_str,
            "summary": {"status": "pending"},
            "reel": reels[i] if i < total_reels else None,
            "reel_time": entry_reel_time,
            "post": posts[i] if i < total_posts else None,
            "post_time": entry_post_time,
        }
        calendar.append(entry)

    # Ordenar por fecha y hora para que el scheduler vaya en orden cronologico
    calendar.sort(key=lambda x: (x["fecha"], x["post_time"]))

    with open(CALENDAR_FILE, "w", encoding="utf-8") as handle:
        json.dump(calendar, handle, indent=2, ensure_ascii=False)

    logging.info("Calendario APILADO generado en %s con %s entradas en 29 dias.", CALENDAR_FILE.name, len(calendar))

if __name__ == "__main__":
    generate_calendar()
