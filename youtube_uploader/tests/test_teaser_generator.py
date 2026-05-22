import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from teaser_generator import build_segment_starts
from teaser_generator import expected_outputs_for


class TeaserGeneratorTests(unittest.TestCase):
    def test_build_segment_starts_uses_full_16_second_windows(self):
        self.assertEqual(build_segment_starts(48.0), [0.0, 16.0, 32.0])
        self.assertEqual(build_segment_starts(49.0), [0.0, 16.0, 32.0])
        self.assertEqual(build_segment_starts(80.0), [0.0, 16.0, 32.0, 48.0, 64.0])
        self.assertEqual(build_segment_starts(15.5), [0.0])

    def test_expected_outputs_for_matches_duration_driven_count(self):
        output_dir = Path("/sdcard/Antigravity/teasers_pendientes")
        outputs = expected_outputs_for(output_dir, "20260509_184854", 65.0)

        self.assertEqual(
            outputs,
            [
                output_dir / "20260509_184854_teaser_1.mp4",
                output_dir / "20260509_184854_teaser_2.mp4",
                output_dir / "20260509_184854_teaser_3.mp4",
                output_dir / "20260509_184854_teaser_4.mp4",
            ],
        )


if __name__ == "__main__":
    unittest.main()
