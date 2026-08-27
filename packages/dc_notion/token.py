"""토큰 찾기.

두 방식이 섞여 있던 것을 하나로 모으되, 둘 다 계속 받습니다.

  1. NOTION_TOKEN_FILE 이 가리키는 파일   (권장)
  2. 관례적인 위치의 파일
  3. NOTION_TOKEN 환경변수                (예전 방식, 계속 지원)

파일 방식을 권하는 이유는 환경변수가 프로세스 목록이나 로그에
묻어 나오기 쉬운 반면, 파일은 권한으로 막을 수 있기 때문입니다.
"""

from __future__ import annotations

import os
from pathlib import Path

TOKEN_PLACES = [
    Path("/run/secrets/notion_token"),                        # 도커 관례
    Path.home() / ".config" / "darkchoco" / "notion_token",
    Path.home() / ".notion_token",
]


def find_token_file() -> Path | None:
    """토큰 파일을 찾습니다. 없으면 None 입니다."""
    env = os.environ.get("NOTION_TOKEN_FILE")
    places = ([Path(env)] if env else []) + TOKEN_PLACES
    for p in places:
        try:
            if p.is_file():
                return p
        except OSError:
            continue
    return None


def find_token() -> str:
    """토큰 문자열을 돌려줍니다. 못 찾으면 어디를 봤는지 알려 줍니다."""
    path = find_token_file()
    if path:
        token = path.read_text(encoding="utf-8").strip()
        if token:
            return token

    token = (os.environ.get("NOTION_TOKEN") or "").strip()
    if token:
        return token

    env = os.environ.get("NOTION_TOKEN_FILE")
    places = ([Path(env)] if env else []) + TOKEN_PLACES
    raise RuntimeError(
        "노션 토큰을 찾지 못했습니다. 아래를 봤습니다.\n  "
        + "\n  ".join(str(p) for p in places)
        + "\n  환경변수 NOTION_TOKEN\n\n"
        "파일을 하나 만들거나 NOTION_TOKEN_FILE 로 경로를 주십시오.\n"
        "도커면 -v <토큰파일>:/run/secrets/notion_token:ro 로 붙입니다."
    )
