#!/usr/bin/env python3
"""노션 굽기와 Supabase 굽기를 같은 때 돌려 견준다. **파일을 안 쓰고 건수와 번호만 찍는다.**

    python tools/bake_compare.py [--json <저장소 밖 자리>]

원천을 Supabase 로 옮기기 전에, 그리고 의심스러울 때 돌린다 (2026-10-03 최현서 — 「같은 시점에 두 원천으로
구워 영역 · 사건 · 관계선 · 공식 발표의 수와 번호가 같은지 보고, 다르면 까닭을 적는다」).

**까닭 찾기.** Supabase 는 정제 배치가 돈 때의 노션이다. 그 뒤 노션에서 고친 줄은 다를 수밖에 없다. 그래서
노션 줄의 마지막 수정 시각과 Supabase 줄의 `notion_edited_at` 을 견줘 「동기화 뒤 바뀐 줄」 을 표마다 센다.
다른 사건이 그런 줄에서 나왔으면 「동기화 뒤 바뀜」, 아니면 「까닭 모름」 으로 가른다. 까닭 모름이 0 이어야
원천을 바꾼다.

열쇠는 둘 다 쓴다 — 노션 팀 토큰(읽기)과 Supabase 읽기 전용 열쇠. 찍는 것은 영토 id(가해 쪽 이름) · 사건 번호 ·
관계 id · 건수뿐이다. 조직명은 안 찍는다.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bake  # noqa: E402
import supa_source  # noqa: E402


def _when(s: str | None) -> float | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _quiet(_msg: str) -> None:
    pass


def stale_rows(n, sources: dict[str, str], src: supa_source.SupaSource) -> dict[str, set[str]]:
    """표마다 「Supabase 동기화 뒤 노션에서 바뀐 줄」 의 노션 페이지 id. 노션에만 있는 줄도 든다."""
    out: dict[str, set[str]] = {}
    for key, spec in supa_source.TABLES.items():
        if key not in sources:
            continue
        rows = src._get(
            f"/rest/v1/{spec['table']}?select=notion_id,notion_edited_at&limit=5000", profile="core")
        seen = {r["notion_id"]: _when(r.get("notion_edited_at")) for r in rows}
        bad: set[str] = set()
        for page in n.query_all(sources[key]):  # 차례대로. 병렬로 안 보낸다
            pid = page["id"]
            edited = _when(page.get("last_edited_time"))
            if pid not in seen or (edited and seen[pid] and edited > seen[pid] + 1):
                bad.add(pid)
        out[key] = bad
    return out


def page_of_events(n, sources: dict[str, str]) -> dict[str, str]:
    """사건 번호(LEAK-n · INC-n) → 노션 페이지 id."""
    out: dict[str, str] = {}
    for key in ("collect", "incident"):
        if key not in sources:
            continue
        for page in n.query_all(sources[key]):
            eid = bake.unique_id((page.get("properties") or {}).get("사건 ID"))
            if eid:
                out[eid] = page["id"]
    return out


def diff_lists(a: list[dict], b: list[dict], keys: tuple[str, ...]) -> dict:
    """id 로 짝지어 견준다. 한쪽에만 있는 id 와 칸마다 다른 id."""
    ia = {x["id"]: x for x in a}
    ib = {x["id"]: x for x in b}
    only_a = sorted(set(ia) - set(ib))
    only_b = sorted(set(ib) - set(ia))
    fields: dict[str, list[str]] = {}
    for i in sorted(set(ia) & set(ib)):
        for k in keys:
            if ia[i].get(k) != ib[i].get(k):
                fields.setdefault(k, []).append(i)
    return {"notion_only": only_a, "supabase_only": only_b, "fields": fields}


def main() -> int:
    ap = argparse.ArgumentParser(description="노션 굽기와 Supabase 굽기를 견줍니다")
    ap.add_argument("--json", help="자세한 결과를 JSON 으로 쓸 자리. 저장소 밖에 둡니다")
    args = ap.parse_args()

    dc = bake._load_dc_notion()
    sources = bake.load_sources()
    n = dc.Notion(verbose=False)
    src = supa_source.SupaSource()

    data_n = bake.bake(n, sources, _quiet)
    data_s = bake.bake(src, {k: k for k in (*bake.REQUIRED_SOURCES, *bake.OPTIONAL_SOURCES)}, _quiet)
    print(f"Supabase 가장 늦은 동기화 {(src.synced or '?')[:16]}Z")

    t_keys = ("name", "islandId", "raw", "posts", "threads", "since", "until", "actor")
    e_keys = tuple(sorted({k for e in data_n["events"] + data_s["events"] for k in e} - {"id"}))
    r_keys = tuple(sorted({k for r in data_n["relations"] + data_s["relations"] for k in r} - {"id"}))
    parts = {
        "영역": diff_lists(data_n["territories"], data_s["territories"], t_keys),
        "사건": diff_lists(data_n["events"], data_s["events"], e_keys),
        "관계선": diff_lists(data_n["relations"], data_s["relations"], r_keys),
        "공식 발표": diff_lists([e for e in data_n["events"] if e.get("kind") == "official"],
                            [e for e in data_s["events"] if e.get("kind") == "official"], ("territoryId",)),
    }
    counts = {
        "영역": (len(data_n["territories"]), len(data_s["territories"])),
        "사건": (len(data_n["events"]), len(data_s["events"])),
        "관계선": (len(data_n["relations"]), len(data_s["relations"])),
        "공식 발표": (sum(e.get("kind") == "official" for e in data_n["events"]),
                  sum(e.get("kind") == "official" for e in data_s["events"])),
    }

    # 같은 순간인데 글자만 다른 게시 시각 (노션 +09:00 · Supabase UTC)
    ev_n = {e["id"]: e for e in data_n["events"]}
    ev_s = {e["id"]: e for e in data_s["events"]}
    same_instant = [i for i in parts["사건"]["fields"].get("postedAt", [])
                    if _when(ev_n[i]["postedAt"]) == _when(ev_s[i]["postedAt"])]

    stale = stale_rows(n, sources, src)
    pages = page_of_events(n, sources)
    stale_pages = set().union(*stale.values()) if stale else set()
    diff_events = set(parts["사건"]["notion_only"]) | set(parts["사건"]["supabase_only"])
    for k, ids in parts["사건"]["fields"].items():
        if k == "postedAt":
            ids = [i for i in ids if i not in same_instant]
        diff_events |= set(ids)
    explained = {i for i in diff_events if pages.get(i) in stale_pages}
    unknown = sorted(diff_events - explained)

    print("\n건수 (노션 · Supabase)")
    for k, (a, b) in counts.items():
        print(f"  {k:5} {a:4} · {b:4}{'' if a == b else '  ← 다름'}")
    for k, p in parts.items():
        f = {kk: len(v) for kk, v in p["fields"].items()}
        if p["notion_only"] or p["supabase_only"] or f:
            print(f"\n{k}")
            if p["notion_only"]:
                print(f"  노션에만 {len(p['notion_only'])}: {', '.join(p['notion_only'][:15])}")
            if p["supabase_only"]:
                print(f"  Supabase 에만 {len(p['supabase_only'])}: {', '.join(p['supabase_only'][:15])}")
            for kk, v in sorted(f.items()):
                print(f"  칸 {kk} 다름 {v}")
    print(f"\n게시 시각 — 같은 순간인데 글자만 다름(시간대 표기) {len(same_instant)}건")
    print("동기화 뒤 노션에서 바뀐 줄 — " + " · ".join(f"{k} {len(v)}" for k, v in stale.items()))
    print(f"다른 사건 {len(diff_events)}건 = 동기화 뒤 바뀜 {len(explained)} + 까닭 모름 {len(unknown)}"
          + (f": {', '.join(unknown[:20])}" if unknown else ""))

    if args.json:
        out = Path(args.json).expanduser().resolve()
        if Path(__file__).resolve().parent.parent in out.parents:
            print("저장소 안에는 쓰지 않습니다", file=sys.stderr)
            return 1
        out.write_text(json.dumps({"counts": counts, "parts": parts, "same_instant": same_instant,
                                   "stale": {k: len(v) for k, v in stale.items()}, "unknown": unknown},
                                  ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if not unknown else 2


if __name__ == "__main__":
    raise SystemExit(main())
