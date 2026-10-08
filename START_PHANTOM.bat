@echo off
setlocal
cd /d "%~dp0"
title Phantom Symptom - One Click Launcher

echo.
echo =============================================
echo        PHANTOM SYMPTOM CROP DOCTOR
echo =============================================
echo.
echo Checking Python packages...
python -m pip install -q -r backend\requirements.txt
if errorlevel 1 (
    echo.
    echo Could not install the required Python packages.
    echo Make sure Python is installed and try again.
    pause
    exit /b 1
)

echo.
echo Starting Phantom Symptom...
start "" http://127.0.0.1:8000
python backend\main.py
pause
