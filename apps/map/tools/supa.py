"""Supabase 를 읽는 자리. **열쇠는 여기서만 읽고, GET 만 보낸다.**

    python tools/supa_schema.py

열쇠는 파일 둘에 값만 하나씩 들어 있다. 노션 팀 토큰
(`NOTION_TOKEN_산출물.txt`)과 같은 꼴이다.

    ~/.config/darkchoco/SUPABASE_URL_산출물.txt
    ~/.config/darkchoco/SUPABASE_SERVICE_KEY_산출물.txt

다른 자리에 두었으면 `DC_SUPABASE_URL_FILE` · `DC_SUPABASE_KEY_FILE` 로 알려 준다.
**두 파일을 한 파일로 합치지 않는다** — 열쇠 사본이 늘어난다 (2026-09-23 최현서).

**`SUPABASE_SERVICE_KEY` 는 전권 열쇠다.** 모든 표를 쓰고 지울 수 있고 권한
설정(RLS)도 건너뛴다. 그래서 셋을 지킨다.

  1. **GET 만 보낸다.** 요청을 만드는 곳이 `get()` 하나이고 메서드가 박혀 있다.
     POST · PATCH · DELETE 를 보내는 코드를 두지 않는다
  2. **열쇠 값을 어디에도 찍지 않는다.** 오류 글에 섞여 나와도 가린다.
     프로젝트 주소도 안 찍는다
  3. **열쇠 파일이 저장소 안에 있으면 멈춘다.** 저장소는 공개될 수 있다

**나중에 읽기 전용 열쇠로 바꾼다** (2026-09-23 최현서). 그때는
`KEY_FILE_DEFAULT` 한 줄과 열쇠 파일만 바꾼다.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

CONFIG = Path.home() / ".config" / "darkchoco"

#: 파일 경로를 알려 주는 환경변수. 저장소에 `.env` 를 두지 않는다
URL_FILE_ENV = "DC_SUPABASE_URL_FILE"
KEY_FILE_ENV = "DC_SUPABASE_KEY_FILE"

#: 환경변수가 없을 때 보는 자리. 읽기 전용 열쇠로 바꿀 때 둘째 줄을 바꾼다
URL_FILE_DEFAULT = CONFIG / "SUPABASE_URL_산출물.txt"
KEY_FILE_DEFAULT = CONFIG / "SUPABASE_SERVICE_KEY_산출물.txt"

TIMEOUT = 20
RETRIES = 2

REPO = Path(__file__).resolve().parent.parent


class SupaError(Exception):
    def __init__(self, message: str, status: int = 0, code: str = ""):
        super().__init__(message)
        self.status = status
        self.code = code


def _read_one(env: str, default: Path, what: str) -> str:
    """값 하나만 든 파일을 읽는다. 앞뒤 빈칸과 줄바꿈은 뗀다."""
    raw = os.environ.get(env)
    path = Path(raw).expanduser().resolve() if raw else default.resolve()
    if path == REPO or REPO in path.parents:
        sys.exit(f"{what} 파일이 저장소 안에 있습니다. 저장소 밖으로 옮겨 주세요.")
    if not path.is_file():
        sys.exit(
            f"{what} 파일이 없습니다: {path.name}\n"
            f"  다른 자리에 두었으면 {env} 로 경로를 알려 주세요."
        )
    # 노션 토큰 파일처럼 BOM 이 붙어 있을 수 있다
    val = path.read_text(encoding="utf-8-sig").strip()
    if not val:
        sys.exit(f"{what} 파일이 비어 있습니다: {path.name}")
    return val


def load() -> tuple[str, str]:
    """(프로젝트 주소, 열쇠). 못 읽으면 어디가 문제인지 알리고 멈춘다."""
    url = _read_one(URL_FILE_ENV, URL_FILE_DEFAULT, "주소")
    key = _read_one(KEY_FILE_ENV, KEY_FILE_DEFAULT, "열쇠")
    return url.rstrip("/"), key


def _hide(text: str, key: str, url: str) -> str:
    """오류 글에 열쇠나 주소가 섞여 나와도 가린다."""
    for s in (key, url):
        if s:
            text = text.replace(s, "***")
    return text


def get(path: str, profile: str | None = None,
        accept: str = "application/json") -> dict | list:
    """GET 한 번. **이 모듈에서 요청을 만드는 곳은 여기 하나다.**

    `profile` 은 스키마 이름이다. Supabase 는 기본으로 `public` 만 연다.
    다른 스키마는 `Accept-Profile` 머리글로 고르고, 「Exposed schemas」 에
    없으면 PGRST106 이 온다.
    """
    url, key = load()
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Accept": accept}
    if profile:
        headers["Accept-Profile"] = profile
    req = urllib.request.Request(url + path, headers=headers, method="GET")

    last: Exception | None = None
    for attempt in range(RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = _hide(e.read().decode("utf-8", "replace"), key, url)
            code = ""
            try:
                j = json.loads(body)
                code = j.get("code", "")
                body = j.get("message", body)
            except ValueError:
                pass
            # 5xx 만 다시 해 본다. 4xx 는 다시 해도 같다
            if e.code >= 500 and attempt < RETRIES:
                time.sleep(2 * (attempt + 1))
                last = e
                continue
            raise SupaError(body[:300], e.code, code) from None
        except urllib.error.URLError as e:
            last = e
            if attempt < RETRIES:
                time.sleep(2 * (attempt + 1))
                continue
    raise SupaError(_hide(f"연결 실패: {last}", key, url)[:300])
