@echo off
chcp 65001 > nul
rem chcp 가 한글 주석보다 먼저다. 더블클릭하면 콘솔이 cp949 로 시작하는데 이 파일은 UTF-8 이라,
rem 그 전에 한글 줄이 있으면 cmd 가 잘못 읽어 주석의 한 글자를 명령으로 돌리기도 한다 (2026-09-06 실측).
rem
rem 다른 배치가 불러 쓰는 공통 설정. 이것만 따로 실행하지 않는다.
rem 여기 한 곳만 고치면 나머지가 다 따라온다.
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

rem 레포 자리. 이 파일이 있는 폴더의 한 단계 위다
set "REPO=%~dp0.."
pushd "%REPO%" > nul
set "REPO=%CD%"
popd > nul

rem 파이썬
where py > nul 2>&1
if %ERRORLEVEL%==0 (set "PY=py -3") else (set "PY=python")

rem 수집 표. **레포 밖에 둔다.** 게시글 본문이 들어가는 파일이다.
rem run.py 와 같은 규칙이다. 환경변수가 있으면 그것이 먼저다.
rem 2026-09-07 에 표를 팀 레포 안 hub\data 로 합쳤다. 거기를 먼저 보고 없으면 옛 자리로 간다.
rem run.py 는 스스로 같은 순서로 찾는다. 여기 값은 「0 처음설정」 이 보여 주는 용도다.
set "DB=%REPO%\..\hub\data\darkchoco.db"
if not exist "%DB%" set "DB=%USERPROFILE%\data\darkchoco.db"
if defined DARKCHOCO_DB set "DB=%DARKCHOCO_DB%"

rem 프젝 폴더와 검증 큐. 사람마다 자리가 다르니 DARKCHOCO_PROJ 로 덮는다.
rem **한글 경로를 이 파일에 적지 않는다.** cmd 가 배치를 시작 코드페이지(더블클릭이면 cp949)로
rem 읽어서, UTF-8 한글이 든 set 줄이 온전히 안 읽힌다. _proj.py 가 PROJ= 와 QUEUE= 를 내고
rem 여기서는 그 줄을 그대로 set 한다. 2026-09-06.
for /f "delims=" %%l in ('%PY% "%~dp0_proj.py"') do set "%%l"

exit /b 0
