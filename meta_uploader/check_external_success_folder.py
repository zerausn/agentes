import logging
import os
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

TARGET_DIR = Path(r"C:\Users\ZN-\Documents\ADM\Carpeta 1\videos subidos exitosamente")

def check_external_folder(folder_path):
    if not folder_path.exists():
        logging.warning("No se encontro la carpeta %s", folder_path)
        return

    files = list(folder_path.glob("*.mp4"))
    logging.info("--- Revisando Carpeta Externa (%s archivos) ---", len(files))
    
    matches = []
    for file_path in files:
        marker = file_path.stem
        # Quitar prefijo opt_ si existe
        if marker.startswith("opt_"):
            marker = marker[4:]
            
        logging.info("Revisando: %s", marker)
        
        # Consultar si existe en Facebook
        existing = find_existing_facebook_video_by_caption_marker(marker)
        if not existing:
            # Buscar tambien en Instagram
            existing = find_existing_instagram_media_by_caption_marker(marker)
        
        if existing:
            logging.info("  [SI] Ya esta en Meta: %s (id: %s)", marker, existing.get("id"))
            matches.append((marker, existing.get("id")))

    logging.info("--- Reporte Final ---")
    if matches:
        logging.info("Se encontraron %s archivos en la carpeta externa que ya estan en Meta:", len(matches))
        for marker, mid in matches:
            logging.info(" - %s (id: %s)", marker, mid)
    else:
        logging.info("No se encontraron coincidencias. Ningun archivo de esta carpeta parece estar en Meta todavia.")

if __name__ == "__main__":
    check_external_folder(TARGET_DIR)
