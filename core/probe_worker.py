"""Headless QtNetwork probe process. Never imports QtWidgets."""
import json
import time

from PySide6.QtCore import QCoreApplication, QObject, QTimer, QUrl, Slot
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkProxyFactory, QNetworkReply, QNetworkRequest

from core.local_network import local_online
from core.models import Probe, Round
from utils.config import Settings


def error_category(error):
    errors = QNetworkReply.NetworkError
    return {
        errors.HostNotFoundError: "DNS_ERROR",
        errors.ProxyNotFoundError: "PROXY_DNS_ERROR",
        errors.ProxyConnectionRefusedError: "PROXY_CONNECTION_REFUSED",
        errors.ProxyConnectionClosedError: "PROXY_CONNECTION_CLOSED",
        errors.ProxyTimeoutError: "PROXY_TIMEOUT",
        errors.ProxyAuthenticationRequiredError: "PROXY_AUTH_REQUIRED",
        errors.ConnectionRefusedError: "CONNECTION_REFUSED",
        errors.RemoteHostClosedError: "CONNECTION_RESET",
        errors.SslHandshakeFailedError: "SSL_ERROR",
        errors.TimeoutError: "REQUEST_TIMEOUT",
        errors.NetworkSessionFailedError: "NETWORK_UNREACHABLE",
    }.get(error, "NETWORK_ERROR")


class ProbeWorker(QObject):
    def __init__(self, settings, publish, targets=None, status_publish=None, revision=0):
        super().__init__()
        self.settings = settings
        self.publish = publish
        self.status_publish = status_publish or (lambda event: None)
        self.revision = revision
        self.custom_targets = targets is not None
        self.targets = targets if self.custom_targets else settings.active_targets
        self.run_after_current = False
        self.active = False
        self.pending = {}
        self.manager = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.run_round)
        self.timer.start(settings.interval_s * 1000)
        QNetworkProxyFactory.setUseSystemConfiguration(True)
        QTimer.singleShot(0, self.run_round)

    @Slot(object)
    def handle_command(self, command):
        if command.get("action") == "configure":
            updated = Settings(**command["settings"]).validate()
            targets_changed = set(updated.selected_targets) != set(self.settings.selected_targets)
            self.settings = updated
            if not self.custom_targets:
                self.targets = updated.active_targets
            self.revision = command.get("revision", self.revision)
            # Update the existing scheduler, never create another detection timer.
            self.timer.setInterval(self.settings.interval_s * 1000)
            self.status_publish({"event": "configured", "revision": self.revision,
                                 "interval_ms": self.timer.interval(), "targets": self.settings.selected_targets,
                                 "scheduler_id": id(self.timer)})
            if targets_changed:
                if self.active:
                    self.run_after_current = True
                else:
                    self.run_round()
        elif command.get("action") == "check":
            self.run_round()
        elif command.get("action") == "stop":
            QCoreApplication.instance().quit()

    def run_round(self):
        if self.active:
            return
        self.active = True
        self.status_publish({"event": "checking", "active": True})
        self.result = Round(local_online=local_online(), revision=self.revision)
        if self.result.local_online is False:
            self.result.probes = [Probe(target[0], False, error="LOCAL_NETWORK_DOWN") for target in self.targets]
            self.complete()
            return
        self.manager = QNetworkAccessManager(self)
        # System proxy selection remains in this isolated process, including PAC.
        for target in self.targets:
            name, url, statuses = target[:3]
            method = target[3] if len(target) > 3 else "HEAD"
            policy = target[4] if len(target) > 4 else "expected"
            request = QNetworkRequest(QUrl(url))
            request.setRawHeader(b"User-Agent", b"VPNWatchdog/0.1")
            request.setRawHeader(b"Cache-Control", b"no-cache")
            request.setAttribute(QNetworkRequest.Attribute.CacheLoadControlAttribute,
                                 QNetworkRequest.CacheLoadControl.AlwaysNetwork)
            request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,
                                 QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
            request.setTransferTimeout(self.settings.timeout_s * 1000)
            start = time.monotonic()
            reply = self.manager.get(request) if method == "GET" else self.manager.head(request)
            reply.setReadBufferSize(4097)
            deadline = QTimer(reply)
            deadline.setSingleShot(True)
            self.pending[reply] = {"name": name, "statuses": statuses, "start": start,
                                   "timer": deadline, "timeout": False, "bytes": 0, "too_large": False, "policy": policy}
            reply.readyRead.connect(lambda r=reply: self.read_body(r))
            deadline.timeout.connect(lambda r=reply: self.expire(r))
            reply.finished.connect(lambda r=reply: self.finished(r))
            deadline.start(self.settings.timeout_s * 1000)

    def read_body(self, reply):
        item = self.pending.get(reply)
        if item is None:
            return
        item["bytes"] += reply.bytesAvailable()
        reply.readAll()
        if item["bytes"] > 4096:
            item["too_large"] = True
            reply.abort()

    def expire(self, reply):
        if reply in self.pending:
            self.pending[reply]["timeout"] = True
            reply.abort()

    def finished(self, reply):
        item = self.pending.pop(reply, None)
        if item is None:
            return
        item["timer"].stop()
        status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        status = int(status) if status else None
        err = reply.error()
        # Ignore HTTP-content errors for reachability, but never TLS/proxy/network errors.
        valid_http = status is not None and (err == QNetworkReply.NetworkError.NoError or err.value >= 200 or item["too_large"])
        valid_http = valid_http and not item["timeout"]
        accepted = status in item["statuses"] or (item["policy"] == "reachable" and status is not None and 200 <= status <= 599)
        success = valid_http and accepted and not item["too_large"]
        note = f"HTTP {status}：网络可达；服务可能限制访问、重定向或异常" if success and status not in item["statuses"] else ""
        reason = ""
        if item["timeout"]:
            reason = "REQUEST_TIMEOUT"
        elif item["too_large"]:
            reason = "RESPONSE_TOO_LARGE"
        elif valid_http and not success:
            reason = f"HTTP_STATUS_{status}"
        elif not success:
            reason = error_category(err)
        self.result.probes.append(Probe(item["name"], success,
                                        round((time.monotonic() - item["start"]) * 1000, 1),
                                        status, reason, bool(valid_http), note))
        reply.deleteLater()
        if not self.pending:
            self.complete()

    def complete(self):
        self.active = False
        if self.manager:
            self.manager.deleteLater()
            self.manager = None
        self.publish(self.result)
        self.status_publish({"event": "checking", "active": False})
        if self.run_after_current:
            self.run_after_current = False
            QTimer.singleShot(0, self.run_round)


def print_round(result):
    print(json.dumps(result.to_dict(), ensure_ascii=True), flush=True)
