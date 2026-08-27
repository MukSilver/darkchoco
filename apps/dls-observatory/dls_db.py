#!/usr/bin/env python3
"""
DLS 관측 DB 관리 도구 (호스트에서 실행).

  python dls_db.py init                      DB 파일 생성 (dls.sqlite3)
  python dls_db.py ingest probe.json         Tor 수집 결과 적재
  python dls_db.py ingest-cache              .cache 의 API 응답 적재
  python dls_db.py stats                     현황 요약
  python dls_db.py list --status offline     현재 상태 목록
  python dls_db.py history "THE MATRIX"      한 사이트의 전체 이력
  python dls_db.py changes --since 2026-08-01  상태가 바뀐 지점만
  python dls_db.py addresses "lockbit3"      주소 변경 이력
  python dls_db.py kr                        한국 관련 유출
  python dls_db.py export merged.json        노션 반영용으로 내보내기

DB 는 호스트에만 둡니다. VM 은 probe.json 만 만들고, 적재는 여기서 합니다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db as D  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except (AttributeError, ValueError):
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = os.path.join(HERE, "dls.sqlite3")


def p(path: str) -> str:
    return path if os.path.isabs(path) else os.path.join(HERE, path)


# --------------------------------------------------------------------------
def cmd_init(db: D.DLSDatabase, args) -> int:
    print(f"[DB] {db.path}")
    tables = [r[0] for r in db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','view') "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    print(f"  테이블/뷰 {len(tables)}개: {', '.join(tables)}")
    return 0


def cmd_ingest(db: D.DLSDatabase, args) -> int:
    path = p(args.file)
    if not os.path.exists(path):
        print(f"[!] 파일이 없습니다: {path}", file=sys.stderr)
        return 1
    print(f"[적재] {path}")
    D.ingest_probe(db, path)
    print("\n[현황]")
    for k, v in db.stats().items():
        print(f"  {k:<14} {v}")
    return 0


def cmd_ingest_cache(db: D.DLSDatabase, args) -> int:
    """sources.py 가 남긴 .cache 폴더의 API 응답을 그대로 적재한다."""
    cache = p(args.cache)
    if not os.path.isdir(cache):
        print(f"[!] 캐시 폴더가 없습니다: {cache}", file=sys.stderr)
        print("    dls_fill.py 를 한 번 실행하면 생깁니다.", file=sys.stderr)
        return 1

    files = sorted(os.listdir(cache))
    done = {"groups": 0, "victims": 0, "look": 0}
    for fn in files:
        url = urllib.parse.unquote(fn[:-5] if fn.endswith(".json") else fn)
        try:
            with open(os.path.join(cache, fn), encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception as exc:  # noqa: BLE001
            print(f"  [!] {fn} 읽기 실패: {exc}")
            continue

        if url.endswith("/v2/groups") and isinstance(data, list):
            r = D.ingest_ransomware_live(db, data)
            print(f"  ransomware.live 그룹 → 사이트 {r['사이트']} / "
                  f"주소 {r['주소']} / 관측 {r['관측']}")
            done["groups"] += r["사이트"]
        elif ("/v2/victims/" in url or "/countryvictims/" in url) and isinstance(data, list):
            n = D.ingest_victims(db, data)
            if n:
                print(f"  {url.rsplit('/v2/', 1)[-1]} → 피해자 {n}건")
            done["victims"] += n
        elif url.endswith("/api/groups") and isinstance(data, list):
            n = D.ingest_ransomlook(db, data, "group")
            print(f"  ransomlook groups → {n}개")
            done["look"] += n
        elif url.endswith("/api/markets") and isinstance(data, list):
            n = D.ingest_ransomlook(db, data, "market")
            print(f"  ransomlook markets → {n}개")
            done["look"] += n

    print("\n[현황]")
    for k, v in db.stats().items():
        print(f"  {k:<14} {v}")
    return 0


def cmd_stats(db: D.DLSDatabase, args) -> int:
    print(f"[DB] {db.path}\n")
    for k, v in db.stats().items():
        print(f"  {k:<14} {v}")
    runs = db.conn.execute(
        "SELECT started_at, source, target_count, ok_count, note "
        "FROM run ORDER BY id DESC LIMIT 5").fetchall()
    if runs:
        print("\n[최근 수집 실행]")
        for r in runs:
            print(f"  {r['started_at'][:19]}  {r['source']:<12} "
                  f"{r['ok_count']}/{r['target_count']}  {r['note'] or ''}")
    return 0


def cmd_list(db: D.DLSDatabase, args) -> int:
    rows = db.current()
    if args.status:
        rows = [r for r in rows if (r["status"] or "") == args.status]
    if args.kind:
        rows = [r for r in rows if (r["kind"] or "") == args.kind]
    if args.gate:
        rows = [r for r in rows if r["signup_required"]]
    print(f"{len(rows)}개\n")
    print(f"{'이름':<28} {'종류':<8} {'상태':<9} {'언어':<10} 진입 조건")
    print("-" * 92)
    for r in rows[:args.limit or len(rows)]:
        print(f"{(r['name'] or '')[:27]:<28} {(r['kind'] or '')[:7]:<8} "
              f"{(r['status'] or '-')[:8]:<9} {(r['language'] or '-')[:9]:<10} "
              f"{(r['how_to_enter'] or '')[:38]}")
    if args.limit and len(rows) > args.limit:
        print(f"… 외 {len(rows) - args.limit}개")
    return 0


def cmd_history(db: D.DLSDatabase, args) -> int:
    rows = db.history(args.name)
    if not rows:
        print(f"'{args.name}' 에 대한 기록이 없습니다.")
        return 1
    print(f"[{args.name}] 관측 {len(rows)}건\n")
    print(f"{'시각':<21} {'출처':<15} {'상태':<9} {'언어':<9} 비고")
    print("-" * 92)
    for r in rows:
        extra = r["how_to_enter"] or r["error"] or r["title"] or ""
        print(f"{r['observed_at'][:19]:<21} {r['source']:<15} "
              f"{(r['status'] or '-')[:8]:<9} {(r['language'] or '-')[:8]:<9} "
              f"{extra[:38]}")
    return 0


def cmd_changes(db: D.DLSDatabase, args) -> int:
    source = None if args.source == "" else args.source
    ch = db.status_changes(args.since, source)
    label = f"'{source}' 관측끼리" if source else "모든 출처 섞어서 (권장하지 않음)"
    if not ch:
        print(f"상태가 바뀐 사이트가 없습니다. — {label}")
        print("(같은 출처의 관측이 2회 이상 쌓여야 비교할 수 있습니다)")
        return 0
    print(f"상태 변화 {len(ch)}건 — {label}\n")
    for c in ch:
        line = f"  {c['at'][:19]}  {c['name'][:30]:<32} {c['from']} → {c['to']}"
        print(line if source else line + f"   ({c['source']})")
    if source:
        print("\n  ※ 한 출처 안에서만 비교합니다. 섞으면 출처 간 의견 차이가"
              "\n    시간에 따른 변화처럼 보입니다. 굳이 보려면 --source ''")
    return 0


def cmd_addresses(db: D.DLSDatabase, args) -> int:
    rows = db.address_history(args.name)
    if not rows:
        print(f"'{args.name}' 의 주소 기록이 없습니다.")
        return 1
    print(f"[{args.name}] 주소 {len(rows)}개\n")
    for r in rows:
        mark = "● 사용중" if r["active"] else "○ 이력"
        kind = f"[{r['kind']}]" if r["kind"] else ""
        print(f"  {mark} {kind:<8} {r['url']}")
        print(f"            {r['first_seen'][:10]} ~ {r['last_seen'][:10]}")
    return 0


def cmd_kr(db: D.DLSDatabase, args) -> int:
    rows = db.kr_victims(args.group)
    print(f"한국 관련 유출 {len(rows)}건\n")
    print(f"{'발견일':<12} {'그룹':<20} {'업종':<18} 피해자")
    print("-" * 92)
    for r in rows:
        print(f"{(r['discovered'] or '')[:10]:<12} {(r['group_name'] or '')[:19]:<20} "
              f"{(r['sector'] or '-')[:17]:<18} {r['victim'][:34]}")
    return 0


def cmd_indicators(db: D.DLSDatabase, args) -> int:
    """연락 수단·지갑 주소·발견된 onion 링크 — 실무 지표 모음."""
    rows = db.conn.execute("""
        SELECT s.name, o.observed_at, o.contacts, o.crypto, o.onion_links,
               o.latest_date_on_page, o.listing_link_count, o.captcha_confidence
        FROM observation o JOIN site s ON s.id = o.site_id
        WHERE o.contacts IS NOT NULL OR o.crypto IS NOT NULL
           OR o.onion_link_count > 0
        ORDER BY o.observed_at DESC, s.name""").fetchall()
    if not rows:
        print("지표가 기록된 관측이 없습니다.")
        print("(확장된 tor_probe.py 로 다시 수집해야 채워집니다)")
        return 0
    print(f"지표가 있는 관측 {len(rows)}건\n")
    for r in rows[:args.limit or len(rows)]:
        print(f"■ {r['name']}   ({r['observed_at'][:10]})")
        for key, label in (("contacts", "연락"), ("crypto", "지갑")):
            if r[key]:
                for k, v in json.loads(r[key]).items():
                    print(f"    {label} {k:<9} {', '.join(v)[:70]}")
        if r["onion_links"]:
            for u in json.loads(r["onion_links"])[:5]:
                print(f"    onion      {u}")
        if r["latest_date_on_page"]:
            print(f"    페이지 최신일 {r['latest_date_on_page']}"
                  f"   게시물 링크 {r['listing_link_count'] or 0}개")
    return 0


def cmd_captcha(db: D.DLSDatabase, args) -> int:
    """캡차 판정을 근거 강도별로 — 오탐 검토용."""
    for conf, label in (("strong", "확실 (실제 위젯·폼 확인)"),
                        ("weak", "약함 (단어만 발견 — 검토 필요)")):
        rows = db.conn.execute("""
            SELECT s.name, o.how_to_enter, o.gate_evidence
            FROM observation o JOIN site s ON s.id = o.site_id
            WHERE o.captcha_confidence = ? AND o.id = (
                SELECT id FROM observation WHERE site_id = s.id
                ORDER BY observed_at DESC, id DESC LIMIT 1)
            ORDER BY s.name""", (conf,)).fetchall()
        print(f"\n[캡차 {label}] {len(rows)}개")
        for r in rows[:args.limit or len(rows)]:
            ev = ""
            if r["gate_evidence"]:
                hits = [e["match"] for e in json.loads(r["gate_evidence"])
                        if e["signal"] == "캡차"]
                ev = f"   ← {hits[0][:44]}" if hits else ""
            print(f"  {r['name'][:30]:<32}{ev}")
    return 0


def cmd_export(db: D.DLSDatabase, args) -> int:
    """dls_fill.py --probe 가 읽을 수 있는 형태로 내보낸다."""
    # 출처를 섞지 않는다. 기본은 Tor 실측만 — API 추정값이 실측으로
    # 둔갑해 노션의 '상태'를 덮어쓰는 사고를 막는다.
    # 단순히 '최신 관측'을 걸러내면 안 된다. 나중에 넣은 API 관측이
    # 먼저 측정한 Tor 실측을 가려버리기 때문에, 출처별 최신을 따로 뽑는다.
    rows = db.latest_by_source(args.source) if args.source else db.current()
    out = []
    skipped_src: dict[str, int] = {}

    # DB 에 JSON 문자열로 넣어둔 칼럼은 다시 객체로 풀어서 내보낸다.
    # (dls_fill 의 추론기가 dict/list 를 기대한다)
    JSON_COLS = ("contacts", "crypto", "onion_links", "external_domains",
                 "gate_signals", "gate_evidence", "subpages", "dist_hint")
    # 그대로 넘길 값 칼럼 — 추론에 쓰이는 원자료를 빠짐없이 실어야 한다.
    PLAIN_COLS = (
        "http_status", "title", "language", "how_to_enter",
        "h1", "meta_description", "og_site_name", "generator", "keywords",
        "content_hash", "body_bytes", "text_length",
        "server", "powered_by", "last_modified", "elapsed_ms",
        "link_count", "onion_link_count", "listing_link_count",
        "captcha_confidence", "latest_date_on_page",
        # 3회차: VM 안에서 본문까지 보고 낸 판정 + 하위 페이지 흔적
        "format_hint", "format_why", "pii_hint", "pii_why",
        "dist_why", "final_url", "subpage_count",
    )

    def _cols(row) -> set[str]:
        return set(row.keys())

    for r in rows:
        if not r["observed_at"]:
            continue
        have = _cols(r)
        rec = {
            "name": r["name"],
            "source": r["source"],
            "checked_at": r["observed_at"],
            "status": r["status"],
            "reachable": (r["status"] == "online"),
            "signup_required": bool(r["signup_required"])
                               if r["signup_required"] is not None else None,
            "has_pgp": bool(r["has_pgp"]) if "has_pgp" in have
                       and r["has_pgp"] is not None else None,
            "countdown": bool(r["countdown"]) if "countdown" in have
                         and r["countdown"] is not None else None,
            "redirected": bool(r["redirected"]) if "redirected" in have
                          and r["redirected"] is not None else None,
        }
        for col in PLAIN_COLS:
            if col in have and r[col] not in (None, ""):
                rec[col] = r[col]
        for col in JSON_COLS:
            if col in have and r[col]:
                try:
                    val = json.loads(r[col])
                except (ValueError, TypeError):
                    continue
                if val:
                    rec[col] = val
        out.append(rec)
    path = p(args.file)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(f"[내보내기] {path} — {len(out)}건")
    # 어떤 원자료가 실제로 실렸는지 보여준다 — 빈 칸이면 추론이 굶는다
    interesting = ("title", "h1", "meta_description", "keywords", "language",
                   "contacts", "crypto", "onion_links", "latest_date_on_page",
                   "listing_link_count", "countdown")
    tally = {k: sum(1 for rec in out if rec.get(k)) for k in interesting}
    print("  실린 항목: " + ", ".join(f"{k} {v}" for k, v in tally.items() if v))
    if args.source:
        total = len(db.current())
        print(f"  출처 '{args.source}' 의 관측만 — 전체 사이트 {total}개 중 {len(out)}개")
        print(f"  → 전부 내보내려면 --source '' (단, API 추정값이 실측처럼 반영됩니다)")
    print(f"\n  python dls_fill.py --probe {os.path.basename(path)} --report r.csv")
    return 0


# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="DLS 관측 DB 관리")
    ap.add_argument("--db", default=DEFAULT_DB, help="SQLite 파일 경로")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="DB 생성/확인")

    s = sub.add_parser("ingest", help="tor_probe 결과(JSON) 적재")
    s.add_argument("file")

    s = sub.add_parser("ingest-cache", help=".cache 의 API 응답 적재")
    s.add_argument("--cache", default=".cache")

    sub.add_parser("stats", help="현황 요약")

    s = sub.add_parser("list", help="현재 상태 목록")
    s.add_argument("--status", help="online / offline")
    s.add_argument("--kind", help="group / market / forum")
    s.add_argument("--gate", action="store_true", help="가입·로그인 필요한 곳만")
    s.add_argument("--limit", type=int, default=0)

    s = sub.add_parser("history", help="한 사이트의 관측 이력")
    s.add_argument("name")

    s = sub.add_parser("changes", help="상태가 바뀐 지점")
    s.add_argument("--since", help="YYYY-MM-DD")
    s.add_argument("--source", default="tor_probe",
                   help="이 출처의 관측끼리만 비교 (기본 tor_probe). "
                        "--source '' 로 두면 전부 섞습니다")

    s = sub.add_parser("addresses", help="주소 변경 이력")
    s.add_argument("name")

    s = sub.add_parser("kr", help="한국 관련 유출")
    s.add_argument("--group")

    s = sub.add_parser("indicators", help="연락 수단·지갑·onion 링크")
    s.add_argument("--limit", type=int, default=0)

    s = sub.add_parser("captcha", help="캡차 판정을 근거 강도별로 (오탐 검토)")
    s.add_argument("--limit", type=int, default=0)

    s = sub.add_parser("export", help="노션 반영용 JSON 내보내기")
    s.add_argument("file", nargs="?", default="merged.json")
    s.add_argument("--source", default="tor_probe",
                   help="이 출처의 관측만 내보냄 (기본 tor_probe). "
                        "빈 문자열이면 전부")

    args = ap.parse_args()
    database = D.DLSDatabase(args.db)
    try:
        fn = {
            "init": cmd_init, "ingest": cmd_ingest, "ingest-cache": cmd_ingest_cache,
            "stats": cmd_stats, "list": cmd_list, "history": cmd_history,
            "changes": cmd_changes, "addresses": cmd_addresses, "kr": cmd_kr,
            "indicators": cmd_indicators, "captcha": cmd_captcha,
            "export": cmd_export,
        }[args.cmd]
        return fn(database, args)
    finally:
        database.conn.commit()
        database.close()


if __name__ == "__main__":
    sys.exit(main())
