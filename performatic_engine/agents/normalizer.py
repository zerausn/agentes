"""
agents/normalizer.py
====================
Agente 1: Normalización de video
Convierte fuentes VFR (Variable Frame Rate) a CFR (Constant Frame Rate)
para evitar desviación de audio en edición y segmentación.
"""

import logging
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


class NormalizerAgent:
    def __init__(self, cfg):
        self.cfg = cfg

    def run(self, input_path: Path) -> Path:
        output_path = self.cfg.normalized_dir / f"{input_path.stem}_cfr.mp4"

        if output_path.exists():
            log.info(f"  Ya normalizado: {output_path}")
            return output_path

        # Detectar si el video es VFR
        is_vfr = self._detect_vfr(input_path)
        if not is_vfr:
            log.info("  Video ya es CFR, copiando sin recodificar...")
            self._copy_stream(input_path, output_path)
        else:
            log.info(f"  Video VFR detectado. Normalizando a {self.cfg.target_fps}fps...")
            self._convert_to_cfr(input_path, output_path)

        log.info(f"  Normalizado: {output_path}")
        return output_path

    def _detect_vfr(self, path: Path) -> bool:
        """Usa ffprobe para detectar si el video tiene frame rate variable."""
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=r_frame_rate,avg_frame_rate",
            "-of", "csv=p=0",
            str(path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        lines = result.stdout.strip().split("\n")
        if len(lines) < 1:
            return False
        # Si r_frame_rate != avg_frame_rate, es VFR
        parts = lines[0].split(",")
        if len(parts) >= 2 and parts[0] != parts[1]:
            log.debug(f"  r_frame_rate={parts[0]}, avg_frame_rate={parts[1]} → VFR")
            return True
        return False

    def _convert_to_cfr(self, input_path: Path, output_path: Path):
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-vf", f"fps={self.cfg.target_fps}",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "18",           # alta calidad, ajusta si es muy lento
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",  # streaming-friendly
            str(output_path),
        ]
        subprocess.run(cmd, check=True)

    def _copy_stream(self, input_path: Path, output_path: Path):
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-c", "copy",
            "-movflags", "+faststart",
            str(output_path),
        ]
        subprocess.run(cmd, check=True)

    def get_video_info(self, path: Path) -> dict:
        """Retorna metadatos básicos del video."""
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,duration,r_frame_rate",
            "-of", "json",
            str(path),
        ]
        import json
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)
        stream = data.get("streams", [{}])[0]
        fps_parts = stream.get("r_frame_rate", "30/1").split("/")
        fps = int(fps_parts[0]) / int(fps_parts[1]) if len(fps_parts) == 2 else 30
        return {
            "width": int(stream.get("width", 1920)),
            "height": int(stream.get("height", 1080)),
            "duration_s": float(stream.get("duration", 0)),
            "fps": fps,
        }
