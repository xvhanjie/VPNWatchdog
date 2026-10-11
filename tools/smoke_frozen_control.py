"""Exercise frozen worker stdin, existing timer updates, target changes and stop."""
from dataclasses import asdict, replace
import json
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from utils.config import Settings
from utils.streams import attach_worker_streams


attach_worker_streams()
settings = Settings(interval_s=8)
process = subprocess.Popen([str(root / "dist/VPNWatchdog.exe"), "--worker", "--settings-json", json.dumps(asdict(settings))],
                           stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           text=True, encoding="utf-8", errors="replace", creationflags=subprocess.CREATE_NO_WINDOW)
messages = queue.Queue()
stderr = []
def read_output():
    for line in process.stdout:
        if line.strip():
            messages.put(json.loads(line))
def read_error():
    for line in process.stderr:
        stderr.append(line.strip())
threading.Thread(target=read_output, daemon=True).start()
threading.Thread(target=read_error, daemon=True).start()


def receive(predicate, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        message = messages.get(timeout=max(0.01, deadline - time.monotonic()))
        if predicate(message):
            return message
    raise AssertionError("frozen worker response timed out")


def send(command):
    process.stdin.write(json.dumps(command) + "\n")
    process.stdin.flush()


try:
    receive(lambda message: "probes" in message)
    scheduler = None
    for interval in (3, 5, 8, 15, 30, 5, 10, 3, 20, 8):
        settings = replace(settings, interval_s=interval)
        send({"action": "configure", "settings": asdict(settings), "revision": 0})
        ack = receive(lambda message: message.get("event") == "configured")
        assert ack["interval_ms"] == interval * 1000
        scheduler = scheduler or ack["scheduler_id"]
        assert scheduler == ack["scheduler_id"]
    for revision, names in enumerate((["ChatGPT"], ["ChatGPT", "YouTube"], ["GitHub", "ChatGPT", "YouTube"]), 1):
        settings = replace(settings, selected_targets=names)
        send({"action": "configure", "settings": asdict(settings), "revision": revision})
        ack = receive(lambda message: message.get("event") == "configured" and message["revision"] == revision)
        assert scheduler == ack["scheduler_id"]
        result = receive(lambda message: "probes" in message and message["revision"] == revision)
        assert {probe["target"] for probe in result["probes"]} == set(names)
        print(f"frozen targets={','.join(names)} HTTP={[probe['http_status'] for probe in result['probes']]}", flush=True)
    send({"action": "stop"})
    process.wait(timeout=5)
    assert process.returncode == 0, stderr
    print("Frozen control OK: ten intervals, same scheduler, three target changes, graceful stop", flush=True)
finally:
    if process.poll() is None:
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
        process.wait(timeout=5)
