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
    
    # NUEVO: DESCARGA DE CACHE (UNA SOLA VEZ)
    from meta_uploader import get_facebook_library_batch, get_instagram_library_batch
    fb_cache = get_facebook_library_batch(max_pages=80)
    ig_cache = get_instagram_library_batch(max_pages=80)
    
    # NUEVO: CACHE DE CARPETA LOCAL DE EXITO (Opcional pero recomendado para redundancia)
    local_success_files = {f.stem for f in EXTERNAL_DST.glob("*.mp4")}
    
    moved_count = 0
    for file_path in files:
        marker = file_path.stem
        
        # 1. Verificar en Cache Local de Exito
        is_in_local_success = marker in local_success_files
        
        # 2. Verificar en Cache de Facebook (Búsqueda en memoria, super rápido)
        is_in_fb = any(marker in desc for desc in fb_cache)
        
        # 3. Verificar en Cache de Instagram
        is_in_ig = any(marker in desc for desc in ig_cache) if not is_in_fb else False

        if is_in_local_success or is_in_fb or is_in_ig:
            reason = "Local Folder" if is_in_local_success else "Facebook" if is_in_fb else "Instagram"
            logging.info("  [MATCH] Ya existe (Detectado en %s): %s. Moviendo...", reason, marker)
            dest_path = EXTERNAL_DST / file_path.name
            try:
                # Si el archivo existe en el destino, simplemente lo borramos de la fuente (evitar colisión de move)
                if dest_path.exists():
                     file_path.unlink()
                else:
                    shutil.move(str(file_path), str(dest_path))
                moved_count += 1
            except Exception as e:
                logging.error("  [ERROR] No se pudo procesar %s: %s", marker, e)
        else:
            logging.info("  [NEW] %s no se encontro en Meta (2000 ultimos) ni en carpeta de exito.", marker)

    logging.info("Finalizado: %s archivos conciliados y movidos.", moved_count)

def main():
    reconcile_folder(EXTERNAL_SRC, "externa_adm")
    logging.info("--- Proceso de Reconciliacion Terminado ---")

if __name__ == "__main__":
    main()
