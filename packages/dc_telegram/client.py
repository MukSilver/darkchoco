"""텔레그램 접속. 두 앱이 같은 세션 파일과 같은 환경변수를 씁니다."""

from __future__ import annotations

import os
from pathlib import Path

from telethon import TelegramClient

# 세션 파일은 앱 폴더가 아니라 실행 위치 기준입니다.
# 앱이 자기 자리를 정하려면 make_client(session=...) 로 넘기십시오.
SESSION_PATH = Path.cwd() / "telegram_session"


def parse_channel(value: str) -> str:
    """채널 입력을 하나의 형태로 맞춥니다.

    https://t.me/foo/ · t.me/foo · @foo · foo 를 전부 'foo' 로 만듭니다.
    끝 슬래시를 떼는 것은 tg-korea-alert 쪽에서 고친 부분입니다.
    """
    value = value.strip().rstrip("/")
    for prefix in ("https://t.me/", "http://t.me/", "t.me/", "@"):
        if value.startswith(prefix):
            value = value[len(prefix):]
            break
    return value.strip("/")


def make_client(session: Path | str | None = None) -> TelegramClient:
    """환경변수에서 자격 증명을 읽어 클라이언트를 만듭니다.

    TELEGRAM_API_ID 와 TELEGRAM_API_HASH 가 필요합니다.
    코드에 직접 적지 않습니다.
    """
    try:
        api_id = int(os.environ["TELEGRAM_API_ID"])
        api_hash = os.environ["TELEGRAM_API_HASH"]
    except KeyError as exc:
        raise RuntimeError(
            "TELEGRAM_API_ID 와 TELEGRAM_API_HASH 를 환경변수로 설정하십시오."
        ) from exc
    return TelegramClient(str(session or SESSION_PATH), api_id, api_hash)
