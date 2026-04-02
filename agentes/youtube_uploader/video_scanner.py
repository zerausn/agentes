import os
import json
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("scanner.log"), logging.StreamHandler()]
)

CONFIG_FILE = 'config.json'
OUTPUT_JSON = 'scanned_videos.json'

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

config = load_config()
scanner_cfg = config.get('scanner', {})

VIDEO_EXTENSIONS = set(scanner_cfg.get('video_extensions', ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv']))
MIN_SIZE_MB = scanner_cfg.get('min_size_mb', 100)
EXCLUDE_FOLDERS = set(folder.lower() for folder in scanner_cfg.get('exclude_folders', []))
EXCLUDE_FILES = set(f.lower() for f in scanner_cfg.get('exclude_files', []))
EXCLUDE_PATTERNS = [p.lower() for p in scanner_cfg.get('exclude_patterns', [])]

def scan_directory(directory):
    """Escanea un directorio de forma recursiva buscando videos grandes."""
    found = []
    logging.info(f"Escaneando: {directory}")
    
    for root, dirs, files in os.walk(directory):
        # Modificar dirs in-place para que os.walk no entre en carpetas excluidas
        dirs[:] = [d for d in dirs if d.lower() not in EXCLUDE_FOLDERS]
        
        for file in files:
            try:
                ext = os.path.splitext(file)[1].lower()
                if ext in VIDEO_EXTENSIONS:
                    # Verificar exclusiones por nombre de archivo o patrón
                    file_lower = file.lower()
                    if file_lower in EXCLUDE_FILES:
                        continue
                    if any(pattern in file_lower for pattern in EXCLUDE_PATTERNS):
                        continue
                        
                    full_path = os.path.join(root, file)
                    size_bytes = os.path.getsize(full_path)
                    size_mb = size_bytes / (1024 * 1024)
                    
                    if size_mb >= MIN_SIZE_MB:
                        found.append({
                            'path': full_path,
                            'size_mb': round(size_mb, 2),
                            'filename': file,
                            'uploaded': False
                        })
            except (OSError, PermissionError):
                continue
    return found

def main():
    unified_folder = r"C:\Users\ZN-\Documents\ADM\Carpeta 1"
    roots_to_scan = [unified_folder] if os.path.exists(unified_folder) else []
    
    logging.info(f"Iniciando escaneo multihilo en {len(roots_to_scan)} raíces...")
    
    all_found = []
    with ThreadPoolExecutor() as executor:
        results = list(executor.map(scan_directory, roots_to_scan))
        for res in results:
            all_found.extend(res)

    existing_videos = []
    existing_paths = set()
    
    if os.path.exists(OUTPUT_JSON):
        with open(OUTPUT_JSON, 'r', encoding='utf-8') as f:
            existing_videos = json.load(f)
            for v in existing_videos:
                existing_paths.add(v['path'])
    
    new_count = 0
    for v in all_found:
        if v['path'] not in existing_paths:
            existing_videos.append(v)
            new_count += 1
            
    existing_videos.sort(key=lambda x: x['size_mb'], reverse=True)
            
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(existing_videos, f, indent=4, ensure_ascii=False)
        
    logging.info(f"Escaneo finalizado. {new_count} nuevos, {len(existing_videos)} totales.")

if __name__ == "__main__":
    main()
