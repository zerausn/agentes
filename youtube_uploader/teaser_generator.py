import json
import logging
import os
import subprocess
from pathlib import Path

# Configuración HARDENED para S24 Ultra
BASE_DIR = Path('/data/data/com.termux/files/home/agentes/youtube_uploader')
JSON_DB = BASE_DIR / 'videos_db.json'
# Log en SDCard para que el usuario pueda verlo desde cualquier app de archivos
LOG_FILE = Path('/sdcard/Antigravity/teaser_generator_debug.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)

TEASER_DURATION_SEC = 16

def build_ffmpeg_teaser_cmd(input_file, start_sec, output_path):
    # Ruta absoluta al ffmpeg de Termux para evitar fallos de PATH en el Widget
    ffmpeg = '/data/data/com.termux/files/usr/bin/ffmpeg'
    return [
        ffmpeg, '-y',
        '-i', str(input_file),
        '-ss', str(round(start_sec, 3)),
        '-t', str(TEASER_DURATION_SEC),
        '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p',
        '-pix_fmt', 'yuv420p',
        '-c:v', 'libx264', '-crf', '18', '-preset', 'ultrafast',
        '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart',
        str(output_path),
    ]

def main():
    logging.info('=' * 60)
    logging.info(' INICIANDO GENERADOR DE TEASERS (S24 ULTRA HARDENED) ')
    logging.info('=' * 60)
    
    input_dir = Path('/sdcard/Antigravity/crudos_pendientes')
    output_dir = Path('/sdcard/Antigravity/teasers_pendientes')
    output_dir.mkdir(exist_ok=True, parents=True)
    
    files = list(input_dir.glob('*.mp4'))
    if not files:
        logging.info('No se encontraron videos en /sdcard/Antigravity/crudos_pendientes/')
        return

    for f in files:
        base_name = f.stem
        # Para depuración, solo procesamos si no existen ya muchos teasers
        logging.info(f'Procesando video: {f.name}')
        
        # Generar segmentos
        for i in range(1, 4): # Generamos los primeros 3 segmentos como prueba robusta
            out_path = output_dir / f'{base_name}_teaser_{i}.mp4'
            start_sec = (i-1) * TEASER_DURATION_SEC
            
            cmd = build_ffmpeg_teaser_cmd(f, start_sec, out_path)
            logging.info(f'EJECUTANDO COMANDO: {" ".join(cmd)}')
            
            # Ejecutar con captura de error completa
            res = subprocess.run(cmd, capture_output=True, text=True)
            
            if res.returncode == 0:
                logging.info(f'  [OK] Segmento {i} generado exitosamente: {out_path.name}')
            else:
                logging.error(f'  [FAIL] Segmento {i} FALLÓ.')
                logging.error(f'  STDOUT: {res.stdout}')
                logging.error(f'  STDERR: {res.stderr}')

    logging.info('Proceso finalizado. Puedes revisar los archivos en /sdcard/Antigravity/teasers_pendientes/')

if __name__ == "__main__":
    main()
