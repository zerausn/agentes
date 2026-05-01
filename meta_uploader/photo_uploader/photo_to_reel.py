"""
photo_to_reel.py
================
Convierte una foto (JPG/PNG) en un video MP4 vertical de 5 segundos
compatible con la API de Reels de Facebook (1080x1920, 9:16).

También puede combinar N fotos en un solo Reel de duracion configurable.

Requiere: ffmpeg instalado y disponible en el PATH del sistema.
"""
import subprocess
import logging
import shutil
import tempfile
from pathlib import Path
from typing import List

# Especificaciones de Reels de Facebook (2025)
REEL_WIDTH = 1080
REEL_HEIGHT = 1920
REEL_DURATION_SECONDS = 5
REEL_FPS = 30
REEL_BITRATE = "4000k"

# Duracion total del Reel combinado (30 segundos)
COMBINED_REEL_DURATION = 30


def check_ffmpeg() -> bool:
    """Verifica que FFmpeg este disponible en el sistema."""
    return shutil.which("ffmpeg") is not None


def _vf_scale_crop() -> str:
    """Filtro estandar de escala y recorte para formato 9:16."""
    return (
        f"scale={REEL_WIDTH}:{REEL_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={REEL_WIDTH}:{REEL_HEIGHT},"
        f"setsar=1"
    )


def convert_photo_to_reel(photo_path: Path, output_path: Path) -> bool:
    """
    Convierte una foto a un video MP4 vertical de 5 segundos apto para Reels.

    Args:
        photo_path: Ruta a la imagen de entrada (JPG, PNG, WEBP).
        output_path: Ruta donde guardar el MP4 generado.

    Returns:
        True si la conversion fue exitosa, False si ocurrio algun error.
    """
    if not photo_path.exists():
        logging.error("[photo_to_reel] No existe la foto: %s", photo_path)
        return False

    if not check_ffmpeg():
        logging.error("[photo_to_reel] FFmpeg no esta disponible en el PATH del sistema.")
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", str(photo_path),
        "-f", "lavfi",
        "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-vf", _vf_scale_crop(),
        "-c:v", "libx264",
        "-preset", "fast",
        "-b:v", REEL_BITRATE,
        "-r", str(REEL_FPS),
        "-t", str(REEL_DURATION_SECONDS),
        "-c:a", "aac",
        "-b:a", "128k",
        "-shortest",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_path),
    ]

    logging.info("[photo_to_reel] Convirtiendo: %s -> %s", photo_path.name, output_path.name)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            logging.error(
                "[photo_to_reel] FFmpeg fallo (codigo %s):\n%s",
                result.returncode, result.stderr[-500:],
            )
            return False

        if not output_path.exists() or output_path.stat().st_size < 10_000:
            logging.error("[photo_to_reel] El video generado parece vacio o no existe.")
            return False

        size_kb = output_path.stat().st_size / 1024
        logging.info("[photo_to_reel] OK - Video generado: %.1f KB", size_kb)
        return True

    except subprocess.TimeoutExpired:
        logging.error("[photo_to_reel] FFmpeg excedio el tiempo limite de 600s en clip individual.")
        return False
    except Exception as exc:
        logging.error("[photo_to_reel] Error inesperado: %s", exc)
        return False


def convert_video_clips_to_combined_reel(
    video_paths: List[Path],
    output_path: Path,
    total_duration: int = COMBINED_REEL_DURATION,
) -> bool:
    """
    Combina multiples Reels cortos ya procesados en un unico Reel de `total_duration` segundos.
    Por ejemplo: toma 10 videos de 5s, corta los primeros 3s de cada uno, y los une.
    Esto evita el doble procesamiento extremo de la imagen 4K original.

    Args:
        video_paths: Lista de rutas de videos MP4 (ordenadas segun deben aparecer).
        output_path: Ruta del MP4 combinado de salida.
        total_duration: Duracion total deseada en segundos.

    Returns:
        True si el Reel combinado se genero correctamente.
    """
    if not video_paths:
        logging.error("[combined_reel] No se proporcionaron videos.")
        return False

    if not check_ffmpeg():
        logging.error("[combined_reel] FFmpeg no esta disponible.")
        return False

    num_videos = len(video_paths)
    dur_por_video = round(total_duration / num_videos, 2)
    logging.info(
        "[combined_reel] Combinando %s videos ya generados (corte: %.2fs c/u) = %ss total",
        num_videos, dur_por_video, total_duration,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        
        # Archivo de lista para el concat demuxer
        concat_list = tmp / "concat_list.txt"
        with open(concat_list, "w", encoding="utf-8") as f:
            for vid in video_paths:
                if not vid.exists():
                    logging.warning("[combined_reel] Video no encontrado, omitiendo: %s", vid)
                    continue
                # inpoint 0 outpoint dur_por_video recorta el video sin recompresion pesada!
                f.write(f"file '{vid.as_posix()}'\n")
                f.write("inpoint 0\n")
                f.write(f"outpoint {dur_por_video}\n")

        # Concatenar todos los clips en el Reel final re-codificando rapidamente para union perfecta
        # Usamos filter_complex guiando concat si no, es c copy. Concat de demuxer funciona muy bien.
        concat_cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_list),
            "-c:v", "libx264",
            "-preset", "fast",
            "-b:v", REEL_BITRATE,
            "-c:a", "aac",
            "-b:a", "128k",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(output_path),
        ]

        logging.info("[combined_reel] Concatenando %s clips pre-renderizados...", len(video_paths))
        try:
            result = subprocess.run(concat_cmd, capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            logging.error("[combined_reel] Timeout en el armado del reel combinado.")
            return False

        if result.returncode != 0:
            logging.error(
                "[combined_reel] FFmpeg concat fallo:\n%s", result.stderr[-500:]
            )
            return False

        if not output_path.exists() or output_path.stat().st_size < 50_000:
            logging.error("[combined_reel] El Reel combinado parece vacio.")
            return False

        size_mb = output_path.stat().st_size / 1_000_000
        logging.info(
            "[combined_reel] OK - Reel combinado super-rapido generado: %.2f MB (%ss total)",
            size_mb, total_duration
        )
        return True
