import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from video_helpers import build_upload_metadata
from video_helpers import build_video_title
from video_helpers import classify_video_kind
from video_helpers import extract_video_stem
from video_helpers import get_video_roots
from video_helpers import infer_library_root_from_path
from video_helpers import is_ephemeral_video_artifact
from video_helpers import is_managed_title
from video_helpers import normalize_video_stem
from video_helpers import parse_ffprobe_stream_data


class VideoHelpersTests(unittest.TestCase):
    def test_infer_library_root_strips_managed_subfolders(self):
        root = Path(r"C:\videos")
        uploaded_path = root / "videos subidos exitosamente" / "clip.mp4"
        excluded_path = root / "videos_excluidos_ya_en_youtube" / "clip.mp4"

        self.assertEqual(infer_library_root_from_path(uploaded_path), root)
        self.assertEqual(infer_library_root_from_path(excluded_path), root)

    def test_get_video_roots_uses_configured_and_env_paths(self):
        base_dir = Path(__file__).resolve().parents[1]
        configured = (base_dir / "media").resolve()
        env_root = (base_dir / "env_media").resolve()

        config = {"scanner": {"video_roots": ["media"]}}
        roots = get_video_roots(
            base_dir,
            config=config,
            environ={"YOUTUBE_UPLOADER_VIDEO_ROOTS": str(env_root)},
            existing_only=False,
        )

        self.assertEqual(roots, [configured, env_root])

    def test_classify_video_kind_uses_three_minute_rule_for_vertical(self):
        self.assertEqual(classify_video_kind(1080, 1920, 179.9), "short")
        self.assertEqual(classify_video_kind(1920, 1080, 179.9), "video")
        self.assertEqual(classify_video_kind(1920, 1080, 45), "short")

    def test_parse_ffprobe_stream_data_builds_metadata(self):
        payload = {"streams": [{"width": 1080, "height": 1920, "duration": "120.5"}]}
        metadata = parse_ffprobe_stream_data(payload)

        self.assertEqual(
            metadata,
            {
                "width": 1080,
                "height": 1920,
                "duration": 120.5,
                "dimensions": "1080x1920",
                "type": "short",
            },
        )

    def test_build_video_title_uses_current_prefix(self):
        video = {
            "filename": "20260310_181426.mp4",
            "creation_date": "2026-03-10 18:14:26",
        }
        self.assertEqual(build_video_title(video), "PW | (20260310_181426)")

    def test_build_video_title_strips_faststart_temp_suffix(self):
        video = {
            "filename": "20260414_170022.faststart.tmp.mp4",
            "creation_date": "2026-04-14 21:44:21",
        }
        self.assertEqual(build_video_title(video), "PW | (20260414_170022)")

    def test_build_video_title_strips_slice_variants(self):
        cases = [
            ("slice_60s_20241109_211317.mp4", "PW | (20241109_211317)"),
            ("slice 60 some title.mp4", "PW | (some title)"),
            ("slice60_test.mp4", "PW | (test)"),
            ("slice-60-v2.mp4", "PW | (v2)"),
            ("ig_compat_slice_60s_clip.mp4", "PW | (clip)"),
        ]
        for filename, expected in cases:
            with self.subTest(filename=filename):
                video = {"filename": filename}
                self.assertEqual(build_video_title(video), expected)

    def test_build_upload_metadata_prefers_second_pass_overrides(self):
        config = {
            "default_metadata": {
                "description": "Descripcion base",
                "tags": ["teatro", "performance"],
                "categoryId": "24",
                "privacyStatus": "private",
                "license": "youtube",
            }
        }
        video = {
            "filename": "clip.mp4",
            "creation_date": "2026-03-10 18:14:26",
            "title_override": "PW Clip | Hook fuerte",
            "description_override": "Descripcion optimizada",
            "tags_override": ["shorts", "clipping"],
            "categoryId_override": "27",
        }

        metadata = build_upload_metadata(video, config)

        self.assertEqual(
            metadata,
            {
                "title": "PW Clip | Hook fuerte",
                "description": "Descripcion optimizada",
                "tags": ["shorts", "clipping"],
                "categoryId": "27",
                "privacyStatus": "private",
                "license": "youtube",
            },
        )

    def test_is_managed_title_accepts_current_legacy_and_timestamp_titles(self):
        self.assertTrue(is_managed_title("PW | 2026-03-10 | (20260310_181426)"))
        self.assertTrue(is_managed_title("Performatic Writings | 2026-03-10"))
        self.assertTrue(is_managed_title("20260310_181426.mp4"))
        self.assertFalse(is_managed_title("Titulo manual del usuario"))

    def test_normalize_video_stem_removes_faststart_marker(self):
        self.assertEqual(normalize_video_stem("20260414_170022.faststart.tmp"), "20260414_170022")
        self.assertEqual(normalize_video_stem("20260414_170022"), "20260414_170022")

    def test_extract_video_stem_prefers_managed_title_marker(self):
        self.assertEqual(extract_video_stem("PW | 2026-04-14 | (20260414_170022.faststart.tmp)"), "20260414_170022")
        self.assertEqual(extract_video_stem(r"C:\videos\20260414_170022.faststart.tmp.mp4"), "20260414_170022")

    def test_is_ephemeral_video_artifact_detects_faststart_temp_files(self):
        self.assertTrue(is_ephemeral_video_artifact("20260414_170022.faststart.tmp.mp4"))
        self.assertTrue(is_ephemeral_video_artifact(r"C:\videos\20260414_170022.faststart.tmp.mp4"))
        self.assertFalse(is_ephemeral_video_artifact("20260414_170022.mp4"))


if __name__ == "__main__":
    unittest.main()
