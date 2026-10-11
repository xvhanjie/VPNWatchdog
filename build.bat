@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    set "WATCHDOG_PYTHON=%~dp0.venv\Scripts\python.exe"
) else (
    set "WATCHDOG_PYTHON=python"
)
"%WATCHDOG_PYTHON%" -m unittest discover -s tests -v
if errorlevel 1 exit /b 1
"%WATCHDOG_PYTHON%" -m unittest tests.gui_cases -v
if errorlevel 1 exit /b 1
"%WATCHDOG_PYTHON%" tools\create_icon.py
if errorlevel 1 exit /b 1
"%WATCHDOG_PYTHON%" -m PyInstaller --noconfirm VPNWatchdog.spec
if errorlevel 1 exit /b 1
echo Built: %~dp0dist\VPNWatchdog.exe
