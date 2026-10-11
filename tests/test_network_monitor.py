from dataclasses import asdict
import json
import unittest
from unittest.mock import patch

from PySide6.QtCore import QByteArray, QCoreApplication

from core.models import Probe, Round
from core.network_monitor import NetworkMonitor
from utils.config import Settings


class MonitorControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.monitor = NetworkMonitor(Settings())

    def tearDown(self):
        self.monitor.stop()
        self.monitor.deleteLater()

    def emit_data(self, data):
        with patch.object(self.monitor.process, "readAllStandardOutput", return_value=QByteArray((json.dumps(data) + "\n").encode())):
            self.monitor.read_output()

    def test_repeated_manual_click_only_sends_one_command(self):
        self.monitor.wanted = self.monitor.ready = True
        with patch.object(self.monitor.process, "write", return_value=1) as write:
            self.assertTrue(self.monitor.request_check())
            for _ in range(20):
                self.assertFalse(self.monitor.request_check())
            self.assertEqual(write.call_count, 1)
            self.emit_data({"event": "checking", "active": False})
            self.assertTrue(self.monitor.request_check())
            self.assertEqual(write.call_count, 2)

    def test_stale_target_round_is_discarded(self):
        self.monitor.wanted = True
        received = []
        self.monitor.sample.connect(received.append)
        self.monitor.configure(Settings(selected_targets=["ChatGPT", "YouTube"]))
        self.emit_data(Round(probes=[Probe("Google", True, 90)], revision=0).to_dict())
        self.assertEqual(received, [])
        self.emit_data(Round(probes=[Probe("ChatGPT", True, 90), Probe("YouTube", True, 100)], revision=1).to_dict())
        self.assertEqual(len(received), 1)

    def test_interval_changes_keep_revision_and_use_existing_process(self):
        self.monitor.wanted = self.monitor.ready = True
        process = self.monitor.process
        with patch.object(process, "write", return_value=1) as write:
            for interval in (5, 10, 3, 20, 8):
                self.monitor.configure(Settings(interval_s=interval))
                self.assertEqual(self.monitor.revision, 0)
                self.assertIs(self.monitor.process, process)
            self.assertEqual(write.call_count, 5)

    def test_pre_ready_change_is_delivered_when_worker_ready(self):
        self.monitor.wanted = True
        latest = Settings(interval_s=8, selected_targets=["YouTube"])
        with patch.object(self.monitor.process, "write", return_value=1) as write:
            self.monitor.configure(latest)
            self.assertEqual(write.call_count, 0)
            self.emit_data({"event": "ready"})
            sent = json.loads(bytes(write.call_args.args[0]))
            self.assertEqual(sent["settings"], asdict(latest))
            self.assertEqual(sent["revision"], 1)
