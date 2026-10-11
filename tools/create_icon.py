"""Generate a Windows ICO with a PNG frame using Qt; no additional dependency."""
import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.models import State
from ui.tray import status_icon


app = QApplication([])
data = QByteArray()
buffer = QBuffer(data)
buffer.open(QIODevice.OpenModeFlag.WriteOnly)
status_icon(State.HEALTHY).pixmap(32, 32).save(buffer, "PNG")
png = bytes(data)
path = Path(__file__).resolve().parents[1] / "resources" / "app.ico"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_bytes(struct.pack("<HHH", 0, 1, 1) + struct.pack("<BBBBHHII", 32, 32, 0, 0, 1, 32, len(png), 22) + png)
print(path)
