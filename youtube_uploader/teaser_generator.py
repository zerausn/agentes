import json
import logging
import os
import subprocess
from pathlib import Path

from video_helpers import resolve_ffmpeg_binary, is_hdr, ffmpeg_has_mediacodec

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
    ffmpeg = resolve_ffmpeg_binary(BASE_DIR)
    ffmpeg_path = str(ffmpeg)

    try:
        hdr = is_hdr(input_file, ffmpeg_binary=ffmpeg_path)
    except Exception:
        hdr = False

    mediacodec_available = ffmpeg_has_mediacodec(ffmpeg_path)

    # Fast path: if not HDR, attempt remux (-c copy) which is fastest.
    if not hdr:
        return [
            ffmpeg_path, '-y',
            '-ss', str(round(start_sec, 3)),
            '-t', str(TEASER_DURATION_SEC),
            '-i', str(input_file),
            '-c', 'copy',
            str(output_path),
        ]

    # If HDR or unknown and mediacodec available, try HW encode
    if mediacodec_available:
        return [
            ffmpeg_path, '-y',
            '-i', str(input_file),
            '-ss', str(round(start_sec, 3)),
            '-t', str(TEASER_DURATION_SEC),
            '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p',
            '-pix_fmt', 'yuv420p',
            '-c:v', 'h264_mediacodec', '-b:v', '6000k',
            '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart',
            str(output_path),
        ]

    # Fallback: software encode (conservador para HDR)
    return [
        ffmpeg_path, '-y',
        '-i', str(input_file),
        '-ss', str(round(start_sec, 3)),
        '-t', str(TEASER_DURATION_SEC),
        '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p',
        '-pix_fmt', 'yuv420p',
        '-c:v', 'libx264', '-crf', '18', '-preset', 'veryfast',
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
        for i in range(1, 4):  # Generamos los primeros 3 segmentos como prueba robusta
            out_path = output_dir / f'{base_name}_teaser_{i}.mp4'
            start_sec = (i - 1) * TEASER_DURATION_SEC

            cmd = build_ffmpeg_teaser_cmd(f, start_sec, out_path)
            logging.info('EJECUTANDO COMANDO: %s', ' '.join(map(str, cmd)))

            # Ejecutar con captura de error completa
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            except Exception as e:
                logging.error('  [FAIL] Segmento %s FALLÓ al ejecutar: %s', i, e)
                continue

            if res.returncode == 0:
                logging.info('  [OK] Segmento %s generado exitosamente: %s', i, out_path.name)
            else:
                logging.error('  [FAIL] Segmento %s FALLÓ.', i)
                logging.error('  STDOUT: %s', (res.stdout or '')[-1000:])
                logging.error('  STDERR: %s', (res.stderr or '')[-2000:])

    logging.info('Proceso finalizado. Puedes revisar los archivos en /sdcard/Antigravity/teasers_pendientes/')

if __name__ == "__main__":
    main()
