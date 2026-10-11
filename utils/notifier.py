import sys
import time

from PySide6.QtWidgets import QSystemTrayIcon


class Notifier:
    def __init__(self, tray, settings, logger, clock=time.monotonic):
        self.tray = tray
        self.settings = settings
        self.logger = logger
        self.clock = clock
        self.last_quality = float("-inf")
        self.last_monitor_error = float("-inf")

    def handle(self, result, update):
        if result.monitor_error:
            if self.settings.notifications and self.clock() - self.last_monitor_error >= self.settings.notification_cooldown_s:
                self.last_monitor_error = self.clock()
                self.tray.showMessage("VPN Watchdog — 监测暂不可用",
                                      result.monitor_error + "\n探测器将自动重启，此结果未证明 VPN 掉线。",
                                      QSystemTrayIcon.MessageIcon.Warning, 10000)
            return
        if not update.event:
            return
        if update.event == "QUALITY":
            if self.clock() - self.last_quality < self.settings.notification_cooldown_s:
                return
            self.last_quality = self.clock()
        if not self.settings.notifications:
            return
        if update.event == "DOWN":
            title = "VPN Watchdog — 网络连接异常"
            message = f"{update.state} · {result.timestamp[11:19]}\n连续失败 {update.consecutive} 轮\n"
            message += "\n".join(f"{p.target}: {p.error or 'FAILED'}" for p in result.probes)
            icon = QSystemTrayIcon.MessageIcon.Critical
        elif update.event == "RECOVERED":
            seconds = int(update.downtime_s or 0)
            title = "VPN Watchdog — 网络已恢复"
            message = f"Network Recovered\n中断持续 {seconds // 60:02d}:{seconds % 60:02d}\n当前请求延迟 {result.latency_ms} ms"
            icon = QSystemTrayIcon.MessageIcon.Information
        else:
            title = "VPN Watchdog — 网络质量下降"
            message = f"{update.state}\n请求延迟 {result.latency_ms} ms\nHTTP 探测失败率 {result.failure_rate:.0f}%"
            icon = QSystemTrayIcon.MessageIcon.Warning
        if self.tray.isSystemTrayAvailable() and self.tray.supportsMessages():
            self.tray.showMessage(title, message, icon, 10000)
        else:
            self.logger.warning("SYSTEM_NOTIFICATION_UNAVAILABLE %s %s", title, message.replace("\n", " "))
        if self.settings.sound and sys.platform == "win32":
            import winsound
            try:
                winsound.MessageBeep(winsound.MB_ICONASTERISK if update.event == "RECOVERED" else winsound.MB_ICONEXCLAMATION)
            except RuntimeError:
                self.logger.warning("系统提示音播放失败")
