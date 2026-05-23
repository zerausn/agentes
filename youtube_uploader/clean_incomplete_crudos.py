import os
import sys
import logging
from pathlib import Path

# Configurar logging para salida a consola
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

def main():
    STORAGE_ROOT = Path(os.environ.get("AGENTES_STORAGE_ROOT", "/sdcard/Antigravity"))
    input_dir = STORAGE_ROOT / "crudos_pendientes"
    markers_dir = STORAGE_ROOT / ".state"

    if not input_dir.exists():
        logging.error(f"El directorio de crudos no existe: {input_dir}")
        sys.exit(1)

    # 1. Obtener la lista de crudos en la carpeta
    extensions = {".mp4", ".webm", ".mkv", ".avi", ".mov", ".wmv", ".flv"}
    files = sorted([f for f in input_dir.iterdir() if f.is_file() and f.suffix.lower() in extensions])
    
    if not files:
        logging.info("No se encontraron crudos en crudos_pendientes.")
        return

    # 2. Obtener la lista de marcadores .done
    done_stems = set()
    if markers_dir.exists():
        done_stems = {f.stem for f in markers_dir.glob("*.done")}

    # 3. Identificar los crudos incompletos y moverlos
    incomplete_count = 0
    for f in files:
        base_name = f.stem
        if base_name in done_stems:
            logging.info(f"✅ {f.name} -> Teasers completos (existe marker .done)")
        else:
            dest = STORAGE_ROOT / f.name
            logging.info(f"❌ {f.name} -> Incompleto (NO existe marker .done). Moviendo a {dest}...")
            try:
                f.rename(dest)
                incomplete_count += 1
                logging.info(f"  [OK] Movido correctamente.")
            except Exception as e:
                logging.error(f"  [ERROR] No se pudo mover: {e}")

    logging.info(f"Proceso terminado. Se movieron {incomplete_count} crudos incompletos a {STORAGE_ROOT}.")

if __name__ == '__main__':
    main()
