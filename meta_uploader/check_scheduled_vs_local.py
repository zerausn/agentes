import logging
import os
from pathlib import Path

# Configurar logs para la consola
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

try:
    from meta_uploader import (
        find_existing_facebook_video_by_caption_marker,
        find_existing_instagram_media_by_caption_marker,
    )
except ImportError:
    logging.error("No se pudo importar meta_uploader.")
    exit(1)

TARGET_DIR = Path(r"C:\Users\ZN-\Documents\ADM\Carpeta 1\videos subidos exitosamente")

def check_scheduled():
    if not TARGET_DIR.exists():
        logging.warning("No se encontro la carpeta %s", TARGET_DIR)
        return

    files = list(TARGET_DIR.glob("*.mp4"))
    logging.info("--- Buscando videos PROGRAMADOS en Meta (%s archivos locales) ---", len(files))
    
    scheduled_matches = []
    
    for file_path in files:
        marker = file_path.stem
        logging.info("Consultando Meta para: %s", marker)
        
        # Consultar en Facebook
        info = find_existing_facebook_video_by_caption_marker(marker)
        
        if info:
            # Si 'published' es False, significa que esta programado o en revision
            is_published = info.get("published", True)
            sched_time = info.get("scheduled_publish_time")
            
            if not is_published or sched_time:
                logging.info("  [PROGRAMADO] Encontrado: %s para la fecha %s", marker, sched_time)
                scheduled_matches.append((marker, sched_time))
            else:
                # Ya esta publicado, no es lo que el usuario busca ahora
                pass

    logging.info("--- Resultado Final ---")
    if scheduled_matches:
        logging.info("Se han encontrado %s videos que ya estan PROGRAMADOS en Facebook pero siguen en tu carpeta local:", len(scheduled_matches))
        for marker, stime in scheduled_matches:
            logging.info(" - %s (Programado para: %s)", marker, stime)
    else:
        logging.info("No se encontraron videos programados de esta carpeta en Facebook.")

if __name__ == "__main__":
    check_scheduled()
