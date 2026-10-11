import unittest
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QTimer

from core.probe_worker import ProbeWorker
from utils.config import Settings
from dataclasses import asdict


class SchedulerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def test_interval_reuses_one_scheduler(self):
        with patch("core.probe_worker.QTimer.singleShot"):
            worker = ProbeWorker(Settings(), lambda result: None)
        scheduler = worker.timer
        for value in (3, 5, 8, 15, 30, 5, 10, 3, 20, 8):
            worker.handle_command({"action": "configure", "settings": asdict(Settings(interval_s=value))})
            self.assertIs(worker.timer, scheduler)
            self.assertEqual(worker.timer.interval(), value * 1000)
            self.assertEqual(worker.findChildren(QTimer), [scheduler])
        worker.timer.stop()
        worker.deleteLater()

    def test_inflight_check_skips_both_manual_and_timer(self):
        with patch("core.probe_worker.QTimer.singleShot"):
            worker = ProbeWorker(Settings(), lambda result: None)
        worker.active = True
        with patch("core.probe_worker.local_online") as local:
            worker.run_round()
            worker.handle_command({"action": "check"})
            local.assert_not_called()
        self.assertIsNone(worker.manager)
        worker.timer.stop()
        worker.deleteLater()
