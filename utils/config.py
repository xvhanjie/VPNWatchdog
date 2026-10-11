import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import NamedTuple


class Target(NamedTuple):
    name: str
    url: str
    expected_status: tuple[int, ...]
    request_method: str
    response_policy: str = "expected"


TARGETS = (
    Target("Google", "https://www.google.com/generate_204", (204,), "HEAD"),
    Target("GitHub", "https://github.com/", (200,), "HEAD"),
    Target("Cloudflare", "https://www.cloudflare.com/cdn-cgi/trace", (200,), "GET"),
    Target("ChatGPT", "https://chatgpt.com/", (200,), "HEAD", "reachable"),
    Target("YouTube", "https://www.youtube.com/", (200,), "HEAD", "reachable"),
)
TARGET_BY_NAME = {target.name: target for target in TARGETS}
DEFAULT_TARGET_NAMES = ("Google", "GitHub", "Cloudflare")


@dataclass
class Settings:
    interval_s: int = 5
    timeout_s: int = 3
    failure_count: int = 3
    recovery_count: int = 2
    good_ms: int = 150
    high_ms: int = 300
    very_high_ms: int = 500
    notification_cooldown_s: int = 600
    notifications: bool = True
    sound: bool = True
    selected_targets: list[str] = field(default_factory=lambda: list(DEFAULT_TARGET_NAMES))

    def validate(self):
        if type(self.interval_s) is not int or not 3 <= self.interval_s <= 30:
            raise ValueError("检测周期必须是 3～30 之间的整数秒")
        if (not isinstance(self.selected_targets, list) or not 1 <= len(self.selected_targets) <= 3
                or any(not isinstance(name, str) or name not in TARGET_BY_NAME for name in self.selected_targets)
                or len(set(self.selected_targets)) != len(self.selected_targets)):
            raise ValueError("请选择 1～3 个不同的合法监测目标")
        for name, low, high in (("timeout_s", 1, 10), ("failure_count", 2, 10),
                                ("recovery_count", 2, 10), ("notification_cooldown_s", 60, 86400)):
            value = getattr(self, name)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"{name} 必须在 {low}–{high} 之间")
        if not all(type(v) is int for v in (self.good_ms, self.high_ms, self.very_high_ms)):
            raise ValueError("延迟阈值必须为整数")
        if not 0 < self.good_ms < self.high_ms < self.very_high_ms <= 60000:
            raise ValueError("延迟阈值必须满足 0 < GOOD < HIGH < VERY HIGH ≤ 60000")
        if type(self.notifications) is not bool or type(self.sound) is not bool:
            raise ValueError("通知和声音必须为布尔值")
        return self

    @property
    def check_interval(self):
        return self.interval_s

    @property
    def active_targets(self):
        return tuple(TARGET_BY_NAME[name] for name in self.selected_targets)


def as_config(settings):
    data = asdict(settings)
    data["check_interval"] = data.pop("interval_s")
    return data


def from_config(data):
    """Normalize hand-edited / legacy JSON; strict GUI validation stays separate."""
    repairs = []
    if not isinstance(data, dict):
        data = {}
        repairs.append("配置不是对象，恢复默认")
    defaults = asdict(Settings())
    values = {key: data.get(key, value) for key, value in defaults.items()}
    interval = data.get("check_interval", data.get("interval_s", 5))
    values["interval_s"] = min(30, max(3, interval)) if type(interval) is int else 5
    if values["interval_s"] != interval or type(interval) is not int:
        repairs.append("检测周期已限制到 3～30 秒")
    raw_targets = values["selected_targets"]
    selected = []
    if isinstance(raw_targets, list):
        for name in raw_targets:
            if isinstance(name, str) and name in TARGET_BY_NAME and name not in selected:
                selected.append(name)
    values["selected_targets"] = selected[:3] or list(DEFAULT_TARGET_NAMES)
    if values["selected_targets"] != raw_targets:
        repairs.append("监测目标已去重、筛选并限制为 1～3 个")
    for name, low, high in (("timeout_s", 1, 10), ("failure_count", 2, 10),
                            ("recovery_count", 2, 10), ("notification_cooldown_s", 60, 86400)):
        value = values[name]
        if type(value) is not int or not low <= value <= high:
            values[name] = defaults[name]
            repairs.append(f"{name} 恢复默认")
    thresholds = [values[key] for key in ("good_ms", "high_ms", "very_high_ms")]
    if not all(type(value) is int for value in thresholds) or not 0 < thresholds[0] < thresholds[1] < thresholds[2] <= 60000:
        for key in ("good_ms", "high_ms", "very_high_ms"):
            values[key] = defaults[key]
        repairs.append("延迟阈值恢复默认")
    for key in ("notifications", "sound"):
        if type(values[key]) is not bool:
            values[key] = defaults[key]
            repairs.append(f"{key} 恢复默认")
    unknown = set(data) - set(defaults) - {"check_interval"}
    if unknown:
        repairs.append("忽略未知配置项: " + ", ".join(sorted(unknown)))
    settings = Settings(**values).validate()
    settings._repairs = repairs
    return settings


def data_dir():
    return Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "VPNWatchdog"


def load(path):
    path = Path(path)
    if not path.exists():
        return Settings()
    raw = path.read_bytes()
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (ValueError, UnicodeError):
        data = {}
    settings = from_config(data)
    if data != as_config(settings):
        settings._repairs.append("配置已迁移/规范化，原文件备份为 settings.json.bak")
        try:
            backup = path.with_suffix(path.suffix + ".bak")
            backup.write_bytes(raw)
            save(path, settings)
        except OSError as error:
            settings._repairs.append(f"配置修复仅在内存生效，无法保存: {error}")
    return settings


def save(path, settings):
    settings.validate()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(as_config(settings), ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
