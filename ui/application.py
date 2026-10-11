import ctypes
import sys
import time
from dataclasses import replace

from PySide6.QtCore import QLockFile, QObject, QTimer
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QSystemTrayIcon

from core.models import State, latency_label
from core.network_monitor import NetworkMonitor
from core.state_manager import StateManager
from ui.main_window import Dashboard
from ui.settings_window import SettingsDialog
from ui.tray import Tray
from utils.config import save
from utils.logger import log_round, make_logger
from utils.notifier import Notifier


class Controller(QObject):
    def __init__(self, app, settings, directory):
        super().__init__()
        self.app = app
        self.settings = settings
        self.directory = directory
        self.logger = make_logger(directory / "logs")
        for repair in getattr(settings, "_repairs", []):
            self.logger.warning("CONFIG_REPAIRED %s", repair)
        self.machine = StateManager(settings)
        self.monitor = NetworkMonitor(settings, self)
        self.window = Dashboard()
        self.window.configure_targets(settings.selected_targets)
        self.tray = Tray(self)
        self.notifier = Notifier(self.tray, settings, self.logger)
        self.paused = False
        self.work_mode = False
        self.outages = 0
        self.timeouts = 0
        self.downtime = 0.
        self.active_seconds = 0.
        self.last_tick = time.monotonic()
        self.last_check = "—"
        self.tray.update_config(settings, False)
        self.window.test.clicked.connect(self.test_now)
        self.window.pause.clicked.connect(self.toggle_pause)
        self.window.settings.clicked.connect(self.show_settings)
        self.window.work.toggled.connect(self.set_work_mode)
        self.window.exit_button.clicked.connect(self.quit)
        self.monitor.sample.connect(self.consume)
        self.monitor.checking_changed.connect(self.checking_changed)
        self.monitor.diagnostic.connect(lambda text: self.logger.warning("WORKER %s", text))
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.tick)
        self.clock_timer.start(1000)
        self.app.aboutToQuit.connect(self.shutdown)
        self.monitor.start()

    def consume(self, result):
        if self.paused:
            return
        update = self.machine.consume(result)
        log_round(self.logger, result, update)
        if update.event == "DOWN":
            self.outages += 1
        elif update.event == "RECOVERED":
            self.downtime += update.downtime_s or 0
        self.timeouts += sum("TIMEOUT" in probe.error for probe in result.probes)
        self.last_check = result.timestamp[11:19]
        self.window.display(result, update, self.outages, self.timeouts, self.downtime)
        if not result.monitor_error:
            grade = latency_label(result.latency_ms, self.settings)
            self.window.detail.setText(self.window.detail.text() + f" · {grade}")
        self.tray.update_status(result, update)
        self.notifier.handle(result, update)
        self.tick()

    def tick(self):
        now = time.monotonic()
        delta = now - self.last_tick
        # Do not count a suspend gap as time actively monitored.
        if not self.paused and delta < 10:
            self.active_seconds += delta
        self.last_tick = now
        seconds = int(self.active_seconds)
        duration = f"{seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}"
        mode = "（工作模式）" if self.work_mode else ""
        self.window.timing.setText(f"最近检查：{self.last_check}    检测周期：{self.monitor.settings.interval_s} 秒{mode}    有效监测时长：{duration}")

    def show(self):
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def toggle_pause(self):
        self.paused = not self.paused
        self.machine.reset_evidence()
        text = "恢复监测" if self.paused else "暂停监测"
        self.window.pause.setText(text)
        self.tray.pause.setText("Resume Monitoring" if self.paused else "Pause Monitoring")
        if self.paused:
            self.monitor.stop()
            self.machine.state = State.UNKNOWN
            self.window.status.setText("PAUSED")
            self.tray.status.setText("Status: PAUSED")
            from ui.tray import status_icon
            self.tray.setIcon(status_icon())
            self.tray.setToolTip("VPN Watchdog — PAUSED")
            self.window.detail.setText("已暂停；连续判定证据已清除。已确认的中断事件将在恢复检测后继续处理。")
            self.logger.info("MONITORING_PAUSED")
        else:
            self.monitor.start()
            self.window.status.setText("UNKNOWN")
            self.logger.info("MONITORING_RESUMED")

    def test_now(self):
        if self.paused:
            self.toggle_pause()
            return
        if not self.monitor.request_check():
            self.window.detail.setText("正在检测中……本次点击不会创建额外的检测任务。")

    def checking_changed(self, checking):
        self.window.test.setEnabled(not checking)
        self.window.test.setText("正在检测中…" if checking else "立即检测")

    def set_work_mode(self, enabled):
        previous = self.work_mode
        self.work_mode = enabled
        for control in (self.window.work, self.tray.work):
            control.blockSignals(True)
            control.setChecked(enabled)
            control.blockSignals(False)
        effective = replace(self.settings, interval_s=3) if enabled else self.settings
        self.machine.settings = effective
        self.monitor.configure(effective)
        self.tray.update_config(effective, enabled)
        self.tick()
        if previous != enabled:
            self.logger.info("WORK_MODE_%s interval=%s", "ON" if enabled else "OFF", effective.interval_s)

    def show_settings(self):
        dialog = SettingsDialog(self.settings, self.window)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.apply_settings(dialog.result_settings)
        except OSError as error:
            QMessageBox.warning(self.window, "保存失败", str(error))
            return

    def apply_settings(self, updated, persist=True):
        updated.validate()
        if persist:
            save(self.directory / "config" / "settings.json", updated)
        targets_changed = set(updated.selected_targets) != set(self.settings.selected_targets)
        if targets_changed:
            duration = (time.monotonic() - self.machine.outage_start) if self.machine.outage_start is not None else None
            self.logger.info("MONITORING_SCOPE_CHANGED previous_targets=%s open_incident_elapsed_s=%s",
                             ",".join(self.settings.selected_targets), duration)
            self.machine.reset_targets()
            self.last_check = "—"
            self.window.configure_targets(updated.selected_targets, clear=True)
            self.tray.reset_status()
        elif updated.selected_targets != self.settings.selected_targets:
            self.window.configure_targets(updated.selected_targets)
        self.settings = updated
        self.notifier.settings = updated
        self.set_work_mode(self.work_mode)
        self.logger.info("SETTINGS_CHANGED interval=%s targets=%s", updated.interval_s, ",".join(updated.selected_targets))

    def test_notification(self):
        self.tray.showMessage("VPN Watchdog — 通知测试", "这是一条测试通知，监测状态没有改变。",
                              QSystemTrayIcon.MessageIcon.Information, 10000)

    def shutdown(self):
        self.clock_timer.stop()
        self.monitor.stop(wait=True)
        self.tray.hide()
        self.logger.info("APPLICATION_EXIT")
        for handler in self.logger.handlers:
            handler.flush()

    def quit(self):
        self.window.allow_close = True
        self.app.quit()


def run(settings, directory, show_dashboard=False):
    if sys.platform == "win32":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("VPNWatchdog.NetworkGuardian")
    app = QApplication(sys.argv[:1])
    app.setApplicationName("VPN Watchdog")
    app.setOrganizationName("NetworkGuardian")
    app.setQuitOnLastWindowClosed(False)
    directory.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(directory / "vpnwatchdog.lock"))
    if not lock.tryLock(100):
        QMessageBox.information(None, "VPN Watchdog", "此数据目录已有一个 VPN Watchdog 实例运行。请双击系统托盘图标打开。")
        return 0
    config_path = directory / "config" / "settings.json"
    if not config_path.exists():
        save(config_path, settings)
    controller = Controller(app, settings, directory)
    if not QSystemTrayIcon.isSystemTrayAvailable():
        controller.window.can_hide = False
        app.setQuitOnLastWindowClosed(True)
        controller.show()
    elif show_dashboard:
        controller.show()
    try:
        return app.exec()
    finally:
        lock.unlock()
