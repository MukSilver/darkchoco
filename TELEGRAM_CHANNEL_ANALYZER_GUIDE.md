# 텔레그램 채널 분석기 사용 가이드

이 도구는 로그인된 Telegram 사용자 계정으로 접근 가능한 채널·그룹의 메시지를 수집하고, JSON 데이터와 Markdown 기본 분석 보고서를 생성한다.

## 1. 제공 기능

| 파일 | 기능 |
|---|---|
| `test.py` | QR 코드로 최초 로그인하고 세션 파일 생성 |
| `check_login.py` | 기존 세션의 로그인 상태 확인 |
| `list_channels.py` | 접근 가능한 채널·슈퍼그룹 목록 출력 |
| `collect_messages.py` | 선택한 채널의 메시지를 JSON으로 수집 |
| `analyze_messages.py` | 수집 JSON을 분석해 Markdown 보고서 생성 |
| `TELEGRAM_LOGIN_GUIDE.md` | API 발급과 QR 로그인 상세 안내 |

## 2. 작업 폴더로 이동

PowerShell을 열고 다음 폴더로 이동한다.

```powershell
cd C:\Users\USER\OneDrive\scan\Pictures\Desktop\whitehat\darknets\telegram
```

가상환경을 활성화한다.

```powershell
..\.venv\Scripts\Activate.ps1
```

활성화 후 PowerShell 앞부분에 `(.venv)`가 표시되는지 확인한다.

## 3. 새 터미널에서 API 환경변수 설정

PowerShell 창을 닫으면 `$env:`로 설정한 API 정보가 사라진다. 새 터미널을 열 때마다 다음 값을 다시 설정해야 한다.

```powershell
$env:TELEGRAM_API_ID = "본인의_api_id"
$env:TELEGRAM_API_HASH = "본인의_api_hash"
```

실제 값을 화면에 출력하지 않고 설정 여부만 확인한다.

```powershell
if ($env:TELEGRAM_API_ID) { "API_ID 설정됨" } else { "API_ID 없음" }
if ($env:TELEGRAM_API_HASH) { "API_HASH 설정됨" } else { "API_HASH 없음" }
```

`api_hash`는 비밀번호처럼 취급하며 채팅, 캡처, 코드 또는 Git 저장소에 공개하지 않는다.

## 4. 로그인 확인

```powershell
python check_login.py
```

정상적인 경우 다음과 같이 출력된다.

```text
로그인 확인 성공
사용자 ID: ...
사용자명: ...
```

로그인된 세션이 없다고 나오면 QR 로그인을 실행한다.

```powershell
python test.py
```

생성된 `telegram_login_qr.png`를 열고 휴대폰 Telegram 앱에서 다음 메뉴로 스캔한다.

```text
설정 → 기기 → 데스크톱 기기 연결
```

로그인 성공 후 `telegram_session.session`이 생성된다. 이 파일이 유지되는 동안 QR 로그인을 반복할 필요가 없다.

## 5. 채널 목록 확인

```powershell
python list_channels.py
```

출력 정보:

```text
ID · 종류(채널/그룹) · username · 이름
```

특정 이름만 찾으려면 PowerShell 검색을 함께 사용한다.

```powershell
python list_channels.py | Select-String -Pattern "LeakBase"
```

분석할 채널의 `username` 또는 `ID`를 기록한다.

## 6. 메시지 수집

### username으로 수집

```powershell
python collect_messages.py LEAKBASE4 `
  --limit 1000 `
  --output .\output\leakbase4_messages.json
```

### t.me 주소로 수집

```powershell
python collect_messages.py https://t.me/LEAKBASE4 `
  --limit 1000 `
  --output .\output\leakbase4_messages.json
```

### 채널 ID로 수집

```powershell
python collect_messages.py -1001234567890 `
  --limit 1000 `
  --output .\output\target_messages.json
```

옵션 설명:

| 옵션 | 설명 |
|---|---|
| `channel` | 채널 username, `t.me` 주소 또는 채널 ID |
| `--limit` | 가져올 최대 메시지 수. 기본값은 1,000개 |
| `--output` | JSON 저장 경로 |

수집이 완료되면 다음 정보가 출력된다.

```text
채널: LeakBase
수집 메시지: 20개
저장 위치: ...\output\leakbase4_messages.json
```

요청한 `--limit`보다 메시지가 적게 수집되는 경우 채널에 실제로 보이는 메시지가 적거나, 과거 메시지가 삭제·제한됐을 수 있다.

### 파일을 덮어쓰지 않는 방법

채널마다 다른 출력 파일명을 사용한다.

```text
output/darkforums_messages.json
output/darkforums_chat_messages.json
output/leakbase4_messages.json
```

기본 출력 파일인 `output/channel_messages.json`만 반복 사용하면 이전 채널 데이터가 덮어써질 수 있다.

## 7. 기본 분석 보고서 생성

```powershell
python analyze_messages.py `
  --input .\output\leakbase4_messages.json `
  --output .\output\leakbase4_analysis.md
```

상위 키워드와 항목 수를 변경하려면 `--top`을 사용한다.

```powershell
python analyze_messages.py `
  --input .\output\leakbase4_messages.json `
  --output .\output\leakbase4_analysis.md `
  --top 30
```

기본 보고서에 포함되는 항목:

- 전체 메시지 수
- 텍스트·미디어 포함 메시지 수
- 조회수·전달 수 합계
- 주요 키워드
- 자주 등장하는 도메인
- 날짜별 게시량
- 조회수 상위 메시지

보고서를 연다.

```powershell
notepad .\output\leakbase4_analysis.md
```

또는 VS Code 탐색기에서 `output` 폴더를 새로 고친 후 파일을 연다.

## 8. OSINT 상세 분석 절차

`analyze_messages.py`는 빠른 기초 통계용이다. 조사 보고서 작성 시에는 생성된 JSON을 함께 검토해 다음 항목을 추가한다.

1. 채널 성격과 활성 상태
2. 운영자·지원 봇·반복 등장 핸들
3. 개인정보 및 한국 관련 유출 주장
4. 판매 품목·가격·결제·에스크로 방식
5. 연결된 Telegram 채널·포럼·판매 사이트·파일 호스팅
6. 포워딩·채널 이전·지원 계정 변경 흔적
7. 날짜별 주요 사건과 운영 인프라 변화
8. 사실, 판매자의 주장, 분석상 추정의 구분
9. 미디어·외부 링크·관리자 정보 등 확인하지 못한 항목

유출 데이터의 실명, 주소, 전화번호, 계좌, 주민번호 등 실제 개인정보는 보고서에 복사하지 않는다. 다음처럼 유형과 확인 사실만 기록한다.

```text
이름·주소·전화번호 형식의 개인정보 샘플 게시 확인. 데이터 진위는 미확인.
```

## 9. 출력 JSON 구조

수집 JSON의 기본 구조는 다음과 같다.

```json
{
  "channel": {
    "id": 1234567890,
    "title": "채널 이름",
    "username": "channel_username"
  },
  "collected_at": "수집 시각",
  "requested_limit": 1000,
  "message_count": 20,
  "messages": [
    {
      "id": 1,
      "date": "게시 시각",
      "text": "메시지 본문",
      "views": 0,
      "forwards": 0,
      "reply_count": 0,
      "has_media": false,
      "grouped_id": null,
      "sender_id": 1234567890
    }
  ]
}
```

## 10. 현재 수집기의 한계

현재 버전은 다음 항목을 직접 내려받지 않는다.

- 사진·영상·문서 등 미디어 원본
- 발신자의 username과 프로필
- 관리자 목록과 권한 변경 기록
- `forwarded from` 원본 메타데이터
- 답글·댓글의 전체 대화 관계
- 삭제된 메시지

따라서 JSON의 `has_media: true`는 첨부파일이 있었다는 의미일 뿐, 해당 파일의 내용을 확인했다는 의미가 아니다. 확인하지 않은 내용은 보고서에서 `미확인`으로 표시한다.

## 11. 문제 해결

### `KeyError: 'TELEGRAM_API_ID'`

현재 PowerShell에 API 환경변수가 없다. 다시 설정한다.

```powershell
$env:TELEGRAM_API_ID = "본인의_api_id"
$env:TELEGRAM_API_HASH = "본인의_api_hash"
```

### `ModuleNotFoundError: No module named 'telethon'`

가상환경이 활성화되지 않았거나 다른 Python을 사용하고 있다.

```powershell
..\.venv\Scripts\Activate.ps1
python -m pip show telethon
```

가상환경을 활성화하지 않고 직접 실행하려면 다음 경로를 사용한다.

```powershell
..\.venv\Scripts\python.exe .\list_channels.py
```

### 로그인된 세션이 없다고 나오는 경우

```powershell
python test.py
```

QR 로그인 후 다시 확인한다.

```powershell
python check_login.py
```

### 보고서가 보이지 않는 경우

```powershell
Get-ChildItem .\output
```

`output/`은 `.gitignore`에 포함되어 있어 Git 변경 목록에는 표시되지 않을 수 있지만 로컬 파일은 존재한다.

### 너무 많은 요청 또는 `FLOOD_WAIT`

Telegram API 요청을 짧은 시간에 반복하면 제한될 수 있다. 수집 프로그램을 반복 실행하지 말고 오류에 표시된 시간만큼 기다린다.

## 12. 보안 및 운영 주의사항

다음 파일과 값은 외부에 공개하거나 Git에 올리지 않는다.

- `api_hash`
- Telegram 인증 코드
- 2단계 인증 비밀번호
- `telegram_session.session`
- 유효한 QR 로그인 이미지
- 수집된 개인정보 원문

현재 `.gitignore`에는 다음 항목이 포함되어 있다.

```gitignore
.env
*.session
*.session-journal
telegram_login_qr.png
output/
__pycache__/
*.py[cod]
```

세션 파일은 로그인된 계정에 접근할 수 있는 인증정보다. 노출된 경우 Telegram 앱의 **설정 → 기기**에서 해당 세션과 의심스러운 세션을 즉시 종료한다.

조사 계정이 실제로 접근 권한을 가진 공개 채널 또는 가입된 채널만 수집하며, Telegram 이용약관과 관련 법률 및 조직의 조사 절차를 준수한다.

## 13. 전체 실행 예시

```powershell
cd C:\Users\USER\OneDrive\scan\Pictures\Desktop\whitehat\darknets\telegram

..\.venv\Scripts\Activate.ps1

$env:TELEGRAM_API_ID = "본인의_api_id"
$env:TELEGRAM_API_HASH = "본인의_api_hash"

python check_login.py
python list_channels.py | Select-String -Pattern "LEAKBASE4"

python collect_messages.py LEAKBASE4 `
  --limit 1000 `
  --output .\output\leakbase4_messages.json

python analyze_messages.py `
  --input .\output\leakbase4_messages.json `
  --output .\output\leakbase4_analysis.md `
  --top 30

notepad .\output\leakbase4_analysis.md
```

