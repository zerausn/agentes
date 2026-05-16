import json
import logging
import os
import subprocess
from pathlib import Path

from datetime import datetime
from video_helpers import (
    resolve_ffmpeg_binary,
    is_hdr,
    ffmpeg_has_mediacodec,
    probe_video_metadata,
    load_json_file,
    save_json_file,
)

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


def build_ffmpeg_teaser_cmd(input_file, start_sec, output_path, ffmpeg_path=None, mediacodec_available=None, codec=None, hdr=None):
    """Build the ffmpeg command for a teaser using pre-computed classification.

    Accepts ffmpeg_path and mediacodec_available to avoid probing repeatedly.
    codec and hdr may be provided by the caller (classification step).
    """
    # Ruta absoluta al ffmpeg de Termux para evitar fallos de PATH en el Widget
    if ffmpeg_path is None:
        ffmpeg = resolve_ffmpeg_binary(BASE_DIR)
        ffmpeg_path = str(ffmpeg)

    if mediacodec_available is None:
        mediacodec_available = ffmpeg_has_mediacodec(ffmpeg_path)

    # If caller didn't provide codec/hdr, probe here (cheapish)
    meta = None
    if codec is None:
        try:
            meta = probe_video_metadata(input_file)
        except Exception:
            meta = None
        codec = (meta.get('codec_name') or '').lower() if meta else ''

    if hdr is None:
        try:
            hdr = is_hdr(input_file, ffmpeg_binary=ffmpeg_path)
        except Exception:
            hdr = False

    # Fast conservative path: input already H.264 and not HDR -> remux copy
    if codec == 'h264' and not hdr:
        return [
            ffmpeg_path, '-y',
            '-ss', str(round(start_sec, 3)),
            '-t', str(TEASER_DURATION_SEC),
            '-i', str(input_file),
            '-c', 'copy',
            str(output_path),
        ]

    # If input codec is HEVC (common on S24) but not HDR, prefer HW transcode
    # to H.264 via mediacodec if available; keeps compatibility with uploaders
    # while speeding up compared to software libx264.
    if codec in ('hevc', 'h265') and not hdr and mediacodec_available:
        return [
            ffmpeg_path, '-y',
            '-hwaccel', 'mediacodec',
            '-c:v', 'hevc_mediacodec',
            '-i', str(input_file),
            '-ss', str(round(start_sec, 3)),
            '-t', str(TEASER_DURATION_SEC),
            '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p',
            '-pix_fmt', 'yuv420p',
            '-c:v', 'h264_mediacodec', '-b:v', '6000k',
            '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart',
            str(output_path),
        ]

    # Otherwise: fallback to software encode to H.264 (safe, compatible)
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


def classify_video_for_pipeline(input_file, ffmpeg_path, mediacodec_available):
    """Return a simple classification dict for the input file.

    Keys: codec (str), hdr (bool), pipeline (one of 'remux','hw_transcode','sw_transcode'), meta (ffprobe metadata or None)
    """
    meta = None
    try:
        meta = probe_video_metadata(input_file)
    except Exception:
        meta = None

    codec = (meta.get('codec_name') or '').lower() if meta else ''
    try:
        hdr = is_hdr(input_file, ffmpeg_binary=ffmpeg_path)
    except Exception:
        hdr = False

    if codec == 'h264' and not hdr:
        pipeline = 'remux'
    elif codec in ('hevc', 'h265') and not hdr and mediacodec_available:
        pipeline = 'hw_transcode'
    else:
        pipeline = 'sw_transcode'

    return {
        'codec': codec,
        'hdr': bool(hdr),
        'pipeline': pipeline,
        'meta': meta,
    }

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

    # Precompute ffmpeg path and mediacodec availability once per run
    ffmpeg_path = str(resolve_ffmpeg_binary(BASE_DIR))
    mediacodec_available = ffmpeg_has_mediacodec(ffmpeg_path)

    for f in files:
        base_name = f.stem
        logging.info(f'Procesando video: {f.name}')

        # Classify the input to decide pipeline; store classification in small DB
        classification_db_path = Path('/sdcard/Antigravity') / 'classification_db.json'
        try:
            db = load_json_file(classification_db_path, {})
        except Exception:
            db = {}

        key = str(f.resolve())
        entry = db.get(key) or {}
        # if we don't have a recent classification, compute it
        needs_probe = True
        if entry.get('classified_at'):
            try:
                classified_time = datetime.fromisoformat(entry['classified_at'])
                # re-probe if older than 1 day
                if (datetime.now() - classified_time).total_seconds() < 86400:
                    needs_probe = False
            except Exception:
                needs_probe = True

        if needs_probe:
            try:
                cls = classify_video_for_pipeline(f, ffmpeg_path, mediacodec_available)
                entry.update(cls)
                entry['classified_at'] = datetime.now().isoformat()
                db[key] = entry
                save_json_file(classification_db_path, db)
                logging.info('  Clasificación: codec=%s hdr=%s pipeline=%s', entry.get('codec'), entry.get('hdr'), entry.get('pipeline'))
            except Exception as e:
                logging.error('  No se pudo clasificar %s: %s', f.name, e)
                entry = entry or {'codec': None, 'hdr': False, 'pipeline': 'sw_transcode'}

        pipeline = entry.get('pipeline', 'sw_transcode')

        # Generar segmentos
        for i in range(1, 4):  # Generamos los primeros 3 segmentos como prueba robusta
            out_path = output_dir / f'{base_name}_teaser_{i}.mp4'
            start_sec = (i - 1) * TEASER_DURATION_SEC

            # build command using the precomputed classification
            cmd = build_ffmpeg_teaser_cmd(f, start_sec, out_path, ffmpeg_path=ffmpeg_path, mediacodec_available=mediacodec_available, codec=entry.get('codec'), hdr=entry.get('hdr'))
            logging.info('EJECUTANDO COMANDO (pipeline=%s): %s', pipeline, ' '.join(map(str, cmd)))

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
