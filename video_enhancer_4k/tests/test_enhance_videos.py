import unittest

from enhance_videos import compute_target_dimensions, parse_fraction, round_even


class EnhanceVideosTest(unittest.TestCase):
    def test_parse_fraction(self) -> None:
        self.assertAlmostEqual(parse_fraction("30000/1001"), 29.97002997, places=5)
        self.assertEqual(parse_fraction("30"), 30.0)

    def test_round_even(self) -> None:
        self.assertEqual(round_even(5.1), 6)
        self.assertEqual(round_even(2160), 2160)

    def test_target_dimensions_landscape(self) -> None:
        width, height = compute_target_dimensions(1920, 1080)
        self.assertEqual((width, height), (3840, 2160))

    def test_target_dimensions_vertical(self) -> None:
        width, height = compute_target_dimensions(1080, 1920)
        self.assertEqual((width, height), (2160, 3840))


if __name__ == "__main__":
    unittest.main()
