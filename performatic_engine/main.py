"""
PERFORMATIC WRITINGS - Motor de Contenido Automatizado
=======================================================
Canal: escriturasperformaticascali@gmail.com
Arquitectura: Dramaturgo Digital + Ingeniero de Atención

Pipeline completo:
  1. Normalización (ffmpeg/ffprobe)
  2. Segmentación (PySceneDetect / TransNetV2)
  3. Transcripción y análisis de hooks (Whisper + spaCy)
  4. Reencuadre 9:16 (YOLOv8 + OpenCV)
  5. Generación de metadatos SMO (LLM)
  6. Upload rotativo con cuota multi-proyecto (YouTube Data API v3)

Uso:
  python main.py --input video.mp4 --mode full
  python main.py --input video.mp4 --mode clips_only
  python main.py --input video.mp4 --mode upload_only --clips_dir ./output/clips
"""

import argparse
import logging
import sys
from pathlib import Path

from agents.normalizer import NormalizerAgent
from agents.segmenter import SegmenterAgent
from agents.transcriber import TranscriberAgent
from agents.reframer import ReframerAgent
from agents.smo_generator import SMOGeneratorAgent
from agents.uploader import UploaderAgent
from config import PipelineConfig

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("pipeline.log"),
    ],
)
log = logging.getLogger("main")


def run_pipeline(input_path: Path, mode: str, clips_dir: Path | None = None):
    cfg = PipelineConfig()
    results = {}

    if mode in ("full", "clips_only"):
        # --- Agente 1: Normalización ---
        log.info("=== AGENTE 1: Normalización VFR → CFR ===")
        normalizer = NormalizerAgent(cfg)
        normalized_path = normalizer.run(input_path)
        results["normalized"] = normalized_path

        # --- Agente 2: Segmentación de escenas ---
        log.info("=== AGENTE 2: Segmentación de escenas ===")
        segmenter = SegmenterAgent(cfg)
        scenes = segmenter.run(normalized_path)
        results["scenes"] = scenes
        log.info(f"  Escenas detectadas: {len(scenes)}")

        # --- Agente 3: Transcripción + análisis de hooks ---
        log.info("=== AGENTE 3: Transcripción y análisis dramatúrgico ===")
        transcriber = TranscriberAgent(cfg)
        transcript_data = transcriber.run(normalized_path, scenes)
        results["transcript"] = transcript_data
        log.info(f"  Hooks identificados: {len(transcript_data['hooks'])}")

        # --- Agente 4: Reencuadre 9:16 ---
        log.info("=== AGENTE 4: Reencuadre vertical 9:16 ===")
        reframer = ReframerAgent(cfg)
        clips = reframer.run(normalized_path, transcript_data["hooks"])
        results["clips"] = clips
        log.info(f"  Clips generados: {len(clips)}")

    else:
        # modo upload_only: clips ya existen
        clips = list(clips_dir.glob("*.mp4")) if clips_dir else []
        results["clips"] = [{"path": str(c), "hook_text": c.stem} for c in clips]

    if mode in ("full", "upload_only"):
        # --- Agente 5: Generación de metadatos SMO ---
        log.info("=== AGENTE 5: Generación de metadatos SMO ===")
        smo = SMOGeneratorAgent(cfg)
        enriched_clips = smo.run(results["clips"], results.get("transcript"))
        results["enriched_clips"] = enriched_clips

        # --- Agente 6: Upload con rotación de proyectos ---
        log.info("=== AGENTE 6: Upload rotativo multi-proyecto ===")
        uploader = UploaderAgent(cfg)
        upload_results = uploader.run(enriched_clips)
        results["uploads"] = upload_results

        total_ok = sum(1 for r in upload_results if r.get("status") == "ok")
        log.info(f"  Videos subidos exitosamente: {total_ok}/{len(upload_results)}")

    log.info("=== PIPELINE COMPLETADO ===")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Performatic Content Engine")
    parser.add_argument("--input", type=Path, required=False)
    parser.add_argument(
        "--mode",
        choices=["full", "clips_only", "upload_only"],
        default="full",
    )
    parser.add_argument("--clips_dir", type=Path, default=None)
    args = parser.parse_args()

    if args.mode != "upload_only" and not args.input:
        parser.error("--input es requerido para modos full y clips_only")

    run_pipeline(args.input, args.mode, args.clips_dir)
