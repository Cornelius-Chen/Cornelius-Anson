@echo off
setlocal

cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python not found in PATH.
  exit /b 1
)

python -m pip install --upgrade pyinstaller >nul
if errorlevel 1 (
  echo [ERROR] Failed to install/upgrade pyinstaller.
  exit /b 1
)

python -m PyInstaller --noconfirm --clean --windowed ^
  --name Dugong ^
  --paths . ^
  --add-data "dugong_app\ui\assets;dugong_app\ui\assets" ^
  dugong_app\main.py

if errorlevel 1 (
  echo [ERROR] Build failed.
  exit /b 1
)

echo.
echo [OK] Build complete:
echo   %~dp0dist\Dugong\Dugong.exe
exit /b 0

