from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from statistics import median


class State(StrEnum):
    UNKNOWN = "UNKNOWN"
    HEALTHY = "HEALTHY"
    HIGH_LATENCY = "HIGH_LATENCY"
    UNSTABLE = "UNSTABLE"
    VPN_DOWN = "VPN_DOWN"
    NO_INTERNET = "NO_INTERNET"
    RECOVERED = "RECOVERED"


def latency_label(value, settings):
    if value is None:
        return "—"
    if value < settings.good_ms:
        return "GOOD"
    if value < settings.high_ms:
        return "NORMAL"
    if value < settings.very_high_ms:
        return "HIGH_LATENCY"
    return "VERY_HIGH_LATENCY"


@dataclass
class Probe:
    target: str
    success: bool
    latency_ms: float | None = None
    http_status: int | None = None
    error: str = ""
    # A validated HTTP response proves reachability even if access is restricted.
    reachable: bool = False
    note: str = ""


@dataclass
class Round:
    timestamp: str = field(default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds"))
    probes: list[Probe] = field(default_factory=list)
    local_online: bool | None = None
    monitor_error: str = ""
    revision: int = 0

    @property
    def successes(self):
        return sum(p.success for p in self.probes)

    @property
    def latency_ms(self):
        values = [p.latency_ms for p in self.probes if p.success and p.latency_ms is not None]
        return round(median(values), 1) if values else None

    @property
    def failure_rate(self):
        return 100 * (1 - self.successes / len(self.probes)) if self.probes else None

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(timestamp=data["timestamp"], probes=[Probe(**p) for p in data["probes"]],
                   local_online=data.get("local_online"), monitor_error=data.get("monitor_error", ""),
                   revision=data.get("revision", 0))
