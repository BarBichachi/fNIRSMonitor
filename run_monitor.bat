@echo off
REM Launches the fNIRS Monitor using its own virtual environment.
REM The system Python does NOT have the dependencies; this guarantees the
REM correct interpreter is used regardless of how the script is started.
setlocal
cd /d "%~dp0"

set "VENV_PY=.venv\Scripts\python.exe"

if exist "%VENV_PY%" goto run

echo [run_monitor] No virtual environment found. Creating one...
py -3.12 -m venv .venv 2>nul
if not exist "%VENV_PY%" python -m venv .venv
if not exist "%VENV_PY%" goto novenv

echo [run_monitor] Installing dependencies from requirements.txt...
"%VENV_PY%" -m pip install --upgrade pip
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 goto pipfail

:run
echo [run_monitor] Launching fNIRS Monitor...
"%VENV_PY%" main.py
if errorlevel 1 pause
exit /b 0

:novenv
echo [run_monitor] ERROR: could not create a virtual environment.
echo [run_monitor] Install Python 3.12 from python.org and try again.
pause
exit /b 1

:pipfail
echo [run_monitor] ERROR: dependency installation failed.
pause
exit /b 1
