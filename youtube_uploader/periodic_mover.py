import json
import logging
import os
import shutil
import time
from pathlib import Path

from video_helpers import (
    SUCCESS_DIR_NAME,
    EXCLUDED_DIR_NAME,
    load_json_file,
    save_json_file,
    infer_library_root_from_path
)

BASE_DIR = Path(__file__).resolve().parent
JSON_DB = BASE_DIR / "scanned_videos.json"
LOG_FILE = BASE_DIR / "periodic_mover.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding="utf-8")
    ]
)

def move_uploaded_videos():
    if not JSON_DB.exists():
        logging.warning("No se encontro scanned_videos.json")
        return

    videos = load_json_file(JSON_DB, [])
    updated = False
    moved_count = 0

    for video in videos:
        if not video.get("uploaded"):
            continue

        file_path = Path(video["path"])
        if not file_path.exists():
            continue

        # Verificar si ya está en una carpeta de éxito/exclusión
        parents = [p.name.lower() for p in file_path.parents]
        if SUCCESS_DIR_NAME.lower() in parents or EXCLUDED_DIR_NAME.lower() in parents:
            continue

        # Intentar mover el archivo
        try:
            root_dir = infer_library_root_from_path(file_path)
            success_folder = root_dir / SUCCESS_DIR_NAME
            success_folder.mkdir(exist_ok=True)
            
            destination = success_folder / file_path.name
            
            # Si el destino ya existe, agregamos un sufijo para evitar colisiones
            if destination.exists():
                destination = success_folder / f"{file_path.stem}_{int(time.time())}{file_path.suffix}"

            logging.info("Intentando mover archivo liberado: %s", file_path.name)
            shutil.move(str(file_path), str(destination))
            
            video["path"] = str(destination)
            updated = True
            moved_count += 1
            logging.info("Archivo movido exitosamente a: %s", destination.parent.name)
            
        except PermissionError:
            logging.debug("Archivo %s sigue bloqueado por otro proceso. Se reintentara luego.", file_path.name)
        except Exception as exc:
            logging.error("Error moviendo %s: %s", file_path.name, exc)

    if updated:
        save_json_file(JSON_DB, videos)
        logging.info("Base de datos actualizada tras mover %s archivos.", moved_count)
    elif moved_count == 0:
        logging.debug("No hay archivos pendientes por mover o todos estan bloqueados.")

def main():
    logging.info("--- Iniciando Servicio de Limpieza Periodica (Cada 10 min) ---")
    while True:
        try:
            move_uploaded_videos()
        except Exception as exc:
            logging.error("Error en el ciclo de limpieza: %s", exc)
        
        # Dormir 10 minutos
        logging.debug("Esperando 10 minutos para el proximo ciclo...")
        time.sleep(600)

if __name__ == "__main__":
    main()
