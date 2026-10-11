"""One diagnostic round for all five candidates; normal monitoring selects ≤3."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QCoreApplication
from core.probe_worker import ProbeWorker
from utils.config import Settings, TARGETS
from utils.streams import attach_worker_streams


attach_worker_streams()
app = QCoreApplication([])
def publish(result):
    for probe in result.probes:
        print(f"{probe.target}: success={probe.success} reachable={probe.reachable} HTTP={probe.http_status} RTT={probe.latency_ms}ms error={probe.error or '-'} {probe.note}", flush=True)
    app.quit()
worker = ProbeWorker(Settings(), publish, targets=TARGETS)
app.exec()
