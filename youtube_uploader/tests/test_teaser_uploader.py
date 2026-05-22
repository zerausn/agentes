import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import teaser_uploader as teaser_uploader_module


class TeaserUploaderTests(unittest.TestCase):
    REFERENCE_NOW = datetime(2026, 4, 8, 12, 0, tzinfo=timezone.utc)

    @classmethod
    def setUpClass(cls):
        cls._original_config = teaser_uploader_module.config
        teaser_uploader_module.config = {
            "scheduling": {
                "colombia_time_offset": -5,
                "publish_hour": 14,
                "publish_minute": 0,
            }
        }

    @classmethod
    def tearDownClass(cls):
        teaser_uploader_module.config = cls._original_config

    def test_get_next_publish_date_is_pinned_to_1745_colombia(self):
        next_date = teaser_uploader_module.get_next_publish_date({}, now_utc=self.REFERENCE_NOW)

        self.assertEqual(next_date, datetime(2026, 4, 9, 22, 45, tzinfo=timezone.utc))

    def test_get_next_publish_date_skips_days_with_existing_shorts(self):
        yt_schedule = {
            "2026-04-09": {"videos": 0, "shorts": 1},
            "2026-04-10": {"videos": 0, "shorts": 0},
        }

        next_date = teaser_uploader_module.get_next_publish_date(yt_schedule, now_utc=self.REFERENCE_NOW)

        self.assertEqual(next_date, datetime(2026, 4, 10, 22, 45, tzinfo=timezone.utc))


if __name__ == "__main__":
    unittest.main()
