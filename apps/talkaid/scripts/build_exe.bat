@echo off
rem Console to UTF-8 so the Korean that Python prints renders.
rem The bat file itself stays ASCII - that is a separate problem.
chcp 65001 >nul 2>&1
setlocal
cd /d "%~dp0.."

rem ASCII only - see the note at the top of setup.bat.
rem
rem Builds a folder that runs WITHOUT Python.
rem Most teammates do NOT need this - if you already have Python,
rem scripts\setup.bat is lighter and has no antivirus trouble.

if not exist ".venv\Scripts\python.exe" (
  echo.
  echo   [!] run  scripts\setup.bat  first.
  echo.
  pause
  exit /b 1
)

echo.
echo   talkaid - build a Python-free copy
echo   ==========================================
echo.
echo   [*] installing pyinstaller  ^(build-time only^)
".venv\Scripts\python.exe" -m pip install --quiet pyinstaller --disable-pip-version-check
if errorlevel 1 goto :fail

echo   [*] building.  takes a minute or two
".venv\Scripts\pyinstaller.exe" talkaid.spec --noconfirm --distpath dist --workpath build
if errorlevel 1 goto :fail

rem Intermediate only.  No reason to keep 25 MB around.
if exist "build" rmdir /s /q "build"

echo.
echo   [*] done.  Hand over the whole  "dist\talkaid"  folder  ^(about 141 MB^).
echo.
echo   Models are NOT bundled.  The receiving PC downloads them on
echo   first run  ^(1.2 GB for MT only, 1.7 GB more for the LLM^).
echo.
echo   Antivirus may block it.  False positives on PyInstaller exes
echo   are a known problem.  If blocked, use scripts\setup.bat instead.
echo.
pause
exit /b 0

:fail
echo.
echo   [!] build failed ^(exit code %ERRORLEVEL%^).
echo.
pause
exit /b 1
