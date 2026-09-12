@echo off
echo ====================================================
echo   FrostSpice Pro — B2B Inventory ^& Sales Manager
echo ====================================================
echo.

:: Check if virtual environment exists
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
)

:: Activate and install dependencies
call venv\Scripts\activate.bat
echo Installing dependencies...
pip install -r requirements.txt --quiet

echo.
echo Starting server on http://localhost:5000
echo Press Ctrl+C to stop.
echo.
python app.py
pause
