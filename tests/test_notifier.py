import unittest

from core.models import State
from core.state_manager import StateManager
from tests.test_state_manager import sample
from utils.config import Settings
from utils.notifier import Notifier


class FakeTray:
    def __init__(self):
        self.messages = []

    def isSystemTrayAvailable(self):
        return True

    def supportsMessages(self):
        return True

    def showMessage(self, *args):
        self.messages.append(args)


class FakeLogger:
    def warning(self, *args):
        pass


class NotificationTests(unittest.TestCase):
    def test_down_recovered_only_once(self):
        settings = Settings(sound=False)
        tray = FakeTray()
        notifier = Notifier(tray, settings, FakeLogger())
        state = StateManager(settings)
        for result in [sample(0)] * 12 + [sample()] * 10:
            notifier.handle(result, state.consume(result))
        self.assertEqual(len(tray.messages), 2)

    def test_quality_cooldown(self):
        settings = Settings(sound=False)
        tray = FakeTray()
        notifier = Notifier(tray, settings, FakeLogger(), clock=lambda: 100)
        state = StateManager(settings)
        for result in [sample(latency=800)] * 3 + [sample()] * 2 + [sample(latency=800)] * 3:
            notifier.handle(result, state.consume(result))
        self.assertEqual(len(tray.messages), 1)

    def test_notifications_disabled(self):
        settings = Settings(notifications=False, sound=False)
        tray = FakeTray()
        state = StateManager(settings)
        notifier = Notifier(tray, settings, FakeLogger())
        for _ in range(3):
            notifier.handle(sample(0), state.consume(sample(0)))
        self.assertFalse(tray.messages)

    def test_monitor_errors_have_separate_cooldown(self):
        settings = Settings(sound=False)
        tray = FakeTray()
        state = StateManager(settings)
        notifier = Notifier(tray, settings, FakeLogger(), clock=lambda: 100)
        for _ in range(20):
            result = sample(error="MONITOR_TIMEOUT")
            notifier.handle(result, state.consume(result))
        self.assertEqual(len(tray.messages), 1)
        self.assertIn("未证明 VPN", tray.messages[0][1])
