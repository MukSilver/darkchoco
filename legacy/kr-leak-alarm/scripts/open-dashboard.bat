@echo off
setlocal
chcp 65001 >nul 2>&1
cd /d "%~dp0.."

if not exist "web\data\data.js" (
  echo.
  echo  [!] No data yet. Run  scripts\run.bat  first,
  echo      or generate sample data:
  echo        python scripts\make_demo_data.py
  echo.
  pause
  exit /b 1
)

echo.
echo  Starting local dashboard on http://127.0.0.1:8787
echo  Press Ctrl+C in this window to stop.
echo.

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m collector.main serve
) else (
  python -m collector.main serve
)
