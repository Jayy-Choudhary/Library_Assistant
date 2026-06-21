@echo off
title Library Assistant Web App
cd /d "%~dp0"
echo Activating virtual environment...
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo [ERROR] Virtual environment not found in .venv/
    echo Please set up the virtual environment first.
    pause
    exit /b 1
)

echo Starting FastAPI server with Uvicorn...
uvicorn main:app --reload --port 8000
pause
