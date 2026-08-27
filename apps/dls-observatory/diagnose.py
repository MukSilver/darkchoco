#!/usr/bin/env python3
"""
연결 진단 도구.

  python diagnose.py                  기본 진단 (DB 전체 목록 + .env ID 검증)
  python diagnose.py --all            접근 가능한 페이지까지 전부 출력
  python diagnose.py --find 랜섬       이름으로 검색 (부분 일치)
  python diagnose.py --deep           모든 페이지 안을 뒤져 인라인 DB 찾기 (느림)
  python diagnose.py --id <32자리>     특정 ID 하나만 정밀 검사
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import notion as nt  # noqa: E402
from dls_fill import load_env  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

API = "https://api.notion.com/v1"


def call(token: str, method: str, path: str, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{API}{path}", data=data, method=method,
        headers={"Authorization": f"Bearer {token}",
                 "Notion-Version": nt.VERSION,
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode()), None
    except urllib.error.HTTPError as e:
        return None, (e.code, e.read().decode("utf-8", "replace"))
    except Exception as e:  # noqa: BLE001
        return None, (0, f"{e.__class__.__name__}: {e}")


def search_all(token: str, obj: str, query: str = "") -> list[dict]:
    """/search 를 끝까지 넘겨가며 전부 가져온다."""
    out, cursor = [], None
    while True:
        body: dict = {"filter": {"property": "object", "value": obj}, "page_size": 100}
        if query:
            body["query"] = query
        if cursor:
            body["start_cursor"] = cursor
        res, err = call(token, "POST", "/search", body)
        if err:
            print(f"  [X] search 실패 (HTTP {err[0]}): {err[1][:200]}")
            return out
        out.extend(res.get("results", []))
        if not res.get("has_more"):
            return out
        cursor = res["next_cursor"]


def plain(rich) -> str:
    return "".join(x.get("plain_text", "") for x in (rich or [])) or "(제목 없음)"


def page_title(p: dict) -> str:
    for prop in (p.get("properties") or {}).values():
        if prop.get("type") == "title":
            return plain(prop.get("title"))
    return "(제목 없음)"


def short(uid: str) -> str:
    return uid.replace("-", "")


def probe(token: str, raw: str) -> bool:
    """ID 하나를 DB → 페이지 → 블록 순으로 정밀 검사. 성공하면 True."""
    uid = raw.replace("-", "").strip()
    print(f"  대상 ID: {uid}")
    if len(uid) != 32:
        print(f"  [X] 32자리가 아닙니다 (현재 {len(uid)}자).")
        return False

    db, err = call(token, "GET", f"/databases/{uid}")
    if not err:
        sources = db.get("data_sources") or []
        print(f"  [O] 데이터베이스입니다 — '{plain(db.get('title'))}'")
        if sources:
            print(f"\n  데이터 소스 {len(sources)}개:")
            for i, s in enumerate(sources, 1):
                print(f"    {i}. {s.get('name')}   (id: {short(s['id'])})")
            ds, dserr = call(token, "GET", f"/data_sources/{short(sources[0]['id'])}")
            if not dserr:
                print(f"\n  '{sources[0].get('name')}' 의 칼럼 "
                      f"{len(ds.get('properties', {}))}개:")
                for name, p in ds.get("properties", {}).items():
                    print(f"    · {name}  ({p['type']})")
        print("\n  .env 설정:")
        print(f"     NOTION_DATABASE_ID={uid}")
        if len(sources) > 1:
            print(f"  ※ 데이터 소스가 {len(sources)}개라 dls_fill.py 실행 시")
            print("     --data-source 2 처럼 골라 쓸 수 있습니다.")
        return True
    print(f"  [X] databases/{uid} → HTTP {err[0]}")
    try:
        print(f"      {json.loads(err[1]).get('message', '')[:300]}")
    except Exception:  # noqa: BLE001
        print(f"      {err[1][:300]}")

    page, perr = call(token, "GET", f"/pages/{uid}")
    if not perr:
        print("\n  ★ 이건 데이터베이스가 아니라 '페이지' ID 입니다.")
        par = page.get("parent", {})
        print(f"     이 페이지의 부모: {par.get('type')} = "
              f"{short(str(par.get(par.get('type'), '')))}")
        # 2025-09-03 부터 행의 부모는 data_source_id 로 오고 database_id 가 함께 붙는다
        if par.get("type") in ("database_id", "data_source_id"):
            parent_db = short(par.get("database_id") or par.get("data_source_id"))
            if par.get("data_source_id"):
                print(f"     데이터 소스 ID: {short(par['data_source_id'])}")
            print(f"\n     ★★ 이 페이지는 DB 의 '행' 입니다. 부모 DB ID:")
            print(f"        {parent_db}")
            print(f"\n     이 DB 에 실제로 접근이 되는지 바로 확인합니다…\n")
            return probe(token, parent_db)

        # 페이지 안의 블록을 끝까지 훑는다 (중첩 컬럼/토글 안쪽까지 1단계 더)
        found = []

        def scan(block_id: str, depth: int = 0):
            cursor = None
            while True:
                q = f"?page_size=100" + (f"&start_cursor={cursor}" if cursor else "")
                kids, kerr = call(token, "GET", f"/blocks/{block_id}/children{q}")
                if kerr:
                    return
                for b in kids.get("results", []):
                    if b.get("type") == "child_database":
                        found.append(b)
                    elif b.get("has_children") and depth < 2:
                        scan(short(b["id"]), depth + 1)
                if not kids.get("has_more"):
                    return
                cursor = kids["next_cursor"]

        scan(uid)
        if found:
            print("\n     이 페이지 안에서 찾은 DB:")
            for b in found:
                name = b.get("child_database", {}).get("title") or "(제목 없음)"
                print(f"       {name}")
                print(f"         ID: {short(b['id'])}")
            print("\n     → 위 ID 를 .env 의 NOTION_DATABASE_ID 에 넣고")
            print("        python diagnose.py 를 다시 돌리세요.")
        else:
            print("\n     [X] 이 페이지 안에서 DB 블록을 찾지 못했습니다.")
            print("         페이지는 보이는데 안쪽 DB 가 안 보이는 상황이면,")
            print("         DB 자체에 별도로 연결을 걸어야 합니다.")
        return False

    blk, berr = call(token, "GET", f"/blocks/{uid}")
    if not berr:
        print(f"\n  ★ 블록입니다 (type={blk.get('type')}).")
        if blk.get("type") == "child_database":
            print("     child_database 블록이므로 이 ID 가 곧 DB ID 인데,")
            print("     databases/ 조회가 막힌 걸 보면 DB 에 연결이 안 걸려 있습니다.")
        return False

    print("\n  ★ DB·페이지·블록 어느 쪽으로도 접근이 안 됩니다")
    print("     = integration 에 이 항목이 공유돼 있지 않습니다.")
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="페이지 목록도 전부 출력")
    ap.add_argument("--find", default="", help="이름으로 검색 (부분 일치)")
    ap.add_argument("--deep", action="store_true", help="모든 페이지 안의 인라인 DB 탐색")
    ap.add_argument("--id", default="", help="이 ID 하나만 정밀 검사")
    args = ap.parse_args()

    load_env()
    token = os.environ.get("NOTION_TOKEN", "").strip()
    raw_id = os.environ.get("NOTION_DATABASE_ID", "").strip()

    if not token:
        print("[X] NOTION_TOKEN 이 비어 있습니다.")
        return 1

    me, err = call(token, "GET", "/users/me")
    if err:
        print(f"[X] 토큰이 거부됐습니다 (HTTP {err[0]}): {err[1][:200]}")
        return 1
    ws = me.get("bot", {}).get("workspace_name") or "(알 수 없음)"
    print(f"[O] 토큰 정상 — integration '{me.get('name')}' / 워크스페이스 '{ws}'\n")

    # --id 단독 검사
    if args.id:
        print("=" * 70)
        print("정밀 검사")
        print("=" * 70)
        return 0 if probe(token, args.id) else 1

    # --find 이름 검색
    if args.find:
        print("=" * 70)
        print(f"'{args.find}' 검색 결과")
        print("=" * 70)
        hits = 0
        for obj in ("database", "page"):
            for item in search_all(token, obj, args.find):
                title = plain(item.get("title")) if obj == "database" else page_title(item)
                if args.find.lower() not in title.lower():
                    continue
                hits += 1
                kind = "DB  " if obj == "database" else "페이지"
                print(f"  [{kind}] {title}")
                print(f"          ID: {short(item['id'])}")
        if not hits:
            print(f"  '{args.find}' 를 포함한 항목이 없습니다.")
            print("  → integration 에 공유되지 않았다는 뜻입니다.")
        return 0

    # 기본: DB 전체
    print("=" * 70)
    dbs = search_all(token, "database")
    print(f"접근 가능한 데이터베이스: {len(dbs)}개")
    print("=" * 70)
    for d in dbs:
        mark = "  ← .env" if short(d["id"]) == raw_id.replace("-", "") else ""
        print(f"  {plain(d.get('title')):<24} {short(d['id'])}"
              f"  ({len(d.get('properties', {}))}칼럼){mark}")

    pages = search_all(token, "page")
    print()
    print("=" * 70)
    print(f"접근 가능한 페이지: {len(pages)}개")
    print("=" * 70)
    if args.all:
        for p in pages:
            print(f"  {page_title(p):<40} {short(p['id'])}")
    else:
        for p in pages[:15]:
            print(f"  {page_title(p):<40} {short(p['id'])}")
        if len(pages) > 15:
            print(f"  … 외 {len(pages) - 15}개  (전부 보려면 --all)")

    # --deep: 페이지 안의 인라인 DB 탐색
    if args.deep:
        print()
        print("=" * 70)
        print(f"페이지 {len(pages)}개 내부의 인라인 DB 탐색 중… (시간이 좀 걸립니다)")
        print("=" * 70)
        known = {short(d["id"]) for d in dbs}
        extra = 0
        for i, p in enumerate(pages, 1):
            if i % 25 == 0:
                print(f"  … {i}/{len(pages)}")
            kids, kerr = call(token, "GET", f"/blocks/{short(p['id'])}/children?page_size=100")
            if kerr:
                continue
            for b in (kids or {}).get("results", []):
                if b.get("type") != "child_database":
                    continue
                bid = short(b["id"])
                if bid in known:
                    continue
                known.add(bid)
                extra += 1
                name = b.get("child_database", {}).get("title") or "(제목 없음)"
                print(f"  [신규] {name}  →  {bid}   (부모: {page_title(p)})")
        print(f"  탐색 완료 — 목록에 없던 DB {extra}개 발견")

    # .env ID 검증
    print()
    print("=" * 70)
    print(".env 의 NOTION_DATABASE_ID 검증")
    print("=" * 70)
    if not raw_id:
        print("  (비어 있음)")
        return 1
    ok = probe(token, raw_id)
    if ok:
        print("\n  → python dls_fill.py --schema 로 넘어가세요.")
        return 0

    print()
    print("=" * 70)
    print("DB 가 목록에 없을 때")
    print("=" * 70)
    print("  다른 DB 16개는 보이는데 특정 DB 하나만 안 보인다면,")
    print("  그 DB 에만 연결이 안 걸린 것입니다. 연결은 상속되지 않아서,")
    print("  다른 페이지 아래에 있는 DB 는 따로 추가해 줘야 합니다.")
    print()
    print("  계정 주인분께: 랜섬웨어 DB 를 열고 → 우측 상단 ⋯ → 연결 →")
    print(f"                '{me.get('name')}' 추가")
    print()
    print("  ※ 그 DB 가 다른 팀스페이스(teamspace)에 있다면, integration 이")
    print("     그 팀스페이스에 접근 권한이 있는지도 확인이 필요합니다.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
