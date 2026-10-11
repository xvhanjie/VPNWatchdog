"""Adapter evidence only: an active adapter does not prove Internet access."""
import ctypes
import sys
from ctypes import wintypes


class IfRow(ctypes.Structure):
    _fields_ = [("name", wintypes.WCHAR * 256), ("index", wintypes.DWORD),
                ("kind", wintypes.DWORD), ("mtu", wintypes.DWORD), ("speed", wintypes.DWORD),
                ("address_length", wintypes.DWORD), ("address", ctypes.c_ubyte * 8),
                ("admin", wintypes.DWORD), ("oper", wintypes.DWORD),
                ("counters", wintypes.DWORD * 13), ("description_length", wintypes.DWORD),
                ("description", ctypes.c_ubyte * 256)]


def local_online():
    if sys.platform != "win32":
        return None
    try:
        api = ctypes.WinDLL("iphlpapi").GetIfTable
        api.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.ULONG), wintypes.BOOL]
        api.restype = wintypes.DWORD
        size = wintypes.ULONG(0)
        api(None, ctypes.byref(size), False)
        for _ in range(3):
            buffer = ctypes.create_string_buffer(size.value)
            code = api(buffer, ctypes.byref(size), False)
            if code == 122:  # Adapter list changed while reading.
                continue
            if code:
                return None
            count = wintypes.DWORD.from_buffer(buffer).value
            offset = ctypes.sizeof(wintypes.DWORD)
            for index in range(count):
                row = IfRow.from_buffer(buffer, offset + index * ctypes.sizeof(IfRow))
                # IF_TYPE_SOFTWARE_LOOPBACK=24; MIB_IF_OPER_STATUS_OPERATIONAL=5.
                if row.kind != 24 and row.admin == 1 and row.oper == 5:
                    return True
            return False
        return None
    except (OSError, ValueError, AttributeError):
        return None
