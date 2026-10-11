import unittest

from core.models import Probe, Round, State
from core.state_manager import StateManager
from utils.config import Settings


def sample(successes=3, latency=90, reachable=False, local=True, error="", total=3):
    return Round(probes=[Probe(str(i), i < successes, latency, 200 if i < successes else None,
                               "" if i < successes else "REQUEST_TIMEOUT", i < successes or reachable)
                         for i in range(total)], local_online=local, monitor_error=error)


class StateTests(unittest.TestCase):
    def setUp(self):
        self.time = 100.
        self.machine = StateManager(Settings(), lambda: self.time)

    def feed(self, result, count=1):
        updates = []
        for _ in range(count):
            self.time += 5
            updates.append(self.machine.consume(result))
        return updates

    def test_single_timeout_does_not_drop(self):
        self.feed(sample(), 2)
        self.assertEqual(self.feed(sample(0))[0].state, State.HEALTHY)
        self.feed(sample(), 2)
        self.assertIsNone(self.machine.outage_start)

    def test_outage_dedup_and_recovery_duration(self):
        self.feed(sample(), 2)
        updates = self.feed(sample(0), 10)
        self.assertEqual([u.event for u in updates].count("DOWN"), 1)
        self.assertEqual(updates[2].consecutive, 3)
        self.assertEqual(self.feed(sample())[0].state, State.VPN_DOWN)
        recovered = self.feed(sample())[0]
        self.assertEqual(recovered.event, "RECOVERED")
        self.assertEqual(recovered.downtime_s, 55)
        self.assertEqual(self.feed(sample())[0].state, State.HEALTHY)
        self.assertEqual(self.feed(sample(0), 3)[-1].event, "DOWN")

    def test_restricted_http_is_not_vpn_down(self):
        update = self.feed(sample(0, reachable=True), 5)[-1]
        self.assertEqual(update.state, State.UNSTABLE)
        self.assertIsNone(self.machine.outage_start)

    def test_partial_does_not_close_outage(self):
        self.feed(sample(0), 3)
        self.feed(sample(1), 4)
        self.assertIsNotNone(self.machine.outage_start)
        self.assertEqual(self.feed(sample(2), 2)[-1].event, "RECOVERED")

    def test_quality_hysteresis(self):
        self.feed(sample(), 2)
        self.assertEqual(self.feed(sample(latency=700), 2)[-1].state, State.HEALTHY)
        self.assertEqual(self.feed(sample(latency=700))[0].state, State.HIGH_LATENCY)
        self.assertEqual(self.feed(sample())[0].state, State.HIGH_LATENCY)
        self.assertEqual(self.feed(sample())[0].state, State.HEALTHY)

    def test_local_down_and_switch_dedup(self):
        self.assertEqual(self.feed(sample(0, local=False), 3)[-1].state, State.NO_INTERNET)
        self.assertEqual(self.feed(sample(0), 3)[-1].state, State.VPN_DOWN)
        self.assertEqual(self.feed(sample(), 2)[-1].event, "RECOVERED")

    def test_sleep_resets_evidence(self):
        self.feed(sample(0), 2)
        self.time += 100
        self.assertNotEqual(self.feed(sample(0))[0].state, State.VPN_DOWN)

    def test_monitor_error_not_an_outage(self):
        self.feed(sample(0), 2)
        self.assertEqual(self.feed(sample(error="worker stalled"))[0].state, State.UNKNOWN)
        self.assertIsNone(self.machine.outage_start)

    def test_worker_error_preserves_open_incident(self):
        self.feed(sample(0), 3)
        self.feed(sample(error="worker stalled"))
        self.assertEqual(self.feed(sample(), 2)[-1].event, "RECOVERED")

    def test_alternating_failures_never_confirm(self):
        for _ in range(30):
            self.feed(sample(0))
            self.feed(sample())
        self.assertIsNone(self.machine.outage_start)

    def test_quorums_for_one_two_three_targets(self):
        for total, success_count, expected in ((1, 1, State.HEALTHY), (1, 0, State.VPN_DOWN),
                                               (2, 2, State.HEALTHY), (2, 1, State.UNSTABLE), (2, 0, State.VPN_DOWN),
                                               (3, 3, State.HEALTHY), (3, 2, State.HEALTHY), (3, 1, State.UNSTABLE), (3, 0, State.VPN_DOWN)):
            with self.subTest(total=total, successes=success_count):
                result = sample(success_count, total=total)
                self.assertEqual(self.machine.classify(result), expected)

    def test_down_and_recovery_for_each_target_count(self):
        for total in (1, 2, 3):
            with self.subTest(total=total):
                self.machine = StateManager(Settings(), lambda: self.time)
                down = self.feed(sample(0, total=total), 3)
                self.assertEqual([u.event for u in down], ["", "", "DOWN"])
                quorum = total // 2 + 1
                up = self.feed(sample(quorum, total=total), 2)
                self.assertEqual([u.event for u in up], ["", "RECOVERED"])
                self.assertEqual(up[0].consecutive, 1)
                self.assertEqual(up[1].consecutive, 2)

    def test_reset_targets_cannot_inherit_old_incident(self):
        self.feed(sample(0), 3)
        self.machine.reset_targets()
        self.assertEqual(self.machine.state, State.UNKNOWN)
        self.assertIsNone(self.machine.outage_start)
        self.assertEqual(self.machine.failures, 0)
        self.assertEqual(self.feed(sample(1, total=1), 2)[-1].state, State.HEALTHY)
        self.assertEqual(self.feed(sample(1, total=1))[0].event, "")

    def test_success_only_metrics_use_dynamic_denominator(self):
        result = Round(probes=[Probe("Google", True, 180), Probe("GitHub", True, 220),
                               Probe("ChatGPT", False, 3000, error="REQUEST_TIMEOUT")])
        self.assertEqual(result.latency_ms, 200)
        self.assertAlmostEqual(result.failure_rate, 100 / 3)
        self.assertEqual(sample(1, total=2).failure_rate, 50)


if __name__ == "__main__":
    unittest.main()
