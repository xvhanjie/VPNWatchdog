"""Render our own UI with synthetic data, without changing the desktop/VPN."""
import os
from dataclasses import replace
from pathlib import Path
import sys
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QFontDatabase
from tests.test_state_manager import sample
from ui.application import Controller
from ui.settings_window import SettingsDialog
from core.models import Probe, Round
from utils.config import Settings, TARGETS


app = QApplication([])
font_path = Path("C:/Windows/Fonts/msyh.ttc")
if font_path.exists():
    QFontDatabase.addApplicationFont(str(font_path))
    app.setFont(QFont("Microsoft YaHei", 10))
app.setQuitOnLastWindowClosed(False)
with patch("ui.application.NetworkMonitor.start"):
    controller = Controller(app, Settings(notifications=False, sound=False), root / ".runtime-gui")
    for result in [sample()] * 2 + [sample(0)] * 3 + [sample()] * 2 + [sample(latency=680)] * 3:
        for probe, target in zip(result.probes, TARGETS):
            probe.target = target[0]
        controller.consume(result)
    assert controller.outages == 1
    assert controller.window.status.text() == "HIGH_LATENCY"
    controller.toggle_pause()
    assert controller.window.status.text() == "PAUSED"
    controller.toggle_pause()
    for _ in range(3):
        result = sample(latency=680)
        for probe, target in zip(result.probes, TARGETS):
            probe.target = target[0]
        controller.consume(result)
    controller.set_work_mode(True)
    assert controller.monitor.settings.interval_s == 3
    controller.set_work_mode(False)
    assert controller.monitor.settings.interval_s == 5
    controller.window.detail.setText("界面测试 · 以下为模拟探测数据，非当前网络测量")
    controller.show()
    app.processEvents()
    output = root / "docs" / "dashboard-preview.png"
    assert controller.window.grab().save(str(output))
    selected = replace(controller.settings, interval_s=8, selected_targets=["ChatGPT", "YouTube"])
    controller.apply_settings(selected, persist=False)
    for _ in range(2):
        controller.consume(Round(probes=[Probe("ChatGPT", True, 210, 403, reachable=True,
                                              note="HTTP 403：网络可达；服务可能限制访问"),
                                         Probe("YouTube", True, 185, 200, reachable=True)]))
    assert controller.window.targets.rowCount() == 2
    assert controller.window.status.text() == "HEALTHY"
    controller.window.detail.setText(controller.window.detail.text() + " · 模拟数据，非当前网络测量")
    app.processEvents()
    assert controller.window.grab().save(str(root / "docs" / "dashboard-selected-preview.png"))
    dialog = SettingsDialog(selected)
    dialog.setWindowTitle("VPN Watchdog 设置 · 预览示例")
    dialog.show()
    app.processEvents()
    assert dialog.grab().save(str(root / "docs" / "settings-preview.png"))
    dialog.close()
    controller.shutdown()
    controller.window.allow_close = True
    controller.window.close()
print(f"GUI smoke OK; preview={output}")
