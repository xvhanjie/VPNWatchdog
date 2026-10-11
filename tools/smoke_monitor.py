"""Live integration: receive data, kill a worker, recover, trigger watchdog, exit."""
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from PySide6.QtCore import QCoreApplication, QTimer
from core.network_monitor import NetworkMonitor
from utils.config import Settings


app = QCoreApplication([])
monitor = NetworkMonitor(Settings(interval_s=3))
stage = 0
good = 0
errors = 0
success = False


def receive(result):
    global stage, good, errors, success
    if result.monitor_error:
        errors += 1
        print(f"diagnostic: {result.monitor_error}", flush=True)
        return
    good += 1
    print(f"round {good}: {result.successes}/3 valid targets; worker_pid={monitor.process.processId()}", flush=True)
    if stage == 0:
        stage = 1
        QTimer.singleShot(0, monitor.process.kill)
    elif stage == 1:
        stage = 2
        QTimer.singleShot(0, monitor.stalled)
    else:
        success = errors >= 2
        app.quit()


monitor.sample.connect(receive)
monitor.diagnostic.connect(lambda message: print(message, flush=True))
limit = QTimer()
limit.setSingleShot(True)
limit.timeout.connect(app.quit)
limit.start(45000)
app.aboutToQuit.connect(lambda: monitor.stop(wait=True))
monitor.start()
app.exec()
assert success, f"monitor smoke failed: rounds={good}, errors={errors}"
assert monitor.process.processId() == 0, "worker not reaped"
print("Monitor smoke OK: crash + watchdog recovery, bounded shutdown", flush=True)
