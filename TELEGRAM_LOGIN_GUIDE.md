# Telegram API 사용자 로그인 가이드

이 문서는 Telegram API 애플리케이션 생성 후 `api_id`와 `api_hash`를 등록하고, Telethon을 이용해 QR 코드로 사용자 계정에 로그인하는 방법을 설명한다.

> 이 방식은 BotFather에서 발급하는 Bot API 토큰 방식이 아니다. 개인 Telegram 사용자 계정으로 접속하는 MTProto API 방식이다.

## 1. Telegram API 애플리케이션 생성

1. 공식 Telegram 앱에서 사용할 계정을 만든다.
2. [my.telegram.org](https://my.telegram.org)에 접속한다.
3. 국가번호를 포함한 전화번호로 로그인한다.
4. **API development tools**를 선택한다.
5. 애플리케이션 정보를 입력한다.

예시:

```text
App title: My Telegram Client
Short name: mytelegramclient
URL: 안적어도 됨
Platform: Desktop
Description: Personal desktop application for testing the Telegram API.
```

6. 생성이 완료되면 화면에 표시되는 다음 두 값을 확인한다.

```text
App api_id
App api_hash
```

## 2. Python 환경 준비

PowerShell에서 이 문서가 있는 폴더로 이동한다.


가상환경을 사용한다면 먼저 활성화하고 필요한 패키지를 설치한다.

```powershell
python -m pip install telethon "qrcode[pil]"
```

## 3. API 키를 환경변수로 등록

현재 PowerShell 창에서만 사용할 환경변수를 설정한다.

```powershell
$env:TELEGRAM_API_ID = "본인의_api_id"
$env:TELEGRAM_API_HASH = "본인의_api_hash"
```

따옴표 안의 예시 문구를 실제 발급 값으로 교체한다. `api_id`는 숫자이고 `api_hash`는 문자열이다.

값을 노출하지 않고 등록 여부만 확인한다.

```powershell
if ($env:TELEGRAM_API_ID) { "API_ID 설정됨" } else { "API_ID 없음" }
if ($env:TELEGRAM_API_HASH) { "API_HASH 설정됨" } else { "API_HASH 없음" }
```

이 방식으로 설정한 환경변수는 현재 PowerShell 창을 닫으면 사라진다. 로그인 세션이 생성된 후에도 현재 코드가 클라이언트를 만들 때 두 환경변수를 읽으므로, 새 PowerShell 창에서는 다시 설정해야 한다.

## 4. QR 코드로 최초 로그인

다음 명령으로 QR 로그인 프로그램을 실행한다.

```powershell
python test.py
```

프로그램이 현재 폴더에 다음 이미지를 생성한다.

```text
telegram_login_qr.png
```

이미지를 연 다음 휴대폰 Telegram 앱에서 아래 메뉴로 이동한다.

```text
설정 → 기기 → 데스크톱 기기 연결
```

Telegram 앱의 스캐너로 QR 코드를 스캔한다. 일반 카메라 앱을 사용하지 않는다. QR 코드는 짧은 시간 후 만료되며, 만료되면 프로그램이 같은 파일 경로에 새 QR 이미지를 만든다. 이 경우 이미지를 다시 열거나 새로 고침한 후 스캔한다.

계정에 2단계 인증이 설정되어 있으면 터미널에서 비밀번호를 추가로 요구한다. 입력한 문자가 터미널에 표시되지 않는 것은 정상이다.

로그인에 성공하면 다음과 같은 결과가 출력된다.

```text
로그인 성공
사용자 ID: ...
사용자명: ...
```

## 5. 로그인 세션 확인

최초 로그인에 성공하면 현재 폴더에 다음 파일이 생성된다.

```text
telegram_session.session
```

로그인 상태를 확인한다.

```powershell
python check_login.py
```

정상적인 경우 `로그인 확인 성공`과 사용자 정보가 출력된다. 세션이 유효한 동안에는 QR 인증을 반복할 필요가 없다.

## 6. 파일별 역할

```text
telegram/
├── test.py                    # 최초 QR 로그인 및 세션 생성
├── check_login.py             # 기존 세션 로그인 상태 확인
├── TELEGRAM_LOGIN_GUIDE.md    # 이 문서
├── .gitignore                 # 민감 파일의 Git 등록 방지
├── telegram_session.session   # 로그인 후 생성되는 민감한 세션 파일
└── telegram_login_qr.png      # 로그인 과정에서 생성되는 임시 QR 이미지
```

QR 이미지는 로그인 성공 후 삭제해도 된다.

```powershell
Remove-Item -LiteralPath .\telegram_login_qr.png
```

`telegram_session.session`은 로그인 유지에 필요하므로 삭제하지 않는다.

## 7. 보안 주의사항

다음 정보는 외부에 공개하거나 Git에 커밋하지 않는다.

- `api_hash`
- Telegram 인증 코드
- 2단계 인증 비밀번호
- `telegram_session.session`
- 유효한 QR 로그인 이미지 또는 QR URL

현재 `.gitignore`에는 다음 항목이 포함되어 있다.

```gitignore
.env
*.session
*.session-journal
telegram_login_qr.png
__pycache__/
*.py[cod]
```

세션 파일은 API 키보다도 민감할 수 있다. 파일을 가진 사람이 해당 로그인 세션을 이용해 계정에 접근할 수 있으므로 전송하거나 업로드하지 않는다.

API 키나 세션이 노출된 경우 Telegram의 **설정 → 기기**에서 의심스러운 세션을 즉시 종료하고, API 애플리케이션과 키도 다시 발급하는 것을 권장한다.

