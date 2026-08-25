#!/usr/bin/env python3
"""
Notion DLS 데이터베이스 자동 채우기.

ransomware.live(v2) 와 ransomlook.io 공개 API 에서 다크웹 유출 사이트(DLS) 정보를
가져와 노션 DB 의 빈 칼럼을 채웁니다.

사용법
------
  python dls_fill.py                  # dry-run: 무엇을 채울지 표만 출력 (아무것도 안 씀)
  python dls_fill.py --apply          # 실제로 노션에 기록
  python dls_fill.py --limit 5        # 앞의 5개 행만 (테스트용)
  python dls_fill.py --row 0apt       # 이름에 '0apt' 가 들어간 행만
  python dls_fill.py --overwrite      # 이미 값이 있는 칼럼도 덮어씀 (기본은 빈 칸만)
  python dls_fill.py --schema         # 노션 DB 칼럼 이름/타입만 출력하고 종료
  python dls_fill.py --no-cache       # 캐시 무시하고 API 재수집
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import time
import sys
from datetime import datetime, timezone

import infer
import notion as nt
import sources as src

HERE = os.path.dirname(os.path.abspath(__file__))

# 윈도우 기본 콘솔 인코딩(cp949)에서 '—' 같은 문자에 UnicodeEncodeError 가 나므로
# 출력 스트림을 UTF-8 로 바꾼다. (파이썬 3.7+)
for _stream in (sys.stdout, sys.stderr):
    try:
        # line_buffering=True 라야 파일로 리다이렉트해도 진행 상황이 바로 보인다
        _stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except (AttributeError, ValueError):
        pass


# --------------------------------------------------------------------------
# 설정 로딩
# --------------------------------------------------------------------------
def load_env() -> None:
    path = os.path.join(HERE, ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip().strip("'\""))


def load_mapping() -> dict:
    with open(os.path.join(HERE, "mapping.json"), encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------------------
# 소스 데이터 → 필드 값 계산
# --------------------------------------------------------------------------
def iso_date(dt: datetime | None) -> str | None:
    return dt.date().isoformat() if dt else None


def placeholder_set(mapping: dict, col: str) -> set[str]:
    ph = mapping.get("placeholders", {})
    vals = ph.get(col, ph.get("_default", []))
    return {str(v).strip().lower() for v in vals if isinstance(v, str)}


def same_value(ptype: str, new, current) -> bool:
    """이미 같은 값이면 굳이 쓰지 않는다 (불필요한 API 호출·이력 오염 방지)."""
    if current is None:
        return False
    if ptype == "checkbox":
        return bool(new) == bool(current)
    if ptype == "multi_select":
        a = [str(x) for x in (new if isinstance(new, (list, tuple)) else [new])]
        b = [str(x) for x in (current if isinstance(current, list) else [current])]
        return a == b
    if ptype == "number":
        try:
            return float(new) == float(current)
        except (TypeError, ValueError):
            return False
    if ptype == "date":
        return str(new)[:10] == str(current)[:10]
    return str(new).strip() == str(current).strip()


def treat_as_empty(value, phs: set[str]) -> bool:
    """빈 값이거나 '미확인' 같은 자리표시자면 True."""
    if nt.is_empty(value):
        return True
    if isinstance(value, list):
        return all(str(v).strip().lower() in phs for v in value)
    return str(value).strip().lower() in phs


def load_probe(path: str) -> dict[str, dict]:
    """tor_probe.py 결과를 {정규화된 이름: 레코드} 로."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    out, dropped = {}, 0
    for rec in data:
        # Tor 가 끊긴 구간에서 나온 판정은 신뢰할 수 없으므로 버린다
        if rec.get("unreliable") or rec.get("status") == "미확인":
            dropped += 1
            continue
        k = src.norm(rec.get("name"))
        if k:
            out[k] = rec
    if dropped:
        print(f"[Tor 수집] 신뢰할 수 없는 구간 {dropped}건 제외")
    return out


def apply_probe(out: dict, matched: list[str], rec: dict, mapping: dict,
                authoritative: set[str]) -> None:
    """Tor 직접 확인 결과를 반영.

    실측이므로 API 추정값보다 우선한다. 여기서 채운 필드는 authoritative 에
    등록해서, 노션에 이미 API 로 넣어둔 값이 있어도 덮어쓰게 한다.
    (이게 없으면 '실제로 접속해 확인한 결과'가 '추정값'에 밀린다.)
    """
    sv = mapping["source_values"]
    # 어느 관측인지 정직하게 라벨링한다 (Tor 실측 vs API 추정)
    origin = rec.get("source") or "tor_probe"
    if origin == "tor_probe":
        matched.append(sv.get("tor_probe", "직접 확인"))
    else:
        matched.append(origin)

    # 상태는 실측일 때만 덮어쓴다. API 추정값은 두 소스 처리 단계에서 이미 반영됨.
    if rec.get("status") and origin == "tor_probe":
        out["status"] = mapping["status_values"].get(rec["status"], rec["status"])
        authoritative.add("status")
    if rec.get("language"):
        out["language"] = rec["language"]
        authoritative.add("language")
    if rec.get("how_to_enter"):
        out["how_to_enter"] = rec["how_to_enter"]
        authoritative.add("how_to_enter")
    if rec.get("signup_required") is not None and rec.get("reachable"):
        out["signup_required"] = bool(rec["signup_required"])
        authoritative.add("signup_required")
    # 사이트 제목·설명 — API 설명이 없을 때만 보조로 쓴다
    desc = rec.get("meta_description") or rec.get("og_description")
    if desc:
        out.setdefault("description", desc)
    elif rec.get("title"):
        out.setdefault("description", f"사이트 제목: {rec['title']}")

    # 최근 활동 — 우선순위: API 피해자 최신일 > 페이지에 적힌 날짜 >
    # 서버 Last-Modified 헤더. 마지막 것을 안 쓰고 있어서 최근 활동이
    # 5건밖에 안 채워졌다. 접속된 곳의 3분의 1이 여기에만 날짜가 있다.
    if rec.get("latest_date_on_page"):
        out.setdefault("last_activity", rec["latest_date_on_page"])
    else:
        lm, _why = infer.last_modified_date(rec.get("last_modified"))
        if lm:
            out.setdefault("last_activity", lm)

    # 연결된 곳 — 페이지에서 발견한 다른 onion 주소 + 클리어넷 미러
    found_parts = [f"발견: {u}" for u in (rec.get("onion_links") or [])[:6]]
    ext, _why = infer.format_external(rec.get("external_domains"),
                                      rec.get("name"))
    if ext:
        found_parts.append(ext)
    if found_parts:
        found = " · ".join(found_parts)
        prev = out.get("linked")
        out["linked"] = f"{prev} · {found}" if prev else found
        authoritative.add("linked")

    # 연락 수단 / 암호화폐 주소
    c = infer.format_contacts(rec.get("contacts"))
    if c:
        out["contacts"] = c
        authoritative.add("contacts")
    if c and rec.get("has_pgp"):
        # PGP 키를 걸어둔 곳은 협상 창구를 운영한다는 뜻이라 연락 수단의 일부다
        out["contacts"] = f"{c} · PGP 키 게시"
    cr = infer.format_crypto(rec.get("crypto"))
    if cr:
        out["crypto"] = cr
        authoritative.add("crypto")
    if rec.get("checked_at"):
        out["checked_date"] = rec["checked_at"][:10]
        authoritative.add("checked_date")


def derive(name: str, onion: str | None, rl: src.RansomwareLive,
           look: src.RansomLook, mapping: dict,
           probe: dict[str, dict] | None = None
           ) -> tuple[dict, list[str], set[str]]:
    """한 행에 대해 (값, 매칭 소스, 실측으로 확정된 필드) 를 만든다."""
    out: dict[str, object] = {}
    matched: list[str] = []
    authoritative: set[str] = set()
    victim_count = 0

    kind_values = mapping["kind_values"]
    status_values = mapping["status_values"]
    source_values = mapping["source_values"]
    sep = mapping.get("join_separator", " · ")

    # 수동 별칭이 있으면 그 이름으로 소스를 찾는다 (표기 차이 보정)
    aliases = {src.norm(k): v for k, v in mapping.get("name_aliases", {}).items()
               if not k.startswith("_") and isinstance(v, str)}
    key = aliases.get(src.norm(name), name)

    # ---------- ransomware.live ----------
    g = rl.find(key, onion)
    if g:
        matched.append(source_values["ransomware_live"])
        canonical = g.get("name") or name

        if g.get("description"):
            out["description"] = g["description"].strip()
        # altname 이 이름과 사실상 같으면 별칭으로 쓸 의미가 없다
        if g.get("altname") and src.norm(g["altname"]) != src.norm(name):
            out["aliases"] = str(g["altname"])
        out.setdefault("kind", kind_values["ransomware_live_group"])

        locs = g.get("locations") or []
        dls = [l for l in locs if (l.get("type") or "").upper() == "DLS"] or locs
        if dls:
            primary = next((l for l in dls if l.get("available")), dls[0])
            slug = primary.get("slug") or ("http://" + (primary.get("fqdn") or ""))
            if slug.startswith("http"):
                out["address"] = slug
            others = [l.get("fqdn") for l in dls
                      if l.get("fqdn") and l.get("fqdn") != primary.get("fqdn")]
            if others:
                out["prev_addresses"] = sep.join(others)
        linked = [f"{(l.get('type') or '기타')}: {l.get('fqdn')}"
                  for l in locs if (l.get("type") or "").upper() != "DLS" and l.get("fqdn")]
        if linked:
            out["linked"] = sep.join(linked)

        if locs:
            online = any(l.get("available") for l in locs)
            out["status"] = status_values["online" if online else "offline"]

        # 피해자 통계
        stats = src.victim_stats(rl.group_victims(canonical))
        if stats:
            victim_count = stats.get("count") or 0
            if stats.get("latest"):
                out["last_activity"] = iso_date(stats["latest"])
            out["scale"] = f"피해자 {stats['count']}건 (최근 {rl.months}개월)"
            if stats["sectors"]:
                sect = ", ".join(f"{s}({c})" for s, c in stats["sectors"][:4])
                ctry = ", ".join(f"{s}({c})" for s, c in stats["countries"][:6])
                out["victim_targets"] = (f"업종 {sect} / 국가 {ctry} "
                                         f"(최근 {rl.months}개월 {stats['count']}건)")

        kr = rl.group_kr_victims(canonical)
        if kr:
            names = ", ".join(filter(None, (v.get("post_title") for v in kr[:6])))
            out["korea_leaks"] = f"있음 — {len(kr)}건: {names}"

    # ---------- ransomlook.io ----------
    # 상세 조회는 행마다 HTTP 1회라 느리다. ransomware.live 에서 이미
    # 설명·상태·주소를 다 얻었으면 건너뛴다(종류만 인덱스에서 무료로 확인).
    # 목록 인덱스에 이름이 있으면 그 자체로 '매칭 성공'이다.
    # 상세 조회(HTTP 1회)가 실패해도 이 사실은 버리지 않는다 — 예전 버그.
    look_hit = look.lookup(key, onion)
    if look_hit:
        look_kind = look_hit[0]
        matched.append(source_values["ransomlook"])
        out.setdefault("kind", kind_values.get(f"ransomlook_{look_kind}", look_kind))

    # 상세는 아직 못 채운 칼럼이 있을 때만 가져온다
    need_detail = bool(look_hit) and not (
        out.get("description") and out.get("status") and out.get("address"))

    hit = look.find(key, onion) if need_detail else None
    if hit:
        kind, detail = hit
        if detail.get("meta"):
            out.setdefault("description", str(detail["meta"]).strip())
        locs = detail.get("locations") or []
        if locs:
            out.setdefault("status",
                           status_values["online" if any(l.get("available") for l in locs)
                                         else "offline"])
            primary = next((l for l in locs if l.get("available")), locs[0])
            if primary.get("slug", "").startswith("http"):
                out.setdefault("address", primary["slug"])
            others = [l.get("fqdn") for l in locs
                      if l.get("fqdn") and l.get("fqdn") != primary.get("fqdn")]
            if others:
                out.setdefault("prev_addresses", sep.join(others))

    # ---------- Tor 직접 확인 (있으면 실측이므로 우선) ----------
    if probe:
        rec = probe.get(src.norm(name)) or probe.get(src.norm(key))
        if rec:
            apply_probe(out, matched, rec, mapping, authoritative)

    # ---------- 공통 ----------
    if matched:
        out["source"] = matched
        out["checked_date"] = datetime.now(timezone.utc).date().isoformat()

    # ---------- 추론 계층 ----------
    # 원자료에서 분류 칼럼을 뽑아낸다. 근거가 없으면 채우지 않고,
    # 약한 근거면 '추정: ' 접두어를 붙여 기계 추측임을 남긴다.
    rec = (probe or {}).get(src.norm(name)) or (probe or {}).get(src.norm(key)) or {}
    # 판정용 텍스트는 두 갈래로 나눠서 넘긴다.
    #
    #   api_desc  — ransomware.live 의 그룹 설명문. 그 그룹이 어떻게 침투하고
    #               무엇을 훔쳤는지를 말한다.
    #   page_desc — 사이트가 자기 페이지에 써둔 설명(meta/og). 그 사이트가
    #               스스로 무엇이라 말하는지다.
    #
    # 섞으면 그룹 설명문의 'rdp'(침투 경로)가 상점 keywords 의 'rdp'(상품)와
    # 같은 취급을 받는다. 실제로 cephalus 가 그래서 초기 접근 브로커가 됐다.
    api_desc = str(out.get("description") or "")
    page_desc = " ".join(str(x) for x in (
        rec.get("meta_description"),
        rec.get("og_description"),
        rec.get("og_title"),
        rec.get("og_site_name"),
    ) if x)
    # 다른 추론기(개인정보·유통자리)는 아직 한 덩어리를 받는다
    desc_text = " ".join(x for x in (api_desc, page_desc) if x)
    kind_now = str(out.get("kind") or "")
    reasons: list[str] = []

    fo = mapping.get("format_overrides", {})
    fmt_override = (fo.get(src.norm(name)) or fo.get(src.norm(key))
                    or fo.get(name.lower()))
    fmt, why = infer.infer_format(kind_now, api_desc, rec.get("title"),
                                  rec.get("keywords"), rec.get("h1"),
                                  page_desc, name, fmt_override)
    # VM 이 본문까지 보고 낸 판정. 호스트는 본문을 못 봤으므로 이게 더 강한
    # 근거다. 다만 VM 은 API 종류를 모르니 모순 검사는 여기서 다시 한다.
    hint = rec.get("format_hint")
    if hint and not fmt_override:
        clean = hint.replace(infer.MAYBE, "")
        contradicts = ((clean == "포럼·마켓" and kind_now == "group")
                       or (clean in ("RaaS", "데이터 갈취")
                           and kind_now in ("market", "forum")))
        if contradicts:
            pass
        elif not fmt or (fmt.startswith(infer.MAYBE)
                         and not hint.startswith(infer.MAYBE)):
            fmt = hint
            why = f"본문 전체 — {rec.get('format_why') or ''}".strip(" —")
    if fmt:
        out["format"] = fmt
        reasons.append(f"형식←{why}")

    # 개인정보도 이름을 본다 — 'AUTHORIZE CVV' 는 이름만으로 카드정보 취급이
    # 확실하고, 죽은 사이트라 페이지를 읽을 수도 없다.
    pii, why = infer.infer_pii(kind_now, desc_text, rec.get("title"),
                               rec.get("keywords"),
                               " ".join(x for x in (rec.get("h1"), name) if x),
                               fmt)
    ph = rec.get("pii_hint")
    if ph and (not pii or (pii.startswith(infer.MAYBE)
                           and not ph.startswith(infer.MAYBE))):
        pii = ph
        why = f"본문 전체 — {rec.get('pii_why') or ''}".strip(" —")
    if pii:
        out["pii_leak"] = pii
        reasons.append(f"개인정보←{why}")

    # 페이지에 걸린 클리어넷 도메인 개수 — 그룹이면 대개 피해 기업이다
    named = [d for d in (rec.get("external_domains") or [])
             if d and not infer._INFRA.search(str(d))]
    dist, why = infer.infer_distribution(
        kind_now, desc_text, rec.get("title"), rec.get("h1"),
        bool(rec.get("countdown")), rec.get("listing_link_count") or 0,
        victim_count, len(named))
    dh = rec.get("dist_hint")
    if dh and not dist:
        dist = dh if isinstance(dh, list) else [dh]
        why = f"본문 전체 — {rec.get('dist_why') or ''}".strip(" —")
    if dist:
        out["distribution"] = dist
        reasons.append(f"유통자리←{why}")

    co = mapping.get("country_overrides", {})
    override = co.get(src.norm(name)) or co.get(src.norm(key)) or co.get(name.lower())
    country, why = infer.infer_country(
        out.get("language") or rec.get("language"),
        out.get("address") or onion, override,
        kind_now, rec.get("external_domains"))
    if country:
        out["country"] = country
        reasons.append(f"국가←{why}")

    if not out.get("scale"):
        scale, why = infer.infer_scale(
            kind_now, rec.get("listing_link_count"), None)
        if scale:
            out["scale"] = scale

    out["_reasons"] = reasons
    return out, matched, authoritative


# --------------------------------------------------------------------------
# 메인
# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="Notion DLS DB 자동 채우기")
    ap.add_argument("--apply", action="store_true", help="실제로 노션에 기록 (기본은 dry-run)")
    ap.add_argument("--overwrite", action="store_true", help="값이 있는 칼럼도 덮어쓰기")
    ap.add_argument("--limit", type=int, default=0, help="처리할 행 수 제한")
    ap.add_argument("--row", default="", help="이름에 이 문자열이 포함된 행만 처리")
    ap.add_argument("--months", type=int, default=6, help="피해자 통계에 쓸 개월 수 (기본 6)")
    ap.add_argument("--schema", action="store_true", help="DB 칼럼 이름/타입만 출력")
    ap.add_argument("--data-source", default="",
                    help="데이터 소스가 여러 개일 때 이름 또는 번호로 선택 (기본: 1번)")
    ap.add_argument("--dump", type=int, nargs="?", const=5, default=0,
                    metavar="N", help="스키마 + 샘플 N행의 현재 값 + 칼럼별 채움률 출력")
    ap.add_argument("--report", default="", metavar="FILE.csv",
                    help="변경 예정 내용을 CSV(UTF-8)로 저장 — 잘리지 않은 전체 값 확인용")
    ap.add_argument("--export-targets", default="", metavar="FILE.csv",
                    help="Tor 수집 대상(name,url)을 CSV로 뽑고 종료 — VM 으로 넘길 입력")
    ap.add_argument("--probe", default="", metavar="FILE.json",
                    help="tor_probe.py 결과를 추가 소스로 사용")
    ap.add_argument("--no-cache", action="store_true", help="API 캐시 삭제 후 재수집")
    ap.add_argument("--cache-hours", type=int, default=72,
                    help="API 캐시 유효 시간(기본 72시간). 크게 잡으면 재수집 대기가 없습니다")
    ap.add_argument("--rl-interval", type=float, default=62.0,
                    help="ransomware.live 호출 간 대기(초). 무료 티어는 1req/분")
    args = ap.parse_args()

    load_env()
    token = os.environ.get("NOTION_TOKEN", "")
    db_id = os.environ.get("NOTION_DATABASE_ID", "").replace("-", "")
    if not token or not db_id:
        print("[!] .env 에 NOTION_TOKEN 과 NOTION_DATABASE_ID 를 설정하세요 "
              "(.env.example 참고)", file=sys.stderr)
        return 1

    mapping = load_mapping()
    cols = {k: v for k, v in mapping["columns"].items() if v}

    n = nt.Notion(token)

    # 2025-09-03 부터 DB 는 여러 데이터 소스를 가질 수 있고,
    # 스키마·행 조회는 데이터 소스 단위로 한다.
    try:
        sources = n.data_sources(db_id)
    except nt.NotionError as exc:
        msg = str(exc)
        print(f"\n[!] 노션 DB 에 접근하지 못했습니다.\n{msg}\n", file=sys.stderr)
        if exc.status == 404:
            print("가능한 원인:", file=sys.stderr)
            print("  1. integration 이 이 DB 에 연결돼 있지 않음"
                  " (DB → ⋯ → 연결 → integration 추가)", file=sys.stderr)
            print("  2. NOTION_DATABASE_ID 가 DB 가 아니라 '페이지' ID", file=sys.stderr)
        elif exc.status == 401:
            print("토큰이 거부됐습니다. Internal Integration Secret 을 확인하세요.",
                  file=sys.stderr)
        print("\n→ python diagnose.py 를 실행하면 원인을 짚어 줍니다.\n", file=sys.stderr)
        return 1

    if len(sources) > 1:
        print(f"\n[데이터 소스] 이 DB 에는 {len(sources)}개의 데이터 소스가 있습니다:")
        for i, s in enumerate(sources, 1):
            print(f"   {i}. {s['name']}   (id: {s['id'].replace('-', '')})")

    picked = sources[0]
    if args.data_source:
        sel = args.data_source.strip()
        if sel.isdigit() and 1 <= int(sel) <= len(sources):
            picked = sources[int(sel) - 1]
        else:
            match = [s for s in sources if sel.lower() in s["name"].lower()]
            if not match:
                print(f"[!] '{sel}' 에 해당하는 데이터 소스가 없습니다.", file=sys.stderr)
                return 1
            picked = match[0]
    elif len(sources) > 1:
        print(f"   → 1번 '{picked['name']}' 을 사용합니다. "
              f"다른 걸 쓰려면 --data-source 2 또는 --data-source 이름")

    ds_id = picked["id"]
    try:
        schema = n.schema(ds_id)
    except nt.NotionError as exc:
        print(f"\n[!] 데이터 소스 스키마 조회 실패\n{exc}\n", file=sys.stderr)
        return 1

    if args.schema:
        print(f"\n[노션 스키마] 데이터 소스 '{picked['name']}' — {len(schema)}개 칼럼\n")
        for name, t in schema.items():
            used = [k for k, v in cols.items() if v == name]
            tag = f"  ← mapping: {used[0]}" if used else ""
            print(f"  {name:<20} {t}{tag}")
        return 0

    # mapping.json 에 적힌 칼럼이 실제 DB 에 있는지 확인
    missing = {k: v for k, v in cols.items() if v not in schema}
    if missing:
        print("[!] mapping.json 의 다음 칼럼을 노션 DB 에서 찾지 못했습니다 (건너뜁니다):")
        for k, v in missing.items():
            print(f"    {k} → '{v}'")
        cols = {k: v for k, v in cols.items() if v in schema}

    # 기존 값에 '덧붙여도 되는' multi_select 칼럼 (나머지는 비어 있을 때만 채움)
    append_cols = set(mapping.get("append_columns", []))

    title_prop = mapping["title_property"]
    if title_prop not in schema:
        title_prop = next((k for k, v in schema.items() if v == "title"), None)
        if not title_prop:
            print("[!] title 타입 칼럼을 찾을 수 없습니다.", file=sys.stderr)
            return 1
    addr_prop = mapping["address_property"] if mapping["address_property"] in schema else None

    print(f"\n[노션] '{picked['name']}' 행 조회 중…")
    pages = n.query_all(ds_id)
    print(f"[노션] {len(pages)}개 행")

    all_pages = pages
    if args.row:
        needle = args.row.lower()
        pages = [p for p in pages
                 if needle in (nt.read_value(p["properties"].get(title_prop)) or "").lower()]
        print(f"[필터] '{args.row}' → {len(pages)}개 행")
    if args.limit:
        pages = pages[:args.limit]
        print(f"[필터] 앞의 {len(pages)}행만 처리 — 대상: "
              + ", ".join((nt.read_value(p['properties'].get(title_prop)) or '?')
                          for p in pages[:8])
              + (" …" if len(pages) > 8 else ""))

    if args.export_targets:
        import csv
        path = args.export_targets if os.path.isabs(args.export_targets) \
            else os.path.join(HERE, args.export_targets)
        out_rows, no_url = [], 0
        for p in pages:
            nm = nt.read_value(p["properties"].get(title_prop)) or ""
            url = nt.read_value(p["properties"].get(addr_prop)) if addr_prop else None
            if not nm:
                continue
            if not url:
                no_url += 1
                continue
            out_rows.append((nm, url))
        with open(path, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["name", "url"])
            w.writerows(out_rows)
        print(f"\n[수집 대상] {path}")
        print(f"  {len(out_rows)}개 (주소 없어 제외 {no_url}개)")
        print("\nVM(Kali)으로 옮긴 뒤:")
        print("  sudo systemctl start tor")
        print("  python3 tor_probe.py --selftest")
        print(f"  python3 tor_probe.py {os.path.basename(path)} -o probe.json")
        return 0

    if args.dump:
        print(f"\n{'=' * 78}")
        print(f"칼럼 현황 — 데이터 소스 '{picked['name']}', 전체 {len(all_pages)}행 "
              f"(표시 대상 {len(pages)}행)")
        print("=" * 78)
        print(f"{'칼럼':<20} {'타입':<14} {'채움':<12} 값 예시")
        print("-" * 78)
        for col, ptype in schema.items():
            vals = [nt.read_value(p["properties"].get(col)) for p in pages]
            filled = [v for v in vals if not nt.is_empty(v)]
            pct = f"{len(filled)}/{len(pages)}"
            samples = []
            for v in filled:
                s = ", ".join(map(str, v)) if isinstance(v, list) else str(v)
                s = s.replace("\n", " ")[:28]
                if s not in samples:
                    samples.append(s)
                if len(samples) >= 3:
                    break
            mapped = next((k for k, c in cols.items() if c == col), "")
            tag = f"[{mapped}] " if mapped else ""
            print(f"{col:<20} {ptype:<14} {pct:<12} {tag}{' | '.join(samples)}")

        print(f"\n{'=' * 78}")
        print(f"샘플 {min(args.dump, len(pages))}행의 현재 값")
        print("=" * 78)
        for p in pages[:args.dump]:
            nm = nt.read_value(p["properties"].get(title_prop)) or "(제목 없음)"
            print(f"\n■ {nm}")
            for col in schema:
                v = nt.read_value(p["properties"].get(col))
                if not nt.is_empty(v):
                    s = ", ".join(map(str, v)) if isinstance(v, list) else str(v)
                    print(f"    {col:<18} {s[:70]}")
        print()
        return 0

    # 소스 수집
    cache_dir = os.path.join(HERE, ".cache")
    if args.no_cache and os.path.isdir(cache_dir):
        shutil.rmtree(cache_dir)
    fetcher = src.Fetcher(cache_dir, cache_hours=args.cache_hours)
    rl = src.RansomwareLive(fetcher, months=args.months, min_interval=args.rl_interval)
    rl.load()
    look = src.RansomLook(fetcher)
    look.load()

    probe: dict[str, dict] = {}
    if args.probe:
        ppath = args.probe if os.path.isabs(args.probe) else os.path.join(HERE, args.probe)
        try:
            probe = load_probe(ppath)
            print(f"[Tor 수집] {ppath} — {len(probe)}개 행 반영")
        except Exception as exc:
            print(f"[!] --probe 파일을 읽지 못했습니다: {exc}", file=sys.stderr)
            return 1

    # 처리
    print(f"\n{'=' * 78}")
    print(f"{'행':<24} {'채울 칼럼':<50}")
    print("=" * 78)

    updated = skipped = failed = 0
    unmatched: list[str] = []
    report_rows: list[tuple] = []
    total = len(pages)
    t0 = time.time()
    for idx, page in enumerate(pages, 1):
        if idx % 25 == 0 or idx == total:
            el = time.time() - t0
            eta = el / idx * (total - idx)
            print(f"  … 진행 {idx}/{total}  경과 {el:.0f}s  남은 예상 {eta:.0f}s "
                  f"(ransomlook 호출 {look.calls}회)", flush=True)
        props = page["properties"]
        name = nt.read_value(props.get(title_prop)) or ""
        if not name:
            continue
        onion = nt.read_value(props.get(addr_prop)) if addr_prop else None

        values, matched, authoritative = derive(
            name, onion, rl, look, mapping, probe)
        reasons = values.pop("_reasons", [])
        # 추론 근거를 노션에도 남긴다. '추정: 러시아' 가 왜 러시아인지 CSV 를
        # 뒤지지 않고 그 행에서 바로 확인할 수 있어야 검수가 된다.
        if reasons:
            values["reasons"] = " · ".join(reasons)[:1900]
            # 값이 바뀌면 근거도 따라 바뀌어야 한다. 빈 칸일 때만 채우면
            # 첫 판정의 근거가 영원히 남아 실제 값과 어긋난다.
            authoritative.add("reasons")

        # 조사 단계 — 접속 확인만 한 행에 '확인만 함'. 사람이 마친 행은 유지.
        stage_col = cols.get("stage")
        if stage_col and stage_col in schema:
            observed = bool(probe and (
                src.norm(name) in probe
                or src.norm(mapping.get("name_aliases", {}).get(name, name)) in probe))
            st = infer.infer_stage(
                nt.read_value(props.get(stage_col)), observed,
                tuple(mapping.get("stage_done_values", ["조사 완료"])),
                mapping.get("stage_checked_value", "확인만 함"))
            if st:
                values["stage"] = st
        if not matched:
            unmatched.append((name, onion or "",
                              src.norm(name), src.norm_loose(name),
                              src.domain_label(onion),
                              ", ".join(rl.suggest(name)),
                              ", ".join(look.suggest(name))))
            skipped += 1
            continue

        payload: dict[str, dict] = {}
        changes: list[str] = []
        for field, value in values.items():
            col = cols.get(field)
            if not col:
                continue
            ptype = schema[col]
            current = nt.read_value(props.get(col))

            phs = placeholder_set(mapping, col)

            if ptype == "multi_select":
                items = value if isinstance(value, list) else [value]
                # '미확인' 같은 자리표시자는 실제 값이 들어오면 밀어낸다
                kept = [c for c in (current or [])
                        if str(c).strip().lower() not in phs]
                # append_columns 에 없는 multi_select 는 '기존 값이 있으면 그대로 둔다'.
                # (예: 종류 — 이미 market 인 행에 group 을 덧붙이면 모순이 된다)
                if (kept and col not in append_cols and not args.overwrite
                        and field not in authoritative):
                    continue
                merged = list(dict.fromkeys(kept + [str(v) for v in items if v]))
                if merged == (current or []):
                    continue
                value = merged
            elif (not args.overwrite and field not in authoritative
                    and not treat_as_empty(current, phs)):
                continue

            if same_value(ptype, value, current):
                continue

            built = nt.build_value(ptype, value)
            if not built:
                continue
            payload[col] = built
            preview = str(value).replace("\n", " / ")
            changes.append(f"{col}={preview[:40]}")
            cur_s = ", ".join(map(str, current)) if isinstance(current, list) \
                else ("" if current is None else str(current))
            new_s = ", ".join(map(str, value)) if isinstance(value, list) else str(value)
            reason = next((r for r in reasons
                           if r.split("←")[0] in (
                               "형식" if field == "format" else
                               "개인정보" if field == "pii_leak" else
                               "유통자리" if field == "distribution" else
                               "국가" if field == "country" else "")), "")
            report_rows.append((name, col, ptype, cur_s, new_s,
                                "+".join(matched) + (f"  [{reason}]" if reason else "")))

        if not payload:
            print(f"{name:<24} 변경 없음 ({'+'.join(matched)})")
            skipped += 1
            continue

        print(f"{name:<24} {', '.join(changes)[:100]}")

        if args.apply:
            try:
                n.update_page(page["id"], payload)
                updated += 1
            except (nt.NotionError, OSError) as exc:
                # 한 행이 실패했다고 나머지 500행을 포기하지 않는다.
                # 이 스크립트는 다시 돌려도 안전하므로(같은 값이면 안 씀),
                # 실패한 행은 다음 실행에서 자연히 채워진다.
                print(f"    [!] 실패: {exc}")
                failed += 1

    print("=" * 78)

    if args.report:
        import csv
        path = args.report if os.path.isabs(args.report) \
            else os.path.join(HERE, args.report)
        with open(path, "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["행 이름", "칼럼", "타입", "현재 값", "새 값", "매칭 소스"])
            w.writerows(report_rows)
            w.writerow([])
            w.writerow(["--- API 에서 못 찾은 행 (진단) ---"])
            w.writerow(["행 이름", "주소", "정규화", "꼬리표 제거", "도메인 라벨",
                        "ransomware.live 유사 후보", "ransomlook 유사 후보"])
            w.writerows(unmatched)
        print(f"\n[리포트] {path}")
        print(f"          변경 항목 {len(report_rows)}건 / 못 찾은 행 {len(unmatched)}개")

    if unmatched:
        names = [u[0] for u in unmatched]
        print(f"\nAPI 에서 못 찾은 행 {len(unmatched)}개:")
        for i in range(0, min(len(names), 40), 4):
            print("   " + " / ".join(names[i:i + 4]))
        if len(names) > 40:
            print(f"   … 외 {len(names) - 40}개")
        near = [u for u in unmatched if u[5] or u[6]]
        if near:
            print(f"\n  ↳ 이 중 {len(near)}개는 비슷한 이름이 소스에 있습니다 "
                  f"(--report 의 진단 표에서 후보 확인):")
            for u in near[:12]:
                cand = u[5] or u[6]
                print(f"      {u[0]:<28} ≈ {cand}")
        print()

    if args.apply:
        print(f"완료: {updated}개 행 업데이트, {skipped}개 건너뜀, {failed}개 실패")
    else:
        print(f"DRY-RUN — 실제로 기록하려면 --apply 를 붙이세요. "
              f"(변경 예정 {len(pages) - skipped}개, 건너뜀 {skipped}개)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
