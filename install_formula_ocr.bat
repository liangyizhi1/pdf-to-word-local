@echo off
setlocal
cd /d "%~dp0"
python -m pip install --no-build-isolation -e ".[portable,formula]"
if errorlevel 1 (
  echo.
  echo Formula OCR installation failed. Check Python and your network connection.
  pause
  exit /b 1
)
echo.
echo Formula OCR installation completed. Enable it in the desktop application.
pause
