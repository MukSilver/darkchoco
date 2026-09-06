#!/usr/bin/env python3
"""랜섬 게시 상태 추적. 협상 기한이 지난 뒤 무엇이 됐는지를 센다.

    python -m collect.track agg                          집계처 한 판. 매일 한 번
    python -m collect.track obs "SAMPLE E&C" --state 게시\ 중 --countdown "9일 3시간 14분" --size 50GB
    python -m collect.track obs u-…  --state 공개됨 --files 12 --at 2026-09-08T09:00+09:00
    python -m collect.track report --out 랜섬_게시상태.md
    python -m collect.track pull                         노션 수집 DB 의 관측 칸 → post_obs

낼 세 숫자 (DEV 5-5). 협상 기한 종료 후 실제 데이터가 공개된 건수 · 게시물이 사라진 사례 ·
공개 여부가 불명확한 사례. 만료 전후를 대조해서 나온다.

## 관측이 두 갈래다

    집계처 (agg)     ransomware.live KR 목록. 자동. 한 판에 요청 1회. **있나 없나만 안다**
    원 출처 (origin)  DLS onion. 사람이 Tor 로 열어 보고 적는다. 카운트다운·공개 여부·파일 수를 안다

집계처 API 에는 카운트다운도 공개 여부도 없다(2026-09-06 실측, 칸 11개). 그래서 자동으로
알 수 있는 것은 「안 보임」뿐이고 세 숫자의 본체는 사람 관측에서 온다. **이 도구는 원 출처를
열지 않는다.** 116곳 재방문은 활동 경계 확인이 먼저다.

## 기록은 items 와 같은 파일의 post_obs 표

uid 로 잇는다. 한 줄이 관측 하나다. 갈아 끼우지 않고 쌓는다. 변화가 곧 데이터다.

    state   게시 중 · 공개됨 · 사라짐 · 연장 · 안 보임 · 불명
            앞 넷은 8/29 sampleenc 에서 세운 갈래(가 공개 · 나 내려감 · 다 연장)이고
            「안 보임」 은 집계처 전용, 「불명」 은 원 출처를 열었는데 못 가른 것이다

집계처 「안 보임」 한 번은 안 센다. 두 판 연속이어야 사라진 것으로 본다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

KST = timezone(timedelta(hours=9))
DEFAULT_DB = Path.home() / "data" / "darkchoco.db"      # DEV 4-3. 제어판이 쓰는 자리

STATES = ("게시 중", "공개됨", "사라짐", "연장", "안 보임", "불명")
SRCS = ("agg", "origin")

POST_OBS_SQL = """
CREATE TABLE IF NOT EXISTS post_obs (
    uid          TEXT NOT NULL,            -- items.uid
    observed_at  TEXT NOT NULL,            -- KST ISO
    src          TEXT NOT NULL,            -- agg | origin
    by           TEXT NOT NULL,            -- 도구 이름 또는 사람
    state        TEXT NOT NULL,            -- 게시 중 | 공개됨 | 사라짐 | 연장 | 안 보임 | 불명
    countdown    TEXT DEFAULT '',          -- 화면 표기 원문. 바꾸지 않는다
    expiry_est   TEXT DEFAULT '',          -- countdown 과 observed_at 으로 계산한 만료
    files_n      INTEGER,                  -- 공개됨일 때 파일 수. 안 셌으면 NULL
    size_claim   TEXT DEFAULT '',          -- 화면의 규모 표기 원문
    note         TEXT DEFAULT ''           -- 근거 한 줄. 값·주소를 넣지 않는다
);
CREATE INDEX IF NOT EXISTS ix_post_obs_uid ON post_obs(uid, observed_at);
"""


class 대상없음(Exception):
    pass


def ensure(con) -> None:
    con.executescript(POST_OBS_SQL)


def now_iso() -> str:
    return datetime.now(KST).replace(microsecond=0).isoformat()


def _dt(s: str) -> datetime:
    d = datetime.fromisoformat(s)
    return d if d.tzinfo else d.replace(tzinfo=KST)


# ── 카운트다운 ─────────────────────────────────────────

_UNIT = re.compile(
    r"(\d+)\s*(일|days?|d\b|시간|hours?|h\b|분|min(?:ute)?s?|m\b|초|sec(?:ond)?s?|s\b)", re.I)
_CLOCK = re.compile(r"(?<!\d)(\d{1,3}):(\d{2}):(\d{2})(?!\d)")


def parse_countdown(text: str):
    """「19일 7시간」 「9 days 3 hours」 「9d 03:14:37」 을 timedelta 로. 모르면 None.

    화면 표기를 그대로 받는다. 숫자와 단위가 하나도 없으면 None 이다 —
    「만료」 「곧」 같은 글자는 시간이 아니다.
    """
    s = (text or "").strip()
    if not s:
        return None
    td = timedelta(0)
    hit = False
    rest = s
    m = _CLOCK.search(s)
    if m:
        h, mi, se = (int(x) for x in m.groups())
        td += timedelta(hours=h, minutes=mi, seconds=se)
        hit = True
        rest = s[:m.start()] + " " + s[m.end():]
    for num, unit in _UNIT.findall(rest):
        n = int(num)
        u = unit.lower()
        if u.startswith(("일", "d")):
            td += timedelta(days=n)
        elif u.startswith(("시", "h")):
            td += timedelta(hours=n)
        elif u.startswith(("분", "m")):
            td += timedelta(minutes=n)
        else:
            td += timedelta(seconds=n)
        hit = True
    return td if hit else None


def expiry_from(observed_at: str, countdown: str) -> str:
    """관측 시각 + 잔여 시간 = 만료 추정. 잔여 시간을 못 읽으면 빈칸."""
    td = parse_countdown(countdown)
    if td is None:
        return ""
    return (_dt(observed_at) + td).replace(microsecond=0).isoformat()


# ── 대상 찾기 ─────────────────────────────────────────

def resolve_uid(con, query: str) -> str:
    """uid 그대로, 아니면 대상 조직 이름 조각. **하나로 좁혀져야 한다.**"""
    q = (query or "").strip()
    if not q:
        raise 대상없음("대상이 비었다")
    if con.execute("SELECT 1 FROM items WHERE uid=?", (q,)).fetchone():
        return q
    rows = con.execute(
        "SELECT uid, target_org FROM items WHERE lower(target_org) LIKE ? ORDER BY first_seen DESC",
        ("%" + q.lower() + "%",)).fetchall()
    if len(rows) == 1:
        return rows[0]["uid"]
    if not rows:
        raise 대상없음("「%s」 에 맞는 줄이 없다" % q)
    raise 대상없음("「%s」 가 %d줄에 걸린다. 더 좁혀라: %s"
                 % (q, len(rows), " · ".join(r["target_org"] for r in rows[:6])))


# ── 기록 ─────────────────────────────────────────────

def record(con, uid: str, *, src: str, by: str, state: str, countdown: str = "",
           at: str | None = None, expiry_est: str = "", files_n=None,
           size_claim: str = "", note: str = "") -> None:
    if state not in STATES:
        raise ValueError("모르는 상태 %r. 되는 것: %s" % (state, " · ".join(STATES)))
    if src not in SRCS:
        raise ValueError("src 는 agg 나 origin 이다: %r" % src)
    ensure(con)
    at = at or now_iso()
    if not expiry_est and countdown:
        expiry_est = expiry_from(at, countdown)
    cur = con.execute(
        "INSERT INTO post_obs (uid, observed_at, src, by, state, countdown, expiry_est, "
        "files_n, size_claim, note) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (uid, at, src, by, state, countdown or "", expiry_est or "",
         files_n, size_claim or "", note or ""))
    con.commit()
    return cur.lastrowid


def mark_agg(con, seen: set, at: str, by: str) -> int:
    """집계처 한 판의 결과를 KR 랜섬 줄마다 적는다. 보였으면 게시 중, 안 보였으면 안 보임."""
    ensure(con)
    uids = [r["uid"] for r in con.execute(
        "SELECT uid FROM items WHERE source='ransom' AND country='KR'")]
    for u in uids:
        record(con, u, src="agg", by=by, at=at,
               state="게시 중" if u in seen else "안 보임")
    return len(uids)


# ── 세 숫자 ───────────────────────────────────────────

def _obs_by_uid(con) -> dict:
    out = {}
    for r in con.execute("SELECT * FROM post_obs ORDER BY uid, observed_at"):
        out.setdefault(r["uid"], []).append(dict(r))
    return out


def _expiry(obs: list) -> str:
    """가장 최근에 적힌 만료 추정. 연장이 있으면 그것이 이긴다."""
    for o in reversed(obs):
        if o["expiry_est"]:
            return o["expiry_est"]
    return ""


def classify(obs: list, now: datetime) -> str:
    """관측 묶음 하나를 공개됨 · 사라짐 · 연장 · 불명 · '' 로.

    한 자리는 한 칸에만 든다. 공개됨 > 사라짐 > 연장 > 불명 순서다.
    """
    origin = [o for o in obs if o["src"] == "origin"]
    agg = [o for o in obs if o["src"] == "agg"]
    last_o = origin[-1]["state"] if origin else ""
    if last_o == "공개됨":
        return "공개됨"
    if last_o == "사라짐":
        return "사라짐"
    if len(agg) >= 2 and agg[-1]["state"] == "안 보임" and agg[-2]["state"] == "안 보임":
        return "사라짐"
    if last_o == "연장":
        return "연장"
    exp = _expiry(obs)
    expired = bool(exp) and _dt(exp) < now
    # 「공개 여부 불명」 은 **기한이 지난 뒤**의 물음이다. 만료 전의 불명(사이트가 안 열렸다 등)은
    # 아직 못 본 것이지 모르는 것이 아니다. 만료를 모르는 건은 불명 그대로 센다.
    if last_o == "불명":
        return "불명" if (not exp or expired) else ""
    if expired:
        after = [o for o in origin if _dt(o["observed_at"]) >= _dt(exp)]
        if not after:
            return "불명"
    return ""


def numbers(con, now: str | None = None) -> dict:
    n = _dt(now) if now else datetime.now(KST)
    out = {"공개됨": [], "사라짐": [], "연장": [], "불명": []}
    for uid, obs in _obs_by_uid(con).items():
        k = classify(obs, n)
        if k:
            out[k].append(uid)
    return out


# ── 노션에서 끌어오기 ───────────────────────────────
# 사람 관측은 노션 수집 DB 의 그 게시물 행에 적는다 (2026-09-06 결정. 관측 DB 를 따로 두지 않는다).
# 노션에는 마지막 관측만 있다. 여기서 읽어 갈 때마다 post_obs 에 한 줄씩 쌓여 이력이 된다.
# 칸 이름은 01_회의/노션DB_설계_후보_관측_20260906.md 와 같다.

OBS_COLS = ("관측 시각", "게시 상태", "카운트다운 표기", "공개된 파일 수", "관측 근거", "관측자")


def pull_rows(con, rows: list) -> dict:
    """노션 수집 DB 행(딕셔너리 목록)에서 관측을 post_obs 로. 이미 있는 (uid, 시각) 은 안 넣는다.

    uid 칸이 비어 있으면 「대상 조직」 조각으로 items 에서 찾는다. 못 찾으면 건너뛰고 사유를 남긴다.
    """
    ensure(con)
    out = {"넣음": 0, "이미 있음": 0, "건너뜀": 0, "사유": []}
    for r in rows:
        at = (r.get("관측 시각") or "").strip()
        state = (r.get("게시 상태") or "").strip()
        who = r.get("대상 조직") or r.get("page_id") or "?"
        if not at:
            out["건너뜀"] += 1
            out["사유"].append("%s: 관측 시각이 없다" % who)
            continue
        if state not in STATES:
            out["건너뜀"] += 1
            out["사유"].append("%s: 모르는 게시 상태 %r" % (who, state))
            continue
        uid = (r.get("uid") or "").strip()
        if not uid:
            try:
                uid = resolve_uid(con, r.get("대상 조직") or "")
            except 대상없음 as e:
                out["건너뜀"] += 1
                out["사유"].append("%s: %s" % (who, e))
                continue
        at = _dt(at).replace(microsecond=0).isoformat()
        if con.execute("SELECT 1 FROM post_obs WHERE uid=? AND observed_at=? AND src='origin'",
                       (uid, at)).fetchone():
            out["이미 있음"] += 1
            continue
        files = r.get("공개된 파일 수")
        record(con, uid, src="origin", by=(r.get("관측자") or "").strip() or "노션",
               state=state, countdown=(r.get("카운트다운 표기") or "").strip(), at=at,
               files_n=int(files) if files not in (None, "") else None,
               size_claim=(r.get("주장 규모") or "").strip(), note=(r.get("관측 근거") or "").strip())
        out["넣음"] += 1
    return out


def fetch_obs_rows() -> list:
    """노션 수집 DB 에서 관측 시각이 찬 행만. 읽기만 한다."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "darkweb-verify-ko" / "tools"))
    from notion import _call, search, title_of  # noqa: E402

    hits = [r for r in search("수집 DB") if r.get("object") == "data_source"
            and title_of(r).strip() == "수집 DB"]
    hits.sort(key=lambda r: r.get("last_edited_time", ""), reverse=True)
    if not hits:
        raise SystemExit("노션에서 「수집 DB」 를 못 찾았다")
    ds = hits[0]["id"]
    schema = _call("/data_sources/" + ds)["properties"]
    missing = [c for c in ("관측 시각", "게시 상태") if c not in schema]
    if missing:
        raise SystemExit("수집 DB 에 칸이 없다: %s — 01_회의/노션DB_설계_후보_관측_20260906.md 대로 더한다"
                         % " · ".join(missing))

    def val(p, c):
        x = p.get(c)
        if not x:
            return None
        t = x["type"]
        if t == "select":
            return x["select"]["name"] if x["select"] else ""
        if t == "rich_text":
            return "".join(s["plain_text"] for s in x["rich_text"]).strip()
        if t == "date":
            return (x["date"] or {}).get("start") or ""
        if t == "number":
            return x["number"]
        if t == "title":
            return "".join(s["plain_text"] for s in x["title"]).strip()
        return None

    rows, cur = [], None
    body = {"page_size": 100, "filter": {"property": "관측 시각", "date": {"is_not_empty": True}}}
    while True:
        if cur:
            body["start_cursor"] = cur
        d = _call("/data_sources/%s/query" % ds, "POST", body)
        for pg in d["results"]:
            p = pg["properties"]
            # 칸 이름이 「UID」 로 만들어졌다 (2026-09-06). 대소문자 어느 쪽이든 읽는다
            rows.append({"page_id": pg["id"], "uid": val(p, "uid") or val(p, "UID") or "",
                         "대상 조직": val(p, "대상 조직") or "", "주장 규모": val(p, "주장 규모") or "",
                         **{c: val(p, c) for c in OBS_COLS}})
        if not d.get("has_more"):
            return rows
        cur = d["next_cursor"]


def cmd_pull(a) -> int:
    from collect.store import Store
    try:
        rows = fetch_obs_rows()
    except SystemExit as e:
        print(e)
        return 1
    s = Store(a.db)
    got = pull_rows(s.con, rows)
    s.close()
    print("노션 관측 %d줄 → 넣음 %d · 이미 있음 %d · 건너뜀 %d"
          % (len(rows), got["넣음"], got["이미 있음"], got["건너뜀"]))
    for why in got["사유"]:
        print("  건너뜀  %s" % why)
    return 0


# ── 보고 ─────────────────────────────────────────────

def report_md(con, now: str | None = None) -> str:
    """세 숫자와 근거 표. 조직명·행위자·상태·시각까지만 나간다. 주소는 안 나간다."""
    n = _dt(now) if now else datetime.now(KST)
    by_uid = _obs_by_uid(con)
    nums = numbers(con, n.isoformat())
    orgs = {r["uid"]: (r["target_org"], r["actor"], r["posted_at"]) for r in con.execute(
        "SELECT uid, target_org, actor, posted_at FROM items WHERE uid IN (%s)"
        % ",".join("?" * len(by_uid)), list(by_uid))} if by_uid else {}
    n_agg = sum(1 for obs in by_uid.values() for o in obs if o["src"] == "agg")
    n_ori = sum(1 for obs in by_uid.values() for o in obs if o["src"] == "origin")

    L = ["# 랜섬 게시 상태 — %s 기준" % n.strftime("%Y-%m-%d %H:%M KST"), ""]
    L += ["    공개된 건수      %3d   협상 기한이 지난 뒤 원 출처에서 자료가 공개된 것" % len(nums["공개됨"]),
          "    사라진 사례      %3d   원 출처에서 내려갔거나 집계처에서 두 판 연속 안 보인 것" % len(nums["사라짐"]),
          "    공개 여부 불명    %3d   기한이 지났는데 그 뒤 원 출처 관측이 없거나 불명인 것" % len(nums["불명"]),
          "    연장            %3d   카운트다운이 늘어난 것" % len(nums["연장"]), ""]
    L += ["관측한 자리 %d곳 · 관측 %d건 (집계처 %d · 원 출처 %d)" % (len(by_uid), n_agg + n_ori, n_agg, n_ori), ""]
    L += ["세 숫자는 사람이 원 출처를 본 관측에서 온다. 집계처는 있나 없나만 안다.",
          "집계처 「안 보임」 한 번은 안 센다. 두 판 연속이어야 사라진 것으로 본다.", ""]
    where = {u: k for k, us in nums.items() for u in us}

    # 표에는 원 출처 관측 · 판정 · 만료 추정 중 하나라도 있는 자리만 낸다.
    # 집계처만 본 자리는 한 줄로 줄인다 — 119곳이 전부 「게시 중」 이면 표가 소음이다
    shown = {u for u, obs in by_uid.items()
             if u in where or _expiry(obs) or any(o["src"] == "origin" for o in obs)}
    rest = {u: obs for u, obs in by_uid.items() if u not in shown}
    if rest:
        last = {}
        for obs in rest.values():
            k = obs[-1]["state"]
            last[k] = last.get(k, 0) + 1
        L += ["집계처만 본 자리 %d곳 — %s" % (len(rest), " · ".join(
            "%s %d" % kv for kv in sorted(last.items(), key=lambda kv: -kv[1]))), ""]
    L += ["| 대상 | 행위자 | 게시 | 판정 | 만료 추정 | 마지막 카운트다운 | 원 출처 마지막 | 집계처 마지막 | 관측 | 근거 |",
          "|---|---|---|---|---|---|---|---|---|---|"]

    def _last(obs, src):
        xs = [o for o in obs if o["src"] == src]
        if not xs:
            return "-"
        o = xs[-1]
        return "%s (%s)" % (o["state"], o["observed_at"][:10])

    def _cd(obs):
        for o in reversed(obs):
            if o["countdown"]:
                return o["countdown"]
        return "-"

    def _note(obs):
        for o in reversed(obs):
            if o["note"]:
                return o["note"]
        return ""

    rows = sorted(((u, by_uid[u]) for u in shown),
                  key=lambda kv: (orgs.get(kv[0], ("", "", ""))[0] or kv[0]))
    for uid, obs in rows:
        org, actor, posted = orgs.get(uid, (uid, "", ""))
        exp = _expiry(obs)
        L.append("| %s | %s | %s | %s | %s | %s | %s | %s | %d | %s |" % (
            org or uid, actor or "-", (posted or "")[:10] or "-", where.get(uid, "-"),
            exp[:16].replace("T", " ") if exp else "-", _cd(obs),
            _last(obs, "origin"), _last(obs, "agg"), len(obs), _note(obs)))
    L.append("")
    return "\n".join(L)


# ── 명령 ─────────────────────────────────────────────

def cmd_agg(a) -> int:
    """ransomlive kr 한 판을 돌리고, 저장된 KR 랜섬 줄마다 보였나 안 보였나를 적는다."""
    from collect.fetch import Fetcher
    from collect.sources.ransomlive import FEEDS, VER, to_item
    from collect.store import Store

    f = FEEDS["kr"]
    fe = Fetcher(dry=a.dry)
    try:
        code, body, _ = fe.get(f["url"])
    except Exception as e:
        print("못 받았다: %s" % e)
        return 1
    if a.dry:
        print("dry run\n%s" % fe.report())
        return 0
    if code != 200 or not body:
        print("HTTP %s" % code)
        return 1
    try:
        rows = json.loads(body)
    except ValueError as e:
        print("JSON 이 아니다: %s" % e)
        return 1
    if not isinstance(rows, list):
        rows = rows.get("victims") or rows.get("data") or []
    if not rows:
        print("줄 0개. 비어서인지 꼴이 바뀌어서인지 확인할 것. **안 보임을 적지 않는다.**")
        return 1
    s = Store(a.db)
    today = date.today().isoformat()
    items = [to_item(r, f, "kr") for r in rows]
    fresh = sum(1 for it in items if s.put(it, today))
    s.log_run(today, "ransomlive/kr", len(items), fresh, VER + " via track")
    seen = {it.uid() for it in items}
    at = now_iso()
    n = mark_agg(s.con, seen, at=at, by="ransomlive/kr")
    absent = [r["uid"] for r in s.con.execute(
        "SELECT uid FROM post_obs WHERE src='agg' AND observed_at=? AND state='안 보임'", (at,))]
    s.close()
    print("집계처 %d줄 · 처음 보는 것 %d · 우리 KR 줄 %d 중 이번 판에 안 보인 것 %d"
          % (len(items), fresh, n, len(absent)))
    print("표 %s" % a.db)
    return 0


def cmd_obs(a) -> int:
    from collect.store import Store
    s = Store(a.db)
    try:
        uid = resolve_uid(s.con, a.target)
    except 대상없음 as e:
        print(e)
        s.close()
        return 1
    org = s.con.execute("SELECT target_org, actor FROM items WHERE uid=?", (uid,)).fetchone()
    try:
        rid = record(s.con, uid, src="origin", by=a.by, state=a.state,
                     countdown=a.countdown or "", at=a.at, expiry_est=a.expiry or "",
                     files_n=a.files, size_claim=a.size or "", note=a.note or "")
    except ValueError as e:
        print(e)
        s.close()
        return 1
    # 방금 넣은 줄을 되읽는다. 「가장 최근 시각」 으로 읽으면 소급 입력(--at) 때
    # 오늘 돌린 집계처 줄이 걸려 엉뚱한 것을 보인다
    r = s.con.execute("SELECT observed_at, expiry_est FROM post_obs WHERE rowid=?",
                      (rid,)).fetchone()
    s.close()
    print("적었다  %s · %s  %s  %s" % (org["target_org"], org["actor"], a.state, r["observed_at"]))
    if r["expiry_est"]:
        print("만료 추정  %s" % r["expiry_est"].replace("T", " "))
    elif a.countdown:
        print("카운트다운 「%s」 을 못 읽었다. --expiry 로 직접 주거나 표기를 확인할 것" % a.countdown)
    return 0


def cmd_report(a) -> int:
    from collect.store import Store
    s = Store(a.db)
    ensure(s.con)
    md = report_md(s.con, a.now)
    s.close()
    if a.out:
        Path(a.out).write_text(md, encoding="utf-8")
        print("썼다  %s" % a.out)
    else:
        print(md)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="랜섬 게시 상태 추적")
    p.add_argument("--db", type=Path, default=DEFAULT_DB, help="수집 표. 기본 %s" % DEFAULT_DB)
    sub = p.add_subparsers(dest="cmd", required=True)

    s1 = sub.add_parser("agg", help="집계처 한 판. 매일 한 번")
    s1.add_argument("--dry", action="store_true", help="요청만 보이고 안 보낸다")
    s1.set_defaults(fn=cmd_agg)

    s2 = sub.add_parser("obs", help="사람 관측을 적는다")
    s2.add_argument("target", help="uid 또는 대상 조직 이름 조각")
    s2.add_argument("--state", required=True, choices=STATES)
    s2.add_argument("--countdown", help="화면 표기 그대로. 예: 9일 3시간 14분")
    s2.add_argument("--expiry", help="만료를 직접 줄 때 (ISO)")
    s2.add_argument("--files", type=int, help="공개된 파일 수")
    s2.add_argument("--size", help="화면의 규모 표기 그대로")
    s2.add_argument("--note", help="근거 한 줄. 값·주소를 넣지 않는다")
    s2.add_argument("--at", help="관측 시각 (ISO). 없으면 지금. 소급 입력에 쓴다")
    s2.add_argument("--by", default="사람", help="누가 봤나")
    s2.set_defaults(fn=cmd_obs)

    s4 = sub.add_parser("pull", help="노션 수집 DB 의 관측 칸을 post_obs 로 끌어온다. 읽기만")
    s4.set_defaults(fn=cmd_pull)

    s3 = sub.add_parser("report", help="세 숫자와 근거 표")
    s3.add_argument("--out", help="md 로 쓸 자리. 없으면 화면에")
    s3.add_argument("--now", help="기준 시각 (ISO). 없으면 지금")
    s3.set_defaults(fn=cmd_report)

    a = p.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
