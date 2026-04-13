import logging
import json
import os
import shutil
from pathlib import Path

# Configurar logs
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

BASE_DIR = Path(__file__).resolve().parent
EXTERNAL_SRC = Path(r"C:\Users\ZN-\Documents\ADM\Carpeta 1\videos subidos exitosamente")
EXTERNAL_DST = Path(r"C:\Users\ZN-\Documents\ADM\Carpeta 1\ya_subidos_fb_ig")

def load_json_file(path):
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return []

def save_json_file(path, data):
    try:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
    except Exception as e:
        logging.error("No se pudo guardar %s: %s", path.name, e)

def reconcile_folder(folder_path, label):
    if not folder_path.exists():
        logging.warning("No se encontro la carpeta %s", folder_path)
        return

    EXTERNAL_DST.mkdir(parents=True, exist_ok=True)
    files = list(folder_path.glob("*.mp4"))
    logging.info("--- Reconciliando Carpeta Externa (%s archivos) ---", len(files))
    
    # 1. CACHE DE LIBRERIA
    from meta_uploader import get_facebook_library_batch, get_instagram_library_batch
    fb_cache = get_facebook_library_batch(max_pages=80)
    ig_cache = get_instagram_library_batch(max_pages=80)
    
    # 2. CARGAR BASES DE DATOS (CALENDARIO Y COLAS)
    calendar = load_json_file(BASE_DIR / "meta_calendar.json")
    pending_posts = load_json_file(BASE_DIR / "pendientes_posts.json")
    pending_reels = load_json_file(BASE_DIR / "pendientes_reels.json")
    
    local_success_files = {f.stem for f in EXTERNAL_DST.glob("*.mp4")}
    
    moved_count = 0
    updated_calendar_count = 0
    removed_queue_count = 0
    
    for file_path in files:
        marker = file_path.stem
        
        is_in_local_success = marker in local_success_files
        is_in_fb = any(marker in desc for desc in fb_cache)
        is_in_ig = any(marker in desc for desc in ig_cache) if not is_in_fb else False

        if is_in_local_success or is_in_fb or is_in_ig:
            reason = "Local Folder" if is_in_local_success else "Facebook" if is_in_fb else "Instagram"
            logging.info("  [MATCH] Ya existe (Detectado en %s): %s. Limpiando...", reason, marker)
            
            # A. LIMPIAR COLAS DE PENDIENTES
            # Buscamos por la ruta del archivo o simplemente por el marcador en el nombre
            original_post_len = len(pending_posts)
            pending_posts = [p for p in pending_posts if marker not in p]
            if len(pending_posts) < original_post_len:
                 removed_queue_count += (original_post_len - len(pending_posts))
                 logging.info("    [COLA] Removido de pendientes_posts.json")

            original_reel_len = len(pending_reels)
            pending_reels = [r for r in pending_reels if marker not in r]
            if len(pending_reels) < original_reel_len:
                 removed_queue_count += (original_reel_len - len(pending_reels))
                 logging.info("    [COLA] Removido de pendientes_reels.json")

            # B. SINCRONIZAR CALENDARIO
            for entry in calendar:
                match_entry = False
                if entry.get("post") and marker in entry["post"].get("filename", ""):
                    match_entry = True
                if entry.get("reel") and marker in entry["reel"].get("filename", ""):
                    match_entry = True
                
                if match_entry and entry["summary"].get("status") != "completed":
                    entry["summary"]["status"] = "completed"
                    entry["summary"]["last_updated_at"] = "triple_sync_by_reconcile"
                    updated_calendar_count += 1
            
            # C. MOVER ARCHIVO FISICO
            dest_path = EXTERNAL_DST / file_path.name
            try:
                if dest_path.exists():
                     file_path.unlink()
                else:
                    shutil.move(str(file_path), str(dest_path))
                moved_count += 1
            except Exception as e:
                logging.error("    [ERROR] No se pudo procesar archivo físico %s: %s", marker, e)
        else:
            logging.info("  [NEW] %s no se encontró remoto ni en éxito.", marker)

    # GUARDAR CAMBIOS EN LAS BASES DE DATOS
    if updated_calendar_count > 0:
        logging.info("Guardando calendario con %s cambios...", updated_calendar_count)
        save_json_file(BASE_DIR / "meta_calendar.json", calendar)
    
    if removed_queue_count > 0:
        logging.info("Guardando colas de pendientes con %s items removidos...", removed_queue_count)
        save_json_file(BASE_DIR / "pendientes_posts.json", pending_posts)
        save_json_file(BASE_DIR / "pendientes_reels.json", pending_reels)

    logging.info("Finalizado: %s archivos movidos | %s colas limpias | %s calendario sincronizado.", 
                 moved_count, removed_queue_count, updated_calendar_count)

def main():
    reconcile_folder(EXTERNAL_SRC, "externa_adm")
    logging.info("--- Proceso de Limpieza Triple Terminado ---")

if __name__ == "__main__":
    main()
