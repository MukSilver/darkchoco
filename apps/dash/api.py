"""화면이 부르는 자리. **노션 「검토 여부」 와, 그에 딸린 「DB 반영」 만 씁니다.**

`serve.py` 가 이 모듈을 붙여 씁니다. 따로 돌리는 것이 아닙니다.

## 왜 서버가 대신 쓰나

브라우저가 노션을 직접 부르면 토큰이 브라우저에 있어야 합니다. 토큰은 최현서 권한으로
돌고 팀원에게 넘기지 않는 것이 규칙입니다. 여기서 대신 쓰면 토큰은 서버가 도는 자리에만
있고 화면에는 안 갑니다.

## 무엇만 쓰나

**「검토 여부」 를 쓰고, 규칙대로 「DB 반영」 을 맞춥니다.** 값은 세 가지(`미검토` ·
`사건 O` · `사건 X`) 만 받습니다. 그 밖의 칸도, 그 밖의 값도, 줄을 만들거나 지우는
것도 안 합니다.

「DB 반영」 은 지도 · RAG · 가이드가 같이 보는 공개 스위치입니다. 2026-09-23 부터
검토가 그것을 이렇게 움직입니다 (`공개로()` · `DEV.md` 같은 날 판단 기록).

    미검토 · 사건 X → 사건 O     켠다
    사건 O · 빈칸  → 사건 O     안 건드린다   일부러 꺼 둔 것을 되살리지 않는다
    무엇이든      → 사건 X     끈다
    무엇이든      → 미검토     끈다

**배포판 `deploy/worker.js` 에 같은 규칙이 JS 로 한 벌 더 있습니다.** 한쪽만 고치면
로컬과 배포가 다르게 움직입니다. `packages/tests/test_공개규칙.py` 가 둘을 맞춰 봅니다.

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


def 공개로(전: str, 후: str) -> bool | None:
    """「검토 여부」 가 전 → 후 로 바뀔 때 「DB 반영」 을 어떻게 하나.

    True 는 켠다, False 는 끈다, None 은 안 건드린다.

    **켜는 것은 사건 O 로 새로 들어갈 때뿐입니다.** 「DB 반영 = 꺼짐」 은 두 뜻입니다 —
    아직 검토 전이거나, 사건인데 일부러 안 내보내는 것(옛 「일부러 반출하지 않음」).
    이미 사건 O 인 줄에서 O 를 한 번 더 누른 것으로 켜면 뒤엣것이 무너집니다.
    빈칸은 화면이 사건 O 로 세므로 사건 O 로 봅니다.

    끄는 쪽은 조건이 없습니다. 안전한 방향입니다.
    """
    if 후 in ("사건 X", "미검토"):
        return False
    if 후 == "사건 O" and 전 in ("미검토", "사건 X"):
        return True
    return None


def 검토바꾸기(page_id: str, 값: str) -> dict:
    """노션 한 줄의 「검토 여부」 를 바꾸고, 규칙대로 「DB 반영」 을 맞춥니다.

    그 두 칸 말고는 안 건드립니다. **전 값은 노션에서 읽습니다.** 화면이 보낸
    값을 믿으면, 화면이 낡았을 때 일부러 꺼 둔 줄을 켤 수 있습니다.
    """
    if 값 not in 검토값:
        raise ValueError("받지 않는 값입니다: %r" % 값)
    page_id = (page_id or "").strip()
    # 노션 page id 는 32자 16진수(붙임표가 있을 수 있습니다). 꼴이 아니면 부르지 않습니다.
    민 = page_id.replace("-", "")
    if len(민) != 32 or any(c not in "0123456789abcdefABCDEF" for c in 민):
        raise ValueError("page id 꼴이 아닙니다")

    전줄 = _노션().page(page_id)
    # **수집 DB 줄이 아니면 안 씁니다.** 「DB 반영」 은 검증 DB 에도 있어서, page id
    # 만 맞으면 남의 DB 의 공개 스위치를 건드릴 수 있습니다. 칸 이름으로 가리면
    # 그쪽에 같은 이름 칸이 생기는 날 뚫리므로 줄의 소속으로 가립니다.
    소속 = ((전줄.get("parent") or {}).get("data_source_id") or "").replace("-", "").lower()
    if 소속 != _수집DB().replace("-", "").lower():
        raise ValueError("수집 DB 줄이 아닙니다")
    칸 = 전줄.get("properties") or {}
    if "검토 여부" not in 칸 or "DB 반영" not in 칸:
        raise ValueError("수집 DB 에 「검토 여부」 · 「DB 반영」 칸이 없습니다. 이름이 바뀌었나 봅니다")
    전 = ((칸["검토 여부"] or {}).get("select") or {}).get("name") or ""
    전반영 = bool((칸["DB 반영"] or {}).get("checkbox"))

    공개 = 공개로(전, 값)
    쓸것 = {"검토 여부": {"select": {"name": 값}}}
    if 공개 is not None:
        쓸것["DB 반영"] = {"checkbox": 공개}
    # **한 번에 씁니다.** 둘로 나누면 앞엣것만 되고 뒤엣것이 실패했을 때
    # 사건 O 인데 공개가 안 켜진 줄이 남습니다
    _노션().request("PATCH", "/pages/" + page_id, {"properties": 쓸것})
    return {"ok": True, "page_id": page_id, "검토": 값,
            "공개": 공개, "DB반영": 전반영 if 공개 is None else 공개}


def 처리(경로: str, 몸: bytes) -> tuple[int, dict]:
    """(HTTP 코드, 돌려줄 것). serve.py 가 부릅니다.

    **주소는 ASCII 로 둡니다.** 한글을 넣으면 브라우저가 퍼센트 인코딩해서 보내는데
    서버가 그것을 그대로 비교해 안 맞습니다. 코드 안 이름은 한글이어도 됩니다.
    """
    if 경로 == "/api/run":
        return _돌리기(몸)
    if 경로 == "/api/status":
        import run_jobs
        return 200, run_jobs.상태()
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


def _돌리기(몸: bytes) -> tuple[int, dict]:
    """정해진 일감 하나를 돌립니다. **화면은 열쇠만 보냅니다.**

    무엇을 돌릴지는 `run_jobs.일감()` 이 정합니다. 화면이 명령이나 인자를 넣지
    못합니다. 목록에 없는 열쇠는 그냥 400 입니다.
    """
    import run_jobs

    try:
        d = json.loads(몸.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return 400, {"오류": "json 이 아닙니다"}
    if not isinstance(d, dict):
        return 400, {"오류": "json 이 객체가 아닙니다"}
    됐나, 왜 = run_jobs.시작(str(d.get("열쇠") or ""))
    if not 됐나:
        return 409 if "돌고 있" in 왜 else 400, {"오류": 왜}
    return 200, run_jobs.상태()
