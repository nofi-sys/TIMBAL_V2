@echo off
setlocal

set "ROOT=%~dp0"
cd /d "%ROOT%"

if not exist ".venv\Scripts\python.exe" (
  echo Falta el entorno virtual en "%ROOT%\.venv".
  echo Instalalo primero o recrealo antes de usar este launcher.
  exit /b 1
)

set "PATH=%ROOT%fluidsynth_dlls;%PATH%"
set "PYFLUIDSYNTH_LIB=%ROOT%fluidsynth_dlls\libfluidsynth-3.dll"
set "TIMBAL_FS_SAMPLE_RATE=48000"
set "TIMBAL_FS_PERIOD_SIZE=64"
set "TIMBAL_FS_PERIODS=2"
set "TIMBAL_SERIAL_BAUD=115200"

if /I "%~1"=="trainer" (
  ".venv\Scripts\python.exe" main.py --run-trainer
  exit /b %errorlevel%
)

if /I "%~1"=="analog" (
  ".venv\Scripts\python.exe" main.py --run-host-analog
  exit /b %errorlevel%
)

if /I "%~1"=="dino" (
  ".venv\Scripts\python.exe" main.py --run-dino
  exit /b %errorlevel%
)

if /I "%~1"=="legacy" (
  ".venv\Scripts\python.exe" main.py --legacy-ui
  exit /b %errorlevel%
)

".venv\Scripts\python.exe" main.py --new-ui
exit /b %errorlevel%
