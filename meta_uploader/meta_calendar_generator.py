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
        latest_timestamp = get_latest_scheduled_facebook_date()
        if latest_timestamp:
            fb_date = datetime.fromtimestamp(latest_timestamp)
            start_date = fb_date + timedelta(days=1)
            logging.info("Meta tiene post programado maximo el %s. Encadenando nuevo calendario a partir de: %s", 
                         fb_date.strftime("%Y-%m-%d"), start_date.strftime("%Y-%m-%d"))
        else:
            start_date = datetime.now()
            logging.info("Meta no tiene contenidos programados. Iniciando desde hoy: %s", start_date.strftime("%Y-%m-%d"))


    reels = load_queue(REELS_FILE)
    posts = load_queue(POSTS_FILE)
    logging.info("Distribuyendo %s reels y %s posts en el calendario...", len(reels), len(posts))

    calendar = []
    target_days = 400

    for index in range(target_days):
        current_date = start_date + timedelta(days=index)
        date_str = current_date.strftime("%Y-%m-%d")
        entry = {
            "fecha": date_str,
            "reel": reels[index] if index < len(reels) else None,
            "reel_time": f"{date_str}T18:30:00",
            "post": posts[index] if index < len(posts) else None,
            "post_time": f"{date_str}T18:30:00",
        }
        calendar.append(entry)

    with open(CALENDAR_FILE, "w", encoding="utf-8") as handle:
        json.dump(calendar, handle, indent=2, ensure_ascii=False)

    logging.info("Calendario generado en %s con %s dias.", CALENDAR_FILE.name, len(calendar))


if __name__ == "__main__":
    generate_calendar()
