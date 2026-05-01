import json
from pathlib import Path
import logging

BASE_DIR = Path(__file__).resolve().parent
CALENDAR_FILE = BASE_DIR / "meta_calendar.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def reset_spam_pause():
    if not CALENDAR_FILE.exists():
        logging.error("No se encontró meta_calendar.json")
        return

    try:
        with open(CALENDAR_FILE, "r", encoding="utf-8") as f:
            plan = json.load(f)
        
        modified = 0
        for day in plan:
            summary = day.get("summary", {})
            if summary.get("status") == "paused_on_spam":
                logging.info(f"Reseteando pausa por spam en fecha: {day.get('fecha')}")
                summary["status"] = "pending"
                summary.pop("active_lane", None)
                summary.pop("active_filename", None)
                
                # También reseteamos el estado del lane que falló (usualmente post o reel)
                if day.get("post") and day["post"].get("status") == "in_progress":
                    day["post"]["status"] = "pending"
                if day.get("reel") and day["reel"].get("status") == "in_progress":
                    day["reel"]["status"] = "pending"
                
                modified += 1
        
        if modified > 0:
            with open(CALENDAR_FILE, "w", encoding="utf-8") as f:
                json.dump(plan, f, indent=2, ensure_ascii=False)
            logging.info(f"Se corrigieron {modified} entradas. Ya puedes reiniciar el supervisor.")
        else:
            logging.info("No se encontraron entradas con estado 'paused_on_spam'.")

    except Exception as e:
        logging.error(f"Error al procesar el calendario: {e}")

if __name__ == "__main__":
    reset_spam_pause()
