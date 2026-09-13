@echo off
rem Console to UTF-8 so the Korean that Python prints renders.
rem The bat file itself stays ASCII - that is a separate problem.
chcp 65001 >nul 2>&1
setlocal
cd /d "%~dp0.."

rem ASCII only - see the note at the top of setup.bat.
rem Opens the window.  The console stays behind it: errors land here.

if not exist ".venv\Scripts\python.exe" (
  echo.
  echo   [!] not set up yet.  Double-click  scripts\setup.bat  first.
  echo.
  pause
  exit /b 1
)

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
set HF_HUB_DISABLE_SYMLINKS=1

rem Arguments pass through.  Pass the MT flag to use the fast engine.
".venv\Scripts\python.exe" talkaid.py %*
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
  echo.
  echo   [!] exited with code %RC%.  See the messages above.
  echo.
  pause
)
exit /b %RC%
