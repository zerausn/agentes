"""
agents/reframer.py
==================
Agente 4: Reencuadre vertical 9:16
- YOLOv8 para detección y seguimiento de personas
- OpenCV para cálculo de crop dinámico
- Regla de oro y tercios para composición
- Suavizado de tracking para evitar jitter
- ffmpeg para exportar el clip final con SRT embebido
"""

import logging
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

# Índice de clase YOLO para "persona"
YOLO_PERSON_CLASS = 0


class ReframerAgent:
    def __init__(self, cfg):
        self.cfg = cfg
        self._yolo_model = None

    @property
    def yolo(self):
        if self._yolo_model is None:
            from ultralytics import YOLO
            log.info(f"  Cargando YOLOv8 ({self.cfg.yolo_model})...")
            self._yolo_model = YOLO(self.cfg.yolo_model)
        return self._yolo_model

    def run(self, video_path: Path, hooks: list[dict]) -> list[dict]:
        clips = []
        for i, hook in enumerate(hooks):
            clip_name = f"{video_path.stem}_clip{i+1:02d}.mp4"
            clip_path = self.cfg.clips_dir / clip_name

            if clip_path.exists():
                log.info(f"  Clip ya existe: {clip_path}")
            else:
                log.info(
                    f"  Procesando clip {i+1}/{len(hooks)}: "
                    f"{hook['start_s']:.1f}s → {hook['end_s']:.1f}s"
                )
                self._process_clip(video_path, hook, clip_path)

            srt_path = self.cfg.srt_dir / f"{video_path.stem}.srt"

            clips.append({
                "path": str(clip_path),
                "hook_text": hook.get("hook_text", ""),
                "burstiness_score": hook.get("burstiness_score", 0),
                "start_s": hook["start_s"],
                "end_s": hook["end_s"],
                "reframe_suggestion": hook.get("reframe_suggestion", "cerrado"),
                "promise": hook.get("promise", ""),
                "curiosity_gap": hook.get("curiosity_gap", ""),
                "srt_path": str(srt_path) if srt_path.exists() else None,
            })

        return clips

    def _process_clip(self, video_path: Path, hook: dict, output_path: Path):
        """
        Extrae el segmento, calcula el crop 9:16 con seguimiento,
        y exporta el clip final.
        """
        import cv2
        import numpy as np

        start_s = hook["start_s"]
        end_s = hook["end_s"]

        # Abrir video en el segmento
        cap = cv2.VideoCapture(str(video_path))
        cap.set(cv2.CAP_PROP_POS_MSEC, start_s * 1000)

        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        src_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        src_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        out_w = self.cfg.output_width
        out_h = self.cfg.output_height

        # El crop debe ser tan alto como el video fuente permite
        # Calculamos el ancho proporcional para 9:16
        crop_h = src_h
        crop_w = int(src_h * out_w / out_h)
        crop_w = min(crop_w, src_w)

        # Buffer de crop coords para suavizado
        smooth_cx = src_w // 2  # centro x inicial
        alpha = 1.0 - self.cfg.tracking_smoothing

        # Preparar escritura temporal (sin audio)
        tmp_video = output_path.with_suffix(".tmp.mp4")
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(tmp_video), fourcc, fps, (out_w, out_h))

        frame_count = 0
        total_frames = int((end_s - start_s) * fps)
        sample_every = max(1, int(fps // 5))  # YOLO cada 5 frames = eficiente

        detected_cx = smooth_cx  # último centro detectado

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            current_time = start_s + frame_count / fps
            if current_time > end_s:
                break

            # Detección YOLO (muestreo cada N frames)
            if frame_count % sample_every == 0:
                detected_cx = self._detect_subject_cx(frame, src_w)

            # Suavizado exponencial del centro
            smooth_cx = int(alpha * detected_cx + (1 - alpha) * smooth_cx)

            # Calcular crop rect
            cx = self._apply_composition_rule(smooth_cx, crop_w, src_w)
            x1 = max(0, cx - crop_w // 2)
            x2 = min(src_w, x1 + crop_w)
            # Ajustar si se sale del borde
            if x2 - x1 < crop_w:
                x1 = max(0, x2 - crop_w)

            cropped = frame[:crop_h, x1:x2]
            resized = cv2.resize(cropped, (out_w, out_h), interpolation=cv2.INTER_LANCZOS4)
            writer.write(resized)

            frame_count += 1
            if frame_count % int(fps * 10) == 0:
                pct = frame_count / total_frames * 100
                log.debug(f"    Reencuadre: {pct:.0f}%")

        cap.release()
        writer.release()

        # Combinar video procesado + audio original con ffmpeg
        self._mux_audio(video_path, tmp_video, output_path, start_s, end_s)
        tmp_video.unlink(missing_ok=True)

    def _detect_subject_cx(self, frame, src_w: int) -> int:
        """Detecta el centro X del sujeto principal con YOLOv8."""
        try:
            results = self.yolo(frame, classes=[YOLO_PERSON_CLASS], verbose=False)
            boxes = results[0].boxes
            if boxes is None or len(boxes) == 0:
                return src_w // 2

            # Tomar la detección con mayor área (sujeto principal)
            best_box = None
            best_area = 0
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                area = (x2 - x1) * (y2 - y1)
                if area > best_area:
                    best_area = area
                    best_box = (x1, y1, x2, y2)

            if best_box:
                cx = int((best_box[0] + best_box[2]) / 2)
                return cx
        except Exception as e:
            log.debug(f"    YOLO error: {e}")

        return src_w // 2

    def _apply_composition_rule(self, raw_cx: int, crop_w: int, src_w: int) -> int:
        """
        Ajusta el centro según la regla de composición configurada.
        - center: sujeto centrado
        - golden_ratio: sujeto en proporción áurea (61.8% desde izquierda)
        - thirds: sujeto en primer tercio
        """
        if self.cfg.composition_rule == "golden_ratio":
            # Offset para poner el sujeto en la proporción áurea del frame
            offset = int(crop_w * 0.118)  # 61.8% - 50% = 11.8%
            return raw_cx - offset
        elif self.cfg.composition_rule == "thirds":
            offset = int(crop_w * (1/3 - 0.5))
            return raw_cx - offset
        return raw_cx  # center

    def _mux_audio(
        self, original: Path, processed_video: Path,
        output: Path, start_s: float, end_s: float
    ):
        """Combina el video reencuadrado con el audio original del segmento."""
        duration = end_s - start_s
        cmd = [
            "ffmpeg", "-y",
            "-i", str(processed_video),
            "-ss", str(start_s),
            "-t", str(duration),
            "-i", str(original),
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "18",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            "-movflags", "+faststart",
            str(output),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
