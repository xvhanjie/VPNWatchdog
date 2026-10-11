"""Pure Python hysteresis. A probe is evidence; an outage is a confirmed event."""
from dataclasses import dataclass
import time

from core.models import State


DOWN = (State.VPN_DOWN, State.NO_INTERNET)


@dataclass
class Update:
    state: State
    observed: State
    changed: bool
    event: str = ""
    consecutive: int = 0
    downtime_s: float | None = None


class StateManager:
    def __init__(self, settings, clock=time.monotonic):
        self.settings = settings
        self.clock = clock
        self.state = State.UNKNOWN
        self.candidate = None
        self.count = 0
        self.outage_start = None
        self.first_failure = None
        self.failures = 0
        self.last_sample = None

    def reset_evidence(self):
        self.candidate = None
        self.count = 0
        self.failures = 0
        self.first_failure = None
        self.last_sample = None

    def reset_targets(self):
        self.reset_evidence()
        self.state = State.UNKNOWN
        # A different probe scope cannot recover an incident of the previous scope.
        self.outage_start = None

    @staticmethod
    def quorum(result):
        return len(result.probes) // 2 + 1

    def classify(self, result):
        if result.monitor_error or not result.probes:
            return State.UNKNOWN
        if result.local_online is False:
            return State.NO_INTERNET
        if result.successes >= self.quorum(result):
            if result.latency_ms is not None and result.latency_ms >= self.settings.high_ms:
                return State.HIGH_LATENCY
            return State.HEALTHY
        if any(probe.reachable or probe.success for probe in result.probes):
            return State.UNSTABLE
        return State.VPN_DOWN

    def consume(self, result):
        now = self.clock()
        # A long unobserved gap (sleep/resume or a stalled worker) is no evidence.
        if self.last_sample is not None and now - self.last_sample > max(30, self.settings.interval_s * 3):
            self.reset_evidence()
        self.last_sample = now
        observed = self.classify(result)
        before = self.state
        if observed == State.UNKNOWN:
            self.reset_evidence()
            self.state = State.UNKNOWN
            return Update(self.state, observed, before != self.state)
        if observed in DOWN:
            if self.first_failure is None:
                self.first_failure = now
            self.failures += 1
        else:
            self.failures = 0
            self.first_failure = None

        # A confirmed outage remains open until quorum succeeds twice, even across
        # NO_INTERNET/VPN_DOWN category changes or worker errors.
        if self.outage_start is not None:
            recovering = result.successes >= self.quorum(result) and observed not in DOWN
            if recovering:
                self.track("RECOVERY")
                if self.count >= self.settings.recovery_count:
                    duration = max(0, now - self.outage_start)
                    self.outage_start = None
                    self.state = State.RECOVERED
                    self.candidate = None
                    confirmed_count = self.count
                    self.count = 0
                    return Update(self.state, observed, True, "RECOVERED", confirmed_count, downtime_s=duration)
            else:
                self.candidate = None
                self.count = 0
                if observed in DOWN and self.failures >= self.settings.failure_count:
                    self.state = observed
            return Update(self.state, observed, before != self.state, consecutive=self.count if recovering else self.failures)

        if observed in DOWN:
            self.track(observed)
            # Mixed local/VPN failures are still consecutive unavailable rounds.
            if self.failures >= self.settings.failure_count:
                self.outage_start = self.first_failure
                self.state = observed
                return Update(self.state, observed, before != self.state, "DOWN", self.failures)
        else:
            self.track(observed)
            threshold = self.settings.recovery_count if observed == State.HEALTHY else self.settings.failure_count
            if self.state == State.RECOVERED or self.count >= threshold:
                self.state = observed
                event = "QUALITY" if before != self.state and observed in (State.HIGH_LATENCY, State.UNSTABLE) else ""
                return Update(self.state, observed, before != self.state, event, self.count)
        return Update(self.state, observed, before != self.state, consecutive=self.failures if observed in DOWN else self.count)

    def track(self, candidate):
        if candidate == self.candidate:
            self.count += 1
        else:
            self.candidate = candidate
            self.count = 1
