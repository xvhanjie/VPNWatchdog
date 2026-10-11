import json
from pathlib import Path
import tempfile
import unittest

from utils.config import Settings, load, save


class ConfigTests(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config" / "settings.json"
            settings = Settings(interval_s=10, sound=False)
            save(path, settings)
            self.assertEqual(load(path), settings)
            self.assertFalse(path.with_suffix(".tmp").exists())

    def test_invalid_inputs(self):
        for settings in (Settings(interval_s=1), Settings(failure_count=1),
                         Settings(high_ms=100), Settings(sound="false"), Settings(timeout_s=True)):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                settings.validate()

    def test_unknown_field_repaired_with_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text(json.dumps({"proxy": "direct"}), encoding="utf-8")
            self.assertEqual(load(path), Settings())
            self.assertTrue(path.with_suffix(".json.bak").exists())
            self.assertNotIn("proxy", json.loads(path.read_text(encoding="utf-8")))

    def test_custom_intervals_and_legacy_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            for interval in (3, 5, 8, 15, 30):
                path.write_text(json.dumps({"check_interval": interval}), encoding="utf-8")
                self.assertEqual(load(path).interval_s, interval)
                self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["check_interval"], interval)
            path.write_text(json.dumps({"interval_s": 12, "sound": False}), encoding="utf-8")
            self.assertEqual(load(path).interval_s, 12)
            self.assertFalse(load(path).sound)

    def test_bad_intervals_and_broken_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            for value, expected in ((1, 3), (100, 30), (True, 5), (None, 5), ("bad", 5)):
                path.write_text(json.dumps({"check_interval": value}), encoding="utf-8")
                self.assertEqual(load(path).interval_s, expected)
            path.write_text("{broken", encoding="utf-8")
            self.assertEqual(load(path), Settings())

    def test_targets_repair_and_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            for raw, expected in (([], ["Google", "GitHub", "Cloudflare"]),
                                  (["invalid", "ChatGPT", "ChatGPT", "YouTube"], ["ChatGPT", "YouTube"]),
                                  (["YouTube", "ChatGPT", "GitHub", "Cloudflare", "Google"], ["YouTube", "ChatGPT", "GitHub"]),
                                  (None, ["Google", "GitHub", "Cloudflare"])):
                path.write_text(json.dumps({"check_interval": 8, "selected_targets": raw}), encoding="utf-8")
                self.assertEqual(load(path).selected_targets, expected)
                self.assertEqual(load(path).check_interval, 8)
                self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["selected_targets"], expected)

    def test_target_validation_is_strict_for_gui_and_worker(self):
        for selected in ([], ["Google"] * 2, ["invalid"], ["Google", "GitHub", "Cloudflare", "ChatGPT"]):
            with self.subTest(selected=selected), self.assertRaises(ValueError):
                Settings(selected_targets=selected).validate()
