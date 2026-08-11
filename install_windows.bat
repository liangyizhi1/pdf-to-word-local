@echo off
setlocal
cd /d "%~dp0"
python -m pip install --no-build-isolation -e ".[portable]"
if errorlevel 1 (
  echo.
  echo Installation failed. Check Python and your network connection.
  pause
  exit /b 1
)
echo.
echo Installation completed. Double-click run_app.bat to start.
pause
