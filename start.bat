@echo off
chcp 65001 >nul
echo =========================================
echo   Social Media Stats Tool
echo =========================================
echo.

cd /d "%~dp0\backend"

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python and add it to PATH.
    pause
    exit /b 1
)

REM Install dependencies
echo [1/2] Checking dependencies...
python -m pip install -q -r requirements.txt
if errorlevel 1 (
    echo [WARN] Dependency install may have issues, trying to continue...
)

REM Start service
echo [2/2] Starting backend server...
echo.
echo Please wait, then open your browser at:
echo   http://localhost:5003
echo.
python app.py

pause
