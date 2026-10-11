import logging
from logging.handlers import RotatingFileHandler


def make_logger(directory):
    directory.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("vpnwatchdog")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)
    handler = RotatingFileHandler(directory / "network.log", maxBytes=2 * 1024 * 1024,
                                 backupCount=5, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%Y-%m-%d %H:%M:%S"))
    logger.addHandler(handler)
    return logger


def log_round(logger, result, update):
    logger.info("STATE=%s observed=%s consecutive=%s latency_ms=%s failure_rate=%s event=%s downtime_s=%s monitor_error=%s",
                update.state, update.observed, update.consecutive, result.latency_ms, result.failure_rate,
                update.event or "-", update.downtime_s, result.monitor_error or "-")
    for probe in result.probes:
        logger.info("TARGET=%s success=%s reachable=%s rtt_ms=%s http=%s error=%s note=%s",
                    probe.target, probe.success, probe.reachable, probe.latency_ms,
                    probe.http_status, probe.error or "-", probe.note or "-")
