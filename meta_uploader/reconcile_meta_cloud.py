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

def load_calendar():
    path = BASE_DIR / "meta_calendar.json"
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return []

def save_calendar(plan):
    path = BASE_DIR / "meta_calendar.json"
    try:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(plan, handle, indent=2, ensure_ascii=False)
    except Exception as e:
        logging.error("No se pudo guardar el calendario: %s", e)

def reconcile_folder(folder_path, label):
    if not folder_path.exists():
        logging.warning("No se encontro la carpeta %s", folder_path)
        return

    EXTERNAL_DST.mkdir(parents=True, exist_ok=True)
    files = list(folder_path.glob("*.mp4"))
    logging.info("--- Reconciliando Carpeta Externa (%s archivos) ---", len(files))
    
    # NUEVO: CACHE DE LIBRERIA
    from meta_uploader import get_facebook_library_batch, get_instagram_library_batch
    fb_cache = get_facebook_library_batch(max_pages=80)
    ig_cache = get_instagram_library_batch(max_pages=80)
    
    # NUEVO: CARGAR CALENDARIO PARA SINCRONIZAR
    calendar = load_calendar()
    
    local_success_files = {f.stem for f in EXTERNAL_DST.glob("*.mp4")}
    
    moved_count = 0
    updated_calendar_count = 0
    for file_path in files:
        marker = file_path.stem
        
        is_in_local_success = marker in local_success_files
        is_in_fb = any(marker in desc for desc in fb_cache)
        is_in_ig = any(marker in desc for desc in ig_cache) if not is_in_fb else False

        if is_in_local_success or is_in_fb or is_in_ig:
            reason = "Local Folder" if is_in_local_success else "Facebook" if is_in_fb else "Instagram"
            logging.info("  [MATCH] Ya existe (Detectado en %s): %s. Moviendo...", reason, marker)
            
            # Sincronizar CALENDARIO
            for entry in calendar:
                # Revisamos si este video estaba asignado a este dia (en post o reel)
                match_entry = False
                if entry.get("post") and entry["post"].get("filename") == file_path.name:
                    match_entry = True
                if entry.get("reel") and entry["reel"].get("filename") == file_path.name:
                    match_entry = True
                
                if match_entry and entry["summary"].get("status") != "completed":
                    entry["summary"]["status"] = "completed"
                    entry["summary"]["last_updated_at"] = "sync_by_reconcile_cloud"
                    updated_calendar_count += 1
            
            dest_path = EXTERNAL_DST / file_path.name
            try:
                if dest_path.exists():
                     file_path.unlink()
                else:
                    shutil.move(str(file_path), str(dest_path))
                moved_count += 1
            except Exception as e:
                logging.error("  [ERROR] No se pudo procesar %s: %s", marker, e)
        else:
            logging.info("  [NEW] %s no se encontro en Meta (2000 ultimos) ni en carpeta de exito.", marker)

    if updated_calendar_count > 0:
        logging.info("Sincronzando %s dias en meta_calendar.json como completados...", updated_calendar_count)
        save_calendar(calendar)

    logging.info("Finalizado: %s archivos conciliados. %s dias sincronizados en calendario.", moved_count, updated_calendar_count)

def main():
    reconcile_folder(EXTERNAL_SRC, "externa_adm")
    logging.info("--- Proceso de Reconciliacion Terminado ---")

if __name__ == "__main__":
    main()
