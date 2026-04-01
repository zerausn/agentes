import os
import json
from pathlib import Path

# Configuraciones
VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv'}
MIN_SIZE_MB = 100 # Solo buscar videos mayores a 100 MB para descartar clips cortos
OUTPUT_JSON = 'scanned_videos.json'

def get_drive_roots():
    """Obtiene las letras de disco disponibles en Windows."""
    import string
    from ctypes import windll
    drives = []
    bitmask = windll.kernel32.GetLogicalDrives()
    for letter in string.ascii_uppercase:
        if bitmask & 1:
            drives.append(f"{letter}:\\")
        bitmask >>= 1
    return drives

def scan_for_large_videos(directories_to_scan):
    print(f"Buscando videos mayores a {MIN_SIZE_MB}MB en: {directories_to_scan}")
    found_videos = []
    
    for directory in directories_to_scan:
        for root, _, files in os.walk(directory):
            # Ignorar carpetas del sistema para acelerar la búsqueda y evitar errores de permisos
            if any(sys_folder in root.lower() for sys_folder in ['\\windows', '\\program files', '\\appdata']):
                continue
                
            for file in files:
                try:
                    ext = os.path.splitext(file)[1].lower()
                    if ext in VIDEO_EXTENSIONS:
                        full_path = os.path.join(root, file)
                        size_bytes = os.path.getsize(full_path)
                        size_mb = size_bytes / (1024 * 1024)
                        
                        if size_mb >= MIN_SIZE_MB:
                            found_videos.append({
                                'path': full_path,
                                'size_mb': round(size_mb, 2),
                                'filename': file,
                                'uploaded': False
                            })
                except (OSError, PermissionError):
                    # Ignorar archivos bloqueados por el sistema
                    pass

    # Ordenar por tamaño descendente (los más grandes primero)
    found_videos.sort(key=lambda x: x['size_mb'], reverse=True)
    return found_videos

def save_results(videos):
    # Fusionar con resultados anteriores si existen
    existing_videos = []
    existing_paths = set()
    
    if os.path.exists(OUTPUT_JSON):
        with open(OUTPUT_JSON, 'r', encoding='utf-8') as f:
            existing_videos = json.load(f)
            for v in existing_videos:
                existing_paths.add(v['path'])
    
    # Agregar solo los nuevos
    new_count = 0
    for v in videos:
        if v['path'] not in existing_paths:
            existing_videos.append(v)
            new_count += 1
            
    # Reordenar todos
    existing_videos.sort(key=lambda x: x['size_mb'], reverse=True)
            
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(existing_videos, f, indent=4, ensure_ascii=False)
        
    print(f"Escaneo finalizado. Se encontraron {new_count} videos nuevos.")
    print(f"Total en base de datos: {len(existing_videos)} videos listos para ser gestionados.")

if __name__ == "__main__":
    # Por defecto, busca en las carpetas comunes del usuario. 
    # Si quieres buscar en todo el disco, descomenta la siguiente línea:
    # drives_to_scan = get_drive_roots() # ['C:\\', 'D:\\', ...]
    
    user_profile = os.environ.get('USERPROFILE', 'C:\\')
    drives_to_scan = [
        os.path.join(user_profile, 'Videos'),
        os.path.join(user_profile, 'Documents'),
        os.path.join(user_profile, 'Downloads'),
        os.path.join(user_profile, 'Desktop')
    ]
    
    videos = scan_for_large_videos(drives_to_scan)
    save_results(videos)
