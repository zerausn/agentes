import unittest

from fb_to_ig_vigia import extract_content_keys, find_duplicate_reason


class VigiaDedupeTests(unittest.TestCase):
    def test_teaser_full_and_pw_prefix_share_same_canonical_keys(self):
        full_message = "20260418_191445 #full #PW"
        teaser_message = "20260418_191445 #teaser #PW"
        scheduled_message = "PW | 2026-04-14 | 20260418_191445"

        full_keys = extract_content_keys(full_message)
        teaser_keys = extract_content_keys(teaser_message)
        scheduled_keys = extract_content_keys(scheduled_message)

        self.assertIn("stem:20260418_191445", full_keys)
        self.assertIn("stem:20260418_191445", teaser_keys)
        self.assertIn("stem:20260418_191445", scheduled_keys)
        self.assertIn("text:20260418_191445", full_keys)
        self.assertIn("text:20260418_191445", teaser_keys)
        self.assertIn("text:20260418_191445", scheduled_keys)

    def test_duplicate_is_detected_from_instagram_catalog_keys(self):
        registry = {"processed_post_ids": set(), "processed_keys": set()}
        ig_catalog_keys = {
            "stem:20251115_183534",
            "text:20251115_183534",
        }

        duplicate, keys, reason = find_duplicate_reason(
            "803559979506784_122135081259044766",
            "20251115_183534 #full #PW",
            registry,
            ig_catalog_keys,
        )

        self.assertTrue(duplicate)
        self.assertIn("stem:20251115_183534", keys)
        self.assertTrue(reason.startswith("instagram:"))

    def test_duplicate_is_detected_from_registry_keys(self):
        registry = {
            "processed_post_ids": set(),
            "processed_keys": {"stem:vid_20260409_wa0016"},
        }
        ig_catalog_keys = set()

        duplicate, keys, reason = find_duplicate_reason(
            "803559979506784_122136967455044766",
            "VID-20260409-WA0016 #full #PW",
            registry,
            ig_catalog_keys,
        )

        self.assertTrue(duplicate)
        self.assertIn("stem:vid_20260409_wa0016", keys)
        self.assertTrue(reason.startswith("registry:"))


if __name__ == "__main__":
    unittest.main()
