#!/usr/bin/env python3
"""한국 관련 랜섬웨어 유출 게시 통계. 기자 요청 1번에 답한다.

    python -m collect.stats --since 2026-01-01 --out 07_케이스/_통계
    python -m collect.stats --since 2026-01-01 --out … --list        조직 목록까지
    python -m collect.stats --since 2026-01-01 --out … --no-notion   깔때기 없이
    python -m collect.stats --since … --out … --source telegram --country all   소스를 바꿔서

> 일정 기간 동안 한국 관련 유출은 몇 건이고, 그중 실제 데이터로 확인된 것은 몇 건일까?

앞은 세는 문제고 뒤는 검증의 문제다. 앞은 수집 표(SQLite)에서 세고, 뒤는 노션(수집 DB · 검증 DB)에
있는 것을 사건 ID 로 이어 깔때기로 낸다. **집계처 게시와 수집 DB 사이에는 줄 단위 키가 없다.**
팀이 골라 올린 것이다. 그 문장을 표에 고정한다. 숨기면 표본 추출을 한 것처럼 읽힌다.

## 분모

기본은 `~/data/darkchoco.db` 의 `source='ransom' AND country='KR'` 이다. 집계처 `countryvictims/KR` 을
그대로 받은 줄이라 「집계처가 한국이라고 한 것」 이라는 뜻이 분명하다. 팀 표(448)는 다른 집계처가 섞여
있고 raw 키가 달라 이번에는 안 쓴다 (DEV 5-1 S3). 표는 `--db`, 조건은 `--source` · `--country` 로 바꾼다.

텔레그램과 포럼은 지금 값이 거의 안 나온다. 수집기가 국가와 대상 조직을 안 채우기 때문이다.
2026-09-07 실측 — 텔레그램은 70줄 중 국가가 찬 것이 5줄이고 그 5줄의 값도 `Unknown` 이라 KR 은 0줄이다.
포럼은 표에 한 줄도 없다. 그래서 텔레그램을 셀 때는 `--country all` 이 있어야 뭐라도 나온다.
분모가 얼마나 비었는지는 `denominator()` 가 세고 결과 머리에 그대로 적는다. 안 적으면 몇 줄만
세어 놓고 다 센 것처럼 읽힌다.

## 규모 칸을 그대로 믿지 않는다

값 있음 · 대시뿐 · 빈칸 셋으로 가른다. 대시(`-` `---`)는 값이 아니고, 빈칸은 「주장 없음」 이 아니다.
집계처가 안 긁은 것일 수 있다 (2026-08-29 실측 두 건). 규모 합계 같은 것은 내지 않는다.

## 나가는 것

건수와 업종이다. 조직 목록은 `--list` 를 줄 때만 따로 낸다. 주소·본문은 어디에도 안 나간다.

**행위자 이름이 나가는 것은 `--source ransom` 일 때뿐이다.** `items.actor` 칸은 소스마다 뜻이 다르다.
랜섬은 그 칸이 랜섬웨어 그룹 이름(조직)이지만, 텔레그램·포럼은 `tg_post.py` 가 글의 `author` 칸을
거기 넣어서 개인 계정명이나 개인 이름 꼴 값이 들어간다. 조직명은 내도 되고 개인 계정명은 안 된다.
`--source all` 도 안 내는 쪽으로 간다 — 섞인 줄에서 어느 것이 조직명인지 가를 방법이 없다.

**막는 자리는 `main()` 한 곳이다.** `load_rows` 로 줄을 받은 직후 고유 게시자 수를 먼저 세고,
랜섬이 아니면 그 자리에서 모든 줄의 actor 를 빈 문자열로 만든다. 그 뒤로는 어떤 렌더 함수도
actor 값을 볼 수 없다. 출력 자리마다 관문을 달던 때 두 번 빠뜨렸다 — md 표·csv·png 에는 달고
`--list` 목록에는 안 달아서 개인 계정명이 그대로 나갔다. 렌더 쪽에 남은 `_actor_ok` 는 값을 막는
것이 아니라 **표를 낼지 말지** 를 정한다. 새 출력 자리를 만들어도 자동으로 안전하다.
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
def _표찾기() -> Path:
    """수집 표 자리. 환경변수 → 팀 레포 안 → 홈 순서로 **있는 것**을 고른다.

    2026-09-07 에 두 표를 하나로 합치면서 자리를 팀 레포 `hub/data/` 로 옮겼다.
    거기가 통합 수집기가 이미 쓰던 자리이고, 두 경로가 같은 파일에 써야 같은 사건이
    한 줄로 뭉친다. `.gitignore` 의 `hub/data/` 가 git 으로 나가는 것을 막는다.

    **레포 밖에 두던 규칙은 공개 레포(darkchoco-skills) 시절 것이다.** 팀 레포는
    비공개이고 통합 수집기가 이미 레포 안에 쌓고 있었다. 그래도 본문이 든 파일이라
    커밋에 안 들어가는지는 늘 확인한다.

    스킬을 `cp -R` 로 떼어 가면 레포가 없다. 그때는 홈 자리로 떨어진다.
    """
    import os
    쓸것 = os.environ.get("DARKCHOCO_DB")
    if 쓸것:
        return Path(쓸것)
    for p in (_레포() / "hub" / "data" / "darkchoco.db",
              Path.home() / "data" / "darkchoco.db"):
        if p.is_file():
            return p
    return _레포() / "hub" / "data" / "darkchoco.db"


def _레포() -> Path:
    """이 파일에서 본 저장소 뿌리. skills/collect/x.py 기준 두 칸 위다."""
    return Path(__file__).resolve().parents[2]


DEFAULT_DB = _표찾기()      # DEV 4-3. 제어판이 쓰는 자리
BLANK = "(빈칸)"
CONFIRMED_VERDICTS = ("확인됨", "신뢰성 높음")
NOTE_NO_KEY = ("%s 게시와 수집 DB 사이에는 줄 단위 키가 없다. 팀이 골라 올린 것이지 "
               "표본을 뽑은 것이 아니다.")
# 수집 표의 source 값을 사람이 읽는 말로. 결과 머리와 표 제목에만 쓴다
SOURCE_KO = {"ransom": "랜섬웨어 집계처", "telegram": "텔레그램", "forum": "포럼", "all": "전체 소스"}
# 수집 표의 source 값 → 노션 수집 DB 「소스」 칸의 한글 값. 깔때기에서 줄을 고를 때 쓴다
SOURCE_KIND = {"ransom": "랜섬웨어", "telegram": "텔레그램", "forum": "포럼"}
# items.country 는 ISO 코드고 노션 「국가」 는 한글 select 다. 아는 짝만 적는다.
# 여기 없는 코드로 깔때기를 내면 분모는 그 나라 줄인데 깔때기는 한국 줄이 된다
COUNTRY_KO = {"KR": "한국"}


def _agg_ko(source: str) -> str:
    """게시를 모은 곳을 뭐라 부를까. 랜섬만 집계처(ransomware.live)를 거친다.

    랜섬이 아닌 소스에는 집계처가 없다. 한 문서 안에서 「집계처가 없는 소스라 …」 바로 밑에
    「집계처 게시 70건」 이 나오면 말이 어긋난다. 보이는 라벨만 바꾸고 자료 구조는 그대로 둔다.
    """
    return "집계처" if source == "ransom" else "수집 표"


def _actor_ok(source: str) -> bool:
    """행위자 이름을 내도 되는 소스인가.

    랜섬은 actor 칸이 랜섬웨어 그룹 이름(조직)이다. 텔레그램·포럼은 tg_post.py 가 글의
    `author` 칸을 actor 에 넣어서 개인 계정명이 들어간다. all 은 둘이 섞여 가를 수 없다.

    실제로 값을 지우는 것은 `main()` 한 곳이다 (`_hide_actors`). 여기를 부르는 렌더 쪽은
    「행위자 표를 낼까 게시자 수만 낼까」 를 정할 뿐이다.
    """
    return source == "ransom"


def _hide_actors(rows: list) -> None:
    """모든 줄의 actor 를 빈 문자열로 만든다. 되돌리지 않는다.

    출력 자리마다 관문을 달다가 두 번 빠뜨렸다. 값을 한 곳에서 지우면 빠뜨릴 자리가 없다.
    이 뒤로 오는 렌더 함수는 actor 값을 아예 볼 수 없다.
    """
    for r in rows:
        r["actor"] = ""


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

def _where(source: str, country: str) -> tuple:
    """소스·국가 조건과 그 값. "all" 이면 그 조건을 뺀다.

    값은 반드시 바인딩(?)으로 넣는다. 이어 붙이면 바깥에서 온 값이 SQL 이 된다.
    """
    where, args = [], []
    if source != "all":
        where.append("source=?")
        args.append(source)
    if country != "all":
        where.append("country=?")
        args.append(country)
    return (" WHERE " + " AND ".join(where)) if where else "", args


def load_rows(con, since: str | None = None, until: str | None = None,
              source: str = "ransom", country: str = "KR") -> list:
    """고른 줄. 기간은 게시일(posted_at) 기준이고 날짜 꼴 YYYY-MM-DD 다.

    기본값은 한국 관련 랜섬 줄이다. 인자를 안 주면 동작이 바뀌지 않는다.
    """
    w, args = _where(source, country)
    out = []
    for r in con.execute("SELECT * FROM items%s ORDER BY posted_at" % w, args):
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


def denominator(con, source: str = "ransom", country: str = "KR",
                since: str | None = None, until: str | None = None) -> dict:
    """분모가 얼마나 비었나. 그 소스의 전체 줄과, 국가·대상 조직이 찬 줄과, 지금 필터로 센 줄.

    텔레그램은 telegram_web.py 가 tg_post.py 로 넘겨 줄을 만든다. country 와 target_org 를 실제로
    넣는 곳은 tg_post.py 고 (`PICK["country"]`), 글에 그 칸이 없으면 빈칸으로 남는다
    (2026-09-07 실측: 텔레그램 70줄 중 국가가 찬 것 5줄). 이 숫자를 결과에 안 적으면 몇 줄만
    세어 놓고 다 센 것처럼 읽힌다. 빈칸은 '' 과 NULL 둘 다 빈 것으로 센다. 수집기마다 꼴이 다르다.

    since·until 을 주면 「기간 안」 을 더 내고, 「국가 있음」 · 「대상 조직 있음」 을 기간 안에서 센다.
    안 그러면 「기간 안 114줄」 밑에 「국가가 찬 것 124줄」 처럼 안쪽이 바깥보다 큰 줄이 나온다.
    기간을 안 걸면 「기간 안」 열쇠가 아예 없다 — 안 준 기간을 0 으로 적으면 기간 때문에 빠진 줄과
    국가 칸 때문에 빠진 줄이 구분이 안 된다. 「전체」 는 언제나 기간을 안 건 그 소스 전체다.
    """
    src_w, src_args = _where(source, "all")          # 국가는 빼고 그 소스 전체를 본다
    total, has_country, has_org = con.execute(
        "SELECT COUNT(*),"
        " SUM(CASE WHEN country    IS NOT NULL AND country    <> '' THEN 1 ELSE 0 END),"
        " SUM(CASE WHEN target_org IS NOT NULL AND target_org <> '' THEN 1 ELSE 0 END)"
        " FROM items%s" % src_w, src_args).fetchone()
    w, args = _where(source, country)
    used = con.execute("SELECT COUNT(*) FROM items%s" % w, args).fetchone()[0]
    out = {"소스": source, "전체": total, "국가 있음": has_country or 0,
           "대상 조직 있음": has_org or 0, "쓴 것": used}
    if since or until:
        # 날짜 판정은 load_rows 와 같은 _day() 로 한다. SQL 로 문자열 비교를 하면
        # posted_at 꼴(마이크로초 유무·시간대)에 따라 load_rows 와 숫자가 어긋난다
        n = n_country = n_org = 0
        for p, ctry, org in con.execute(
                "SELECT posted_at, country, target_org FROM items%s" % src_w, src_args):
            day = _day(p or "")
            if since and (not day or day < since):
                continue
            if until and (not day or day > until):
                continue
            n += 1
            n_country += 0 if ctry in (None, "") else 1
            n_org += 0 if org in (None, "") else 1
        out["기간 안"] = n
        out["국가 있음"] = n_country
        out["대상 조직 있음"] = n_org
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


def actor_unique(rows: list) -> int:
    """빈칸을 뺀 고유 actor 수. 랜섬이 아닌 소스에서는 이 숫자만 낸다.

    이름은 하나도 안 내고 몇 명인지만 센다. 개인 계정명이 산출물로 나가면 안 된다.
    """
    return len({(r.get("actor") or "").strip() for r in rows if (r.get("actor") or "").strip()})


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


def _pick_source(c: dict, source: str) -> bool:
    """수집 DB 줄 하나가 이 소스에 드는가.

    「소스」 칸은 2026-09-06 에 만들었고 옛 줄은 아직 비어 있다. 새 칸을 쓰되 옛 줄이 통째로
    빠지지 않게 게시 성격으로 되짚는 층을 남긴다. 되짚기는 ransom 일 때만 된다 —
    「소스」 칸이 빈 줄이 텔레그램인지 포럼인지는 알 방법이 없다.
    """
    if source == "all":
        return True
    kind = (c.get("소스") or "").strip()
    if kind:
        return kind == SOURCE_KIND.get(source)
    if source == "ransom":
        return c.get("게시 성격") == "랜섬웨어 유출"
    return False


def funnel(n_agg: int, collected, verified, source: str = "ransom", country: str = "KR") -> dict:
    """집계처 N → 수집 DB n → 검증 완료 m → 실제 데이터 확인.

    collected · verified 는 노션에서 받은 줄이다. None 이면 노션을 안 읽은 것이다.
    「실제 데이터 확인」 = 진위 판정이 확인됨·신뢰성 높음이고 핵심 검증 결과에 샘플 확인이 있는 것.
    게시물이 있다는 것과 데이터가 진짜라는 것은 다른 물음이다.

    **줄을 고를 때 노션 「소스」 칸을 게시 성격보다 먼저 본다. 의도한 설계다** (`_pick_source`).
    2026-09-07 지금은 「소스」 칸이 전부 비어 있어 실제 숫자가 안 바뀌지만, 수집기가 그 칸을 채우기
    시작하면 게시 성격과 어긋나는 줄에서 숫자가 달라진다. 기본 인자(ransom · KR)로 돌려도 움직인다.
    그때는 「소스」 칸이 더 정확하다 — 게시 성격은 글의 내용이고 소스는 어디서 났나다.

    국가는 items 가 ISO 코드고 노션이 한글이라 COUNTRY_KO 로 잇는다. 짝을 모르는 코드면
    깔때기를 아예 안 낸다. 틀린 숫자를 내느니 안 내는 쪽이 맞다.
    """
    out = {"집계처": n_agg, "수집 DB": None, "검증 완료": None, "실제 데이터 확인": None,
           "판정": {}, "검증 DB 전체": None, "분모 밖 검증": {},
           "주의": NOTE_NO_KEY % _agg_ko(source)}
    if collected is None or verified is None:
        return out
    country_ko = None
    if country != "all":
        country_ko = COUNTRY_KO.get(country)
        if country_ko is None:
            # 분모는 그 나라 줄인데 깔때기만 한국 줄이면 다른 모집단이 한 표에 붙는다
            out["국가 못 잇음"] = ("국가 %s 는 수집 DB 국가 표기와 잇는 짝을 모른다. "
                              "깔때기를 내지 않는다" % country)
            return out
    # 검토 관문. 수집 DB 에 수집기가 자동으로 넣는 줄이 들어온다 (2026-09-06 결정).
    # 「검토 여부」 가 미검토·사건 X 면 「팀이 골라 올린 것」 이 아니다. 빈칸은 자동 이전의 사건이라 사건 O
    collected = [c for c in collected
                 if (c.get("검토 여부") or "사건 O") not in ("미검토", "사건 X")]
    kind_of = {_num(c.get("사건 ID")): (c.get("게시 성격") or BLANK) for c in collected}
    # 국가 조건은 COUNTRY_KO 로 옮긴 한글 값으로 건다. all 이면 조건을 안 건다
    ids = {_num(c.get("사건 ID")) for c in collected
           if _pick_source(c, source) and (country_ko is None or c.get("국가") == country_ko)}
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

    # 「소스」 칸은 2026-09-06 에 만들었다. 아직 빈 줄이 있어서 깔때기가 게시 성격으로 되짚는다
    collected = [{"사건 ID": val(r["properties"], "사건 ID"),
                  "소스": val(r["properties"], "소스"),
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
              top: int = 10, source: str = "ransom", country: str = "KR",
              den: dict | None = None, n_actor: int | None = None) -> str:
    """n_actor 는 actor 를 지우기 전에 센 고유 게시자 수다. 안 주면 여기서 센다.

    main() 은 actor 를 이미 지우고 부르기 때문에 여기서 세면 0 이 나온다. 그래서 미리 센 값을 받는다.
    """
    n = datetime.fromisoformat(now) if now else datetime.now(KST)
    ko = SOURCE_KO.get(source, source)
    kuk = "조건 없음" if country == "all" else country
    if source == "ransom" and country == "KR":
        L = ["# %s — %s" % (_title(source, country), _period(rows, since, until)),
             "",
             "    기준 %s · 분모는 집계처(ransomware.live)가 한국이라고 적은 줄"
             % n.strftime("%Y-%m-%d %H:%M KST"),
             "    한국 여부는 집계처의 국가 칸이다. 오분류 사례가 있다 (2026-08-30 기록 1건)",
             ""]
    else:
        # 분모가 바뀌면 무엇을 셌는지부터 적는다. 제목만 보고 소스를 짐작하게 두지 않는다
        L = ["# %s — %s" % (_title(source, country), _period(rows, since, until)),
             "",
             "    기준 %s" % n.strftime("%Y-%m-%d %H:%M KST"),
             "    분모  %s · 국가 %s · %d줄" % (source, kuk, len(rows))]
        if den:
            # 기간을 건 숫자를 같이 적는다. 안 적으면 기간 때문에 빠진 줄이 국가 칸 때문인 것처럼 읽힌다
            gi = ("기간 안에 든 것 %d줄. " % den["기간 안"]) if "기간 안" in den else ""
            L.append("          그 소스 전체 %d줄. %s그중 국가가 찬 것 %d줄 · 대상 조직이 찬 것 %d줄"
                     % (den["전체"], gi, den["국가 있음"], den["대상 조직 있음"]))
            # 같은 모집단끼리 견준다. 「국가 있음」 은 기간을 걸면 기간 안에서 센 값이라,
            # 기간을 안 건 「전체」 와 견주면 기간이 좁을수록 분자만 줄어 경고가 헛나간다
            # (2026-09-07 실측: 랜섬 11/11 로 다 찬 것에 「절반도 안 된다」 가 찍혔다)
            base = den.get("기간 안", den["전체"])
            if base and den["국가 있음"] * 2 < base:
                L.append("    주의  국가가 찬 줄이 절반도 안 된다. 수집기가 국가를 안 채운다")
                if country != "all":
                    # all 이면 국가 조건을 아예 안 걸어서 국가 칸이 비어도 분모에서 안 빠진다.
                    # 그때 이 문장은 거짓이다. 조건을 걸었을 때만 낸다
                    L.append("          이 분모는 「%s 게시 전부」 가 아니라 「국가 칸이 찬 몇 줄」 이다" % ko)
        L.append("")
    L += ["## 게시 %d건" % len(rows), ""]

    L.append("**월별**")
    L.append("")
    L.append("| 월 | 건수 |")
    L.append("|---|---|")
    for k, v in by_month(rows).items():
        L.append("| %s | %d |" % (k, v))
    L.append("")

    # 같은 actor 칸이지만 랜섬은 랜섬웨어 그룹 이름(조직)이고, 텔레그램·포럼은 tg_post.py 가
    # 글의 `author` 칸을 거기 넣어 개인 계정명이 들어간다. 조직명은 되고 개인 계정명은 안 된다
    if _actor_ok(source):
        L.append("**행위자별** (상위 %d)" % top)
        L.append("")
        L.append("| 그룹 | 건수 |")
        L.append("|---|---|")
        for k, v in by_actor(rows, top):
            L.append("| %s | %d |" % (k, v))
    else:
        L.append("**게시자별**")
        L.append("")
        L.append("    게시자 이름은 개인 계정일 수 있어 내지 않는다. 고유 게시자 %d명만 센다"
                 % (actor_unique(rows) if n_actor is None else n_actor))
    L.append("")

    L.append("**업종별** (%s 표기 그대로)" % _agg_ko(source))
    L.append("")
    L.append("| 업종 | 건수 |")
    L.append("|---|---|")
    for k, v in by_industry(rows):
        L.append("| %s | %d |" % (k, v))
    L.append("")

    s = size_split(rows)
    L += ["**규모 표기**", "",
          "    값 있음 %d · 대시뿐 %d · 빈칸 %d" % (s["값 있음"], s["대시뿐"], s["빈칸"])]
    if source == "ransom":
        L += ["    빈칸은 「주장 없음」 이 아니다. 집계처가 안 긁은 것일 수 있다.",
              "    2026-08-29 실측: 한 건은 집계처 웹 화면에만, 한 건은 원 출처에만 규모가 있었다.",
              "    그래서 규모 합계는 내지 않는다."]
    else:
        # 집계처를 안 거친 소스다. 빈칸을 만든 것은 집계처가 아니라 우리 수집기다
        L += ["    빈칸은 「주장 없음」 이 아니다. 수집기가 안 채운 것일 수 있다.",
              "    글에 규모 칸이 없으면 그대로 빈칸이 된다. 그래서 규모 합계는 내지 않는다.",
              "    대시를 값 없음으로 보는 것은 랜섬 집계처 관례다. 다른 소스에서는 대시가 값일 수 있다."]
    L.append("")

    L.append("**발견 지연** (집계처가 처음 본 날 − 게시일)")
    L.append("")
    # 발견일은 집계처가 준다. 집계처가 없는 소스에서는 뺄 두 날짜 중 하나가 없다.
    # all 은 섞여 있으니 랜섬 줄만 골라 내고, 몇 줄로 냈는지를 같이 적는다
    lag_rows = rows if source == "ransom" else (
        [r for r in rows if (r.get("source") or "") == "ransom"] if source == "all" else [])
    if source not in ("ransom", "all"):
        L.append("    집계처가 없는 소스라 발견일 지연을 못 낸다")
    elif source == "all" and not lag_rows:
        L.append("    소스가 섞여 있고 랜섬 줄이 없다. 발견일 지연을 못 낸다")
    else:
        d = discovery_lag(lag_rows)
        if d["줄"]:
            L.append("    줄 %d · 중앙값 %s일 · 최대 %s일" % (d["줄"], d["중앙값(일)"], d["최대(일)"]))
            if source == "all":
                L.append("    랜섬 줄 %d개로만 냈다. 다른 소스는 집계처가 없어 발견일이 없다"
                         % len(lag_rows))
        else:
            L.append("    아직 없음. 발견일은 2026-09-06 부터 저장한다%s"
                     % (" (랜섬 줄 %d개를 봤다)" % len(lag_rows) if source == "all" else ""))
    L.append("")

    f = funnel
    agg = _agg_ko(source)                 # 랜섬만 집계처를 거친다. 그 밖은 우리 수집 표가 시작점이다
    L += ["## 주장과 확인", ""]
    if f["수집 DB"] is None:
        L += ["    %s 게시 %d건" % (agg, f["집계처"])]
        if f.get("국가 못 잇음"):
            L.append("    " + f["국가 못 잇음"])
        else:
            L.append("    노션을 안 읽었다 (--no-notion). 검증 수치는 없다")
        L.append("")
    else:
        L += ["    %s 게시                %4d   자동 수집" % (agg, f["집계처"]),
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
            scope = ("랜섬웨어 게시 · 한국" if (source == "ransom" and country == "KR")
                     else "%s · 국가 %s" % (ko, kuk))
            L.append("    팀이 검증한 것은 전체 %d건이고 그중 이 분모(%s)에 드는 것이 %d건이다."
                     % (f["검증 DB 전체"], scope, f["검증 완료"]))
            if outside:
                L.append("    나머지 %d건은 이 통계 밖이다 — %s" % (
                    sum(outside.values()), " · ".join("%s %d" % kv for kv in _rank(Counter(outside)))))
            L.append("")
        L += ["**%s**" % f["주의"], ""]
    L += ["게시물이 있다는 것과 데이터가 진짜라는 것은 다른 물음이다. 앞은 여기서 세고 뒤는 사람이 검증한다.", ""]
    return "\n".join(L)


def list_table(rows: list, source: str = "ransom") -> str:
    """대상 조직 목록. 랜섬이 아니면 「행위자」 칸 자체를 뺀다.

    main() 이 actor 를 이미 지워서 값은 어차피 안 나가지만, 빈칸만 늘어선 칸은 뜻이 없다.
    남는 칸(게시일 · 대상 · 규모 표기 · 업종)은 그대로 낸다.
    """
    show_actor = _actor_ok(source)
    head = ["게시일", "대상"] + (["행위자"] if show_actor else []) + ["규모 표기", "업종"]
    L = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r in sorted(rows, key=lambda r: r["day"], reverse=True):
        cells = [r["day"] or "-", r.get("target_org") or "-"]
        if show_actor:
            cells.append(r.get("actor") or "-")
        cells += [(r.get("claimed_size") or "").strip() or "-", r["raw_d"].get("산업 분야") or "-"]
        L.append("| " + " | ".join(cells) + " |")
    return "\n".join(L) + "\n"


def render_csv(rows: list, top: int = 10, source: str = "ransom") -> dict:
    """csv 로 낼 표. 행위자별은 랜섬일 때만 만든다.

    랜섬이 아니면 actor 가 개인 계정명이라 파일로도 안 낸다. 안 만들면 md 와 csv 의 이름이
    어긋날 일도 없다 — md 는 「게시자별」 인데 csv 만 「행위자별」 로 남던 것이 사라진다.
    """
    def csv(header, pairs):
        buf = io.StringIO()
        buf.write(header + "\n")
        for k, v in pairs:
            buf.write("%s,%d\n" % (str(k).replace(",", " "), v))
        return buf.getvalue()
    out = {
        "월별": csv("월,건수", by_month(rows).items()),
        "업종별": csv("업종,건수", by_industry(rows)),
        "규모": csv("표기,건수", size_split(rows).items()),
    }
    if _actor_ok(source):
        out["행위자별"] = csv("행위자,건수", by_actor(rows, top))
    return out


def actor_placeholder_csv(n: int) -> str:
    """랜섬이 아닐 때 행위자별.csv 자리에 덮어쓸 한 줄짜리 표.

    같은 --out 폴더에 소스를 바꿔 다시 돌리는 것이 자연스러운 쓰임이라, 안 만들기만 하면
    옛 판이 그대로 남는다. 지우지 않고 덮는다 — 지우기는 되돌릴 수 없고, 덮으면 옛 값이
    확실히 사라진다. 머리글에 이름을 안 낸다는 것을 적어 둔다.
    """
    return "항목(게시자 이름은 개인 계정일 수 있어 내지 않는다),건수\n고유 게시자 수,%d\n" % n


def _title(source: str, country: str) -> str:
    """그림·문서 제목. md 와 png 가 같은 말을 쓰게 한 곳에 모은다."""
    if source == "ransom" and country == "KR":
        return "한국 관련 랜섬웨어 유출 게시"
    return "%s 게시" % SOURCE_KO.get(source, source)


def write_png(out: Path, rows: list, top: int = 10, source: str = "ransom",
              country: str = "KR") -> list:
    """matplotlib 이 있으면 그래프 둘. 없으면 빈 목록. 표만으로도 보고서는 된다.

    행위자별 그림은 랜섬일 때만 그린다. 랜섬이 아니면 x축에 개인 계정명이 그대로 박힌다.
    제목도 source 를 받아 md 와 같은 말을 쓴다. 안 받으면 텔레그램 그림에 「랜섬웨어」 가 나간다.
    """
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
    charts = [("월별", list(by_month(rows).items()), "월")]
    if _actor_ok(source):
        charts.append(("행위자별", by_actor(rows, top), "그룹"))
    title = _title(source, country)
    for name, pairs, xl in charts:
        if not pairs:
            continue
        fig, ax = plt.subplots(figsize=(max(6, len(pairs) * 0.5), 3.6))
        ax.bar([str(k) for k, _ in pairs], [v for _, v in pairs], color="#c9563f")
        ax.set_ylabel("건수")
        ax.set_xlabel(xl)
        ax.set_title("%s — %s" % (title, name))
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
        fig.tight_layout()
        p = out / ("%s.png" % name)
        fig.savefig(p, dpi=150)
        plt.close(fig)
        made.append(p)
    return made


# ── 명령 ─────────────────────────────────────────────

def main() -> int:
    p = argparse.ArgumentParser(
        description="유출 게시 통계. --source 로 랜섬웨어 집계처 · 텔레그램 · 포럼을 고른다 (기본 ransom · KR)")
    p.add_argument("--db", type=Path, default=DEFAULT_DB, help="수집 표. 기본 %s" % DEFAULT_DB)
    p.add_argument("--since", help="게시일 하한 YYYY-MM-DD")
    p.add_argument("--until", help="게시일 상한 YYYY-MM-DD")
    p.add_argument("--source", choices=("ransom", "telegram", "forum", "all"), default="ransom",
                   help="어느 소스를 셀까. 기본 ransom")
    p.add_argument("--country", default="KR",
                   help="국가 칸 값. all 을 주면 국가 조건을 뺀다. 기본 KR")
    p.add_argument("--out", required=True, type=Path, help="md · csv · png 를 쓸 폴더")
    p.add_argument("--top", type=int, default=10, help="행위자 상위 몇 개까지")
    p.add_argument("--list", action="store_true", help="대상 조직 목록도 따로 낸다")
    p.add_argument("--no-notion", action="store_true", help="노션을 안 읽는다. 깔때기 없이")
    p.add_argument("--now", help="기준 시각 (ISO)")
    a = p.parse_args()

    from collect.store import Store
    s = Store(a.db)
    rows = load_rows(s.con, a.since, a.until, a.source, a.country)
    den = denominator(s.con, a.source, a.country, a.since, a.until)
    s.close()

    # 게시자 이름을 막는 자리는 여기 하나다. 출력 자리마다 관문을 달다가 두 번 빠뜨렸다
    # (md 표·csv·png 에는 달고 --list 목록에는 안 달았다). 값을 한 곳에서 지우면 빠뜨릴 자리가 없다.
    # 아래 어떤 렌더 함수도 이 뒤로는 actor 값을 볼 수 없다. 수는 지우기 전에 미리 세 둔다
    n_actor = actor_unique(rows)
    if not _actor_ok(a.source):
        _hide_actors(rows)

    if not rows:
        print("고른 줄이 0개다. 기간과 표를 확인할 것 (%s · 소스 %s · 국가 %s)"
              % (a.db, a.source, a.country))
        if a.country != "all":
            # 「N줄 중 M줄」 로 읽히는 두 수는 모집단이 같아야 한다. 「전체」 는 기간을 안 건 값이고
            # 「국가 있음」 은 기간을 걸면 기간 안에서 센 값이다. 기간을 걸었으면 문장을 갈라 적는다
            if "기간 안" in den:
                print("  그 소스 전체 %d줄. 그중 기간 안에 든 것 %d줄" % (den["전체"], den["기간 안"]))
                print("  기간 안 %d줄 중 국가가 찬 것 %d줄. 국가를 빼려면 --country all"
                      % (den["기간 안"], den["국가 있음"]))
            else:
                print("  그 소스 전체 %d줄 중 국가가 찬 것 %d줄. 국가를 빼려면 --country all"
                      % (den["전체"], den["국가 있음"]))
        else:
            # 이미 국가를 뺐다. 그 줄을 또 찍으면 안 해 본 수를 권하는 꼴이 된다
            print("  그 소스 전체 %d줄. 국가 조건은 이미 뺐으니 기간 때문일 수 있다%s"
                  % (den["전체"],
                     " (기간 안에 든 것 %d줄)" % den["기간 안"] if "기간 안" in den else ""))
        return 1

    if a.no_notion:
        f = funnel(len(rows), None, None, a.source, a.country)
    else:
        try:
            collected, verified = fetch_notion()
        except Exception as e:                       # 노션이 막혀도 앞부분은 낸다
            # em dash(U+2014)를 안 쓴다. cp949 콘솔·파이프에서 이 줄이 UnicodeEncodeError 로 죽어
            # 앞부분이라도 내려던 안내가 오히려 프로그램을 끊었다
            print("노션을 못 읽었다: %s · 깔때기 없이 낸다" % e)
            collected = verified = None
        f = funnel(len(rows), collected, verified, a.source, a.country)

    a.out.mkdir(parents=True, exist_ok=True)
    stamp = (datetime.fromisoformat(a.now) if a.now else datetime.now(KST)).strftime("%Y%m%d")
    md = render_md(rows, f, a.since, a.until, a.now, a.top, a.source, a.country, den, n_actor)
    (a.out / ("통계_%s.md" % stamp)).write_text(md, encoding="utf-8")
    csvs = render_csv(rows, a.top, a.source)
    for name, text in csvs.items():
        (a.out / ("%s.csv" % name)).write_text(text, encoding="utf-8")
    n_csv = len(csvs)
    pngs = write_png(a.out, rows, a.top, a.source, a.country)
    if a.list:
        (a.out / ("목록_%s.md" % stamp)).write_text(list_table(rows, a.source), encoding="utf-8")
    if not _actor_ok(a.source):
        # 옛 산출물이 같은 폴더에 남는 문제. 안 만들기만 하면 앞서 랜섬으로 돌린 판이 그대로 남는다.
        # 지우지 않고 덮는다. 목록은 --list 를 안 줘도, 그 자리에 옛 파일이 있으면 새 판이 덮는다
        (a.out / "행위자별.csv").write_text(actor_placeholder_csv(n_actor), encoding="utf-8")
        n_csv += 1
        for p in sorted(a.out.glob("목록_*.md")):
            p.write_text(list_table(rows, a.source), encoding="utf-8")

    print("게시 %d건 · 기간 %s" % (len(rows), _period(rows, a.since, a.until)))
    if a.source != "ransom" or a.country != "KR":
        # 화면에 나가는 줄에는 cp949 에 없는 글자를 안 쓴다. 대시(U+2014)에서 콘솔이 죽는다
        gi = (" 기간 안에 든 것 %d줄." % den["기간 안"]) if "기간 안" in den else ""
        print("분모  %s · 국가 %s · 그 소스 전체 %d줄.%s 그중 국가가 찬 것 %d줄 · 대상 조직이 찬 것 %d줄"
              % (a.source, a.country, den["전체"], gi, den["국가 있음"], den["대상 조직 있음"]))
    if f["수집 DB"] is not None:
        print("깔때기  %s %d → 수집 DB %d → 검증 완료 %d → 실제 데이터 확인 %d"
              % (_agg_ko(a.source), f["집계처"], f["수집 DB"], f["검증 완료"], f["실제 데이터 확인"]))
    elif f.get("국가 못 잇음"):
        print("깔때기  " + f["국가 못 잇음"])
    print("썼다  %s  (md · csv %d · png %d%s)"
          % (a.out, n_csv, len(pngs), " · 목록" if a.list else ""))
    if not pngs:
        print("png 는 없다. matplotlib 이 없으면 표만 나간다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
