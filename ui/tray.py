from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from core.models import State


COLORS = {State.HEALTHY: "#16a34a", State.RECOVERED: "#16a34a", State.HIGH_LATENCY: "#eab308",
          State.UNSTABLE: "#f97316", State.VPN_DOWN: "#ef4444", State.NO_INTERNET: "#64748b",
          State.UNKNOWN: "#64748b"}


def status_icon(state=State.UNKNOWN):
    pixmap = QPixmap(32, 32)
    pixmap.fill(QColor("transparent"))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QColor("#ffffff"))
    painter.setBrush(QColor(COLORS[state]))
    painter.drawEllipse(3, 3, 26, 26)
    painter.drawLine(10, 17, 14, 21)
    painter.drawLine(14, 21, 23, 11)
    painter.end()
    return QIcon(pixmap)


class Tray(QSystemTrayIcon):
    def __init__(self, controller):
        super().__init__(status_icon(), controller.window)
        self.setToolTip("VPN Watchdog — UNKNOWN")
        self.menu = QMenu()
        heading = self.menu.addAction("VPN Watchdog")
        heading.setEnabled(False)
        self.status = self.menu.addAction("Status: UNKNOWN")
        self.latency = self.menu.addAction("Latency: —")
        self.checked = self.menu.addAction("Last Check: —")
        self.cycle = self.menu.addAction("Check Interval: —")
        for action in (self.status, self.latency, self.checked, self.cycle):
            action.setEnabled(False)
        self.menu.addSeparator()
        self.menu.addAction("Open Dashboard", controller.show)
        self.pause = self.menu.addAction("Pause Monitoring", controller.toggle_pause)
        self.menu.addAction("Run Test Now", controller.test_now)
        self.work = QAction("Work Mode (3 seconds)", self.menu)
        self.work.setCheckable(True)
        self.work.toggled.connect(controller.set_work_mode)
        self.menu.addAction(self.work)
        self.menu.addAction("Settings", controller.show_settings)
        self.menu.addAction("Test Notification", controller.test_notification)
        self.menu.addSeparator()
        self.menu.addAction("Exit", controller.quit)
        self.setContextMenu(self.menu)
        self.activated.connect(lambda reason: controller.show() if reason == self.ActivationReason.DoubleClick else None)
        self.show()

    def update_status(self, result, update):
        latency = f"{result.latency_ms:.0f} ms" if result.latency_ms is not None else "—"
        self.setIcon(status_icon(update.state))
        self.setToolTip(f"VPN Watchdog — {update.state}\nRTT: {latency}")
        self.status.setText(f"Status: {update.state}")
        self.latency.setText(f"Latency: {latency}")
        self.checked.setText(f"Last Check: {result.timestamp[11:19]}")

    def update_config(self, settings, work_mode):
        self.cycle.setText(f"Check Interval: {settings.interval_s} s" + (" (Work Mode)" if work_mode else ""))

    def reset_status(self):
        self.setIcon(status_icon())
        self.setToolTip("VPN Watchdog — UNKNOWN")
        self.status.setText("Status: UNKNOWN")
        self.latency.setText("Latency: —")
        self.checked.setText("Last Check: —")
