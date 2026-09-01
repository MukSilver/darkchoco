r"""텔레그램. 채널에서 글을 모으고 노션 보고서로 냅니다.

`apps/tg-notion-report` 에서 왔습니다(2026-08-30 에 그 앱은 지웠습니다).
이수빈 님이 만든 것이고 **판정 로직은 한 글자도 안 바꿨습니다.**

    collect       실계정으로 채널에서 글을 가져옵니다 (telethon)
    analyze       972줄. 글을 깊게 봅니다
    summary       가볍게 셉니다
    report        노션 보고서로 냅니다
    safe_update   739줄. **손대면 안 되는 판정입니다**
    pipeline      위를 차례로 부릅니다
    monitor · channels · login

safe_update 가 지키는 것은 이겁니다 — 주소가 정확히 맞아야 하고, 후보가
0개거나 2개 이상이면 멈춥니다. 그것 때문에 엉뚱한 페이지를 덮은 적이
없습니다. 옮길 때 AST 를 견주어 바뀐 것이 없는지 확인했습니다.

━━━ 아래는 2026-09-01 에 되살린 것입니다 ━━━

통합 전 저장소(telegram-channel-monitor)의 README.md 와
TELEGRAM_CHANNEL_ANALYZER_GUIDE.md 가 대응 문서 없이 사라졌습니다.
두 문서를 통째로 되살리는 것은 이번 범위가 아니라서, **운영에 직접
걸리는 것만** 여기로 옮깁니다. 코드 옆에 두면 같이 안 사라집니다.

돌리는 법
─────────
hub 어댑터가 아닙니다. registry.py 는 hub/events/sources/ 안의 파일만
어댑터로 세고, dc.py 도 hub/events/run.py 도 이 폴더를 부르지 않습니다.
**스크립트를 직접 부릅니다.** 통합 전에도 같은 방식이었습니다.
docs/흐름.md 의 「events/telegram/ 9종으로 흡수」는 파일이 어디로 갔다는
말이지, dc.py 로 돈다는 말이 아닙니다.

    python hub/events/telegram/pipeline.py https://t.me/<채널>
    python hub/events/telegram/pipeline.py https://t.me/<채널> --apply-notion
    python hub/events/telegram/monitor.py                    # 목록 일괄

--apply-notion 을 빼면 미리보기입니다. 노션에 쓰지 않습니다.
`dc.py list` 에 보이는 telegram 은 hub/places 쪽 갈래로 다른 것입니다.

환경변수
────────
API ID·Hash 와 노션 토큰은 코드에 적지 않습니다. 사용자 환경변수로 둡니다.

    [Environment]::SetEnvironmentVariable("TELEGRAM_API_ID", "<값>", "User")
    [Environment]::SetEnvironmentVariable("TELEGRAM_API_HASH", "<값>", "User")
    [Environment]::SetEnvironmentVariable("NOTION_TOKEN", "<값>", "User")

PowerShell 창을 닫으면 `$env:` 로 준 값은 사라집니다. 새 터미널을 열
때마다 다시 설정하거나, 위처럼 "User" 범위에 저장합니다.

확인할 때 **값을 화면에 찍지 말고 설정 여부만** 봅니다. api_hash 는
비밀번호처럼 다룹니다. 채팅·캡처·코드·커밋 어디에도 넣지 않습니다.

    if ($env:TELEGRAM_API_ID) { "API_ID 설정됨" } else { "API_ID 없음" }
    if ($env:TELEGRAM_API_HASH) { "API_HASH 설정됨" } else { "API_HASH 없음" }

노션 토큰은 이 폴더의 스크립트가 NOTION_TOKEN 환경변수에서만 읽습니다
(report.py 와 safe_update.py 의 main). 다른 도구가 쓰는 토큰 파일
(~/.config/darkchoco/notion_token) 은 여기서는 안 봅니다.

채널 목록 만드는 법
───────────────────
monitor.py 는 이 폴더의 telegram_channels.txt 를 읽습니다. 한 줄에 주소
하나씩 적습니다. 빈 줄과 `#` 으로 시작하는 줄은 건너뜁니다.

    https://t.me/example_channel_1
    https://t.me/example_channel_2

이 파일은 .gitignore 로 막혀 있습니다. 무엇을 보고 있는지가 드러납니다.

노션 안전 규칙
──────────────
- 데이터 소스 이름은 기본이 `텔레그램 DB` 입니다
- 채널 주소를 담는 `주소`·`Address`·`채널 주소` 같은 열이 있어야 합니다
- 주소나 Telegram ID 가 **정확히** 일치하는 페이지가 1개일 때만 씁니다
- 후보가 0개이거나 여러 개이면 엉뚱한 페이지를 고치지 않도록 멈춥니다
- 사람이 쓴 본문과 손으로 관리하는 열은 자동으로 바꾸지 않습니다

주의사항
────────
- 공개 채널과 **합법적인 OSINT·CTI 조사 범위에서만** 씁니다
- `output/` 에는 **메시지 원문이 들어 있습니다.** 밖으로 내지 않습니다
- API Hash·노션 토큰·세션 파일(telegram_session.session)은 어디에도
  커밋하지 않습니다. 세션 파일 하나면 남이 그 계정으로 읽습니다.
  세션이 샜으면 텔레그램 앱의 설정 → 기기 에서 그 세션을 바로 끊습니다
"""
