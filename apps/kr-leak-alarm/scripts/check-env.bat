@echo off
setlocal
chcp 65001 >nul 2>&1
cd /d "%~dp0.."

echo.
echo  ---- environment check ----------------------------
where python
python --version
echo.
echo  project folder: %CD%
if exist ".venv\Scripts\python.exe" (echo  venv          : OK) else (echo  venv          : not created yet)
if exist "config.json"              (echo  config.json   : OK) else (echo  config.json   : will be created on first run)
if exist "web\data\data.js"         (echo  dashboard data: OK) else (echo  dashboard data: none yet)
echo.

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m collector.main doctor
) else (
  python -m collector.main doctor
)
echo.
pause
