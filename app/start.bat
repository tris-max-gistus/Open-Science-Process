@echo off
cd /d "%~dp0"
python start.py
if errorlevel 1 (
    echo.
    echo Something went wrong. See the message above.
    pause
)
