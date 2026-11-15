@echo off
setlocal
cd /d "%~dp0"
set "DEKU_PYTHON="
if exist "local\python-path.txt" set /p "DEKU_PYTHON="<"local\python-path.txt"
if defined DEKU_PYTHON (
  "%DEKU_PYTHON%" run_launcher.py
) else (
  py -3 run_launcher.py
)
if errorlevel 1 pause
