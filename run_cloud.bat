@echo off
title Library Assistant - Cloud Mode
cd /d "%~dp0"

echo [1/2] Setting cloud database configurations...
set LIBRARY_ASSISTANT_REMOTE_URL=https://jaychoudhary.pythonanywhere.com
set LIBRARY_ASSISTANT_API_KEY=jay-library-secret-key-2026

echo [2/2] Starting application in Cloud Mode...
python library_assistant.py
if errorlevel 1 (
    echo.
    echo [ERROR] The application crashed or failed to start.
    echo Please make sure you have run 'install_requirements.bat' first.
)

pause
