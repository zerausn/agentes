import logging
import os
import shutil
from pathlib import Path

# Configurar logs básicos para la consola antes de importar nada que los configure
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

try:
    from meta_uploader import (
        find_existing_facebook_video_by_caption_marker,
        find_existing_instagram_media_by_caption_marker,
    )
except ImportError:
    logging.error("No se pudo importar meta_uploader. Asegurate de estar en la carpeta correcta.")
    exit(1)

BASE_DIR = Path(__file__).resolve().parent
EXTERNAL_SRC = Path(r"C:\Users\ZN-\Documents\ADM\Carpeta 1\videos subidos exitosamente")
EXTERNAL_DST = Path(r"C:\Users\ZN-\Documents\ADM\Carpeta 1\ya_subidos_fb_ig")

def reconcile_folder(folder_path, label):
    if not folder_path.exists():
        logging.warning("No se encontro la carpeta %s", folder_path)
        return

    EXTERNAL_DST.mkdir(parents=True, exist_ok=True)
    files = list(folder_path.glob("*.mp4"))
    logging.info("--- Reconciliando Carpeta Externa (%s archivos) ---", len(files))
    
    moved_count = 0
    for file_path in files:
        marker = file_path.stem
        logging.info("Revisando en Facebook: %s", marker)
        
        # Consultar si existe en Facebook
        existing = find_existing_facebook_video_by_caption_marker(marker)
        if not existing:
            existing = find_existing_instagram_media_by_caption_marker(marker)
        
        if existing:
            logging.info("  [MATCH] Ya existe en Facebook: %s (id: %s). Moviendo...", marker, existing.get("id"))
            dest_path = EXTERNAL_DST / file_path.name
            try:
                shutil.move(str(file_path), str(dest_path))
                moved_count += 1
            except Exception as e:
                logging.error("  [ERROR] No se pudo mover %s: %s", marker, e)
        else:
            logging.info("  [NEW] No se encontro remoto.")

    logging.info("Finalizado: %s archivos movidos a la carpeta de descarte.", moved_count)

def main():
    reconcile_folder(EXTERNAL_SRC, "externa_adm")
    logging.info("--- Proceso de Reconciliacion Terminado ---")

if __name__ == "__main__":
    main()
