@echo off
echo ========================================
echo   AI Learning Coach - Startup
echo ========================================
echo.

cd /d "%~dp0"

echo [1/2] Installing dependencies...
pip install streamlit google-generativeai python-dotenv --quiet
if errorlevel 1 (
    echo ERROR: pip install failed. Make sure Python is installed.
    pause
    exit /b 1
)

echo [2/2] Launching Streamlit app...
echo.
echo App will open at: http://localhost:8501
echo Press Ctrl+C in this window to stop.
echo.
streamlit run app.py --server.headless false

pause
