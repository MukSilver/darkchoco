"""화면이 부르는 자리. **노션 「검토 여부」 한 칸만 씁니다.**

`serve.py` 가 이 모듈을 붙여 씁니다. 따로 돌리는 것이 아닙니다.

## 왜 서버가 대신 쓰나

브라우저가 노션을 직접 부르면 토큰이 브라우저에 있어야 합니다. 토큰은 최현서 권한으로
돌고 팀원에게 넘기지 않는 것이 규칙입니다. 여기서 대신 쓰면 토큰은 서버가 도는 자리에만
있고 화면에는 안 갑니다.

## 무엇만 쓰나

**「검토 여부」 하나뿐입니다.** 값도 세 가지(`미검토` · `사건 O` · `사건 X`) 만 받습니다.
그 밖의 칸도, 그 밖의 값도, 줄을 만들거나 지우는 것도 안 합니다.

범위를 이렇게 좁혀 두는 이유는 이 자리가 **인증 없이 열려 있기 때문**입니다.
127.0.0.1 에만 붙지만 같은 PC 의 다른 프로그램은 부를 수 있습니다. 무엇을 할 수 있는지가
좁으면 잘못 불려도 되돌릴 수 있습니다 — 사람이 노션에서 값을 되돌리면 그만입니다.

**임의 명령은 실행하지 않습니다.** 화면의 명령 단추는 복사만 합니다. 그것과 이것은
위험이 전혀 다릅니다.

## 다른 탭이 부르는 것을 막습니다

브라우저의 아무 웹페이지나 이 주소로 요청을 보낼 수 있습니다(CSRF). `Origin` 헤더가
우리 자리인지 보고 아니면 막습니다. 게다가 `Content-Type` 을 json 으로 요구해서
form 으로 몰래 보내는 길도 막습니다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages"))
sys.path.insert(0, str(ROOT))

# 받는 값은 이 셋뿐입니다. 노션 선택지와 글자가 같아야 합니다.
검토값 = {"미검토", "사건 O", "사건 X"}

_n = None


def _노션():
    global _n
    if _n is None:
        from dc_notion import Notion

        _n = Notion(verbose=False, allow_env_token=False)
    return _n


def _수집DB() -> str:
    from hub.events.push import 수집DB

    return 수집DB


def 검토바꾸기(page_id: str, 값: str) -> dict:
    """노션 한 줄의 「검토 여부」 를 바꿉니다. 그 칸 말고는 안 건드립니다."""
    if 값 not in 검토값:
        raise ValueError("받지 않는 값입니다: %r" % 값)
    page_id = (page_id or "").strip()
    # 노션 page id 는 32자 16진수(붙임표가 있을 수 있습니다). 꼴이 아니면 부르지 않습니다.
    민 = page_id.replace("-", "")
    if len(민) != 32 or any(c not in "0123456789abcdefABCDEF" for c in 민):
        raise ValueError("page id 꼴이 아닙니다")

    _노션().request("PATCH", "/pages/" + page_id,
                   {"properties": {"검토 여부": {"select": {"name": 값}}}})
    return {"ok": True, "page_id": page_id, "검토": 값}


def 처리(경로: str, 몸: bytes) -> tuple[int, dict]:
    """(HTTP 코드, 돌려줄 것). serve.py 가 부릅니다."""
    # **주소는 ASCII 로 둡니다.** 한글을 넣으면 브라우저가 퍼센트 인코딩해서 보내는데
    # 서버가 그것을 그대로 비교해 안 맞습니다. 코드 안 이름은 한글이어도 됩니다.
    if 경로 != "/api/review":
        return 404, {"오류": "그런 자리가 없습니다"}
    try:
        d = json.loads(몸.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return 400, {"오류": "json 이 아닙니다"}
    if not isinstance(d, dict):
        return 400, {"오류": "json 이 객체가 아닙니다"}
    try:
        return 200, 검토바꾸기(str(d.get("page_id") or ""), str(d.get("검토") or ""))
    except ValueError as e:
        return 400, {"오류": str(e)}
    except Exception as e:  # noqa: BLE001  노션이 막히거나 토큰이 없을 때
        return 502, {"오류": "%s: %s" % (type(e).__name__, str(e)[:300])}
