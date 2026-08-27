"""토큰 찾기.

세 곳이 각자 다른 방식을 쓰던 것을 하나로 모으되, 기존 설정을 깨지 않게
전부 계속 받습니다.

  1. NOTION_TOKEN_FILE 이 가리키는 파일   (권장)
  2. 관례적인 위치의 파일
  3. NOTION_TOKEN 환경변수                (allow_env=True 일 때만)

파일 방식을 권하는 이유는, 환경변수로 값을 넘기면 `docker inspect` 와
셸 히스토리에 남기 때문입니다. 파일은 권한으로 막을 수 있습니다.

skills 는 이 이유로 환경변수를 아예 받지 않습니다. 그 방침을 지키려면
allow_env=False 로 부릅니다.
"""

from __future__ import annotations

import os
from pathlib import Path

TOKEN_PLACES = [
    Path("/run/secrets/notion_token"),                            # 도커 관례
    Path.home() / ".config" / "darkchoco" / "notion_token",
    Path.home() / ".config" / "darkchoco" / "notion_token.txt",    # skills 가 쓰던 자리
    Path.cwd() / ".notion_token.txt",                              # skills 가 쓰던 자리
    Path.home() / ".notion_token",
]


def _places() -> list[Path]:
    env = os.environ.get("NOTION_TOKEN_FILE")
    return ([Path(env)] if env else []) + TOKEN_PLACES


def find_token_file() -> Path | None:
    """토큰 파일을 찾습니다. 없으면 None 입니다."""
    for p in _places():
        try:
            if p.is_file():
                return p
        except OSError:
            continue
    return None


def find_token(allow_env: bool = True) -> str:
    """토큰 문자열을 돌려줍니다. 못 찾으면 어디를 봤는지 알려 줍니다.

    allow_env=False 면 NOTION_TOKEN 환경변수를 보지 않습니다.
    """
    path = find_token_file()
    if path:
        token = path.read_text(encoding="utf-8").strip()
        if token:
            return token

    if allow_env:
        token = (os.environ.get("NOTION_TOKEN") or "").strip()
        if token:
            return token

    looked = ["  " + str(p) for p in _places()]
    if allow_env:
        looked.append("  환경변수 NOTION_TOKEN")

    raise RuntimeError(
        "노션 토큰을 찾지 못했습니다. 아래를 봤습니다.\n"
        + "\n".join(looked)
        + "\n\n파일을 하나 만들거나 NOTION_TOKEN_FILE 로 경로를 주십시오.\n"
        "도커면 -v <토큰파일>:/run/secrets/notion_token:ro 로 붙입니다."
    )
