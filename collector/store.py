"""
store.py — SQLite 저장소. NEW(미확인) 상태 관리를 담당한다.

보안 노트:
  * 모든 쿼리는 파라미터 바인딩만 사용한다 (SQL 인젝션 차단).
  * DB 파일은 로컬 data/ 아래에만 생성되며 .gitignore 로 커밋이 차단된다.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS victims (
    uid             TEXT PRIMARY KEY,
    victim          TEXT NOT NULL,
    victim_key      TEXT NOT NULL,
    group_name      TEXT NOT NULL,
    group_key       TEXT NOT NULL,
    country         TEXT DEFAULT '',
    sector          TEXT DEFAULT '',
    website         TEXT DEFAULT '',
    description     TEXT DEFAULT '',
    published       TEXT DEFAULT '',
    discovered      TEXT DEFAULT '',
    post_url        TEXT DEFAULT '',
    sources         TEXT DEFAULT '[]',
    kr_tier         TEXT DEFAULT 'none',
    kr_score        INTEGER DEFAULT 0,
    kr_reasons      TEXT DEFAULT '[]',
    supply_tier     TEXT DEFAULT 'none',
    supply_score    INTEGER DEFAULT 0,
    supply_reasons  TEXT DEFAULT '[]',
    first_seen      TEXT NOT NULL,
    last_seen       TEXT NOT NULL,
    is_new          INTEGER NOT NULL DEFAULT 1,
    acknowledged_at TEXT DEFAULT ''
);

-- ★ supply_tier 인덱스는 여기 두지 않는다.
--   기존 DB 에서는 CREATE TABLE IF NOT EXISTS 가 no-op 이라 supply_tier 컬럼이 아직 없고,
--   그 상태에서 인덱스를 만들면 "no such column" 으로 전체 스크립트가 실패한다.
--   컬럼을 추가한 뒤 _migrate() 안에서 생성한다.
CREATE INDEX IF NOT EXISTS idx_victims_tier    ON victims(kr_tier);
CREATE INDEX IF NOT EXISTS idx_victims_new     ON victims(is_new);
CREATE INDEX IF NOT EXISTS idx_victims_seen    ON victims(first_seen DESC);
CREATE INDEX IF NOT EXISTS idx_victims_group   ON victims(group_key);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at   TEXT NOT NULL,
    finished_at  TEXT DEFAULT '',
    fetched      INTEGER DEFAULT 0,
    kr_matched   INTEGER DEFAULT 0,
    new_count    INTEGER DEFAULT 0,
    status       TEXT DEFAULT 'running',
    detail       TEXT DEFAULT ''
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, db_path: str | Path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA)
        self._migrate()
        self.conn.commit()

    # ── 스키마 마이그레이션 ─────────────────────────────────
    def _migrate(self) -> None:
        """기존 DB 를 손실 없이 최신 스키마로 올린다.

        CREATE TABLE IF NOT EXISTS 는 이미 있는 테이블에 컬럼을 추가해 주지 않는다.
        구버전에서 만들어진 DB 에 새 컬럼을 직접 붙여야 기존 이력이 보존된다.
        """
        existing = {
            row["name"]
            for row in self.conn.execute("PRAGMA table_info(victims)").fetchall()
        }
        additions = (
            ("supply_tier", "TEXT DEFAULT 'none'"),
            ("supply_score", "INTEGER DEFAULT 0"),
            ("supply_reasons", "TEXT DEFAULT '[]'"),
        )
        for column, ddl in additions:
            if column not in existing:
                self.conn.execute(f"ALTER TABLE victims ADD COLUMN {column} {ddl}")
                log.info("스키마 마이그레이션: victims.%s 컬럼 추가", column)
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_victims_supply ON victims(supply_tier)"
        )

    def close(self) -> None:
        try:
            self.conn.commit()
            self.conn.close()
        except Exception:
            pass

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ── 소규모 상태 저장 (벤더 순회 커서 등) ─────────────────
    def get_setting(self, key: str, default: str = "") -> str:
        row = self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row else default

    def set_setting(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )
        self.conn.commit()

    # ── 실행 이력 ───────────────────────────────────────────
    def start_run(self) -> int:
        cur = self.conn.execute("INSERT INTO runs (started_at) VALUES (?)", (_now(),))
        self.conn.commit()
        return int(cur.lastrowid or 0)

    def finish_run(
        self, run_id: int, *, fetched: int, kr_matched: int, new_count: int,
        status: str = "ok", detail: str = "",
    ) -> None:
        self.conn.execute(
            "UPDATE runs SET finished_at=?, fetched=?, kr_matched=?, new_count=?, status=?, detail=? WHERE id=?",
            (_now(), fetched, kr_matched, new_count, status, detail[:2000], run_id),
        )
        self.conn.commit()

    def is_first_run(self) -> bool:
        row = self.conn.execute("SELECT COUNT(*) AS c FROM victims").fetchone()
        return int(row["c"]) == 0

    # ── 업서트 ──────────────────────────────────────────────
    def upsert_many(self, records: Iterable[Any]) -> list[dict[str, Any]]:
        """레코드를 저장하고, 이번에 '처음 본' 건들만 반환한다."""
        newly_seen: list[dict[str, Any]] = []
        now = _now()

        for rec in records:
            existing = self.conn.execute(
                "SELECT * FROM victims WHERE uid = ?", (rec.uid,)
            ).fetchone()

            if existing is None:
                self.conn.execute(
                    """INSERT INTO victims (
                        uid, victim, victim_key, group_name, group_key, country, sector,
                        website, description, published, discovered, post_url, sources,
                        kr_tier, kr_score, kr_reasons,
                        supply_tier, supply_score, supply_reasons,
                        first_seen, last_seen, is_new
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
                    (
                        rec.uid, rec.victim, rec.victim_key, rec.group, rec.group_key,
                        rec.country, rec.sector, rec.website, rec.description,
                        rec.published, rec.discovered, rec.post_url,
                        json.dumps([rec.source], ensure_ascii=False),
                        rec.kr_tier, rec.kr_score,
                        json.dumps(rec.kr_reasons, ensure_ascii=False),
                        rec.supply_tier or "none", rec.supply_score,
                        json.dumps(rec.supply_reasons, ensure_ascii=False),
                        now, now,
                    ),
                )
                row = self.conn.execute("SELECT * FROM victims WHERE uid = ?", (rec.uid,)).fetchone()
                newly_seen.append(_row_to_dict(row))
            else:
                # 기존 건: 더 좋은 정보로 보강 (빈 값만 채우고, 등급은 높은 쪽 유지)
                try:
                    sources = set(json.loads(existing["sources"] or "[]"))
                except json.JSONDecodeError:
                    sources = set()
                sources.add(rec.source)

                merged = {
                    "country": existing["country"] or rec.country,
                    "sector": existing["sector"] or rec.sector,
                    "website": existing["website"] or rec.website,
                    "description": existing["description"] or rec.description,
                    "published": existing["published"] or rec.published,
                    "discovered": existing["discovered"] or rec.discovered,
                    "post_url": existing["post_url"] or rec.post_url,
                }
                if rec.kr_score > int(existing["kr_score"] or 0):
                    kr_tier, kr_score = rec.kr_tier, rec.kr_score
                    kr_reasons = json.dumps(rec.kr_reasons, ensure_ascii=False)
                else:
                    kr_tier, kr_score = existing["kr_tier"], existing["kr_score"]
                    kr_reasons = existing["kr_reasons"]

                # 공급망 축도 동일하게 '더 높은 등급 유지' 규칙을 적용한다.
                # (구버전 DB 에서 올라온 행은 supply_* 가 비어 있을 수 있으므로 기본값 처리)
                old_supply = int(_safe_int(existing, "supply_score"))
                if rec.supply_score > old_supply:
                    supply_tier, supply_score = rec.supply_tier or "none", rec.supply_score
                    supply_reasons = json.dumps(rec.supply_reasons, ensure_ascii=False)
                else:
                    supply_tier = _safe_str(existing, "supply_tier") or "none"
                    supply_score = old_supply
                    supply_reasons = _safe_str(existing, "supply_reasons") or "[]"

                self.conn.execute(
                    """UPDATE victims SET country=?, sector=?, website=?, description=?,
                       published=?, discovered=?, post_url=?, sources=?,
                       kr_tier=?, kr_score=?, kr_reasons=?,
                       supply_tier=?, supply_score=?, supply_reasons=?,
                       last_seen=? WHERE uid=?""",
                    (
                        merged["country"], merged["sector"], merged["website"],
                        merged["description"], merged["published"], merged["discovered"],
                        merged["post_url"], json.dumps(sorted(sources), ensure_ascii=False),
                        kr_tier, kr_score, kr_reasons,
                        supply_tier, supply_score, supply_reasons,
                        now, rec.uid,
                    ),
                )

        self.conn.commit()
        return newly_seen

    # ── 조회 ────────────────────────────────────────────────
    # 두 축은 OR 로 묶는다 — 한국 관련이거나 공급망 위험이면 표시 대상.
    def list_victims(
        self, *, min_score: int = 0, min_supply_score: int = 999, limit: int = 5000
    ) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """SELECT * FROM victims
               WHERE kr_score >= ? OR COALESCE(supply_score, 0) >= ?
               ORDER BY COALESCE(NULLIF(discovered,''), NULLIF(published,''), first_seen) DESC
               LIMIT ?""",
            (int(min_score), int(min_supply_score), int(limit)),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def list_new(self, *, min_score: int = 0, min_supply_score: int = 999) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """SELECT * FROM victims WHERE is_new = 1
               AND (kr_score >= ? OR COALESCE(supply_score, 0) >= ?)
               ORDER BY first_seen DESC""",
            (int(min_score), int(min_supply_score)),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def stats(self) -> dict[str, Any]:
        def scalar(sql: str, params: tuple = ()) -> int:
            row = self.conn.execute(sql, params).fetchone()
            return int(row[0]) if row and row[0] is not None else 0

        by_tier = {
            r["kr_tier"]: int(r["c"])
            for r in self.conn.execute(
                "SELECT kr_tier, COUNT(*) AS c FROM victims GROUP BY kr_tier"
            ).fetchall()
        }
        by_supply = {
            (r["supply_tier"] or "none"): int(r["c"])
            for r in self.conn.execute(
                "SELECT supply_tier, COUNT(*) AS c FROM victims GROUP BY supply_tier"
            ).fetchall()
        }
        top_groups = [
            {"group": r["group_name"], "count": int(r["c"])}
            for r in self.conn.execute(
                """SELECT group_name, COUNT(*) AS c FROM victims
                   WHERE kr_score >= 60 GROUP BY group_key ORDER BY c DESC LIMIT 15"""
            ).fetchall()
        ]
        last_run = self.conn.execute(
            "SELECT * FROM runs ORDER BY id DESC LIMIT 1"
        ).fetchone()

        return {
            "total": scalar("SELECT COUNT(*) FROM victims"),
            "new": scalar("SELECT COUNT(*) FROM victims WHERE is_new = 1"),
            "confirmed": by_tier.get("confirmed", 0),
            "strong": by_tier.get("strong", 0),
            "likely": by_tier.get("likely", 0),
            "review": by_tier.get("review", 0),
            "by_tier": by_tier,
            # 공급망 축
            "supply_direct": by_supply.get("direct", 0),
            "supply_critical": by_supply.get("critical", 0),
            "supply_korea_ops": by_supply.get("korea_ops", 0),
            "supply_sector": by_supply.get("sector", 0),
            "supply_total": sum(v for k, v in by_supply.items() if k != "none"),
            "by_supply": by_supply,
            "top_groups": top_groups,
            "last_run": dict(last_run) if last_run else None,
        }

    # ── NEW 해제 ────────────────────────────────────────────
    def acknowledge(self, uids: list[str] | None = None) -> int:
        now = _now()
        if uids:
            placeholders = ",".join("?" for _ in uids)
            cur = self.conn.execute(
                f"UPDATE victims SET is_new=0, acknowledged_at=? WHERE uid IN ({placeholders}) AND is_new=1",
                (now, *uids),
            )
        else:
            cur = self.conn.execute(
                "UPDATE victims SET is_new=0, acknowledged_at=? WHERE is_new=1", (now,)
            )
        self.conn.commit()
        return cur.rowcount


def _safe_int(row: sqlite3.Row, key: str) -> int:
    """구버전 DB 행에는 없는 컬럼일 수 있으므로 안전하게 읽는다."""
    try:
        return int(row[key] or 0)
    except (IndexError, KeyError, TypeError, ValueError):
        return 0


def _safe_str(row: sqlite3.Row, key: str) -> str:
    try:
        return str(row[key] or "")
    except (IndexError, KeyError, TypeError):
        return ""


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        return {}
    d = dict(row)
    for key in ("sources", "kr_reasons", "supply_reasons"):
        try:
            d[key] = json.loads(d.get(key) or "[]")
        except (json.JSONDecodeError, TypeError):
            d[key] = []
    d.setdefault("supply_tier", "none")
    d["supply_tier"] = d.get("supply_tier") or "none"
    d["supply_score"] = int(d.get("supply_score") or 0)
    d["is_new"] = bool(d.get("is_new"))
    return d
