from dataclasses import replace

from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox,
                               QFormLayout, QGroupBox, QLabel, QMessageBox, QSpinBox, QVBoxLayout)
from utils.config import Settings, TARGETS


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.original = settings
        self.result_settings = None
        self.setWindowTitle("VPN Watchdog 设置")
        form = QFormLayout(self)
        self.interval = QSpinBox()
        self.interval.setRange(3, 30)
        self.interval.setSuffix(" 秒")
        self.interval.setValue(settings.interval_s)
        form.addRow("检测间隔（3～30秒）", self.interval)
        group = QGroupBox("监测目标")
        target_layout = QVBoxLayout(group)
        self.target_boxes = {}
        for target in TARGETS:
            box = QCheckBox(target.name)
            box.setChecked(target.name in settings.selected_targets)
            self.target_boxes[target.name] = box
            box.toggled.connect(lambda checked, name=target.name: self.guard_targets(name, checked))
            target_layout.addWidget(box)
        self.selection_hint = QLabel()
        target_layout.addWidget(self.selection_hint)
        self.update_selection_hint()
        form.addRow(group)
        self.fields = {}
        for name, label, low, high in (("timeout_s", "请求超时（秒）", 1, 10),
                                      ("failure_count", "连续异常轮数", 2, 10),
                                      ("recovery_count", "连续恢复轮数", 2, 10),
                                      ("good_ms", "GOOD 上限（ms）", 1, 60000),
                                      ("high_ms", "HIGH LATENCY 起点（ms）", 2, 60000),
                                      ("very_high_ms", "VERY HIGH 起点（ms）", 3, 60000),
                                      ("notification_cooldown_s", "质量提醒冷却（秒）", 60, 86400)):
            spin = QSpinBox()
            spin.setRange(low, high)
            spin.setValue(getattr(settings, name))
            form.addRow(label, spin)
            self.fields[name] = spin
        self.notifications = QCheckBox("发送 Windows 系统通知")
        self.notifications.setChecked(settings.notifications)
        self.sound = QCheckBox("额外播放系统提示音")
        self.sound.setChecked(settings.sound)
        form.addRow(self.notifications)
        form.addRow(self.sound)
        note = QLabel("默认遵循 Windows 系统代理。ChatGPT / YouTube 的非 200 响应只表示网络路径可达，不能保证服务功能正常。\n不添加开机启动。通知显示及系统自身声音受 Windows 通知设置控制。")
        note.setWordWrap(True)
        form.addRow(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
                                   | QDialogButtonBox.StandardButton.RestoreDefaults)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("保存并应用")
        buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(self.restore_defaults)
        buttons.accepted.connect(self.validate)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def selected_targets(self):
        return [name for name, box in self.target_boxes.items() if box.isChecked()]

    def update_selection_hint(self, message="请选择 1～3 个监测目标。"):
        self.selection_hint.setText(f"已选择：{len(self.selected_targets())} / 3 · {message}")

    def guard_targets(self, name, checked):
        count = len(self.selected_targets())
        if count > 3 or count == 0:
            box = self.target_boxes[name]
            box.blockSignals(True)
            box.setChecked(not checked)
            box.blockSignals(False)
            self.update_selection_hint("最多选择 3 个监测目标。" if count > 3 else "至少选择 1 个监测目标。")
        else:
            self.update_selection_hint()

    def restore_defaults(self):
        defaults = Settings()
        self.interval.setValue(defaults.interval_s)
        for name, spin in self.fields.items():
            spin.setValue(getattr(defaults, name))
        for name, box in self.target_boxes.items():
            box.blockSignals(True)
            box.setChecked(name in defaults.selected_targets)
            box.blockSignals(False)
        self.notifications.setChecked(defaults.notifications)
        self.sound.setChecked(defaults.sound)
        self.update_selection_hint()

    def validate(self):
        values = {name: widget.value() for name, widget in self.fields.items()}
        values.update(interval_s=self.interval.value(), selected_targets=self.selected_targets(),
                      notifications=self.notifications.isChecked(), sound=self.sound.isChecked())
        try:
            self.result_settings = replace(self.original, **values).validate()
        except ValueError as error:
            QMessageBox.warning(self, "设置无效", str(error))
            return
        self.accept()
