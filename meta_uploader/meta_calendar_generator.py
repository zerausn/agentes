import json
from datetime import datetime, timedelta
import logging

LOG_FILE = "calendar.log"
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()])

def generate_calendar(start_date=None):
    if start_date is None:
        start_date = datetime.now()
        
    calendar = []
    
    try:
        with open("pendientes_reels.json", "r", encoding="utf-8") as f:
            reels = json.load(f)
    except FileNotFoundError:
        reels = []
        
    try:
        with open("pendientes_posts.json", "r", encoding="utf-8") as f:
            posts = json.load(f)
    except FileNotFoundError:
        posts = []
        
    logging.info(f"Distribuyendo {len(reels)} Reels y {len(posts)} Posts en el calendario...")

    # Generamos los días necesarios basados en el mayor de los dos (Reels o Posts), ya que es máximo 1 por día
    max_days = max(len(reels), len(posts))
    
    for i in range(max_days):
        current_date = start_date + timedelta(days=i)
        dia_str = current_date.strftime("%Y-%m-%d")
        
        # Horarios óptimos (Reels a la tarde, Posts al mediodía)
        reel_time = "18:00:00"
        post_time = "12:00:00"
        
        entry = {
            "fecha": dia_str,
            "reel": None,
            "reel_time": f"{dia_str}T{reel_time}",
            "post": None,
            "post_time": f"{dia_str}T{post_time}"
        }
        
        if i < len(reels):
            entry["reel"] = reels[i]
            
        if i < len(posts):
            entry["post"] = posts[i]
            
        calendar.append(entry)
        
    with open("meta_calendar.json", "w", encoding="utf-8") as f:
        json.dump(calendar, f, indent=4)
        
    logging.info(f"Calendario generado exitosamente con {len(calendar)} días en 'meta_calendar.json'.")

if __name__ == "__main__":
    generate_calendar()
