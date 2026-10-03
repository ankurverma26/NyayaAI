@echo off
REM One-click demo launcher for NyayaAI (Windows). Run from anywhere: scripts\run_demo.bat
cd /d "%~dp0\.."
call .venv\Scripts\activate.bat

echo [1/4] Validating statute files...
python scripts\validate_laws.py
if errorlevel 1 (
  echo.
  echo Statute files have errors. Fix them first.
  pause
  exit /b 1
)

echo [2/4] Loading statutes into the database...
python scripts\load_laws.py

echo [3/4] Building / checking the search index...
python scripts\search_cli.py --stats

echo [4/4] Starting backend (port 8000) and frontend (port 5173)...
start "NyayaAI backend" cmd /k "call .venv\Scripts\activate.bat && uvicorn backend.main:app --port 8000"
start "NyayaAI frontend" cmd /k "cd frontend && npm run dev"
timeout /t 10 >nul
start http://localhost:5173
echo Demo started. Close the two new windows to stop it.
