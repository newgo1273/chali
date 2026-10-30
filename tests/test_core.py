import json
import os
import tempfile
import unittest
from pathlib import Path

from chali.config import DEFAULTS, color_contrast_ratio, load_config, save_config
from chali.dashboard import _render_chat
from chali.stream import (
    StreamEvent,
    _alert_text,
    _format_message_time,
    youtube_video_id,
)


class ConfigTests(unittest.TestCase):
    def test_defaults_are_independent(self):
        first = load_config(Path("does-not-exist.json"))
        first["streamlabs"]["socket_token"] = "not-shared"
        second = load_config(Path("still-does-not-exist.json"))
        self.assertEqual(second["streamlabs"]["socket_token"], DEFAULTS["streamlabs"]["socket_token"])

    def test_save_load_and_secure_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            config = load_config(Path(directory) / "missing.json")
            save_config(config, path)
            self.assertEqual(load_config(path), config)
            if os.name == "posix":
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_rejects_bad_color(self):
        config = load_config(Path("missing-config.json"))
        config["chat"]["author_badge_background"] = "blue"
        with self.assertRaises(ValueError):
            save_config(config, Path("unused.json"))

    def test_rejects_low_contrast_badge_colors(self):
        config = load_config(Path("missing-config.json"))
        config["chat"]["author_badge_foreground"] = "#3451A3"
        with self.assertRaisesRegex(ValueError, "contrast ratio"):
            save_config(config, Path("unused.json"))

    def test_default_badge_colors_are_high_contrast(self):
        chat = load_config(Path("missing-config.json"))["chat"]
        self.assertGreaterEqual(
            color_contrast_ratio(
                chat["author_badge_foreground"], chat["author_badge_background"]
            ),
            4.5,
        )

    def test_merges_older_config(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({"youtube": {"demo_mode": False}}), encoding="utf-8")
            config = load_config(path)
            self.assertFalse(config["youtube"]["demo_mode"])
            self.assertIn("socket_token", config["streamlabs"])


class StreamTests(unittest.TestCase):
    def test_extracts_supported_youtube_urls(self):
        self.assertEqual(youtube_video_id("https://www.youtube.com/watch?v=AbCdEf_1234"), "AbCdEf_1234")
        self.assertEqual(youtube_video_id("https://youtu.be/AbCdEf_1234"), "AbCdEf_1234")
        self.assertEqual(youtube_video_id("https://youtube.com/live/AbCdEf_1234"), "AbCdEf_1234")

    def test_rejects_non_youtube_urls(self):
        with self.assertRaises(ValueError):
            youtube_video_id("https://example.com/watch?v=AbCdEf_1234")

    def test_formats_known_message_time(self):
        self.assertEqual(_format_message_time("2024-01-02 03:04:05"), "03:04:05")
        self.assertEqual(_format_message_time("03:04:05"), "03:04:05")

    def test_parses_streamlabs_alert(self):
        parsed = _alert_text({"type": "donation", "message": [{"name": "Ari", "amount": "12.5"}]})
        self.assertEqual(parsed, ("Donation: Ari", 12.5, "$"))

    def test_chat_badge_format(self):
        rendered = _render_chat(
            StreamEvent(
                "chat",
                {"time": "12:34:56", "author": "Ari", "message": "Hello chat"},
            ),
            badge_attr=1,
            width=80,
        )
        self.assertEqual(
            "".join(text for text, _ in rendered[0]),
            "[12:34:56] [Ari]: Hello chat",
        )


if __name__ == "__main__":
    unittest.main()
