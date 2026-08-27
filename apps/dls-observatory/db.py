"""
DLS 관측 데이터베이스 (SQLite, 표준 라이브러리만 사용).

설계 원칙
---------
1. **관측은 지우지 않고 쌓는다.** observation 테이블은 append-only 라서
   "언제부터 offline 인지", "언제 캡차가 생겼는지" 를 나중에 되물을 수 있다.
   지금까지처럼 덮어쓰면 그 질문에 영원히 답할 수 없다.
2. **site 는 이름이 아니라 key 로 식별한다.** 표기 차이(대소문자·공백·괄호)로
   같은 사이트가 둘로 갈라지지 않게 정규화된 key 를 쓴다.
3. **주소는 사이트에 종속된 이력이다.** 주소가 바뀌면 예전 행을 고치지 않고
   last_seen 만 닫은 뒤 새 행을 추가한다 → 주소 변경 이력이 공짜로 남는다.
4. 노션은 원본이 아니라 이 DB 의 **표시용 뷰**다.

테이블
------
  site         사이트 하나 = 한 행
  alias        별칭·이전 이름
  address      주소 이력 (사이트당 여러 개)
  observation  관측 기록 (append-only) ← 핵심
  victim       ransomware.live 피해자
  run          수집 실행 이력
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any, Iterable

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS site (
    id          INTEGER PRIMARY KEY,
    key         TEXT NOT NULL UNIQUE,      -- 정규화된 이름 (매칭용)
    name        TEXT NOT NULL,             -- 표시용 원래 이름
    kind        TEXT,                      -- group / market / forum
    country     TEXT,
    description TEXT,
    first_seen  TEXT NOT NULL,
    last_seen   TEXT NOT NULL,
    notion_page_id TEXT
);

CREATE TABLE IF NOT EXISTS alias (
    site_id  INTEGER NOT NULL REFERENCES site(id) ON DELETE CASCADE,
    alias    TEXT NOT NULL,
    source   TEXT,
    PRIMARY KEY (site_id, alias)
);

CREATE TABLE IF NOT EXISTS address (
    id         INTEGER PRIMARY KEY,
    site_id    INTEGER NOT NULL REFERENCES site(id) ON DELETE CASCADE,
    url        TEXT NOT NULL,
    host       TEXT,
    is_onion   INTEGER NOT NULL DEFAULT 0,
    kind       TEXT,                       -- DLS / Chat / Mirror / 기타
    first_seen TEXT NOT NULL,
    last_seen  TEXT NOT NULL,
    active     INTEGER NOT NULL DEFAULT 1,
    UNIQUE (site_id, url)
);

-- append-only. 같은 (site, 시각, 출처) 는 한 번만 들어간다.
CREATE TABLE IF NOT EXISTS observation (
    id          INTEGER PRIMARY KEY,
    site_id     INTEGER NOT NULL REFERENCES site(id) ON DELETE CASCADE,
    address_id  INTEGER REFERENCES address(id) ON DELETE SET NULL,
    observed_at TEXT NOT NULL,
    source      TEXT NOT NULL,             -- tor_probe / ransomware.live / ransomlook.io
    status      TEXT,                      -- online / offline / 미확인
    reachable   INTEGER,
    http_status INTEGER,
    title       TEXT,
    language    TEXT,
    signup_required INTEGER,
    gate_signals    TEXT,                  -- JSON 배열
    gate_evidence   TEXT,                  -- JSON: 어떤 패턴이 걸렸는지 (오탐 검증용)
    captcha_confidence TEXT,               -- strong / weak / none
    how_to_enter    TEXT,
    -- 페이지 성격
    h1              TEXT,
    meta_description TEXT,
    og_site_name    TEXT,
    generator       TEXT,
    keywords        TEXT,
    -- 변경 감지 (본문을 저장하지 않고 내용 변화를 알아내는 지문)
    content_hash    TEXT,
    body_bytes      INTEGER,
    text_length     INTEGER,
    -- 인프라
    server          TEXT,
    powered_by      TEXT,
    last_modified   TEXT,
    elapsed_ms      INTEGER,
    redirected      INTEGER,
    -- 링크 구조
    link_count      INTEGER,
    onion_links     TEXT,                  -- JSON 배열: 미러·연관 사이트 후보
    onion_link_count INTEGER,
    external_domains TEXT,                 -- JSON 배열
    listing_link_count INTEGER,            -- 피해자 게시물처럼 보이는 링크 '개수'
    -- 지표
    contacts        TEXT,                  -- JSON: tox/session/telegram/jabber/email
    crypto          TEXT,                  -- JSON: btc/xmr/eth
    has_pgp         INTEGER,
    countdown       INTEGER,
    latest_date_on_page TEXT,
    error       TEXT,
    UNIQUE (site_id, observed_at, source)
);

CREATE TABLE IF NOT EXISTS victim (
    id         INTEGER PRIMARY KEY,
    group_key  TEXT NOT NULL,
    group_name TEXT,
    victim     TEXT NOT NULL,
    country    TEXT,
    sector     TEXT,
    discovered TEXT,
    attackdate TEXT,
    claim_url  TEXT,
    website    TEXT,
    UNIQUE (group_key, victim, discovered)
);

CREATE TABLE IF NOT EXISTS run (
    id          INTEGER PRIMARY KEY,
    started_at  TEXT NOT NULL,
    source      TEXT NOT NULL,
    target_count INTEGER,
    ok_count    INTEGER,
    note        TEXT
);

CREATE INDEX IF NOT EXISTS idx_obs_site_time ON observation(site_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_obs_time      ON observation(observed_at);
CREATE INDEX IF NOT EXISTS idx_addr_site     ON address(site_id);
CREATE INDEX IF NOT EXISTS idx_victim_group  ON victim(group_key);
CREATE INDEX IF NOT EXISTS idx_victim_country ON victim(country);

-- 사이트별 '가장 최근 관측' 한 줄
CREATE VIEW IF NOT EXISTS current_state AS
SELECT s.id AS site_id, s.key, s.name, s.kind, s.country,
       o.observed_at, o.source, o.status, o.title, o.language,
       o.signup_required, o.how_to_enter, o.captcha_confidence,
       o.http_status, o.error, o.content_hash, o.onion_link_count,
       o.contacts, o.crypto, o.latest_date_on_page, o.h1, o.meta_description
FROM site s
LEFT JOIN observation o ON o.id = (
    SELECT id FROM observation
    WHERE site_id = s.id
    ORDER BY observed_at DESC, id DESC
    LIMIT 1
);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def norm_key(name: str | None) -> str:
    if not name:
        return ""
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def host_of(url: str | None) -> tuple[str, bool]:
    if not url:
        return "", False
    v = str(url).strip().lower()
    for pre in ("http://", "https://"):
        if v.startswith(pre):
            v = v[len(pre):]
    v = v.split("/")[0].split("?")[0].split(":")[0]
    if v.startswith("www."):
        v = v[4:]
    return v, v.endswith(".onion")


class DLSDatabase:
    def __init__(self, path: str = "dls.sqlite3"):
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.conn.commit()

    def _migrate(self) -> None:
        """예전 스키마로 만든 DB 에 새 칼럼을 붙인다 (데이터는 보존)."""
        have = {r["name"] for r in
                self.conn.execute("PRAGMA table_info(observation)")}
        want = {
            "gate_evidence": "TEXT", "captcha_confidence": "TEXT",
            "h1": "TEXT", "meta_description": "TEXT", "og_site_name": "TEXT",
            "generator": "TEXT", "keywords": "TEXT",
            "content_hash": "TEXT", "body_bytes": "INTEGER",
            "text_length": "INTEGER", "server": "TEXT", "powered_by": "TEXT",
            "last_modified": "TEXT", "elapsed_ms": "INTEGER",
            "redirected": "INTEGER", "link_count": "INTEGER",
            "onion_links": "TEXT", "onion_link_count": "INTEGER",
            "external_domains": "TEXT", "listing_link_count": "INTEGER",
            "contacts": "TEXT", "crypto": "TEXT", "has_pgp": "INTEGER",
            "countdown": "INTEGER", "latest_date_on_page": "TEXT",
            # 3회차 신규
            "final_url": "TEXT",          # 리다이렉트 최종 주소 — 주소 이전 추적
            "subpages": "TEXT",           # 읽은 하위 경로 (JSON)
            "subpage_count": "INTEGER",
            "format_hint": "TEXT", "format_why": "TEXT",
            "pii_hint": "TEXT", "pii_why": "TEXT",
            "dist_hint": "TEXT", "dist_why": "TEXT",
            "passed_interstitial": "INTEGER",
        }
        added = 0
        for col, typ in want.items():
            if col not in have:
                self.conn.execute(
                    f"ALTER TABLE observation ADD COLUMN {col} {typ}")
                added += 1
        if added:
            print(f"[DB] 관측 테이블에 새 칼럼 {added}개 추가 (기존 데이터 보존)")

    def close(self) -> None:
        self.conn.close()

    # -- 사이트 ------------------------------------------------------------
    def upsert_site(self, name: str, *, kind: str | None = None,
                    country: str | None = None, description: str | None = None,
                    seen_at: str | None = None) -> int:
        key = norm_key(name)
        if not key:
            raise ValueError("사이트 이름이 비어 있습니다")
        ts = seen_at or now()
        cur = self.conn.execute("SELECT id FROM site WHERE key = ?", (key,))
        row = cur.fetchone()
        if row:
            sid = row["id"]
            # 이미 있는 값을 빈 값으로 덮어쓰지 않는다
            self.conn.execute("""
                UPDATE site SET
                  last_seen = MAX(last_seen, ?),
                  kind        = COALESCE(?, kind),
                  country     = COALESCE(?, country),
                  description = COALESCE(?, description)
                WHERE id = ?""", (ts, kind, country, description, sid))
            return sid
        cur = self.conn.execute("""
            INSERT INTO site (key, name, kind, country, description, first_seen, last_seen)
            VALUES (?,?,?,?,?,?,?)""",
            (key, name, kind, country, description, ts, ts))
        return cur.lastrowid

    def site_id(self, name: str) -> int | None:
        row = self.conn.execute("SELECT id FROM site WHERE key = ?",
                                (norm_key(name),)).fetchone()
        return row["id"] if row else None

    def add_alias(self, site_id: int, alias: str, source: str = "") -> None:
        if not alias:
            return
        self.conn.execute(
            "INSERT OR IGNORE INTO alias (site_id, alias, source) VALUES (?,?,?)",
            (site_id, alias, source))

    # -- 주소 --------------------------------------------------------------
    def upsert_address(self, site_id: int, url: str, *, kind: str | None = None,
                       seen_at: str | None = None, active: bool = True) -> int | None:
        if not url:
            return None
        ts = seen_at or now()
        host, is_onion = host_of(url)
        row = self.conn.execute(
            "SELECT id FROM address WHERE site_id = ? AND url = ?",
            (site_id, url)).fetchone()
        if row:
            self.conn.execute("""
                UPDATE address SET last_seen = MAX(last_seen, ?),
                                   active = ?, kind = COALESCE(?, kind)
                WHERE id = ?""", (ts, 1 if active else 0, kind, row["id"]))
            return row["id"]
        cur = self.conn.execute("""
            INSERT INTO address (site_id, url, host, is_onion, kind,
                                 first_seen, last_seen, active)
            VALUES (?,?,?,?,?,?,?,?)""",
            (site_id, url, host, 1 if is_onion else 0, kind, ts, ts,
             1 if active else 0))
        return cur.lastrowid

    def deactivate_other_addresses(self, site_id: int, keep_url: str) -> None:
        """현재 주소만 active 로 남기고 나머지는 이력으로 내린다."""
        self.conn.execute(
            "UPDATE address SET active = 0 WHERE site_id = ? AND url <> ?",
            (site_id, keep_url))

    # -- 관측 --------------------------------------------------------------
    def add_observation(self, site_id: int, *, observed_at: str, source: str,
                        address_id: int | None = None, **fields) -> bool:
        """중복이면 False. append-only 라 기존 관측은 절대 수정하지 않는다."""
        cols = ("status", "reachable", "http_status", "title", "language",
                "signup_required", "gate_signals", "gate_evidence",
                "captcha_confidence", "how_to_enter",
                "h1", "meta_description", "og_site_name", "generator", "keywords",
                "content_hash", "body_bytes", "text_length",
                "server", "powered_by", "last_modified", "elapsed_ms", "redirected",
                "link_count", "onion_links", "onion_link_count", "external_domains",
                "listing_link_count", "contacts", "crypto", "has_pgp", "countdown",
                "latest_date_on_page",
                "final_url", "subpages", "subpage_count",
                "format_hint", "format_why", "pii_hint", "pii_why",
                "dist_hint", "dist_why", "passed_interstitial",
                "error")
        vals = []
        for c in cols:
            v = fields.get(c)
            if isinstance(v, (list, tuple, dict)):
                v = json.dumps(v, ensure_ascii=False) if v else None
            if isinstance(v, bool):
                v = int(v)
            vals.append(v)
        try:
            self.conn.execute(f"""
                INSERT INTO observation
                  (site_id, address_id, observed_at, source, {", ".join(cols)})
                VALUES (?,?,?,?,{",".join("?" * len(cols))})""",
                [site_id, address_id, observed_at, source] + vals)
            return True
        except sqlite3.IntegrityError:
            return False

    # -- 피해자 ------------------------------------------------------------
    def add_victim(self, group_name: str, victim: str, **f) -> bool:
        try:
            self.conn.execute("""
                INSERT INTO victim (group_key, group_name, victim, country, sector,
                                    discovered, attackdate, claim_url, website)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (norm_key(group_name), group_name, victim,
                 f.get("country"), f.get("sector"), f.get("discovered"),
                 f.get("attackdate"), f.get("claim_url"), f.get("website")))
            return True
        except sqlite3.IntegrityError:
            return False

    # -- 실행 기록 ---------------------------------------------------------
    def add_run(self, source: str, target_count: int, ok_count: int,
                started_at: str | None = None, note: str = "") -> int:
        cur = self.conn.execute("""
            INSERT INTO run (started_at, source, target_count, ok_count, note)
            VALUES (?,?,?,?,?)""",
            (started_at or now(), source, target_count, ok_count, note))
        return cur.lastrowid

    # -- 조회 --------------------------------------------------------------
    def current(self, limit: int | None = None) -> list[sqlite3.Row]:
        q = "SELECT * FROM current_state ORDER BY name"
        if limit:
            q += f" LIMIT {int(limit)}"
        return self.conn.execute(q).fetchall()

    def latest_by_source(self, source: str) -> list[sqlite3.Row]:
        """출처별로 사이트마다 '그 출처의 가장 최근 관측' 한 줄씩.

        current_state 뷰는 출처를 가리지 않고 최신 한 줄만 고르기 때문에,
        나중에 넣은 API 관측이 먼저 측정한 Tor 실측을 가려버린다.
        실측만 뽑아야 할 때는 이 메서드를 쓴다.
        """
        return self.conn.execute("""
            SELECT s.name, s.kind, s.country, o.*
            FROM observation o
            JOIN site s ON s.id = o.site_id
            WHERE o.source = ? AND o.id = (
                SELECT id FROM observation
                WHERE site_id = o.site_id AND source = ?
                ORDER BY observed_at DESC, id DESC LIMIT 1)
            ORDER BY s.name""", (source, source)).fetchall()

    def history(self, name: str) -> list[sqlite3.Row]:
        sid = self.site_id(name)
        if not sid:
            return []
        return self.conn.execute("""
            SELECT observed_at, source, status, http_status, title, language,
                   signup_required, how_to_enter, error
            FROM observation WHERE site_id = ?
            ORDER BY observed_at""", (sid,)).fetchall()

    def status_changes(self, since: str | None = None,
                       source: str | None = "tor_probe") -> list[dict]:
        """상태가 바뀐 지점만 뽑는다 (online→offline 등).

        **한 출처 안에서만 비교한다.** 이걸 섞으면 'ransomware.live 는 살아
        있다 하고 Tor 실측은 죽었다 한다' 는 의견 차이가 시간에 따른 변화로
        둔갑한다. 실제로 그렇게 해봤더니 진짜 변화 22건이 100건으로 부풀었다.
        source=None 을 주면 예전처럼 전부 섞어서 본다 (권장하지 않음).
        """
        q = """
        SELECT s.name, o.observed_at, o.status, o.source
        FROM observation o JOIN site s ON s.id = o.site_id
        WHERE o.status IS NOT NULL
        """
        args: list[Any] = []
        if source:
            q += " AND o.source = ?"
            args.append(source)
        if since:
            q += " AND o.observed_at >= ?"
            args.append(since)
        # 출처별로 따로 이어붙여야 하므로 정렬 키에 source 를 넣는다
        q += " ORDER BY s.name, o.source, o.observed_at"

        out: list[dict] = []
        prev_key: tuple | None = None
        prev_status: str | None = None
        for r in self.conn.execute(q, args):
            key = (r["name"], r["source"])
            if key != prev_key:
                prev_key, prev_status = key, r["status"]
                continue
            if r["status"] != prev_status:
                out.append({"name": r["name"], "at": r["observed_at"],
                            "from": prev_status, "to": r["status"],
                            "source": r["source"]})
                prev_status = r["status"]
        out.sort(key=lambda c: (c["to"], c["from"], c["name"]))
        return out

    def address_history(self, name: str) -> list[sqlite3.Row]:
        sid = self.site_id(name)
        if not sid:
            return []
        return self.conn.execute("""
            SELECT url, kind, is_onion, first_seen, last_seen, active
            FROM address WHERE site_id = ? ORDER BY first_seen""", (sid,)).fetchall()

    def kr_victims(self, group_name: str | None = None) -> list[sqlite3.Row]:
        q = "SELECT * FROM victim WHERE country = 'KR'"
        args: list[Any] = []
        if group_name:
            q += " AND group_key = ?"
            args.append(norm_key(group_name))
        return self.conn.execute(q + " ORDER BY discovered DESC", args).fetchall()

    def stats(self) -> dict:
        c = self.conn
        def one(q, *a):
            r = c.execute(q, a).fetchone()
            return r[0] if r else 0
        return {
            "사이트": one("SELECT COUNT(*) FROM site"),
            "주소": one("SELECT COUNT(*) FROM address"),
            "  ├ onion": one("SELECT COUNT(*) FROM address WHERE is_onion=1"),
            "  └ 현재 사용": one("SELECT COUNT(*) FROM address WHERE active=1"),
            "관측 기록": one("SELECT COUNT(*) FROM observation"),
            "  ├ online": one("SELECT COUNT(*) FROM observation WHERE status='online'"),
            "  └ offline": one("SELECT COUNT(*) FROM observation WHERE status='offline'"),
            "피해자": one("SELECT COUNT(*) FROM victim"),
            "  └ 한국": one("SELECT COUNT(*) FROM victim WHERE country='KR'"),
            "수집 실행": one("SELECT COUNT(*) FROM run"),
            "언어 판별됨": one("SELECT COUNT(DISTINCT site_id) FROM observation "
                            "WHERE language IS NOT NULL AND language <> ''"),
        }


# --------------------------------------------------------------------------
# 적재 (ingest)
# --------------------------------------------------------------------------
# 접속은 되지만 사이트가 살아 있는 게 아닌 경우. 제목만으로 판별 가능하며
# 이걸 online 으로 기록하면 "운영 중"이라는 잘못된 인상을 준다.
_TAKEDOWN = re.compile(
    r"(domain|site|this)\s+(has\s+been\s+)?seized|seized\s+by|"
    r"law\s+enforcement|операция|been\s+taken\s+down", re.I)
_PARKED = re.compile(
    r"\bis\s+parked\b|domain\s+(is\s+)?for\s+sale|coming\s+soon|"
    r"decommissioned|test\s+page\s+for", re.I)
# 주소는 살아 있지만 원래 운영자 것이 아닌 경우. 압수(수사기관)와 구분한다 —
# 보안업체가 인수해 연구용으로 돌리는 경우가 있다.
# 실제 사례: sabbath 의 onion 이 "This is a research system operated by
# Kaspersky Lab" 을 띄우고 있었다. 이걸 online 으로 세면 그룹이 아직
# 활동 중인 것처럼 보인다.
_SINKHOLE = re.compile(
    r"research\s+system\s+operated\s+by|\bsinkhole[dn]?\b|\bhoneypot\b|"
    r"operated\s+by\s+(kaspersky|trend\s*micro|eset|group-?ib)|"
    r"this\s+(server|site)\s+is\s+(now\s+)?(controlled|operated)\s+by", re.I)


def classify_title(title: str | None, status: str | None,
                   extra: str | None = None) -> tuple[str | None, str | None]:
    """(보정된 status, 사유). 제목이 압수·인계·주차 페이지면 online 을 취소한다.

    제목만 보면 놓친다. sabbath 는 제목이 'Welcome page' 였고 정작
    'research system operated by Kaspersky Lab' 은 meta 설명에 있었다.
    extra 로 meta·h1 을 같이 넘긴다.
    """
    if status != "online":
        return status, None
    title = " ".join(x for x in (title, extra) if x)
    if not title.strip():
        return status, None
    if _TAKEDOWN.search(title):
        return "압수됨", f"제목이 압수 안내: {title[:60]}"
    if _SINKHOLE.search(title):
        return "인계됨", f"제3자가 인수해 운영 중: {title[:60]}"
    if _PARKED.search(title):
        return "offline", f"제목이 빈 페이지: {title[:60]}"
    return status, None


def ingest_probe(db: DLSDatabase, path: str, verbose: bool = True) -> dict:
    """tor_probe.py 결과(JSON) → DB."""
    with open(path, encoding="utf-8") as fh:
        records = json.load(fh)

    added = dup = skipped = new_sites = takedown = found_links = 0
    for rec in records:
        name = (rec.get("name") or "").strip()
        if not name:
            continue
        # Tor 가 끊긴 구간의 판정은 신뢰할 수 없으므로 넣지 않는다
        if rec.get("unreliable") or rec.get("status") == "미확인":
            skipped += 1
            continue

        ts = rec.get("checked_at") or now()
        existed = db.site_id(name) is not None
        sid = db.upsert_site(name, seen_at=ts)
        if not existed:
            new_sites += 1

        url = rec.get("final_url") or rec.get("url") or ""
        aid = db.upsert_address(sid, url, seen_at=ts,
                                active=bool(rec.get("reachable")))
        # 살아있는 주소를 확인했으면 나머지는 이력으로 내린다 → 주소 변경 추적
        if aid and rec.get("reachable"):
            db.deactivate_other_addresses(sid, url)

        status, reason = classify_title(
            rec.get("title"), rec.get("status"),
            " ".join(str(x) for x in (rec.get("meta_description"),
                                      rec.get("h1"),
                                      rec.get("og_description")) if x))
        if reason:
            takedown += 1
            if verbose:
                print(f"    [보정] {name}: {reason}")

        ok = db.add_observation(
            sid, observed_at=ts, source="tor_probe", address_id=aid,
            status=status,
            reachable=rec.get("reachable"),
            http_status=rec.get("http_status"),
            title=rec.get("title"),
            language=rec.get("language"),
            signup_required=rec.get("signup_required"),
            gate_signals=rec.get("gate_signals"),
            gate_evidence=rec.get("gate_evidence"),
            captcha_confidence=rec.get("captcha_confidence"),
            how_to_enter=rec.get("how_to_enter"),
            h1=rec.get("h1"),
            meta_description=rec.get("meta_description") or rec.get("og_description"),
            og_site_name=rec.get("og_site_name"),
            generator=rec.get("generator"),
            keywords=rec.get("keywords"),
            content_hash=rec.get("content_hash"),
            body_bytes=rec.get("body_bytes"),
            text_length=rec.get("text_length"),
            server=rec.get("server"),
            powered_by=rec.get("powered_by"),
            last_modified=rec.get("last_modified"),
            elapsed_ms=rec.get("elapsed_ms"),
            redirected=rec.get("redirected"),
            link_count=rec.get("link_count"),
            onion_links=rec.get("onion_links"),
            onion_link_count=rec.get("onion_link_count"),
            external_domains=rec.get("external_domains"),
            listing_link_count=rec.get("listing_link_count"),
            contacts=rec.get("contacts"),
            crypto=rec.get("crypto"),
            has_pgp=rec.get("has_pgp"),
            countdown=rec.get("countdown"),
            latest_date_on_page=rec.get("latest_date_on_page"),
            # 3회차 신규
            final_url=rec.get("final_url"),
            subpages=rec.get("subpages"),
            subpage_count=rec.get("subpage_count"),
            format_hint=rec.get("format_hint"),
            format_why=rec.get("format_why"),
            pii_hint=rec.get("pii_hint"),
            pii_why=rec.get("pii_why"),
            dist_hint=rec.get("dist_hint"),
            dist_why=rec.get("dist_why"),
            passed_interstitial=rec.get("passed_interstitial"),
            error=rec.get("error"))
        # 페이지에서 발견한 다른 onion 주소 = 미러·연관 사이트 후보.
        # active=0 으로 넣어 '이력'에만 남기고 현재 주소를 덮어쓰지 않는다.
        for extra in (rec.get("onion_links") or [])[:10]:
            if db.upsert_address(sid, f"http://{extra}", kind="발견된 링크",
                                 seen_at=ts, active=False):
                found_links += 1

        added += 1 if ok else 0
        dup += 0 if ok else 1

    ok_count = sum(1 for r in records if r.get("reachable"))
    db.add_run("tor_probe", len(records), ok_count,
               note=os.path.basename(path))
    db.conn.commit()
    result = {"파일": path, "레코드": len(records), "새 관측": added,
              "중복 건너뜀": dup, "신뢰불가 제외": skipped, "신규 사이트": new_sites,
              "제목 기반 보정": takedown, "발견된 onion 링크": found_links}
    if verbose:
        for k, v in result.items():
            print(f"  {k}: {v}")
    return result


def ingest_ransomware_live(db: DLSDatabase, groups: Iterable[dict],
                           observed_at: str | None = None) -> dict:
    """ransomware.live /v2/groups 응답 → DB."""
    ts = observed_at or now()
    sites = addrs = obs = 0
    for g in groups:
        name = g.get("name")
        if not name:
            continue
        sid = db.upsert_site(name, kind="group",
                             description=(g.get("description") or None),
                             seen_at=g.get("added_date") or ts)
        sites += 1
        if g.get("altname"):
            db.add_alias(sid, g["altname"], "ransomware.live")

        locs = g.get("locations") or []
        for loc in locs:
            url = loc.get("slug") or (f"http://{loc.get('fqdn')}" if loc.get("fqdn") else "")
            if not url:
                continue
            db.upsert_address(sid, url, kind=loc.get("type"),
                              seen_at=ts, active=bool(loc.get("available")))
            addrs += 1

        if locs:
            online = any(l.get("available") for l in locs)
            if db.add_observation(sid, observed_at=ts, source="ransomware.live",
                                  status="online" if online else "offline",
                                  reachable=online,
                                  title=(locs[0].get("title") or None)):
                obs += 1
    db.conn.commit()
    return {"사이트": sites, "주소": addrs, "관측": obs}


def ingest_ransomlook(db: DLSDatabase, names: Iterable[str], kind: str,
                      observed_at: str | None = None) -> int:
    """ransomlook /api/groups | /api/markets 이름 목록 → DB (존재 사실만 기록)."""
    ts = observed_at or now()
    n = 0
    for name in names:
        if isinstance(name, str) and name.strip():
            db.upsert_site(name.strip(), kind=kind, seen_at=ts)
            n += 1
    db.conn.commit()
    return n


def ingest_victims(db: DLSDatabase, victims: Iterable[dict]) -> int:
    n = 0
    for v in victims:
        g = v.get("group") or v.get("group_name")
        name = v.get("victim") or v.get("post_title")
        if not g or not name:
            continue
        if db.add_victim(g, name,
                         country=v.get("country"),
                         sector=v.get("activity"),
                         discovered=v.get("discovered"),
                         attackdate=v.get("attackdate") or v.get("published"),
                         claim_url=v.get("claim_url"),
                         website=v.get("website") or v.get("domain")):
            n += 1
    db.conn.commit()
    return n
