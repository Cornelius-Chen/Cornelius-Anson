@echo off
setlocal

cd /d "%~dp0"

set "APP_EXE=%~dp0dist\Dugong\Dugong.exe"
if not exist "%APP_EXE%" (
  echo [ERROR] Dugong.exe not found.
  echo Run build_exe.bat first.
  exit /b 1
)

REM -------- identity --------
if "%DUGONG_SOURCE_ID%"=="" set "DUGONG_SOURCE_ID=cornelius"
if "%DUGONG_SKIN_ID%"=="" set "DUGONG_SKIN_ID=auto"

REM -------- transport --------
if "%DUGONG_TRANSPORT%"=="" set "DUGONG_TRANSPORT=github"
if "%DUGONG_GITHUB_REPO%"=="" set "DUGONG_GITHUB_REPO=Cornelius-Chen/Cornelius-Anson"
if "%DUGONG_GITHUB_BRANCH%"=="" set "DUGONG_GITHUB_BRANCH=main"
if "%DUGONG_GITHUB_FOLDER%"=="" set "DUGONG_GITHUB_FOLDER=dugong_sync"
if "%DUGONG_SYNC_INTERVAL_SECONDS%"=="" set "DUGONG_SYNC_INTERVAL_SECONDS=5"

REM Token should be provided from user env for security:
REM   setx DUGONG_GITHUB_TOKEN "your_new_token_here"
if "%DUGONG_TRANSPORT%"=="github" (
  if "%DUGONG_GITHUB_TOKEN%"=="" (
    echo [ERROR] DUGONG_GITHUB_TOKEN is empty.
    echo Set it once in your user env:
    echo   setx DUGONG_GITHUB_TOKEN "your_new_token_here"
    exit /b 1
  )
)

start "" "%APP_EXE%"
exit /b 0

