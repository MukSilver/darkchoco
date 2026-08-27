@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0.."

echo.
echo  ==========================================
echo   Kr-Leak-alarm  -  collector
echo  ==========================================
echo.

rem ---- 1. check python ----------------------------------------
where python >nul 2>&1
if errorlevel 1 (
  echo  [!] Python not found in PATH.
  echo      Install Python 3.10+ from https://www.python.org/downloads/
  echo      IMPORTANT: check "Add python.exe to PATH" during setup.
  echo.
  pause
  exit /b 1
)

rem ---- 2. create venv on first run ------------------------------
if not exist ".venv\Scripts\python.exe" (
  echo  [*] Creating virtual environment ^(first run only^)...
  python -m venv .venv
  if errorlevel 1 goto :fail
  echo  [*] Installing dependencies...
  ".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet --disable-pip-version-check
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt --quiet --disable-pip-version-check
  if errorlevel 1 goto :fail
  echo  [*] Setup done.
  echo.
)

rem ---- 3. prepare config ---------------------------------------
if not exist "config.json" (
  echo  [*] config.json not found - copying config.example.json
  copy /y "config.example.json" "config.json" >nul
)

rem ---- 4. run collector ----------------------------------------
".venv\Scripts\python.exe" -m collector.main run %*
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
  echo  [*] Done. Run  scripts\open-dashboard.bat  to view results.
) else (
  echo  [!] Finished with errors ^(exit code %RC%^). See logs\collector.log
)
echo.
pause
exit /b %RC%

:fail
echo.
echo  [!] Setup failed ^(exit code %ERRORLEVEL%^).
echo      Try running these manually to see the full error:
echo        python -m venv .venv
echo        .venv\Scripts\python.exe -m pip install -r requirements.txt
echo.
pause
exit /b 1
