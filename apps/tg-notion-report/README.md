# Telegram Channel Monitoring & Notion Report Automation

공개 Telegram 채널의 신규 메시지를 수집하고, 채널 분석 보고서를 생성한 뒤 검증된 Notion 페이지에 자동으로 반영하는 도구입니다.

## 주요 기능

- Telegram API를 이용한 공개 채널 메시지 수집
- 기존 메시지를 제외한 신규 메시지 증분 수집
- 채널별 Markdown 분석 보고서 자동 생성
- Telegram 주소가 정확히 일치하는 Notion 페이지만 업데이트
- 일치 후보가 0개이거나 2개 이상이면 업데이트 중단
- 여러 채널 순차 모니터링 및 실행 로그 저장
- Windows 작업 스케줄러를 이용한 매일 09:00·18:00 자동 실행

## 설치

Python 3.10 이상에서 다음 명령을 실행합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 환경변수

Telegram API ID·Hash와 Notion 토큰은 코드에 직접 작성하지 않습니다. PowerShell에서 사용자 환경변수로 저장합니다.

```powershell
[Environment]::SetEnvironmentVariable("TELEGRAM_API_ID", "본인_API_ID", "User")
[Environment]::SetEnvironmentVariable("TELEGRAM_API_HASH", "본인_API_HASH", "User")
[Environment]::SetEnvironmentVariable("NOTION_TOKEN", "본인_NOTION_TOKEN", "User")
```

Telegram 로그인 세션은 각 사용자가 직접 생성해야 하며, 세션 파일은 GitHub에 올리지 않습니다.

## 채널 목록 입력

`telegram_channels.example.txt`를 복사해 `telegram_channels.txt`를 만들고 공개 채널 주소를 한 줄에 하나씩 입력합니다.

```text
https://t.me/example_channel_1
https://t.me/example_channel_2
```

빈 줄과 `#`으로 시작하는 줄은 무시합니다.

## 실행

단일 채널 전체 실행:

```powershell
python .\telegram_pipeline.py https://t.me/example_channel --apply-notion
```

목록에 등록된 여러 채널 실행:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\telegram_schedule.ps1 -Run
```

예약 실행 등록:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\telegram_schedule.ps1 -Install
```

## Notion 안전 규칙

- 데이터 소스 이름은 기본적으로 `텔레그램 DB`를 사용합니다.
- 채널 주소를 저장하는 `주소`, `Address` 또는 호환되는 URL 열이 필요합니다.
- 주소 또는 Telegram ID가 정확히 일치하는 페이지가 1개일 때만 자동 작성합니다.
- 일치하는 페이지가 없거나 여러 개이면 잘못된 페이지 수정을 막기 위해 업데이트를 중단합니다.
- 사람이 작성한 본문과 수동 관리 열은 자동으로 변경하지 않습니다.

## 주의사항

- 공개 채널과 합법적인 OSINT·CTI 조사 범위에서만 사용하세요.
- `output` 폴더에는 메시지 원문이 포함될 수 있으므로 외부에 공유하지 마세요.
- API Hash, Notion 토큰, Telegram 세션 파일은 절대 GitHub에 커밋하지 마세요.
