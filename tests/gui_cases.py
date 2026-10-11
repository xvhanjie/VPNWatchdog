"""Separate QtWidgets test process; run: python -m unittest tests.gui_cases -v."""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from core.models import Probe, Round, State
from ui.application import Controller
from ui.settings_window import SettingsDialog
from utils.config import Settings, load


def successful(names, latency=90):
    return Round(probes=[Probe(name, True, latency, 200, reachable=True) for name in names])


class GuiCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.start = patch("ui.application.NetworkMonitor.start")
        self.mock_start = self.start.start()
        self.controller = Controller(self.app, Settings(sound=False, notifications=False), Path(self.temp.name))

    def tearDown(self):
        self.controller.shutdown()
        for handler in list(self.controller.logger.handlers):
            handler.close()
            self.controller.logger.removeHandler(handler)
        self.controller.window.allow_close = True
        self.controller.window.close()
        self.start.stop()
        self.temp.cleanup()

    def test_spinbox_all_requested_values_and_defaults(self):
        dialog = SettingsDialog(Settings())
        self.assertEqual((dialog.interval.minimum(), dialog.interval.maximum()), (3, 30))
        for interval in (3, 5, 8, 15, 30):
            dialog.interval.setValue(interval)
            dialog.validate()
            self.assertEqual(dialog.result_settings.interval_s, interval)
        dialog.restore_defaults()
        self.assertEqual(dialog.interval.value(), 5)
        self.assertEqual(dialog.selected_targets(), Settings().selected_targets)
        dialog.close()

    def test_checkbox_guard_zero_four_and_five(self):
        dialog = SettingsDialog(Settings())
        dialog.target_boxes["ChatGPT"].setChecked(True)
        dialog.target_boxes["YouTube"].setChecked(True)
        self.assertEqual(len(dialog.selected_targets()), 3)
        dialog.target_boxes["Google"].setChecked(False)
        dialog.target_boxes["GitHub"].setChecked(False)
        dialog.target_boxes["Cloudflare"].setChecked(False)
        self.assertEqual(dialog.selected_targets(), ["Cloudflare"])
        dialog.target_boxes["ChatGPT"].setChecked(True)
        dialog.target_boxes["Cloudflare"].setChecked(False)
        self.assertEqual(dialog.selected_targets(), ["ChatGPT"])
        dialog.close()

    def test_interval_only_preserves_evidence_and_work_mode(self):
        c = self.controller
        for _ in range(10):
            c.consume(successful(c.settings.selected_targets))
        count = c.machine.count
        c.apply_settings(replace(c.settings, interval_s=15))
        self.assertEqual((c.machine.state, c.machine.count), (State.HEALTHY, count))
        c.set_work_mode(True)
        self.assertEqual((c.settings.interval_s, c.monitor.settings.interval_s), (15, 3))
        c.apply_settings(replace(c.settings, interval_s=12))
        self.assertEqual(c.monitor.settings.interval_s, 3)
        c.set_work_mode(False)
        self.assertEqual(c.monitor.settings.interval_s, 12)
        self.assertIn("12 秒", c.window.timing.text())
        self.assertEqual(load(Path(self.temp.name) / "config/settings.json").interval_s, 12)

    def test_scope_change_resets_cache_and_dynamic_rows(self):
        c = self.controller
        c.consume(successful(c.settings.selected_targets))
        c.consume(successful(c.settings.selected_targets))
        for names in (["ChatGPT"], ["ChatGPT", "YouTube"], ["GitHub", "ChatGPT", "YouTube"]):
            c.apply_settings(replace(c.settings, selected_targets=names))
            self.assertEqual((c.machine.state, c.machine.count), (State.UNKNOWN, 0))
            self.assertEqual(c.window.history.toPlainText(), "")
            self.assertEqual(c.window.targets.rowCount(), len(names))
            self.assertEqual(c.last_check, "—")
            self.assertEqual(c.window.targets.item(0, 2).text(), "—")
            c.consume(successful(names))
            c.consume(successful(names))
            self.assertEqual(c.machine.state, State.HEALTHY)
            self.assertEqual([c.window.targets.item(row, 0).text() for row in range(len(names))], names)
            self.assertNotIn("Google:", c.window.history.toPlainText())
        saved = load(Path(self.temp.name) / "config/settings.json")
        self.assertEqual(saved.selected_targets, ["GitHub", "ChatGPT", "YouTube"])
        log = (Path(self.temp.name) / "logs/network.log").read_text(encoding="utf-8")
        self.assertIn("TARGET=Google", log)
        self.assertIn("SETTINGS_CHANGED", log)

    def test_target_order_only_does_not_reset_state_or_rtt(self):
        c = self.controller
        c.consume(successful(c.settings.selected_targets))
        c.consume(successful(c.settings.selected_targets))
        count = c.machine.count
        c.apply_settings(replace(c.settings, interval_s=8, selected_targets=list(reversed(c.settings.selected_targets))))
        self.assertEqual((c.machine.state, c.machine.count), (State.HEALTHY, count))
        self.assertEqual(c.monitor.revision, 0)
        self.assertEqual(c.window.targets.item(0, 2).text(), "90")

    def test_partial_failure_and_restricted_response_are_visible(self):
        c = self.controller
        names = c.settings.selected_targets
        result = successful(names)
        result.probes[2] = Probe(names[2], False, 3000, error="REQUEST_TIMEOUT")
        c.consume(result)
        c.consume(result)
        self.assertEqual(c.machine.state, State.HEALTHY)
        self.assertIn("33.3%", c.window.metrics.text())
        self.assertIn("异常目标", c.window.detail.text())
        c.apply_settings(replace(c.settings, selected_targets=["ChatGPT"]))
        result = Round(probes=[Probe("ChatGPT", True, 90, 403, reachable=True, note="服务限制")])
        c.consume(result)
        self.assertEqual(c.window.targets.item(0, 1).text(), "网络可达（HTTP 403）")

    def test_pause_and_busy_manual_check_do_not_restart_worker(self):
        c = self.controller
        with patch.object(c.monitor, "request_check", return_value=False) as check:
            c.test_now()
            check.assert_called_once()
            self.assertIn("正在检测", c.window.detail.text())
        self.mock_start.reset_mock()
        c.toggle_pause()
        c.apply_settings(replace(c.settings, interval_s=8, selected_targets=["YouTube"]))
        self.mock_start.assert_not_called()
        c.test_now()
        self.assertFalse(c.paused)
        self.assertEqual(c.monitor.settings.interval_s, 8)
        self.mock_start.assert_called_once()
