@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%~dp0src"
python -m pdf2word_local.gui
if errorlevel 1 (
  echo.
  echo The application could not start. Check that Python 3.10 or newer is installed.
  pause
)
