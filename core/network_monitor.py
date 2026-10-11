"""Supervise a persistent isolated probe process; GUI and CLI use the same API."""
import json
import sys
from dataclasses import asdict
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

from core.models import Round


class NetworkMonitor(QObject):
    sample = Signal(object)
    diagnostic = Signal(str)
    checking_changed = Signal(bool)
    configured = Signal(object)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.wanted = False
        self.expected_exit = False
        self.buffer = bytearray()
        self.is_checking = False
        self.ready = False
        self.revision = 0
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.readyReadStandardError.connect(self.read_error)
        self.process.finished.connect(self.exited)
        self.process.errorOccurred.connect(self.process_error)
        self.watchdog = QTimer(self)
        self.watchdog.setSingleShot(True)
        self.watchdog.timeout.connect(self.stalled)

    def start(self):
        self.wanted = True
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.expected_exit = True
            self.process.kill()
        else:
            self.launch()

    def launch(self):
        if not self.wanted or self.process.state() != QProcess.ProcessState.NotRunning:
            return
        self.expected_exit = False
        self.buffer.clear()
        self.ready = False
        self.set_checking(True)
        args = ["--worker", "--settings-json", json.dumps(asdict(self.settings)), "--revision", str(self.revision)]
        if not getattr(sys, "frozen", False):
            args.insert(0, str(Path(__file__).resolve().parents[1] / "main.py"))
        self.process.start(sys.executable, args)
        self.arm_watchdog(startup=True)

    def set_checking(self, value):
        if self.is_checking != value:
            self.is_checking = value
            self.checking_changed.emit(value)

    def send(self, command):
        self.process.write((json.dumps(command) + "\n").encode("utf-8"))

    def configure(self, settings):
        settings.validate()
        if set(settings.selected_targets) != set(self.settings.selected_targets):
            self.revision += 1
        self.settings = settings
        if self.ready and self.wanted and not self.expected_exit:
            self.send({"action": "configure", "settings": asdict(settings), "revision": self.revision})
            self.arm_watchdog()

    def request_check(self):
        if not self.wanted or not self.ready or self.is_checking or self.expected_exit:
            return False
        self.set_checking(True)
        self.send({"action": "check"})
        return True

    def arm_watchdog(self, startup=False):
        # Includes startup and potentially slow Windows proxy/PAC discovery.
        seconds = self.settings.interval_s + self.settings.timeout_s + (15 if startup else 8)
        self.watchdog.start(seconds * 1000)

    def stop(self, wait=False):
        self.wanted = False
        self.watchdog.stop()
        self.expected_exit = True
        self.ready = False
        self.set_checking(False)
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
            if wait:
                self.process.waitForFinished(2000)

    def read_output(self):
        self.buffer.extend(bytes(self.process.readAllStandardOutput()))
        if len(self.buffer) > 65536:
            self.fail("探测进程输出超过限制")
            return
        while b"\n" in self.buffer:
            line, _, remainder = self.buffer.partition(b"\n")
            self.buffer = bytearray(remainder)
            try:
                data = json.loads(line)
                if data.get("event"):
                    if self.wanted and not self.expected_exit:
                        if data["event"] == "ready":
                            self.ready = True
                            self.configure(self.settings)
                        elif data["event"] == "checking":
                            self.set_checking(bool(data["active"]))
                        elif data["event"] == "configured":
                            self.configured.emit(data)
                    continue
                result = Round.from_dict(data)
            except (ValueError, TypeError, KeyError):
                self.fail("探测进程返回无效数据")
                return
            if self.wanted and not self.expected_exit and result.revision == self.revision:
                self.arm_watchdog()
                self.sample.emit(result)

    def read_error(self):
        message = bytes(self.process.readAllStandardError()).decode("utf-8", errors="replace").strip()
        if message:
            self.diagnostic.emit(message[:2000])

    def fail(self, message):
        if self.wanted:
            self.sample.emit(Round(monitor_error=message))
            self.expected_exit = False
            self.process.kill()

    def stalled(self):
        self.fail("MONITOR_TIMEOUT：系统代理/PAC 解析或探测进程未响应；不能据此认定 VPN 掉线")

    def process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart and self.wanted:
            self.watchdog.stop()
            self.sample.emit(Round(monitor_error="无法启动探测进程"))
            QTimer.singleShot(self.settings.interval_s * 1000, self.launch)

    def exited(self, code, status):
        self.watchdog.stop()
        self.ready = False
        self.set_checking(False)
        if self.wanted:
            if not self.expected_exit:
                self.sample.emit(Round(monitor_error=f"探测进程退出 code={code}"))
            QTimer.singleShot(50 if self.expected_exit else self.settings.interval_s * 1000, self.launch)
