"""Live process test: intervals and selected groups change without restarting."""
from dataclasses import replace
from pathlib import Path
import sys
import time

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from PySide6.QtCore import QCoreApplication, QTimer
from core.network_monitor import NetworkMonitor
from utils.config import Settings
from utils.streams import attach_worker_streams


attach_worker_streams()
app = QCoreApplication([])
monitor = NetworkMonitor(Settings(interval_s=3))
intervals = [3, 5, 8, 15, 30, 5, 10, 3, 20, 8]
groups = [["ChatGPT"], ["ChatGPT", "YouTube"], ["Google", "GitHub", "Cloudflare"],
          ["GitHub", "ChatGPT", "YouTube"]]
acknowledged = []
measured = []
expected_group = None
worker_pid = None
scheduler_id = None
phase = "intervals"
finished = False
failure = None


def check_pid():
    global worker_pid
    current = monitor.process.processId()
    if worker_pid is None:
        worker_pid = current
    assert worker_pid == current and current != 0, "settings update restarted the worker"


def configured(event):
    global phase, expected_group, scheduler_id
    check_pid()
    if scheduler_id is None:
        scheduler_id = event["scheduler_id"]
    assert scheduler_id == event["scheduler_id"], "a new detection scheduler was created"
    if phase == "intervals":
        expected = intervals.pop(0)
        assert event["interval_ms"] == expected * 1000
        acknowledged.append(expected)
        print(f"ack interval={expected}s pid={worker_pid}", flush=True)
        if intervals:
            monitor.configure(replace(monitor.settings, interval_s=intervals[0]))
        else:
            phase = "groups"
            expected_group = groups.pop(0)
            monitor.configure(replace(monitor.settings, selected_targets=expected_group))


def sample(result):
    global expected_group, finished, phase
    if result.monitor_error:
        raise AssertionError(result.monitor_error)
    if phase != "groups" or [probe.target for probe in sorted(result.probes, key=lambda p: monitor.settings.selected_targets.index(p.target))] != expected_group:
        return
    check_pid()
    measured.append(list(expected_group))
    print(f"group={','.join(expected_group)} responses={[(p.http_status, p.error or '-') for p in result.probes]} pid={worker_pid}", flush=True)
    if groups:
        expected_group = groups.pop(0)
        monitor.configure(replace(monitor.settings, selected_targets=expected_group))
    else:
        phase = "finished"
        finished = True
        app.quit()


def guarded(callback):
    def call(value):
        global failure
        try:
            callback(value)
        except Exception as error:
            failure = error
            app.quit()
    return call


monitor.configured.connect(guarded(configured))
monitor.sample.connect(guarded(sample))
limit = QTimer()
limit.setSingleShot(True)
limit.timeout.connect(app.quit)
limit.start(45000)
app.aboutToQuit.connect(lambda: monitor.stop(wait=True))
monitor.start()
app.exec()
assert failure is None, str(failure)
assert finished and len(acknowledged) == 10 and len(measured) == 4, "dynamic smoke did not finish"
assert monitor.process.processId() == 0
print("Dynamic smoke OK: same worker, ten interval changes, four target groups", flush=True)
