import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / 'config.json'
SCANNED_FILE = BASE_DIR / 'scanned_videos.json'

def clean_scanned_videos():
    if not os.path.exists(CONFIG_FILE) or not os.path.exists(SCANNED_FILE):
        print("Archivos no encontrados.")
        return

    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    scanner_cfg = config.get('scanner', {})
    exclude_folders = [f.lower() for f in scanner_cfg.get('exclude_folders', [])]
    exclude_files = [f.lower() for f in scanner_cfg.get('exclude_files', [])]
    exclude_patterns = [p.lower() for p in scanner_cfg.get('exclude_patterns', [])]

    with open(SCANNED_FILE, 'r', encoding='utf-8') as f:
        videos = json.load(f)

    original_count = len(videos)
    cleaned_videos = []

    for v in videos:
        path_lower = v['path'].lower()
        filename_lower = v['filename'].lower()
        
        # Saltarse si ya fue subido exitosamente (opcional, pero mantengamos lo que ya está bien)
        # si queremos una limpieza total, quitamos el 'if v.get("uploaded")'
        
        should_exclude = False
        
        # Check folders
        if any(folder in path_lower for folder in exclude_folders):
            should_exclude = True
            
        # Validar si el archivo todavía existe en disco
        if not os.path.exists(v['path']):
            should_exclude = True
        
        # Check files
        if filename_lower in exclude_files:
            should_exclude = True
            
        # Check patterns
        if any(pattern in filename_lower for pattern in exclude_patterns):
            should_exclude = True
            
        if not should_exclude:
            cleaned_videos.append(v)
        else:
            print(f"Excluyendo: {v['path']}")

    with open(SCANNED_FILE, 'w', encoding='utf-8') as f:
        json.dump(cleaned_videos, f, indent=4, ensure_ascii=False)
    
    print(f"Limpieza completada: {original_count} -> {len(cleaned_videos)} videos.")

if __name__ == "__main__":
    clean_scanned_videos()
