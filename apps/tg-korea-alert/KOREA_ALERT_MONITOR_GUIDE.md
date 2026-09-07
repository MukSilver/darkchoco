# Telegram Korea Alert Monitor

`OsintCTI Threat Alert`와 `Data Leak Monitor`의 새 게시물 중 한국 관련 내용만 Discord로 전달한다.

## Discord 웹훅 만들기

1. Discord 서버에서 알림을 받을 채널을 연다.
2. 채널 이름 옆 톱니바퀴의 `채널 편집`을 선택한다.
3. `연동` > `웹후크` > `새 웹후크`를 선택한다.
4. 이름과 게시할 채널을 확인하고 `웹후크 URL 복사`를 누른다.
5. URL은 비밀번호처럼 취급하고 저장소나 채팅에 올리지 않는다.

웹훅 메뉴가 없다면 해당 서버에서 `웹후크 관리` 권한이 필요하다.

## 실행

처음 한 번 필요한 패키지를 설치한다.

```powershell
python -m pip install -r .\requirements.txt
```

기존 Telegram 로그인 환경변수와 Discord 웹훅을 PowerShell에 설정한다.

권장 방식은 대화형 설정 스크립트를 한 번 실행하는 것이다. 입력값은 화면에 표시되며 Git에서 제외된 `.env`에 저장된다.

```powershell
python .\setup_config.py
```

입력값을 화면에서 숨기려면 `python .\setup_config.py --hidden`을 사용한다. 숨김 모드에서는 키를 입력해도 문자나 별표가 표시되지 않는다.

그다음 Telegram 로그인을 한 번 완료하고 모니터를 실행한다.

```powershell
python .\test.py
python .\korea_alert_monitor.py
```

Discord 웹훅만 먼저 시험하려면 별도 PowerShell 창에서 다음을 실행한다. Telegram이나 SQLite에는 연결하지 않고 샘플 알림 한 건을 보낸 뒤 종료한다.

```powershell
python .\korea_alert_monitor.py --test-alert
```

키워드, DART, Gemini의 세 판별 단계를 모두 시험하고 Discord로 결과를 받으려면 다음을 실행한다.

```powershell
python .\test_classifier.py --discord
```

환경변수를 직접 설정하려면 다음 방식을 사용할 수도 있다.

```powershell
$env:TELEGRAM_API_ID="발급받은 API ID"
$env:TELEGRAM_API_HASH="발급받은 API Hash"
$env:DISCORD_WEBHOOK_URL="복사한 Discord 웹훅 URL"
python .\korea_alert_monitor.py
```

기본값은 username이 각각 `breachdetect`, `osint_cti`인 채널이다(코드의 `DEFAULT_CHANNELS` 순서). 실제 username이 달라지면 직접 지정한다.

```powershell
python .\korea_alert_monitor.py --channels channel_username_1 channel_username_2
```

공백이 있는 표시 이름은 따옴표로 감싼다.

```powershell
python .\korea_alert_monitor.py --channels "OsintCTI Threat Alert" "Data Leak Monitor"
```

첫 실행에서는 각 채널의 현재 최신 메시지 ID만 `alert_monitor.db`에 저장하고 기존 게시물을 보내지 않는다. 다음 실행부터는 프로그램이 꺼져 있던 동안 올라온 메시지도 마지막 처리 ID 이후부터 확인한다.

## 한국 관련 필터

한국어 국가·주요 도시명, `Korea`, `South Korea`, `Korean`, `KR`, `KOR`, 주요 도시 영문명, `.kr` 계열 도메인을 탐지한다. 단어 안에 우연히 포함된 `kr`은 탐지하지 않는다.

## 상시 실행

별도 서버 제품이 필수인 것은 아니지만 프로그램을 실행하는 장치는 켜져 있어야 한다. 개인 PC, NAS, 라즈베리파이, VPS 중 하나에서 실행할 수 있다. Windows에서는 작업 스케줄러로 로그인 또는 부팅 시 실행하도록 등록할 수 있다.

SQLite는 별도 설치가 필요 없으며 Python에 포함되어 있다. 처리 위치와 Discord 전송 기록은 프로젝트 루트의 `alert_monitor.db`에 저장된다.

## DART 및 Gemini 기업 판별

`.env`에 다음 키가 필요하다.

```text
DART_API_KEY=...
GEMINI_API_KEY=...
```

판별 순서는 명시적 한국 키워드·국가·`.kr` 도메인, DART 기업명, Gemini 순서다. DART 기업목록은 시작 시 SQLite로 내려받고 7일 동안 재사용한다. Gemini 판정 결과도 회사명별로 캐시한다. Gemini는 상세 조사나 웹 검색 없이 기업의 본사 국가만 짧게 반환한다. 기업명이 추출되면 이름만 보내고, 추출되지 않은 경우에도 이메일·IP 주소·긴 토큰을 마스킹한 본문 최대 1,200자만 사용한다.
