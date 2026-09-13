@echo off
rem Console to UTF-8 so the Korean that Python prints renders.
rem The bat file itself stays ASCII - that is a separate problem.
chcp 65001 >nul 2>&1
setlocal
cd /d "%~dp0.."

rem ASCII only - see the note at the top of setup.bat.
rem
rem Opens the window WITHOUT a console.  The log lives inside the window now
rem (the "log" toggle at the bottom).  Anything printed before the window
rem exists goes to %TEMP%\talkaid.log instead.
rem
rem --once and --help print to a console, so those keep one.

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

echo %* | findstr /I /C:"--once" /C:"--help" /C:"-h" >nul
if not errorlevel 1 goto :console

rem start returns immediately, so this console closes right away.
start "" ".venv\Scripts\pythonw.exe" talkaid.py %*
exit /b 0

:console
".venv\Scripts\python.exe" talkaid.py %*
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
  echo.
  echo   [!] exited with code %RC%.  See the messages above.
  echo.
  pause
)
exit /b %RC%
