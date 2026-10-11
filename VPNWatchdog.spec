# Build on Windows: python -m PyInstaller --noconfirm VPNWatchdog.spec
from pathlib import Path
import os
import PySide6

root = Path(SPECPATH)
# Build hosts may have unrelated codec/PDF DLLs on PATH. Never bundle their UCRT
# or OpenSSL in place of the operating system / Python / Qt runtime.
os.environ['PATH'] = os.pathsep.join([str(Path(PySide6.__file__).parent),
                                     str(Path(os.environ['SystemRoot']) / 'System32'),
                                     os.environ['SystemRoot']])
a = Analysis([str(root / 'main.py')], pathex=[str(root)],
             binaries=[], datas=[], hiddenimports=[],
             excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
                       'PySide6.QtQuick', 'PySide6.QtQml', 'PySide6.QtPdf',
                       'numpy', 'matplotlib', 'pandas', 'tkinter'],
             noarchive=False)
# UCRT is an OS component on supported Windows 10/11. A PATH-provided UCRT can
# override newer system exports and make QtCore fail with error 127.
a.binaries = [entry for entry in a.binaries if Path(entry[0]).name.lower() != 'ucrtbase.dll']
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [],
          name='VPNWatchdog', debug=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False,
          icon=str(root / 'resources' / 'app.ico'))
