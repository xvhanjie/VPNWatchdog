"""One blocking stdin reader; Qt delivers commands on the worker event thread."""
import json
import sys
import threading

from PySide6.QtCore import QObject, Signal


class WorkerControl(QObject):
    command = Signal(object)

    def __init__(self, handler):
        super().__init__()
        self.command.connect(handler)
        self.reader = threading.Thread(target=self.read, name="worker-command-reader", daemon=True)
        self.reader.start()

    def read(self):
        for line in sys.stdin:
            if len(line) > 16384:
                continue
            try:
                command = json.loads(line)
                if isinstance(command, dict):
                    self.command.emit(command)
            except ValueError:
                continue
        self.command.emit({"action": "stop"})
