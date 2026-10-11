from PySide6.QtWidgets import (QAbstractItemView, QHBoxLayout, QLabel, QMainWindow,
                               QPushButton, QTableWidget, QTableWidgetItem, QTextEdit,
                               QVBoxLayout, QWidget)

from ui.tray import COLORS, status_icon


class Dashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.allow_close = False
        self.can_hide = True
        self.target_names = []
        self.setWindowTitle("VPN Watchdog / Network Guardian")
        self.setWindowIcon(status_icon())
        self.resize(820, 670)
        body = QWidget()
        self.setCentralWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(24, 20, 24, 20)
        title = QLabel("VPN WATCHDOG")
        title.setStyleSheet("font-size: 14px; font-weight: 600; color: #64748b;")
        layout.addWidget(title)
        self.status = QLabel("UNKNOWN")
        self.status.setStyleSheet("font-size: 30px; font-weight: 700;")
        layout.addWidget(self.status)
        self.detail = QLabel("正在等待第一轮真实网络探测…")
        self.detail.setWordWrap(True)
        layout.addWidget(self.detail)
        self.metrics = QLabel("请求延迟：—    HTTP 探测失败率：—    连续异常：0")
        layout.addWidget(self.metrics)
        self.scope = QLabel("监测目标：—")
        layout.addWidget(self.scope)
        self.timing = QLabel("最近检查：—    监测时长：00:00:00")
        layout.addWidget(self.timing)
        self.counters = QLabel("本次运行：异常 0 次 · Timeout 0 次 · 总中断 0 秒")
        layout.addWidget(self.counters)
        self.targets = QTableWidget(0, 4)
        self.targets.setHorizontalHeaderLabels(["检测目标", "结果", "请求 RTT (ms)", "HTTP"])
        self.targets.horizontalHeader().setStretchLastSection(True)
        self.targets.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.targets.verticalHeader().hide()
        self.targets.setMaximumHeight(150)
        self.targets.setColumnWidth(0, 130)
        self.targets.setColumnWidth(1, 310)
        layout.addWidget(self.targets)
        buttons = QHBoxLayout()
        self.test = QPushButton("立即检测")
        self.pause = QPushButton("暂停监测")
        self.work = QPushButton("工作模式（3秒）")
        self.work.setCheckable(True)
        self.settings = QPushButton("设置")
        self.exit_button = QPushButton("退出")
        for button in (self.test, self.pause, self.work, self.settings, self.exit_button):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        layout.addWidget(QLabel("最近记录（最多 200 行）"))
        self.history = QTextEdit()
        self.history.setReadOnly(True)
        self.history.document().setMaximumBlockCount(200)
        layout.addWidget(self.history)
        note = QLabel("检测反映当前系统代理 / TUN 路径的可用性。HTTP 失败率不是 ICMP 丢包率。关闭窗口后继续在托盘监测。")
        note.setWordWrap(True)
        note.setStyleSheet("color: #64748b;")
        layout.addWidget(note)

    def closeEvent(self, event):
        if self.allow_close or not self.can_hide:
            event.accept()
        else:
            self.hide()
            event.ignore()

    def display(self, result, update, outages, timeouts, downtime):
        self.status.setText(str(update.state))
        self.status.setStyleSheet(f"font-size: 30px; font-weight: 700; color: {COLORS[update.state]};")
        self.setWindowIcon(status_icon(update.state))
        count = len(self.target_names)
        self.detail.setText(result.monitor_error or f"本轮观测：{update.observed} · {result.successes}/{count} 个目标符合检测规则 · 已确认状态采用连续轮次防抖")
        failed = [probe.target for probe in result.probes if not probe.success]
        if failed:
            self.detail.setText(self.detail.text() + " · 异常目标：" + " / ".join(failed))
        rtt = f"{result.latency_ms:.0f} ms" if result.latency_ms is not None else "—"
        rate = f"{result.failure_rate:.1f}%" if result.failure_rate is not None else "—"
        self.metrics.setText(f"请求延迟中位数：{rtt}    HTTP 探测失败率：{rate}    连续判定轮数：{update.consecutive}")
        self.counters.setText(f"本次运行：异常 {outages} 次 · Timeout {timeouts} 次 · 已结束事件总中断 {downtime:.0f} 秒")
        probes = {probe.target: probe for probe in result.probes}
        for row, name in enumerate(self.target_names):
            probe = probes.get(name)
            if probe is None:
                values = [name, "未取得结果", "—", "—"]
            else:
                outcome = f"网络可达（HTTP {probe.http_status}）" if probe.note else ("OK" if probe.success else probe.error)
                values = [probe.target, outcome,
                      str(probe.latency_ms) if probe.latency_ms is not None else "—", str(probe.http_status or "—")]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if probe is not None:
                    item.setToolTip(probe.note or probe.error)
                self.targets.setItem(row, column, item)
        lines = [f"{result.timestamp[11:19]} {update.state} / observed={update.observed} RTT={rtt}"]
        lines.extend(f"  {p.target}: {p.error or 'OK'} {p.latency_ms}ms {p.note}" for p in result.probes if p.target in self.target_names)
        if result.monitor_error:
            lines.append(result.monitor_error)
        self.history.append("\n".join(lines))

    def configure_targets(self, names, clear=False):
        cached = {name: [self.targets.item(row, column).clone() for column in range(4)]
                  for row, name in enumerate(self.target_names)
                  if not clear and all(self.targets.item(row, column) is not None for column in range(4))}
        self.target_names = list(names)
        self.scope.setText("监测目标：" + " / ".join(names))
        if clear:
            self.status.setText("UNKNOWN")
            self.status.setStyleSheet(f"font-size: 30px; font-weight: 700; color: {COLORS['UNKNOWN']};")
            self.setWindowIcon(status_icon())
            self.detail.setText("监测目标已更新，等待新组合的检测结果…")
            self.metrics.setText("请求延迟中位数：—    HTTP 探测失败率：—    连续判定轮数：0")
            self.history.clear()
        self.targets.setRowCount(len(names))
        for row, name in enumerate(names):
            for column, value in enumerate((name, "等待检测", "—", "—")):
                self.targets.setItem(row, column, cached[name][column] if name in cached else QTableWidgetItem(value))
