@echo off
setlocal enabledelayedexpansion

REM ============================================================
REM Library Assistant - install external Python requirements
REM Creates/uses the current Python environment (no venv created).
REM ============================================================

echo [0/3] Checking Python on PATH...
where python >nul 2>nul
if errorlevel 1 (
  echo Python not found on PATH.
  echo Install Python from: https://www.python.org/downloads/
  echo And make sure "Add Python to PATH" is checked during installation.
  pause
  exit /b 1
)

echo [1/3] Upgrading pip...
python -m pip install --upgrade pip
if errorlevel 1 (
  echo Pip upgrade failed. Check your Python installation.
  pause
  exit /b 1
)

echo [2/3] Installing requirements (Pillow, Requests)...
python -m pip install pillow requests
if errorlevel 1 (
  echo Requirements installation failed.
  pause
  exit /b 1
)

echo [3/3] Verifying imports...
python -c "import PIL; print('Pillow OK -', PIL.__version__)" 
if errorlevel 1 (
  echo Import verification failed.
  pause
  exit /b 1
)

echo.
echo All dependencies installed successfully.

pause

