import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from second_pass.local_clip_optimizer import cleanup_packaging_text
from second_pass.local_clip_optimizer import parse_srt_or_vtt_text
from second_pass.local_clip_optimizer import score_hook_text
from second_pass.local_clip_optimizer import transcript_stats_for_window
from second_pass.register_optimized_videos import merge_registered_records


class SecondPassTests(unittest.TestCase):
    def test_parse_srt_or_vtt_text_reads_cues(self):
        raw_text = """1
00:00:00,000 --> 00:00:02,000
Mira esto porque cambia todo.

2
00:00:02,500 --> 00:00:05,000
No cometas este error.
"""
        cues = parse_srt_or_vtt_text(raw_text)

        self.assertEqual(
            cues,
            [
                {"start": 0.0, "end": 2.0, "text": "Mira esto porque cambia todo."},
                {"start": 2.5, "end": 5.0, "text": "No cometas este error."},
            ],
        )

    def test_score_hook_text_rewards_curiosity_language(self):
        weak = score_hook_text("registro de ensayo")
        strong = score_hook_text("Mira esto: por que nadie te dice este error?")
        self.assertGreater(strong, weak)

    def test_transcript_stats_for_window_prefers_intro_hook(self):
        cues = [
            {"start": 0.2, "end": 2.4, "text": "Mira esto porque cambia todo."},
            {"start": 4.0, "end": 6.0, "text": "Luego explico el proceso completo."},
        ]

        stats = transcript_stats_for_window(0.0, 10.0, cues)

        self.assertEqual(stats["hook_text"], "Mira esto porque cambia todo.")
        self.assertGreater(stats["hook_score"], 0.0)
        self.assertGreater(stats["intro_speech_ratio"], 0.0)

    def test_cleanup_packaging_text_limits_word_count(self):
        text = cleanup_packaging_text("Esto es una frase demasiado larga para dejarla completa", max_words=5)
        self.assertEqual(text, "Esto es una frase demasiado")

    def test_merge_registered_records_updates_existing_path(self):
        existing = [{"path": "C:/clips/a.mp4", "uploaded": True, "size_mb": 10}]
        added, updated = merge_registered_records(
            existing,
            [{"path": "C:/clips/a.mp4", "uploaded": False, "title_override": "Nuevo", "size_mb": 11}],
        )

        self.assertEqual((added, updated), (0, 1))
        self.assertTrue(existing[0]["uploaded"])
        self.assertEqual(existing[0]["title_override"], "Nuevo")
        self.assertEqual(existing[0]["size_mb"], 11)


if __name__ == "__main__":
    unittest.main()
