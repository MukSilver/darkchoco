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
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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


접개 = {"사람자동": _사람자동, "있없": _있없, "첫줄": _첫줄}


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
