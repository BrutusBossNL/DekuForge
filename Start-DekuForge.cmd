@echo off
setlocal
cd /d "%~dp0"
if exist "%LOCALAPPDATA%\Programs\NX2navi\python\python.exe" (
  "%LOCALAPPDATA%\Programs\NX2navi\python\python.exe" run_launcher.py
) else (
  py -3 run_launcher.py
)
if errorlevel 1 pause
