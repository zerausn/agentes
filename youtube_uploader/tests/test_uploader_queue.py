import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import uploader as uploader_module
from uploader import build_pending_upload_queues
from uploader import normalize_upload_lane
from uploader import pop_next_pending_video


class UploaderQueueTests(unittest.TestCase):
    REFERENCE_NOW = datetime(2026, 4, 8, 12, 0, tzinfo=timezone.utc)

    @classmethod
    def setUpClass(cls):
        cls._original_config = uploader_module.config
        uploader_module.config = {
            "scheduling": {
                "colombia_time_offset": -5,
                "publish_hour": 17,
                "publish_minute": 45,
            }
        }

    @classmethod
    def tearDownClass(cls):
        uploader_module.config = cls._original_config

    def test_build_pending_upload_queues_sorts_each_lane_by_weight(self):
        videos = [
            {"filename": "video_a.mp4", "type": "video", "size_mb": 120, "uploaded": False},
            {"filename": "short_a.mp4", "type": "short", "size_mb": 90, "uploaded": False},
            {"filename": "video_b.mp4", "type": "video", "size_mb": 180, "uploaded": False},
            {"filename": "short_b.mp4", "type": "short", "size_mb": 110, "uploaded": False},
            {"filename": "video_tmp.faststart.tmp.mp4", "type": "video", "size_mb": 500, "uploaded": False},
            {"filename": "done.mp4", "type": "video", "size_mb": 999, "uploaded": True},
        ]

        queues = build_pending_upload_queues(videos)

        self.assertEqual([item["filename"] for item in queues["video"]], ["video_b.mp4", "video_a.mp4"])
        self.assertEqual([item["filename"] for item in queues["short"]], ["short_b.mp4", "short_a.mp4"])

    def test_pop_next_pending_video_prefers_earliest_gap_then_lane_weight(self):
        videos = [
            {
                "filename": "video_heavy.mp4",
                "type": "video",
                "size_mb": 300,
                "uploaded": False,
            },
            {
                "filename": "short_heavy.mp4",
                "type": "short",
                "size_mb": 500,
                "uploaded": False,
            },
        ]
        queues = build_pending_upload_queues(videos)
        yt_schedule = {
            "2026-04-09": {"videos": 0, "shorts": 1},
            "2026-04-10": {"videos": 0, "shorts": 0},
        }

        selected, lane, next_date = pop_next_pending_video(
            queues,
            videos,
            yt_schedule,
            now_utc=self.REFERENCE_NOW,
        )

        self.assertEqual(selected["filename"], "video_heavy.mp4")
        self.assertEqual(lane, "video")
        self.assertEqual(next_date, datetime(2026, 4, 9, 22, 45, tzinfo=timezone.utc))

    def test_pop_next_pending_video_uses_heaviest_lane_head_when_dates_tie(self):
        videos = [
            {
                "filename": "video_light.mp4",
                "type": "video",
                "size_mb": 100,
                "uploaded": False,
            },
            {
                "filename": "short_heavy.mp4",
                "type": "short",
                "size_mb": 250,
                "uploaded": False,
            },
        ]
        queues = build_pending_upload_queues(videos)
        yt_schedule = {}

        selected, lane, next_date = pop_next_pending_video(
            queues,
            videos,
            yt_schedule,
            now_utc=self.REFERENCE_NOW,
        )

        self.assertEqual(selected["filename"], "short_heavy.mp4")
        self.assertEqual(lane, "short")
        self.assertEqual(next_date, datetime(2026, 4, 9, 22, 45, tzinfo=timezone.utc))

    def test_normalize_upload_lane_defaults_unknown_types_to_video(self):
        self.assertEqual(normalize_upload_lane({"type": "short"}), "short")
        self.assertEqual(normalize_upload_lane({"type": "video"}), "video")
        self.assertEqual(normalize_upload_lane({"type": "otro"}), "video")


if __name__ == "__main__":
    unittest.main()
