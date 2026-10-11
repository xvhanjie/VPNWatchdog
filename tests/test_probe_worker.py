from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import time
import unittest
from unittest.mock import patch

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer
from PySide6.QtNetwork import QNetworkProxy, QNetworkProxyFactory, QNetworkReply

from core.probe_worker import ProbeWorker, error_category
from utils.config import Settings


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = b"x" * (10000 if self.path == "/large" else 64)
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except OSError:
            pass

    def do_HEAD(self):
        if self.path == "/slow":
            time.sleep(2)
        if self.path == "/long":
            time.sleep(4.2)
        status = {"/restricted": 403, "/rate": 429, "/redirect": 302}.get(self.path, 200)
        try:
            self.send_response(status)
            self.send_header("Content-Length", "0")
            self.end_headers()
        except OSError:
            pass

    def log_message(self, *args):
        pass


class ProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance() or QCoreApplication([])
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.server.daemon_threads = True
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(2)

    def probe(self, paths, online=True, method="HEAD", policy="expected", interval_s=30, timeout_s=1, keep_scheduler=False, events=None):
        loop = QEventLoop()
        results = []
        def publish(result):
            results.append(result)
            loop.quit()
        targets = [(str(index), f"http://127.0.0.1:{self.server.server_port}{path}", (200,), method, policy)
                   for index, path in enumerate(paths)]
        QNetworkProxyFactory.setUseSystemConfiguration(False)
        QNetworkProxy.setApplicationProxy(QNetworkProxy(QNetworkProxy.ProxyType.NoProxy))
        with patch("core.probe_worker.local_online", return_value=online), \
             patch("core.probe_worker.QNetworkProxyFactory.setUseSystemConfiguration"):
            worker = ProbeWorker(Settings(interval_s=interval_s, timeout_s=timeout_s), publish, targets,
                                 status_publish=events.append if events is not None else None)
            if not keep_scheduler:
                worker.timer.stop()
            else:
                QTimer.singleShot(200, lambda: worker.handle_command({"action": "check"}))
            deadline = QTimer()
            deadline.setSingleShot(True)
            deadline.timeout.connect(loop.quit)
            deadline.start(7000)
            loop.exec()
            deadline.stop()
            worker.timer.stop()
            worker.deleteLater()
        self.assertEqual(len(results), 1, "probe did not finish within five seconds")
        return results[0]

    def test_parallel_head_and_restriction(self):
        result = self.probe(["/ok", "/restricted", "/rate"])
        self.assertEqual(result.successes, 1)
        self.assertTrue(all(p.reachable for p in result.probes))
        self.assertEqual({p.http_status for p in result.probes}, {200, 403, 429})

    def test_parallel_deadline(self):
        start = time.monotonic()
        result = self.probe(["/slow", "/slow", "/ok"])
        self.assertLess(time.monotonic() - start, 1.8)
        self.assertEqual(result.successes, 1)
        self.assertEqual(sum(p.error == "REQUEST_TIMEOUT" for p in result.probes), 2)

    def test_redirect_not_healthy(self):
        result = self.probe(["/redirect", "/ok", "/ok"])
        redirect = next(p for p in result.probes if p.http_status == 302)
        self.assertFalse(redirect.success)
        self.assertTrue(redirect.reachable)

    def test_reachability_policy_accepts_server_responses(self):
        result = self.probe(["/redirect", "/restricted", "/rate"], policy="reachable")
        self.assertEqual(result.successes, 3)
        self.assertTrue(all(p.note and not p.error for p in result.probes))

    def test_get_body_cap(self):
        result = self.probe(["/large", "/ok", "/ok"], method="GET")
        self.assertEqual(result.successes, 2)
        large = next(p for p in result.probes if p.target == "0")
        self.assertEqual(large.error, "RESPONSE_TOO_LARGE")
        self.assertTrue(large.reachable)

    def test_local_down_short_circuits(self):
        result = self.probe(["/ok", "/ok", "/ok"], online=False)
        self.assertEqual(result.successes, 0)
        self.assertTrue(all(p.error == "LOCAL_NETWORK_DOWN" for p in result.probes))

    def test_error_categories(self):
        errors = QNetworkReply.NetworkError
        for error, expected in ((errors.HostNotFoundError, "DNS_ERROR"),
                                (errors.ProxyTimeoutError, "PROXY_TIMEOUT"),
                                (errors.SslHandshakeFailedError, "SSL_ERROR"),
                                (errors.ConnectionRefusedError, "CONNECTION_REFUSED")):
            self.assertEqual(error_category(error), expected)

    def test_three_second_timer_does_not_overlap_long_round(self):
        events = []
        result = self.probe(["/long"], interval_s=3, timeout_s=5, keep_scheduler=True, events=events)
        self.assertEqual(result.successes, 1)
        starts = [event for event in events if event.get("event") == "checking" and event["active"]]
        self.assertEqual(len(starts), 1, "manual click / timer overlapped the 4.2-second request")
