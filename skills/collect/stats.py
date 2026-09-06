#!/usr/bin/env python3
"""한국 관련 랜섬웨어 유출 게시 통계. 기자 요청 1번에 답한다.

    python -m collect.stats --since 2026-01-01 --out 07_케이스/_통계
    python -m collect.stats --since 2026-01-01 --out … --list        조직 목록까지
    python -m collect.stats --since 2026-01-01 --out … --no-notion   깔때기 없이

> 일정 기간 동안 한국 관련 유출은 몇 건이고, 그중 실제 데이터로 확인된 것은 몇 건일까?

앞은 세는 문제고 뒤는 검증의 문제다. 앞은 수집 표(SQLite)에서 세고, 뒤는 노션(수집 DB · 검증 DB)에
있는 것을 사건 ID 로 이어 깔때기로 낸다. **집계처 게시와 수집 DB 사이에는 줄 단위 키가 없다.**
팀이 골라 올린 것이다. 그 문장을 표에 고정한다. 숨기면 표본 추출을 한 것처럼 읽힌다.

## 분모

`~/data/darkchoco.db` 의 `source='ransom' AND country='KR'`. 집계처 `countryvictims/KR` 을 그대로
받은 줄이라 「집계처가 한국이라고 한 것」 이라는 뜻이 분명하다. 팀 표(448)는 다른 집계처가 섞여 있고
raw 키가 달라 이번에는 안 쓴다 (DEV 5-1 S3). `--db` 로 바꿀 수 있다.

## 규모 칸을 그대로 믿지 않는다

값 있음 · 대시뿐 · 빈칸 셋으로 가른다. 대시(`-` `---`)는 값이 아니고, 빈칸은 「주장 없음」 이 아니다.
집계처가 안 긁은 것일 수 있다 (2026-08-29 실측 두 건). 규모 합계 같은 것은 내지 않는다.

## 나가는 것

건수와 그룹명과 업종뿐이다. 조직 목록은 `--list` 를 줄 때만 따로 낸다. 주소·본문은 어디에도 안 나간다.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import statistics
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collect.sources.ransomlive import DASH  # noqa: E402

KST = timezone(timedelta(hours=9))
DEFAULT_DB = Path.home() / "data" / "darkchoco.db"
BLANK = "(빈칸)"
CONFIRMED_VERDICTS = ("확인됨", "신뢰성 높음")
NOTE_NO_KEY = ("집계처 게시와 수집 DB 사이에는 줄 단위 키가 없다. 팀이 골라 올린 것이지 "
               "표본을 뽑은 것이 아니다.")


# ── 시각 ───────────────────────────────────────────────

def _kst(s: str):
    """집계처 시각(UTC ISO)을 KST datetime 으로. 못 읽으면 None."""
    try:
        d = datetime.fromisoformat((s or "").strip())
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(KST)


def _day(s: str) -> str:
    d = _kst(s)
    if d:
        return d.strftime("%Y-%m-%d")
    m = re.match(r"(\d{4}-\d{2}-\d{2})", (s or "").strip())
    return m.group(1) if m else ""


# ── 고르기 ─────────────────────────────────────────────

def load_rows(con, since: str | None = None, until: str | None = None) -> list:
    """한국 관련 랜섬 줄. 기간은 게시일(posted_at) 기준이고 날짜 꼴 YYYY-MM-DD 다."""
    out = []
    for r in con.execute("SELECT * FROM items WHERE source='ransom' AND country='KR' "
                         "ORDER BY posted_at"):
        d = dict(r)
        day = _day(d.get("posted_at") or "")
        if since and (not day or day < since):
            continue
        if until and (not day or day > until):
            continue
        try:
            d["raw_d"] = json.loads(d.get("raw") or "{}")
        except ValueError:
            d["raw_d"] = {}
        d["day"] = day
        out.append(d)
    return out


# ── 가르기 ─────────────────────────────────────────────

def _rank(counter: Counter) -> list:
    """건수 많은 순. 같으면 빈칸을 뒤로, 그다음 이름순."""
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0] == BLANK, kv[0]))


def by_month(rows: list) -> dict:
    c = Counter((r["day"][:7] or "(미상)") for r in rows)
    return dict(sorted(c.items()))


def by_actor(rows: list, top: int = 10) -> list:
    c = Counter((r.get("actor") or BLANK) for r in rows)
    ranked = _rank(c)
    if len(ranked) <= top:
        return ranked
    head, tail = ranked[:top], ranked[top:]
    return head + [("그 밖 (%d개 그룹)" % len(tail), sum(n for _, n in tail))]


def by_industry(rows: list) -> list:
    c = Counter((r["raw_d"].get("산업 분야") or BLANK) for r in rows)
    return _rank(c)


def size_split(rows: list) -> dict:
    out = {"값 있음": 0, "대시뿐": 0, "빈칸": 0}
    for r in rows:
        s = (r.get("claimed_size") or "").strip()
        if not s:
            out["빈칸"] += 1
        elif s in DASH:
            out["대시뿐"] += 1
        else:
            out["값 있음"] += 1
    return out


def discovery_lag(rows: list) -> dict:
    """집계처가 처음 본 날 − 게시일. 발견일이 있는 줄만 (2026-09-06 부터 저장)."""
    lags = []
    for r in rows:
        p, f = _kst(r.get("posted_at") or ""), _kst(r["raw_d"].get("발견일") or "")
        if p and f:
            lags.append(round((f - p).total_seconds() / 86400, 1))
    if not lags:
        return {"줄": 0, "중앙값(일)": None, "최대(일)": None}
    return {"줄": len(lags), "중앙값(일)": round(statistics.median(lags), 1), "최대(일)": max(lags)}


# ── 깔때기 ─────────────────────────────────────────────

def _num(sid) -> int:
    m = re.search(r"(\d+)", str(sid or ""))
    return int(m.group(1)) if m else -1


def funnel(n_agg: int, collected, verified) -> dict:
    """집계처 N → 수집 DB n → 검증 완료 m → 실제 데이터 확인.

    collected · verified 는 노션에서 받은 줄이다. None 이면 노션을 안 읽은 것이다.
    「실제 데이터 확인」 = 진위 판정이 확인됨·신뢰성 높음이고 핵심 검증 결과에 샘플 확인이 있는 것.
    게시물이 있다는 것과 데이터가 진짜라는 것은 다른 물음이다.
    """
    out = {"집계처": n_agg, "수집 DB": None, "검증 완료": None, "실제 데이터 확인": None,
           "판정": {}, "검증 DB 전체": None, "분모 밖 검증": {}, "주의": NOTE_NO_KEY}
    if collected is None or verified is None:
        return out
    # 검토 관문. 수집 DB 에 수집기가 자동으로 넣는 줄이 들어온다 (2026-09-06 결정).
    # 「검토 여부」 가 미검토·사건 X 면 「팀이 골라 올린 것」 이 아니다. 빈칸은 자동 이전의 사건이라 사건 O
    collected = [c for c in collected
                 if (c.get("검토 여부") or "사건 O") not in ("미검토", "사건 X")]
    kind_of = {_num(c.get("사건 ID")): (c.get("게시 성격") or BLANK) for c in collected}
    ids = {_num(c.get("사건 ID")) for c in collected
           if c.get("게시 성격") == "랜섬웨어 유출" and c.get("국가") == "한국"}
    ids.discard(-1)
    ver = [v for v in verified if _num(v.get("사건 ID")) in ids]
    out["수집 DB"] = len(ids)
    out["검증 완료"] = len(ver)
    out["실제 데이터 확인"] = sum(
        1 for v in ver if v.get("진위 판정") in CONFIRMED_VERDICTS
        and "샘플 확인" in (v.get("핵심 검증 결과") or []))
    out["판정"] = dict(Counter(v.get("진위 판정") or BLANK for v in ver))
    # 팀이 검증한 것 전체와, 그중 이 분모(랜섬웨어 유출 · 한국) 밖에 있는 것의 성격.
    # 랜섬 KR 깔때기가 0 이어도 「검증을 안 했다」 는 뜻이 아니다. 포럼 게시 검증이 따로 있다
    out["검증 DB 전체"] = len(verified)
    out["분모 밖 검증"] = dict(Counter(
        kind_of.get(_num(v.get("사건 ID")), "(수집 DB 에 없음)")
        for v in verified if _num(v.get("사건 ID")) not in ids))
    return out


def fetch_notion() -> tuple:
    """노션 수집 DB · 검증 DB 에서 깔때기에 쓸 칸만 읽는다. 읽기만 한다."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "darkweb-verify-ko" / "tools"))
    from notion import _call, search, title_of  # noqa: E402

    def ds(name):
        hits = [r for r in search(name) if r.get("object") == "data_source"
                and title_of(r).strip() == name]
        hits.sort(key=lambda r: r.get("last_edited_time", ""), reverse=True)
        if not hits:
            raise SystemExit("노션에서 「%s」 를 못 찾았다" % name)
        return hits[0]["id"]

    def rows(d):
        out, cur = [], None
        while True:
            body = {"page_size": 100}
            if cur:
                body["start_cursor"] = cur
            r = _call("/data_sources/%s/query" % d, "POST", body)
            out += r["results"]
            if not r.get("has_more"):
                return out
            cur = r["next_cursor"]

    def val(p, c):
        x = p.get(c)
        if not x:
            return None
        t = x["type"]
        if t == "select":
            return x["select"]["name"] if x["select"] else ""
        if t == "multi_select":
            return [o["name"] for o in x["multi_select"]]
        if t == "unique_id":
            return "%s-%s" % (x["unique_id"].get("prefix") or "", x["unique_id"]["number"])
        if t == "title":
            return "".join(t_["plain_text"] for t_ in x["title"]).strip()
        return None

    collected = [{"사건 ID": val(r["properties"], "사건 ID"),
                  "게시 성격": val(r["properties"], "게시 성격"),
                  "국가": val(r["properties"], "국가"),
                  "검토 여부": val(r["properties"], "검토 여부")} for r in rows(ds("수집 DB"))]
    verified = [{"사건 ID": val(r["properties"], "사건 ID"),
                 "진위 판정": val(r["properties"], "진위 판정"),
                 "핵심 검증 결과": val(r["properties"], "핵심 검증 결과") or []}
                for r in rows(ds("검증 DB"))]
    return collected, verified


# ── 내보내기 ───────────────────────────────────────────

def _period(rows: list, since, until) -> str:
    days = sorted(r["day"] for r in rows if r["day"])
    lo = since or (days[0] if days else "?")
    hi = until or (days[-1] if days else "?")
    return "%s ~ %s" % (lo, hi)


def render_md(rows: list, funnel: dict, since=None, until=None, now: str | None = None,
              top: int = 10) -> str:
    n = datetime.fromisoformat(now) if now else datetime.now(KST)
    L = ["# 한국 관련 랜섬웨어 유출 게시 — %s" % _period(rows, since, until),
         "",
         "    기준 %s · 분모는 집계처(ransomware.live)가 한국이라고 적은 줄"
         % n.strftime("%Y-%m-%d %H:%M KST"),
         "    한국 여부는 집계처의 국가 칸이다. 오분류 사례가 있다 (2026-08-30 기록 1건)",
         "",
         "## 게시 %d건" % len(rows), ""]

    L.append("**월별**")
    L.append("")
    L.append("| 월 | 건수 |")
    L.append("|---|---|")
    for k, v in by_month(rows).items():
        L.append("| %s | %d |" % (k, v))
    L.append("")

    L.append("**행위자별** (상위 %d)" % top)
    L.append("")
    L.append("| 그룹 | 건수 |")
    L.append("|---|---|")
    for k, v in by_actor(rows, top):
        L.append("| %s | %d |" % (k, v))
    L.append("")

    L.append("**업종별** (집계처 표기 그대로)")
    L.append("")
    L.append("| 업종 | 건수 |")
    L.append("|---|---|")
    for k, v in by_industry(rows):
        L.append("| %s | %d |" % (k, v))
    L.append("")

    s = size_split(rows)
    L += ["**규모 표기**", "",
          "    값 있음 %d · 대시뿐 %d · 빈칸 %d" % (s["값 있음"], s["대시뿐"], s["빈칸"]),
          "    빈칸은 「주장 없음」 이 아니다. 집계처가 안 긁은 것일 수 있다.",
          "    2026-08-29 실측: 한 건은 집계처 웹 화면에만, 한 건은 원 출처에만 규모가 있었다.",
          "    그래서 규모 합계는 내지 않는다.", ""]

    d = discovery_lag(rows)
    L.append("**발견 지연** (집계처가 처음 본 날 − 게시일)")
    L.append("")
    if d["줄"]:
        L.append("    줄 %d · 중앙값 %s일 · 최대 %s일" % (d["줄"], d["중앙값(일)"], d["최대(일)"]))
    else:
        L.append("    아직 없음. 발견일은 2026-09-06 부터 저장한다")
    L.append("")

    f = funnel
    L += ["## 주장과 확인", ""]
    if f["수집 DB"] is None:
        L += ["    집계처 게시 %d건" % f["집계처"],
              "    노션을 안 읽었다 (--no-notion). 검증 수치는 없다", ""]
    else:
        L += ["    집계처 게시                %4d   자동 수집" % f["집계처"],
              "      → 팀이 수집 DB 에 올림     %4d   사람이 골라 올린 것" % f["수집 DB"],
              "        → 검증 완료               %4d   검증 DB 와 사건 ID 로 잇는다" % f["검증 완료"],
              "          → 실제 데이터 확인        %4d   진위 판정 확인됨·신뢰성 높음 + 샘플 확인" % f["실제 데이터 확인"],
              ""]
        if f["판정"]:
            L.append("    검증 완료 %d건의 진위 판정 — %s" % (
                f["검증 완료"], " · ".join("%s %d" % kv for kv in _rank(Counter(f["판정"])))))
            L.append("")
        if f["검증 DB 전체"] is not None:
            outside = f["분모 밖 검증"]
            L.append("    팀이 검증한 것은 전체 %d건이고 그중 이 분모(랜섬웨어 게시 · 한국)에 드는 것이 %d건이다."
                     % (f["검증 DB 전체"], f["검증 완료"]))
            if outside:
                L.append("    나머지 %d건은 이 통계 밖이다 — %s" % (
                    sum(outside.values()), " · ".join("%s %d" % kv for kv in _rank(Counter(outside)))))
            L.append("")
        L += ["**%s**" % f["주의"], ""]
    L += ["게시물이 있다는 것과 데이터가 진짜라는 것은 다른 물음이다. 앞은 여기서 세고 뒤는 사람이 검증한다.", ""]
    return "\n".join(L)


def list_table(rows: list) -> str:
    L = ["| 게시일 | 대상 | 행위자 | 규모 표기 | 업종 |", "|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: r["day"], reverse=True):
        L.append("| %s | %s | %s | %s | %s |" % (
            r["day"] or "-", r.get("target_org") or "-", r.get("actor") or "-",
            (r.get("claimed_size") or "").strip() or "-", r["raw_d"].get("산업 분야") or "-"))
    return "\n".join(L) + "\n"


def render_csv(rows: list, top: int = 10) -> dict:
    def csv(header, pairs):
        buf = io.StringIO()
        buf.write(header + "\n")
        for k, v in pairs:
            buf.write("%s,%d\n" % (str(k).replace(",", " "), v))
        return buf.getvalue()
    return {
        "월별": csv("월,건수", by_month(rows).items()),
        "행위자별": csv("행위자,건수", by_actor(rows, top)),
        "업종별": csv("업종,건수", by_industry(rows)),
        "규모": csv("표기,건수", size_split(rows).items()),
    }


def write_png(out: Path, rows: list, top: int = 10) -> list:
    """matplotlib 이 있으면 그래프 둘. 없으면 빈 목록. 표만으로도 보고서는 된다."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib import font_manager
    except ImportError:
        return []
    for fam in ("Malgun Gothic", "NanumGothic", "Apple SD Gothic Neo"):
        if any(f.name == fam for f in font_manager.fontManager.ttflist):
            matplotlib.rcParams["font.family"] = fam
            break
    matplotlib.rcParams["axes.unicode_minus"] = False
    made = []
    for name, pairs, xl in (("월별", list(by_month(rows).items()), "월"),
                            ("행위자별", by_actor(rows, top), "그룹")):
        if not pairs:
            continue
        fig, ax = plt.subplots(figsize=(max(6, len(pairs) * 0.5), 3.6))
        ax.bar([str(k) for k, _ in pairs], [v for _, v in pairs], color="#c9563f")
        ax.set_ylabel("건수")
        ax.set_xlabel(xl)
        ax.set_title("한국 관련 랜섬웨어 유출 게시 — %s" % name)
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
        fig.tight_layout()
        p = out / ("%s.png" % name)
        fig.savefig(p, dpi=150)
        plt.close(fig)
        made.append(p)
    return made


# ── 명령 ─────────────────────────────────────────────

def main() -> int:
    p = argparse.ArgumentParser(description="한국 관련 랜섬웨어 유출 게시 통계")
    p.add_argument("--db", type=Path, default=DEFAULT_DB, help="수집 표. 기본 %s" % DEFAULT_DB)
    p.add_argument("--since", help="게시일 하한 YYYY-MM-DD")
    p.add_argument("--until", help="게시일 상한 YYYY-MM-DD")
    p.add_argument("--out", required=True, type=Path, help="md · csv · png 를 쓸 폴더")
    p.add_argument("--top", type=int, default=10, help="행위자 상위 몇 개까지")
    p.add_argument("--list", action="store_true", help="대상 조직 목록도 따로 낸다")
    p.add_argument("--no-notion", action="store_true", help="노션을 안 읽는다. 깔때기 없이")
    p.add_argument("--now", help="기준 시각 (ISO)")
    a = p.parse_args()

    from collect.store import Store
    s = Store(a.db)
    rows = load_rows(s.con, a.since, a.until)
    s.close()
    if not rows:
        print("고른 줄이 0개다. 기간과 표를 확인할 것 (%s)" % a.db)
        return 1

    if a.no_notion:
        f = funnel(len(rows), None, None)
    else:
        try:
            collected, verified = fetch_notion()
        except Exception as e:                       # 노션이 막혀도 앞부분은 낸다
            print("노션을 못 읽었다: %s — 깔때기 없이 낸다" % e)
            collected = verified = None
        f = funnel(len(rows), collected, verified)

    a.out.mkdir(parents=True, exist_ok=True)
    stamp = (datetime.fromisoformat(a.now) if a.now else datetime.now(KST)).strftime("%Y%m%d")
    md = render_md(rows, f, a.since, a.until, a.now, a.top)
    (a.out / ("통계_%s.md" % stamp)).write_text(md, encoding="utf-8")
    for name, text in render_csv(rows, a.top).items():
        (a.out / ("%s.csv" % name)).write_text(text, encoding="utf-8")
    pngs = write_png(a.out, rows, a.top)
    if a.list:
        (a.out / ("목록_%s.md" % stamp)).write_text(list_table(rows), encoding="utf-8")

    print("게시 %d건 · 기간 %s" % (len(rows), _period(rows, a.since, a.until)))
    if f["수집 DB"] is not None:
        print("깔때기  집계처 %d → 수집 DB %d → 검증 완료 %d → 실제 데이터 확인 %d"
              % (f["집계처"], f["수집 DB"], f["검증 완료"], f["실제 데이터 확인"]))
    print("썼다  %s  (md · csv 4 · png %d%s)" % (a.out, len(pngs), " · 목록" if a.list else ""))
    if not pngs:
        print("png 는 없다. matplotlib 이 없으면 표만 나간다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
