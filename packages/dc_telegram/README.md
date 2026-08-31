# dc_telegram

텔레그램 접속과 수집의 공용 부품입니다.

## 왜 만들었나

`tg-notion-report` 와 `tg-korea-alert` 가 같은 코드에서 복사돼 나온 뒤
각자 자라고 있었습니다. 확인 시점에 이렇게 벌어져 있었습니다.

| 파일 | 차이 |
|---|---|
| `TELEGRAM_LOGIN_GUIDE.md` | 완전 동일 |
| `check_login.py` · `list_channels.py` | 3줄 |
| `collect_messages.py` | **312줄** |

**어느 한쪽이 최신인 것이 아니라 서로 다른 기능이 붙어 있었습니다.**

- `tg-notion-report` (305줄) — 증분 수집, 원자적 쓰기, 채널·발신자·포워드 메타데이터
- `tg-korea-alert` (139줄) — 날짜 범위 필터, 타임존, `parse_channel` 의 끝 슬래시 처리

그래서 **둘 다 살려서 한 벌로 합쳤습니다.** 어느 쪽 기능도 버리지 않았습니다.

## 구성

| 파일 | 무엇 |
|---|---|
| `client.py` | 접속·채널명 정규화 |
| `collect.py` | 수집 본체 |
| `meta.py` | 채널·발신자·포워드·리액션 |
| `store.py` | 증분 병합·원자적 쓰기 |
| `timeutil.py` | 날짜·타임존 |

## 쓰는 법

```python
import asyncio
from pathlib import Path
from dc_telegram import collect_messages

# 증분 수집 + 메타데이터 (tg-notion-report 방식)
asyncio.run(collect_messages(
    "https://t.me/example",
    Path("out/example.json"),
    incremental=True,
))

# 날짜 범위 (tg-korea-alert 방식)
from dc_telegram import parse_day
asyncio.run(collect_messages(
    "@example",
    Path("out/example.json"),
    from_day=parse_day("2026-08-01"),
    to_day=parse_day("2026-08-27"),
    with_meta=False,
))
```

기본값은 `incremental=False` · `from_day=to_day=None` · `with_meta=True` 입니다.
앞의 둘이 꺼져 있어 어느 앱에서 불러도 예전 동작을 해치지 않습니다.
`with_meta` 만 켜져 있습니다. 발신자·포워드·리액션이 필요 없으면
`with_meta=False` 로 끕니다.

## 환경변수

```
TELEGRAM_API_ID
TELEGRAM_API_HASH
```

코드에 직접 적지 않습니다. 없으면 실행 시 바로 알려 줍니다.

## 테스트

```bash
python packages/tests/test_dc_telegram.py
```

`telethon` 이 없어도 순수 로직은 검증됩니다.

## 규칙

**이 패키지는 `apps/` 를 import 하지 않습니다.**
