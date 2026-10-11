import signal

from PySide6.QtCore import QCoreApplication, QTimer

from core.network_monitor import NetworkMonitor
from core.state_manager import StateManager
from core.models import latency_label
from utils.logger import make_logger, log_round


def run(settings, directory, once=False):
    app = QCoreApplication([])
    monitor = NetworkMonitor(settings)
    state = StateManager(settings)
    logger = make_logger(directory / "logs")
    for repair in getattr(settings, "_repairs", []):
        logger.warning("CONFIG_REPAIRED %s", repair)
    def show(result):
        update = state.consume(result)
        log_round(logger, result, update)
        if result.monitor_error:
            print(result.monitor_error, flush=True)
        else:
            for probe in result.probes:
                label = probe.error or latency_label(probe.latency_ms, settings)
                print(f"{result.timestamp} {probe.target}: {label} RTT={probe.latency_ms}ms HTTP={probe.http_status} {probe.note}", flush=True)
        print(f"STATUS={update.state} observed={update.observed} consecutive={update.consecutive} event={update.event or '-'} downtime={update.downtime_s}", flush=True)
        if once:
            app.exit(2 if result.monitor_error else 0)
    monitor.sample.connect(show)
    monitor.diagnostic.connect(lambda text: print(text, flush=True))
    app.aboutToQuit.connect(lambda: monitor.stop(wait=True))
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    heartbeat = QTimer()
    heartbeat.start(200)
    heartbeat.timeout.connect(lambda: None)
    monitor.start()
    return app.exec()
