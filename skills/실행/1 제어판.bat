@echo off
chcp 65001 > nul
rem chcp 가 맨 앞이다. 더블클릭하면 콘솔이 cp949 로 시작하는데 이 파일은 UTF-8 이라 그 전의 한글 줄이 깨진다.
rem 제어판을 켠다. 더블클릭해서 쓴다.
rem 「0 처음설정」 이 설정을 다 확인했다고 하면 이것을 누른다.
rem 공통 배치 이름은 ASCII 다. 「_공통.bat」 일 때는 call 줄이 cp949 시작에서 깨졌다 (2026-09-06).
setlocal
call "%~dp0_common.bat"

%PY% -c "import questionary" 2>nul
if errorlevel 1 (
  echo.
  echo   questionary 가 없다. 먼저 아래를 한 번 돌린다.
  echo.
  echo       %PY% -m pip install -r "%REPO%\requirements.txt"
  echo.
  pause
  exit /b 1
)

%PY% "%REPO%\run.py"
