import unittest
from datetime import datetime, timezone

from fb_to_ig_vigia import (
    _normalize_marker,
    _normalize_registry_key,
    _pick_newer_candidate,
    extract_content_keys,
    find_duplicate_reason,
    parse_created_time,
)


class VigiaDedupeTests(unittest.TestCase):
    def test_teaser_uses_derivative_key_not_bare_stem(self):
        teaser = extract_content_keys(
            "#PW | PW  (20260429_185945)_teaser_14\n\nlinktr.ee/performaticwritingscali"
        )

        self.assertIn("content:20260429_185945_teaser_14", teaser)
        self.assertNotIn("content:20260429_185945", teaser)
        self.assertNotIn("stem:20260429_185945", teaser)

    def test_distinct_teasers_from_same_source_do_not_collide(self):
        teaser_13 = extract_content_keys("#SW | PW  (20260429_185945)_teaser_13")
        teaser_16 = extract_content_keys("#GW | PW  (20260429_185945)_teaser_16")

        self.assertIn("content:20260429_185945_teaser_13", teaser_13)
        self.assertIn("content:20260429_185945_teaser_16", teaser_16)
        self.assertEqual(teaser_13 & teaser_16, set())

    def test_same_teaser_across_pages_shares_content_and_text_keys(self):
        performatic = extract_content_keys(
            "#PW | PW  (20260429_185945)_teaser_13\n\n#PW\nSiguenos tambien en Facebook"
        )
        ghawazee = extract_content_keys(
            "#GW | PW  (20260429_185945)_teaser_13\n\n#GW\nSiguenos tambien en Facebook"
        )

        self.assertEqual(performatic, ghawazee)
        self.assertIn("content:20260429_185945_teaser_13", performatic)
        self.assertIn("text:pw (20260429_185945)_teaser_13", performatic)

    def test_page_prefixes_normalize_to_same_marker(self):
        expected = "pw (20260429_185945)_teaser_13"
        for caption in (
            "#PW | PW  (20260429_185945)_teaser_13",
            "#SW | PW  (20260429_185945)_teaser_13",
            "#GW | PW  (20260429_185945)_teaser_13",
            "#SC | PW  (20260429_185945)_teaser_13",
        ):
            self.assertEqual(_normalize_marker(caption), expected)

    def test_full_video_and_numbered_teaser_are_distinct(self):
        full = extract_content_keys("20260418_191445 #full #PW")
        teaser = extract_content_keys("20260418_191445_teaser_1 #teaser #PW")

        self.assertIn("content:20260418_191445", full)
        self.assertIn("content:20260418_191445_teaser_1", teaser)
        self.assertNotIn("content:20260418_191445", teaser)
        self.assertEqual(full & teaser, set())

    def test_unnumbered_teaser_does_not_block_full_video(self):
        full = extract_content_keys("20260418_191445 #full #PW")
        teaser = extract_content_keys("20260418_191445 #teaser #PW")

        self.assertIn("content:20260418_191445", full)
        self.assertIn("content:20260418_191445_teaser", teaser)
        self.assertNotIn("content:20260418_191445", teaser)
        self.assertEqual(full & teaser, set())

    def test_scheduled_full_video_dedupes_against_full_message(self):
        scheduled = extract_content_keys("PW | 2026-04-14 | 20260418_191445")
        full = extract_content_keys("20260418_191445 #full #PW")

        self.assertIn("content:20260418_191445", scheduled)
        self.assertIn("content:20260418_191445", full)

    def test_old_bare_stem_registry_key_does_not_block_new_teaser(self):
        registry = {
            "processed_post_ids": set(),
            "processed_keys": {"stem:20260429_185945"},
        }

        duplicate, keys, reason = find_duplicate_reason(
            "803559979506784_122157974637044766",
            "#GW | PW  (20260429_185945)_teaser_16",
            registry,
            set(),
        )

        self.assertFalse(duplicate)
        self.assertEqual(reason, "")
        self.assertIn("content:20260429_185945_teaser_16", keys)

    def test_same_teaser_is_detected_from_registry_content_key(self):
        registry = {
            "processed_post_ids": set(),
            "processed_keys": {"content:20260429_185945_teaser_13"},
        }

        duplicate, keys, reason = find_duplicate_reason(
            "824642984061807_122152834503038597",
            "#SW | PW  (20260429_185945)_teaser_13",
            registry,
            set(),
        )

        self.assertTrue(duplicate)
        self.assertIn("content:20260429_185945_teaser_13", keys)
        self.assertEqual(reason, "registry:content:20260429_185945_teaser_13")

    def test_duplicate_is_detected_from_instagram_catalog_keys(self):
        registry = {"processed_post_ids": set(), "processed_keys": set()}
        ig_catalog_keys = {"content:20251115_183534"}

        duplicate, keys, reason = find_duplicate_reason(
            "803559979506784_122135081259044766",
            "20251115_183534 #full #PW",
            registry,
            ig_catalog_keys,
        )

        self.assertTrue(duplicate)
        self.assertIn("content:20251115_183534", keys)
        self.assertTrue(reason.startswith("instagram:"))

    def test_registry_loader_helper_normalizes_old_page_prefixed_text_key(self):
        self.assertEqual(
            _normalize_registry_key("text:#sw | pw (20260429_180341)_teaser_1"),
            "text:pw (20260429_180341)_teaser_1",
        )
        self.assertEqual(
            _normalize_registry_key("stem:20260429_185945"),
            "stem:20260429_185945",
        )


class VigiaSelectionTests(unittest.TestCase):
    def test_parse_created_time_accepts_graph_api_offset(self):
        parsed = parse_created_time("2026-10-26T19:26:19+0000")

        self.assertEqual(
            parsed,
            datetime(2026, 10, 26, 19, 26, 19, tzinfo=timezone.utc),
        )

    def test_parse_created_time_accepts_z_and_naive_values(self):
        self.assertEqual(
            parse_created_time("2026-10-26T19:26:19Z"),
            datetime(2026, 10, 26, 19, 26, 19, tzinfo=timezone.utc),
        )
        self.assertEqual(
            parse_created_time("2026-10-26 19:26:19"),
            datetime(2026, 10, 26, 19, 26, 19, tzinfo=timezone.utc),
        )
        self.assertIsNone(parse_created_time(""))
        self.assertIsNone(parse_created_time("not-a-date"))

    def test_pick_newer_candidate_compares_across_pages(self):
        older = {"id": "older", "created_time": "2026-10-26T19:00:00+0000"}
        newer = {"id": "newer", "created_time": "2026-10-26T19:26:19+0000"}

        picked, keys = _pick_newer_candidate(older, {"old"}, newer, {"new"})
        self.assertIs(picked, newer)
        self.assertEqual(keys, {"new"})

        picked, keys = _pick_newer_candidate(newer, {"new"}, older, {"old"})
        self.assertIs(picked, newer)
        self.assertEqual(keys, {"new"})

        picked, keys = _pick_newer_candidate(None, None, older, {"old"})
        self.assertIs(picked, older)
        self.assertEqual(keys, {"old"})

    def test_pick_newer_candidate_falls_back_to_string_comparison(self):
        current = {"id": "current", "created_time": "unknown-b"}
        new = {"id": "new", "created_time": "unknown-a"}

        picked, keys = _pick_newer_candidate(current, {"current"}, new, {"new"})
        self.assertIs(picked, current)
        self.assertEqual(keys, {"current"})


if __name__ == "__main__":
    unittest.main()
