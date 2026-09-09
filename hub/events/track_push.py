#!/usr/bin/env python3
"""집계처 한 판을 돌려 **노션 수집 DB 의 관측 칸**에 적습니다.

    python hub/events/track_push.py              미리보기. 노션에 안 씁니다
    python hub/events/track_push.py --apply      실제로 씁니다
    python hub/events/track_push.py --dry        요청도 안 보냅니다. 무엇을 볼지만 냅니다

## 왜 `collect.track agg` 와 따로 두나

`track agg` 는 로컬 SQLite 의 `items` 를 돌면서 결과를 `post_obs` 에 쌓습니다.
**GitHub Actions 는 실행마다 새 컨테이너라 그 표가 안 남습니다.** 그러면
「안 보임이 두 판 연속이면 사라진 것」 규칙이 영원히 성립하지 않습니다.

그래서 이 도구는 저장 자리를 바꿉니다.

    track agg          items(SQLite) 를 돌고 → post_obs(SQLite) 에 쌓는다
    track_push.py      노션 수집 DB 를 돌고 → 노션 관측 칸에 쓴다

**노션 자체가 이력입니다.** 직전 상태가 그 줄에 남아 있으므로, 이번 결과와 합치면
이력 표 없이도 「두 판 연속」 을 가릅니다. 로컬 `post_obs` 는 그대로 두고
사람 관측(`track obs`)도 지금처럼 로컬에서 넣습니다. **바뀌는 것은 집계처 갈래뿐입니다.**

## 사람이 적은 것을 덮지 않습니다

노션은 한 줄에 관측 하나만 담습니다. 집계처가 함부로 쓰면 사람이 Tor 로 보고 적은
값이 지워집니다. 그래서 아래 셋은 건너뜁니다.

    관측자가 「집계처」 가 아닌 줄        사람이 적은 것입니다
    게시 상태가 「공개됨」 · 「사라짐」    확정된 것입니다. 집계처가 뒤집지 않습니다
    UID 가 없는 줄                    이을 자리가 없습니다

## 무엇을 쓰나

    게시 상태     게시 중 · 안 보임 · 사라짐
    관측 시각     이번 판을 돈 시각
    관측자        집계처
    관측 근거     한 줄. 값이나 주소를 넣지 않습니다

집계처는 **있나 없나만** 압니다. 카운트다운도 공개 여부도 API 에 없습니다
(2026-09-06 실측, 칸 11개). 그래서 파일 수와 규모는 안 건드립니다.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# **표준 라이브러리를 먼저 잡아 둡니다.** 아래에서 도구 폴더를 경로에 잠깐 넣는데,
# 거기 `inspect.py` 가 있어서 표준 `inspect` 를 가립니다. 한 번 가려지면
# `sys.modules` 에 남아 경로를 빼도 안 돌아옵니다. `dataclasses` 가
# `inspect.signature` 를 부르므로 `collect.fetch` 를 들일 때 죽습니다.
import inspect  # noqa: F401
import dataclasses  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills"))

# **도구 폴더를 경로에 계속 두면 안 됩니다.** 거기 `inspect.py` 가 있어서 표준
# 라이브러리 `inspect` 를 가립니다. `dataclasses` 가 `inspect.signature` 를 부르므로
# `collect.fetch` 를 불러오는 순간 죽습니다. 그래서 노션 모듈을 들일 때만 잠깐 넣습니다.
_도구 = Path(__file__).resolve().parents[2] / "skills" / "skills" / "darkweb-verify-ko" / "tools"


def _노션():
    """notion 모듈을 들여옵니다. 경로는 넣었다 바로 뺍니다."""
    s = str(_도구)
    sys.path.insert(0, s)
    try:
        import notion
        return notion
    finally:
        if s in sys.path:
            sys.path.remove(s)

KST = timezone(timedelta(hours=9))

# 집계처가 손대도 되는 상태입니다. 이 밖은 확정이라 건너뜁니다.
열린상태 = ("", "게시 중", "안 보임")

# 집계처가 적은 줄인지 가르는 표시입니다.
집계처 = "집계처"


def 지금() -> str:
    return datetime.now(KST).replace(microsecond=0).isoformat()


def 수집DB() -> tuple[str, dict]:
    """수집 DB 의 data_source id 와 칸 목록. 같은 이름이 여럿이면 최신을 씁니다."""
    n = _노션()
    _call, search, title_of = n._call, n.search, n.title_of

    hits = [r for r in search("수집 DB") if r.get("object") == "data_source"
            and title_of(r).strip() == "수집 DB"]
    hits.sort(key=lambda r: r.get("last_edited_time", ""), reverse=True)
    if not hits:
        raise SystemExit("노션에서 「수집 DB」 를 못 찾았다")
    ds = hits[0]["id"]
    schema = _call("/data_sources/" + ds)["properties"]
    없는칸 = [c for c in ("관측 시각", "게시 상태", "관측자", "관측 근거")
             if c not in schema]
    if 없는칸:
        raise SystemExit(
            "수집 DB 에 칸이 없다: %s — 01_회의/노션DB_설계_후보_관측_20260906.md 대로 더한다"
            % " · ".join(없는칸))
    return ds, schema


def 값(p: dict, 칸: str):
    """노션 속성 하나를 파이썬 값으로. 없으면 None 입니다."""
    x = p.get(칸)
    if not x:
        return None
    t = x["type"]
    if t == "select":
        return x["select"]["name"] if x["select"] else ""
    if t == "rich_text":
        return "".join(s["plain_text"] for s in x["rich_text"]).strip()
    if t == "date":
        return (x["date"] or {}).get("start") or ""
    if t == "title":
        return "".join(s["plain_text"] for s in x["title"]).strip()
    if t == "number":
        return x["number"]
    return None


def 랜섬줄들(ds: str) -> list[dict]:
    """수집 DB 에서 소스가 랜섬인 줄. 읽기만 합니다."""
    _call = _노션()._call

    rows, cur = [], None
    body = {"page_size": 100}
    while True:
        if cur:
            body["start_cursor"] = cur
        d = _call("/data_sources/%s/query" % ds, "POST", body)
        for pg in d["results"]:
            p = pg["properties"]
            소스 = (값(p, "소스") or "")
            if "랜섬" not in 소스:
                continue
            uid = (값(p, "UID") or 값(p, "uid") or "").strip()
            rows.append({
                "page_id": pg["id"],
                "uid": uid,
                "대상 조직": 값(p, "대상 조직") or "",
                "게시 상태": (값(p, "게시 상태") or "").strip(),
                "관측자": (값(p, "관측자") or "").strip(),
                "관측 시각": (값(p, "관측 시각") or "").strip(),
            })
        if not d.get("has_more"):
            break
        cur = d.get("next_cursor")
    return rows


def 집계처판(dry: bool = False) -> set | None:
    """ransomware.live KR 한 판. 요청 한 번입니다. uid 집합을 냅니다.

    **0건이면 None 을 냅니다.** 비어서인지 꼴이 바뀌어서인지 못 가르므로
    아무것도 안 씁니다. `track agg` 도 같은 자리에서 멈춥니다.
    """
    import json

    from collect.fetch import Fetcher
    from collect.sources.ransomlive import FEEDS, to_item

    f = FEEDS["kr"]
    fe = Fetcher(dry=dry)
    try:
        code, body, _ = fe.get(f["url"])
    except Exception as e:
        print("못 받았다: %s" % e)
        return None
    if dry:
        print("dry run\n%s" % fe.report())
        return set()
    if code != 200 or not body:
        print("HTTP %s" % code)
        return None
    try:
        rows = json.loads(body)
    except ValueError as e:
        print("JSON 이 아니다: %s" % e)
        return None
    if not isinstance(rows, list):
        rows = rows.get("victims") or rows.get("data") or []
    if not rows:
        print("줄 0개. 비어서인지 꼴이 바뀌어서인지 확인할 것. **안 보임을 적지 않습니다.**")
        return None
    return {to_item(r, f, "kr").uid() for r in rows}


def 판정(이전상태: str, 보였나: bool) -> str:
    """이번 판의 결과와 직전 상태를 합쳐 새 상태를 냅니다.

    「안 보임」 한 번은 안 셉니다. 두 판 연속이어야 사라진 것으로 봅니다.
    직전이 이미 「안 보임」 인데 이번에도 안 보이면 「사라짐」 입니다.
    """
    if 보였나:
        return "게시 중"
    if 이전상태 == "안 보임":
        return "사라짐"
    return "안 보임"


def 쓰기(page_id: str, 상태: str, 시각: str, 근거: str) -> None:
    _call = _노션()._call
    _call("/pages/" + page_id, "PATCH", {"properties": {
        "게시 상태": {"select": {"name": 상태}},
        "관측 시각": {"date": {"start": 시각}},
        "관측자": {"rich_text": [{"text": {"content": 집계처}}]},
        "관측 근거": {"rich_text": [{"text": {"content": 근거}}]},
    }})


def main() -> int:
    ap = argparse.ArgumentParser(
        description="집계처 한 판을 노션 수집 DB 의 관측 칸에 적습니다")
    ap.add_argument("--apply", action="store_true", help="실제로 씁니다. 없으면 미리보기")
    ap.add_argument("--dry", action="store_true", help="집계처도 안 부릅니다")
    a = ap.parse_args()

    ds, _ = 수집DB()
    줄들 = 랜섬줄들(ds)
    print("수집 DB 의 랜섬 줄 %d" % len(줄들))

    보인것 = 집계처판(dry=a.dry)
    if 보인것 is None:
        print("::warning::집계처를 못 읽었습니다. 아무것도 안 씁니다")
        return 1
    if a.dry:
        return 0
    print("집계처가 보인 uid %d" % len(보인것))

    시각 = 지금()
    셈 = {"게시 중": 0, "안 보임": 0, "사라짐": 0}
    건너뜀 = {"사람 관측": 0, "확정 상태": 0, "uid 없음": 0}
    바뀐것 = []

    for r in 줄들:
        if not r["uid"]:
            건너뜀["uid 없음"] += 1
            continue
        if r["관측자"] and r["관측자"] != 집계처:
            건너뜀["사람 관측"] += 1
            continue
        if r["게시 상태"] not in 열린상태:
            건너뜀["확정 상태"] += 1
            continue

        새상태 = 판정(r["게시 상태"], r["uid"] in 보인것)
        셈[새상태] += 1
        if 새상태 != r["게시 상태"]:
            바뀐것.append((r["대상 조직"], r["게시 상태"] or "(빈칸)", 새상태))
        if a.apply:
            쓰기(r["page_id"], 새상태, 시각,
                 "집계처 목록 대조. 있나 없나만 봅니다")

    print("\n판정  게시 중 %d · 안 보임 %d · 사라짐 %d"
          % (셈["게시 중"], 셈["안 보임"], 셈["사라짐"]))
    print("건너뜀  사람 관측 %d · 확정 상태 %d · uid 없음 %d"
          % (건너뜀["사람 관측"], 건너뜀["확정 상태"], 건너뜀["uid 없음"]))

    if 바뀐것:
        print("\n바뀐 줄 %d" % len(바뀐것))
        for 이름, 전, 후 in 바뀐것[:20]:
            print("  %-40s %s → %s" % (이름[:40], 전, 후))
        if len(바뀐것) > 20:
            print("  … 그리고 %d 줄" % (len(바뀐것) - 20))
    else:
        print("\n바뀐 줄이 없습니다")

    if not a.apply:
        print("\n미리보기입니다. 실제로 쓰려면 --apply 를 줍니다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
