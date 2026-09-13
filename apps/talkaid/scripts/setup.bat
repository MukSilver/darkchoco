@echo off
rem Console to UTF-8 so the Korean that Python prints renders.
rem The bat file itself stays ASCII - that is a separate problem.
chcp 65001 >nul 2>&1
setlocal
cd /d "%~dp0.."

rem ============================================================
rem  talkaid - first-time setup.  Run this once.
rem
rem  ASCII only, on purpose.  Korean inside a .bat breaks on
rem  Korean Windows: cmd reads the file in the codepage it
rem  started with (cp949 on double-click) and multi-byte chars
rem  inside if(...) blocks shift the byte offsets, so a line
rem  splits mid-token.  The launcher bat under skills/ records the
rem  same bug.  kr-leak-alarm/scripts/*.bat avoid it by staying
rem  ASCII.  Korean instructions live in README.md instead.
rem ============================================================

rem run.bat calls this with /auto when .venv is missing.  In that case do not
rem pause at the end - the window is about to open on its own.
set "AUTO="
if /I "%~1"=="/auto" set "AUTO=1"

echo.
echo   talkaid - first-time setup
echo   ==========================================
echo.

where python >nul 2>&1
if errorlevel 1 goto :nopython

if not exist ".venv\Scripts\python.exe" (
  echo   [*] creating .venv  ^(first run only^)
  python -m venv .venv
  if errorlevel 1 goto :fail
)

echo   [*] installing requirements.txt
".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet --disable-pip-version-check
".venv\Scripts\python.exe" -m pip install -r requirements.txt --quiet --disable-pip-version-check
if errorlevel 1 goto :fail

echo   [*] downloading models and running one test sentence
echo.
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
rem Without this, huggingface_hub dies with WinError 1314 when
rem Windows Developer Mode is off (it cannot create symlinks).
set HF_HUB_DISABLE_SYMLINKS=1
".venv\Scripts\python.exe" setup.py
if errorlevel 1 goto :fail

echo.
if defined AUTO (
  echo   [*] setup done.  opening the window...
  echo.
  exit /b 0
)
echo   [*] done.  Now double-click  scripts\run.bat
echo.
pause
exit /b 0

:nopython
echo   [!] python not found in PATH.
echo       Install Python 3.10+ from https://www.python.org/downloads/
echo       IMPORTANT: tick "Add python.exe to PATH" during setup.
echo.
pause
exit /b 1

:fail
echo.
echo   [!] setup failed ^(exit code %ERRORLEVEL%^).
echo       Run these by hand to see the real error:
echo         python -m venv .venv
echo         .venv\Scripts\python.exe -m pip install -r requirements.txt
echo         .venv\Scripts\python.exe setup.py
echo.
pause
exit /b 1
