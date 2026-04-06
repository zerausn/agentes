import os
import json
import subprocess
import logging
from pathlib import Path

BASE_DIR = Path(r"C:\Users\ZN-\Documents\Antigravity\agentes\agentes\youtube_uploader")
JSON_DB = BASE_DIR / 'scanned_videos.json'
TARGET_DIR = r"C:\Users\ZN-\Documents\ADM\Carpeta 1"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_video_info(file_path):
    try:
        cmd = [
            'ffprobe', '-v', 'error', 
            '-select_streams', 'v:0', 
            '-show_entries', 'stream=width,height,duration', 
            '-of', 'json', file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)
        
        if 'streams' in data and len(data['streams']) > 0:
            stream = data['streams'][0]
            width = int(stream.get('width', 0))
            height = int(stream.get('height', 0))
            duration = float(stream.get('duration', 0))
            
            is_vertical_or_square = height >= width
            
            # Nueva regla de YouTube (Oct 2024): Shorts hasta 3 min si son verticales/cuadrados
            if is_vertical_or_square:
                is_short = duration <= 180
            else:
                # Horizontales siguen siendo shorts solo si son < 60s (y a veces ni eso)
                is_short = duration <= 60
            
            return {
                "width": width,
                "height": height,
                "duration": duration,
                "type": "short" if is_short else "video"
            }
    except Exception as e:
        logging.error(f"Error analizando {file_path}: {e}")
    return None

def main():
    if not os.path.exists(JSON_DB):
        logging.error("No se encontró scanned_videos.json")
        return

    with open(JSON_DB, 'r', encoding='utf-8') as f:
        videos = json.load(f)

    stats = {"short": 0, "video": 0, "error": 0}
    
    # Solo analizar archivos en Carpeta 1 que no hayan sido subidos
    for v in videos:
        if not v.get('uploaded', False) and TARGET_DIR in v['path']:
            if os.path.exists(v['path']):
                info = get_video_info(v['path'])
                if info:
                    v['type'] = info['type']
                    v['duration'] = info['duration']
                    v['dimensions'] = f"{info['width']}x{info['height']}"
                    stats[info['type']] += 1
                else:
                    stats["error"] += 1
            else:
                logging.warning(f"Archivo no encontrado: {v['path']}")

    with open(JSON_DB, 'w', encoding='utf-8') as f:
        json.dump(videos, f, indent=4, ensure_ascii=False)

    print("\n--- RESUMEN DE CLASIFICACIÓN LOCAL ---")
    print(f"Shorts detectados: {stats['short']}")
    print(f"Videos normales: {stats['video']}")
    print(f"Errores: {stats['error']}")

if __name__ == "__main__":
    main()
