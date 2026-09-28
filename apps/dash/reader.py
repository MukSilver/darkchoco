#!/usr/bin/env python3
"""노션 속성을 값으로 옮기는 자리. **칸 이름을 모릅니다.**

무엇을 낼지는 `dbs.json` 이 정하고 여기는 **종류를 보고 옮기기만** 합니다.
그래서 DB 를 하나 더 얹을 때 이 파일을 안 고쳐도 됩니다.

`deploy/worker.js` 에 같은 구실을 하는 짝이 있습니다. 언어가 달라 두 벌인데,
**칸 목록은 `dbs.json` 한 장을 같이 읽어서** 어긋날 자리가 종류 처리뿐입니다.
전에는 칸 목록까지 두 벌이라 한쪽을 고치고 다른 쪽을 잊었습니다.

## 종류마다 무엇을 내나

    title · rich_text        글자 그대로
    select · status          선택지 이름
    multi_select             이름 목록. **값이 아니라 분류 이름입니다**
    date                     시작 날짜
    checkbox                 참 거짓
    number                   숫자
    unique_id                「LEAK-197」 꼴
    created_time · last_edited_time   시각
    formula · rollup         안에 든 것을 한 겹 벗겨 다시 본다
    **relation**             **개수만.** 가리키는 page id 를 그대로 내면
                             레지스트리 밖 DB 의 줄을 짚는 열쇠가 나갑니다
    **people**               **「기입됨 / 미기입」.** 실명이 들어가는 자리입니다
    files                    개수만. 파일 이름에 값이 섞입니다

## 게시처 DB 는 센 것만 냅니다 (2026-09-25)

`명부셈()` 이 게시처 DB 셋(포럼 · 랜섬웨어 · 텔레그램)의 줄을 받아 **건수만** 돌려줍니다.
이름 · 주소 · 담당자 · 한국 관련 유출 글은 화면과 구운 파일로 안 갑니다(반출경계표 7-1).
`deploy/worker.js` 에 같은 짝이 있고 `packages/tests/test_명부집계.py` 가 둘을 맞춰 봅니다.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

KST = timezone(timedelta(hours=9))

HERE = Path(__file__).resolve().parent
레지스트리자리 = HERE / "dbs.json"


def 레지스트리() -> dict:
    """`dbs.json` 을 읽습니다. 주석 칸(`_` 로 시작)은 그대로 둡니다."""
    with 레지스트리자리.open(encoding="utf-8") as f:
        return json.load(f)


def DB하나(열쇠: str) -> dict:
    """레지스트리에서 DB 하나를 꺼냅니다. 없으면 무엇이 있는지 같이 알립니다."""
    for d in 레지스트리().get("DB") or []:
        if d.get("열쇠") == 열쇠:
            return d
    있는것 = [d.get("열쇠") for d in 레지스트리().get("DB") or []]
    raise KeyError("dbs.json 에 %r 가 없습니다. 있는 것: %s" % (열쇠, " · ".join(있는것)))


def _글(조각들: list) -> str:
    return "".join(x.get("plain_text", "") for x in (조각들 or [])).strip()


def 값(속성: dict | None) -> Any:
    """노션 속성 하나를 값으로. 모르는 종류는 빈 문자열입니다.

    **모르는 종류를 지어내지 않습니다.** 노션이 새 종류를 내놓으면 빈칸이
    되고, 빈칸은 화면에서 보이므로 사람이 알아챕니다.
    """
    v = 속성 or {}
    t = v.get("type") or ""

    if t == "title":
        return _글(v.get("title"))
    if t == "rich_text":
        return _글(v.get("rich_text"))
    if t in ("select", "status"):
        return ((v.get(t) or {}).get("name")) or ""
    if t == "multi_select":
        return [x.get("name", "") for x in (v.get("multi_select") or [])]
    if t == "date":
        return ((v.get("date") or {}).get("start")) or ""
    if t == "checkbox":
        return bool(v.get("checkbox"))
    if t == "number":
        return v.get("number")
    if t == "url":
        return v.get("url") or ""
    if t == "unique_id":
        u = v.get("unique_id") or {}
        n = u.get("number")
        return "%s-%s" % (u.get("prefix") or "", n) if n is not None else ""
    if t in ("created_time", "last_edited_time"):
        return v.get(t) or ""

    # **개수만 냅니다.** page id 는 레지스트리 밖 DB 의 줄을 짚는 열쇠입니다
    if t == "relation":
        return len(v.get("relation") or [])
    if t == "files":
        return len(v.get("files") or [])

    # **실명이 들어가는 자리입니다.** 이름 대신 찼는지만 냅니다
    if t in ("people", "created_by", "last_edited_by"):
        것 = v.get(t)
        return "기입됨" if (것 if isinstance(것, list) else [것] if 것 else []) else "미기입"

    # 한 겹 벗겨 다시 봅니다. 안에 든 것이 위의 종류 중 하나입니다
    if t == "formula":
        f = v.get("formula") or {}
        ft = f.get("type") or ""
        return f.get(ft, "") if ft else ""
    if t == "rollup":
        r = v.get("rollup") or {}
        rt = r.get("type") or ""
        if rt == "array":
            return [값(x) for x in (r.get("array") or [])]
        return r.get(rt, "") if rt else ""

    return ""


def _사람자동(v: Any) -> str:
    """실명 선택지를 **사람 / 자동 / 미기입** 셋으로 접습니다.

    화면에서 쓸모 있는 것은 「누가」가 아니라 「기계가 넣었나 사람이 넣었나」
    입니다. 그 비율은 그대로 읽히면서 실명은 브라우저에 아예 안 실립니다.
    """
    s = (v or "").strip() if isinstance(v, str) else ""
    if not s or s == "미기입":
        return "미기입"
    return "자동" if s == "자동" else "사람"


def _있없(v: Any) -> str:
    """찼는지만 냅니다. 검증자·기록자·담당자처럼 **실명만 들어가는** 칸입니다."""
    if isinstance(v, str):
        return "기입됨" if v.strip() and v.strip() != "미기입" else "미기입"
    return "기입됨" if v else "미기입"


def _첫줄(v: Any) -> str:
    """줄글의 첫 줄만. 검증 요약처럼 1,500자가 넘는 칸이 있습니다."""
    s = v if isinstance(v, str) else ""
    return s.split("\n")[0][:120]


def _KST날(v: Any) -> str:
    """시각을 KST 날짜(YYYY-MM-DD)로. 텔레그램 · 집계처 시각은 UTC 라 그대로 자르면
    UTC 15시 이후 글이 하루 앞섭니다. 날짜만 있으면 그대로, 시간대가 없으면 앞 열 글자입니다."""
    s = v.strip() if isinstance(v, str) else ""
    if len(s) <= 10:
        return s
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return s[:10]
    return (d.astimezone(KST) if d.tzinfo else d).date().isoformat()


접개 = {"사람자동": _사람자동, "있없": _있없, "첫줄": _첫줄, "KST날": _KST날}


def 줄(페이지: dict, 칸들: list) -> dict:
    """노션 페이지 하나를 `dbs.json` 이 적은 대로 옮깁니다.

    `id` 는 늘 담습니다. 화면이 노션으로 가는 링크를 만드는 데 씁니다.
    """
    p = 페이지.get("properties") or {}
    out: dict[str, Any] = {"id": 페이지.get("id", "")}
    for c in 칸들:
        v = 값(p.get(c["노션"]))
        접 = c.get("접기")
        if 접:
            접함수 = 접개.get(접)
            if 접함수 is None:
                raise ValueError("모르는 접기 갈래입니다: %r (dbs.json)" % 접)
            v = 접함수(v)
        elif c.get("날짜만") and isinstance(v, str):
            v = v[:10]
        out[c["낼"]] = v
    return out


def 열이름들(칸들: list) -> list:
    """표의 열로 그릴 이름만. `안그림` 인 칸은 뺍니다 (거르개만 씁니다)."""
    return [c["낼"] for c in 칸들 if not c.get("안그림")]


# ── 게시처 DB 집계 (2026-09-25) ─────────────────────────────────────
확인일갈래 = ("7일 안", "30일 안", "30일 넘음", "빈칸")
_날꼴 = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# 「한국 관련 유출」 에 적힌 자리표시. 이것만 있는 줄은 안 셉니다
_자리표시 = frozenset({"미기입", "해당 없음", "없음", "-", "모름", "n/a"})
_건수꼴 = re.compile(r"(\d[\d,]*)\s*건")


def _갈래값(v: Any) -> str:
    """선택지 이름. 비었거나 모르는 꼴이면 「빈칸」."""
    return v.strip() if isinstance(v, str) and v.strip() else "빈칸"


def _확인일갈래(v: Any, 오늘: str) -> str:
    """오늘에서 며칠 지났나. 7일 안(앞날 포함) · 30일 안 · 30일 넘음 · 빈칸(없거나 틀린 날)."""
    s = v[:10] if isinstance(v, str) else ""
    if not _날꼴.match(s):
        return "빈칸"
    try:
        며칠 = (date.fromisoformat(오늘) - date.fromisoformat(s)).days
    except ValueError:
        return "빈칸"
    return "7일 안" if 며칠 <= 7 else "30일 안" if 며칠 <= 30 else "30일 넘음"


def 한국유출있나(v: Any) -> bool:
    """「한국 관련 유출」 에 실제로 무엇이 적혀 있나.

    자리표시(미기입 · 해당 없음)만 있는 줄, **「N건」 의 N 이 모두 0 인 기계 줄**은 안 셉니다
    (2026-09-25 최현서 「0건 줄은 빼고 셈」). 사람이 쓴 글은 셉니다.
    """
    if not isinstance(v, str):
        return False
    for 한줄 in v.splitlines():
        s = 한줄.strip()
        if not s or s.lower() in _자리표시:
            continue
        수들 = [int(x.replace(",", "")) for x in _건수꼴.findall(s)]
        if 수들 and not any(수들):
            continue
        return True
    return False


def 명부셈(페이지들: list, 칸: dict, 오늘: str) -> dict:
    """게시처 DB 줄들을 **건수로만** 셉니다. 이름 · 주소 · 담당자는 읽지도 않습니다.

    `칸` 은 dbs.json 「명부」.칸 — 상태 · 확인일 · 조사단계 · 한국유출 · DB반영 의 노션 칸 이름.
    """
    out = {"줄수": 0, "상태": {}, "조사단계": {}, "확인일": {k: 0 for k in 확인일갈래},
           "한국유출": 0, "DB반영": 0}
    for pg in 페이지들:
        p = pg.get("properties") or {}
        out["줄수"] += 1
        for 열쇠 in ("상태", "조사단계"):
            k = _갈래값(값(p.get(칸[열쇠])))
            out[열쇠][k] = out[열쇠].get(k, 0) + 1
        out["확인일"][_확인일갈래(값(p.get(칸["확인일"])), 오늘)] += 1
        if 한국유출있나(값(p.get(칸["한국유출"]))):
            out["한국유출"] += 1
        if 값(p.get(칸["DB반영"])) is True:
            out["DB반영"] += 1
    return out
