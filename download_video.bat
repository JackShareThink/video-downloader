@echo off
chcp 65001 >nul
title Video Downloader
cd /d "%~dp0"
if "%~1"=="" (
  python "%~dp0video_downloader.py"
  echo.
  pause
) else (
  python "%~dp0video_downloader.py" %*
)
