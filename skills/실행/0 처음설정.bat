@echo off
chcp 65001 > nul
rem chcp 가 맨 앞이다. 더블클릭하면 콘솔이 cp949 로 시작하는데 이 파일은 UTF-8 이라 그 전의 한글 줄이 깨진다.
rem 공통 배치 이름도 ASCII 다. 「_공통.bat」 일 때는 한글 마지막 바이트가 뒤의 따옴표를 삼켜 call 이 실패했다 (2026-09-06).
setlocal
call "%~dp0_common.bat"

echo.
echo   처음 설정
echo   ─────────────────────────────────────────────
echo   밖에 아무 요청도 걸지 않는다. 무엇이 있고 무엇이 없는지만 본다.
echo.

set "CONF=%USERPROFILE%\.config\darkchoco"
if not exist "%CONF%" mkdir "%CONF%"

set MISSING=0

call :check "%CONF%\telegram_channels" "읽을 텔레그램 채널 목록" "한 줄에 채널 하나. osint_cti 처럼 t.me/ 뒤의 것만"
call :check "%CONF%\discord_webhook"   "디스코드 웹훅 주소"      "알림을 보낼 채널의 웹훅 URL 한 줄"
call :check "%CONF%\discord_token"     "디스코드 봇 토큰"        "알림을 읽을 때 쓴다"
call :check "%CONF%\discord_channel"   "감시할 채널 번호"        "alert_watch 가 읽을 채널 ID 한 줄. run.py 는 보는데 여기서 빠져 있었다"
call :check "%CONF%\telegram_api"      "텔레그램 api_id/hash"    "첫 줄 api_id · 둘째 줄 api_hash"
call :check "%CONF%\notion_token"      "노션 토큰"               "9단계에서 쓴다"

echo.
echo   ─────────────────────────────────────────────
echo   파이썬 꾸러미
%PY% -c "import requests" 2>nul && (echo     requests   있다) || (echo     requests   없다.  pip install requests)
%PY% -c "import telethon" 2>nul && (echo     telethon   있다) || (echo     telethon   없다.  pip install telethon   ^(비공개 채널에만 필요^))

echo.
echo   수집 표
if exist "%DB%" (
  echo     있다   %DB%
  %PY% -c "import sqlite3,sys;c=sqlite3.connect(sys.argv[1]);print('    줄 %%d개' %% c.execute('select count(*) from items').fetchone()[0])" "%DB%" 2>nul
) else (
  echo     아직 없다. 처음 수집할 때 만들어진다
  echo     자리   %DB%
)

echo.
echo   검증 큐 폴더
if exist "%QUEUE%" (echo     있다   %QUEUE%) else (echo     아직 없다. 큐를 만들 때 생긴다)

echo.
if %MISSING% GTR 0 (
  echo   ─────────────────────────────────────────────
  echo   없는 것이 %MISSING%개 있다. 위에 적힌 자리에 파일을 만들면 된다.
  echo   **레포 안에 넣지 마라. 이 레포는 공개다.**
  echo.
  echo   설정 폴더를 열려면 아무 키나 누른다. 그냥 닫아도 된다.
  pause > nul
  explorer "%CONF%"
) else (
  echo   ─────────────────────────────────────────────
  echo   설정이 다 있다. 「1 제어판」 을 눌러도 된다.
  echo.
  pause
)
endlocal
exit /b 0

:check
if exist %1 (
  echo     있다   %~2
) else (
  echo     없다   %~2
  echo            %~1
  echo            %~3
  set /a MISSING+=1
)
exit /b 0
