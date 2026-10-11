"""Verify frozen supervisor → frozen worker JSON pipes and natural shutdown."""
from pathlib import Path
import subprocess
import sys


root = Path(__file__).resolve().parents[1]
executable = root / "dist" / "VPNWatchdog.exe"
command = [str(executable), "--once", "--data-dir", str(root / ".runtime-packaged")]
process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           creationflags=subprocess.CREATE_NO_WINDOW)
try:
    output, errors = process.communicate(timeout=45)
except subprocess.TimeoutExpired:
    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
    process.wait(timeout=5)
    raise AssertionError("Frozen EXE did not exit within 45 seconds")
text = output.decode("utf-8", errors="replace")
print(text)
print(errors.decode("utf-8", errors="replace"))
assert process.returncode == 0, f"frozen return code={process.returncode}"
assert "STATUS=" in text and all(name + ":" in text for name in ("Google", "Cloudflare", "GitHub"))
print(f"Frozen smoke OK; exe_bytes={executable.stat().st_size}")
