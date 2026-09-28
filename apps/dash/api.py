"""화면이 부르는 자리. **노션 「검토 여부」 와 그에 딸린 「DB 반영」, 그리고 포럼 사건 줄만 씁니다.**

`serve.py` 가 이 모듈을 붙여 씁니다. 따로 돌리는 것이 아닙니다.

## 왜 서버가 대신 쓰나

브라우저가 노션을 직접 부르면 토큰이 브라우저에 있어야 합니다. 토큰은 최현서 권한으로
돌고 팀원에게 넘기지 않는 것이 규칙입니다. 여기서 대신 쓰면 토큰은 서버가 도는 자리에만
있고 화면에는 안 갑니다.

## 무엇만 쓰나

**「검토 여부」 를 쓰고, 규칙대로 「DB 반영」 을 맞춥니다.** 값은 세 가지(`미검토` ·
`사건 O` · `사건 X`) 만 받습니다. 그 밖의 칸도, 그 밖의 값도, 줄을 지우는 것도 안
합니다. **줄을 만드는 것은 포럼 사건 하나뿐입니다** (아래 「포럼 사건 받기」, 2026-09-23).
사람이 화면에서 미리 보고 누를 때만 오고, 미검토 · 공개 꺼짐으로 들어갑니다.

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


# ── 포럼 사건 받기 (2026-09-23) ─────────────────────────────────────────
#
# 포럼 킷이 낸 「칸 값」 을 수집 DB 에 **새 줄로** 올립니다. 위에서 「줄을 만들지 않는다」
# 고 적은 범위를 이것 하나만큼 넓혔습니다. 사람이 화면에서 미리 보고 누를 때만 옵니다.
#
# **배포판 `deploy/worker.js` 의 포럼사건받기() 와 같은 줄을 만듭니다.** UID 는 옛 길
# (kit_in.py → push.py) 과 같은 코드로 만듭니다. `packages/tests/test_포럼사건.py` 가 셋을
# 맞춰 봅니다. 본문은 안 받습니다.

포럼줄상한 = 20
_포럼본문값 = {"받음", "안 봄", "403"}
_제어 = dict.fromkeys(list(range(0x20)) + [0x7F], " ")


def _포럼글(v, n: int) -> str:
    return (v if isinstance(v, str) else "").translate(_제어).strip()[:n]


def 포럼줄검사(d) -> list[dict]:
    """킷이 보낸 것을 거릅니다. 못 받을 것이면 ValueError. worker.js 의 포럼줄검사() 와 같습니다."""
    import re
    from urllib.parse import urlparse

    if not isinstance(d, dict) or d.get("종류") != "darkchoco-forum-rows" or d.get("판") != 1:
        raise ValueError("포럼 킷이 낸 칸 값이 아닙니다")
    줄들 = d.get("줄") if isinstance(d.get("줄"), list) else []
    if not 줄들:
        raise ValueError("줄이 없습니다")
    if len(줄들) > 포럼줄상한:
        raise ValueError("한 번에 %d줄까지 받습니다" % 포럼줄상한)
    밖 = []
    for x in 줄들:
        x = x if isinstance(x, dict) else {}
        주소 = _포럼글(x.get("URL"), 2000)
        u = urlparse(주소)
        if u.scheme not in ("http", "https") or not u.netloc:
            raise ValueError("http 주소가 아닙니다: %s" % 주소[:80])
        신호 = x.get("한국 신호") if isinstance(x.get("한국 신호"), dict) else {}
        도메인 = [_포럼글(v, 100).lower() for v in (신호.get("도메인") or [])
                if isinstance(신호.get("도메인"), list)]
        도메인 = [v for v in 도메인 if re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)*\.kr", v)][:10]
        밖.append({
            "제목": _포럼글(x.get("제목"), 500),
            "URL": 주소,
            # JS 의 URL.host 와 맞춥니다 — 소문자, 기본 포트는 뺍니다
            "곳": u.netloc.lower().removesuffix(":443" if u.scheme == "https" else ":80"),
            "게시자": _포럼글(x.get("게시자"), 200),
            "날짜": _포럼글(x.get("날짜"), 60),
            "게시판": _포럼글(x.get("게시판"), 200),
            "본문": x.get("본문") if x.get("본문") in _포럼본문값 else "안 봄",
            "신호": {"도메인": 도메인, "한글": 신호.get("한글") is True,
                   "korea": 신호.get("korea") is True},
        })
    return 밖


def 포럼UID(x: dict) -> str:
    """옛 길과 **같은 코드**로 만듭니다. kit_in.py 가 킷 줄을 Item 으로 만드는 꼴 그대로입니다."""
    sys.path.insert(0, str(ROOT / "skills"))
    from collect.kit_in import src_id_of
    from dc_store import Item

    return Item(source="forum", venue=x["곳"], src_id=src_id_of(x["URL"], x["곳"]),
                actor=x["게시자"], target_org="", title=x["제목"][:120],
                post_url=x["URL"]).uid()


def 포럼근거(신호: dict) -> str:
    근거 = []
    if 신호["도메인"]:
        근거.append("설명문에 한국 도메인 '%s' (검토 필요)" % 신호["도메인"][0])
    if 신호["korea"]:
        근거.append("설명문에 'korea' 언급 (검토 필요)")
    if 신호["한글"]:
        근거.append("설명문에 한글 포함 (검토 필요)")
    근거.append("사람이 고른 글. 대상 조직은 검토하면서 채운다")
    return " · ".join(근거)


def 포럼줄속성(x: dict, uid: str, 오늘: str) -> dict:
    """노션 속성. worker.js 의 포럼줄속성() 과 같습니다."""
    def 글칸(v):
        return {"rich_text": [{"text": {"content": str(v or "")[:2000]}}]}

    p = {
        "자료 제목": {"title": [{"text": {"content": (x["제목"][:120] or "제목 없음")[:2000]}}]},
        "수집자": {"select": {"name": "자동"}},
        "검토 여부": {"select": {"name": "미검토"}},
    }
    if x["게시자"]:
        p["게시자 핸들"] = 글칸(x["게시자"])
    p["게시 플랫폼"] = 글칸(x["곳"])
    p["원문 URL"] = 글칸(x["URL"])
    날 = x["날짜"]
    if len(날) >= 10 and 날[4] == "-" and 날[7] == "-":
        p["게시 시각"] = {"date": {"start": 날}}
    p["수집일"] = {"date": {"start": 오늘}}
    p["게시 성격"] = {"select": {"name": "확인 못 함"}}
    p["소스"] = {"select": {"name": "포럼"}}
    p["UID"] = 글칸(uid)
    p["한국 관련"] = {"select": {"name": "미확인"}}
    p["한국 관련 근거"] = 글칸(포럼근거(x["신호"]))
    return p


def 포럼게시처칸(곳: str, 표, 선택지: list[str]) -> dict:
    """게시처 칸. worker.js 의 포럼게시처칸() 과 같습니다. 포럼 줄은 「명부 없음」 을 안 켭니다."""
    if 표 is None:
        return {}
    from hub.events import publisher
    return publisher.속성(표, 선택지, "포럼", 곳, "")


def 포럼사건받기(d) -> dict:
    from datetime import datetime, timedelta, timezone

    줄들 = [(x, 포럼UID(x)) for x in 포럼줄검사(d)]
    오늘 = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")
    n = _노션()
    조건 = []
    for x, uid in 줄들:
        조건 += [{"property": "UID", "rich_text": {"equals": uid}},
               {"property": "원문 URL", "rich_text": {"equals": x["URL"]}}]
    있는것 = n.request("POST", "/data_sources/%s/query" % _수집DB(),
                    {"filter": {"or": 조건}, "page_size": 100}) or {}
    본것 = set()
    for r in 있는것.get("results") or []:
        칸 = r.get("properties") or {}
        for k in ("UID", "원문 URL"):
            v = "".join(t.get("plain_text", "") for t in ((칸.get(k) or {}).get("rich_text") or []))
            if v:
                본것.add(v)
    # 게시처 — 포럼 명부로 맞춘다 (hub/events/publisher.py). **못 읽어도 줄은 올린다**
    from hub.events import publisher
    try:
        표 = publisher.명부표.노션에서(n, 갈래들=("포럼",))
        선택지 = publisher.선택지읽기(n, _수집DB())
    except Exception:  # noqa: BLE001
        표, 선택지 = None, []
    결과, 썼다 = [], 0
    for x, uid in 줄들:
        if uid in 본것 or x["URL"] in 본것:
            결과.append({"제목": x["제목"][:80], "결과": "겹침"})
            continue
        try:
            n.request("POST", "/pages", {
                "parent": {"type": "data_source_id", "data_source_id": _수집DB()},
                "properties": {**포럼줄속성(x, uid, 오늘), **포럼게시처칸(x["곳"], 표, 선택지)}})
            썼다 += 1
            본것.update((uid, x["URL"]))
            결과.append({"제목": x["제목"][:80], "결과": "올림"})
        except Exception as e:  # noqa: BLE001
            결과.append({"제목": x["제목"][:80], "결과": "실패 — %s" % str(e)[:120]})
    return {"ok": True, "썼다": 썼다, "결과": 결과}


def 처리(경로: str, 몸: bytes) -> tuple[int, dict]:
    """(HTTP 코드, 돌려줄 것). serve.py 가 부릅니다.

    **주소는 ASCII 로 둡니다.** 한글을 넣으면 브라우저가 퍼센트 인코딩해서 보내는데
    서버가 그것을 그대로 비교해 안 맞습니다. 코드 안 이름은 한글이어도 됩니다.
    """
    if 경로 == "/api/run":
        return _돌리기(몸)
    if 경로 == "/api/forum-rows":
        try:
            return 200, 포럼사건받기(json.loads(몸.decode("utf-8")))
        except (ValueError, UnicodeDecodeError) as e:
            return 400, {"오류": str(e)[:300]}
        except Exception as e:  # noqa: BLE001  노션이 막히거나 토큰이 없을 때
            return 502, {"오류": "%s: %s" % (type(e).__name__, str(e)[:300])}
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
