"""Windowed PyInstaller sets streams to None, even for a worker with pipes."""
import ctypes
import os
import sys


def attach_worker_streams():
    if sys.platform != "win32":
        return
    import msvcrt
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetStdHandle.argtypes = [ctypes.c_ulong]
    kernel.GetStdHandle.restype = ctypes.c_void_p
    for name, identifier in (("stdout", -11), ("stderr", -12), ("stdin", -10)):
        if getattr(sys, name) is not None:
            if hasattr(getattr(sys, name), "reconfigure"):
                getattr(sys, name).reconfigure(encoding="utf-8")
            continue
        handle = kernel.GetStdHandle(identifier & 0xFFFFFFFF)
        try:
            if not handle or handle == ctypes.c_void_p(-1).value:
                raise OSError("No inherited stream")
            reading = name == "stdin"
            descriptor = msvcrt.open_osfhandle(handle, (os.O_RDONLY if reading else os.O_WRONLY) | os.O_BINARY)
            stream = os.fdopen(descriptor, "r" if reading else "w", buffering=1, encoding="utf-8", errors="replace")
        except OSError:
            stream = open(os.devnull, "r" if name == "stdin" else "w", encoding="utf-8")
        setattr(sys, name, stream)
