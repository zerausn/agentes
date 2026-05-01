"""
agents/segmenter.py
===================
Agente 2: Segmentación de escenas
Backend seleccionable: PySceneDetect (rápido) o TransNetV2 (preciso)
"""

import logging
from pathlib import Path

log = logging.getLogger(__name__)


class SegmenterAgent:
    def __init__(self, cfg):
        self.cfg = cfg

    def run(self, video_path: Path) -> list[dict]:
        if self.cfg.segmenter_backend == "transnetv2":
            return self._run_transnetv2(video_path)
        return self._run_pyscenedetect(video_path)

    def _run_pyscenedetect(self, video_path: Path) -> list[dict]:
        from scenedetect import VideoManager, SceneManager
        from scenedetect.detectors import ContentDetector

        vm = VideoManager([str(video_path)])
        sm = SceneManager()
        sm.add_detector(ContentDetector(threshold=self.cfg.scene_threshold))
        vm.set_downscale_factor()
        vm.start()
        sm.detect_scenes(frame_source=vm)
        raw_scenes = sm.get_scene_list()
        vm.release()

        scenes = []
        for start, end in raw_scenes:
            duration = end.get_seconds() - start.get_seconds()
            if duration >= self.cfg.min_scene_duration_s:
                scenes.append({
                    "start_s": round(start.get_seconds(), 3),
                    "end_s": round(end.get_seconds(), 3),
                    "duration_s": round(duration, 3),
                })
        return scenes

    def _run_transnetv2(self, video_path: Path) -> list[dict]:
        """
        Requiere: pip install transnetv2
        Más preciso para disolvencias y cortes suaves.
        """
        try:
            from transnetv2 import TransNetV2
        except ImportError:
            log.warning("TransNetV2 no instalado, usando PySceneDetect como fallback")
            return self._run_pyscenedetect(video_path)

        model = TransNetV2()
        video_frames, single_frame_predictions, all_frame_predictions = \
            model.predict_video(str(video_path))

        scenes_frames = model.predictions_to_scenes(single_frame_predictions)
        import cv2
        cap = cv2.VideoCapture(str(video_path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        cap.release()

        scenes = []
        for start_f, end_f in scenes_frames:
            start_s = start_f / fps
            end_s = end_f / fps
            duration = end_s - start_s
            if duration >= self.cfg.min_scene_duration_s:
                scenes.append({
                    "start_s": round(start_s, 3),
                    "end_s": round(end_s, 3),
                    "duration_s": round(duration, 3),
                })
        return scenes
