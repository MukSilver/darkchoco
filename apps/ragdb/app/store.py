# -*- coding: utf-8 -*-
"""SQLite 저장 — 설계서 「저장 위치」 의 표 가운데 질의와 운영이 쓰는 일곱.

chunks 와 documents 는 scripts/chunk.py 가 만든다. 여기는 그 둘을 읽기만 한다.
SQLite 는 검색 엔진이 아니라 키로 꺼내는 저장소다. 도는 질의는 점조회와 덧붙이기뿐이다.
"""
import datetime
import json
import os
import sqlite3

from . import config as cfg

KST = datetime.timezone(datetime.timedelta(hours=9))

SCHEMA = """
CREATE TABLE IF NOT EXISTS qa_log (
  id                   INTEGER PRIMARY KEY AUTOINCREMENT,
  at                   TEXT NOT NULL,
  question_hash        TEXT,
  question_len         INTEGER,
  sources              TEXT,
  no_evidence          INTEGER,
  used_prepared        INTEGER,
  reused               INTEGER,
  evaluation           INTEGER,
  pii_masked           INTEGER,
  term_items           TEXT,
  score_sources        TEXT,
  no_dictionary        INTEGER,
  expansion_truncated  INTEGER,
  rerank_applied       INTEGER,
  rerank_ms            INTEGER,
  cost                 REAL,
  word_fps             TEXT
);
CREATE INDEX IF NOT EXISTS idx_qa_log_no_evidence ON qa_log(no_evidence, at);

CREATE TABLE IF NOT EXISTS answers (
  question_key  TEXT PRIMARY KEY,
  question      TEXT,
  answer        TEXT,
  sources       TEXT,
  model         TEXT,
  created_at    TEXT,
  reviewed      INTEGER DEFAULT 0,
  doc_hashes    TEXT
);

CREATE TABLE IF NOT EXISTS answer_cache (
  version     TEXT NOT NULL,
  key_fp      TEXT NOT NULL,
  answer      TEXT,
  sources     TEXT,
  model       TEXT,
  created_at  TEXT,
  hits        INTEGER DEFAULT 0,
  PRIMARY KEY (version, key_fp)
);

CREATE TABLE IF NOT EXISTS usage (
  day          TEXT PRIMARY KEY,
  new_answers  INTEGER DEFAULT 0,
  rerank_cost  REAL DEFAULT 0,
  answer_cost  REAL DEFAULT 0,
  eval_cost    REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS recheck_queue (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  qa_log_id   INTEGER,
  branch      TEXT,
  row_name    TEXT,
  hits        INTEGER DEFAULT 1,
  handled     INTEGER DEFAULT 0,
  created_at  TEXT
);

CREATE TABLE IF NOT EXISTS export_log (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  at         TEXT NOT NULL,
  version    TEXT NOT NULL,
  documents  INTEGER,
  chunks     INTEGER
);

CREATE TABLE IF NOT EXISTS review_log (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  at      TEXT NOT NULL,
  who     TEXT,
  what    TEXT,
  target  TEXT
);
"""


def now():
    return datetime.datetime.now(KST).isoformat(timespec="seconds")


def today():
    """하루 차단기는 한국 시간 자정에 새로 센다 (F-18 처리 4)."""
    return datetime.datetime.now(KST).strftime("%Y-%m-%d")


def connect(path=None):
    """DR-09 — WAL, busy_timeout 5초, synchronous NORMAL."""
    path = path or cfg.SQLITE_PATH
    os.makedirs(os.path.dirname(path), exist_ok=True)
    c = sqlite3.connect(path, timeout=5)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=5000")
    c.execute("PRAGMA synchronous=NORMAL")
    c.executescript(SCHEMA)
    return c


def j(v):
    return json.dumps(v, ensure_ascii=False)


# ── 조각 ──
def chunks_by_id(con, ids):
    """chunk_id 점조회. 돌려주는 순서는 받은 순서."""
    if not ids:
        return []
    rows = con.execute(
        "SELECT chunk_id, document_id, kind, title, section, body, visibility, observed_at, status "
        "FROM chunks WHERE chunk_id IN (%s)" % ",".join("?" * len(ids)), list(ids)).fetchall()
    by = {r["chunk_id"]: dict(r) for r in rows}
    return [by[i] for i in ids if i in by]


# ── 사전 답변 (F-16) ──
def answer_holds(con, row):
    """사전 답변을 아직 써도 되는가. 답에 쓰인 근거 문서가 만든 때 그대로여야 한다 (F-16 처리 3, F-07 처리 2).

    상태가 offline 으로 바뀌면 내용 해시도 바뀌므로 따로 보지 않는다. 만들 때 이미 offline 이던 대상을
    설명한 답은 그대로 써도 된다.
    """
    hashes = json.loads(row["doc_hashes"] or "{}")
    if not hashes:
        return False
    for did, h in hashes.items():
        d = con.execute("SELECT content_hash, visibility FROM documents WHERE document_id = ?", (did,)).fetchone()
        if not d or d["content_hash"] != h or not d["visibility"]:
            return False
    return True


def prepared_answer(con, key):
    """검토를 통과했고 아직 써도 되는 것만 돌려준다 (TC-13)."""
    r = con.execute("SELECT * FROM answers WHERE question_key = ? AND reviewed = 1", (key,)).fetchone()
    if not r or not answer_holds(con, r):
        return None
    return {"answer": json.loads(r["answer"]), "sources": json.loads(r["sources"] or "[]"),
            "model": r["model"], "created_at": r["created_at"]}


# ── 재사용 답변 (F-21) ──
def cached_answer(con, version, key_fp):
    r = con.execute("SELECT * FROM answer_cache WHERE version = ? AND key_fp = ?", (version, key_fp)).fetchone()
    if not r:
        return None
    with con:
        con.execute("UPDATE answer_cache SET hits = hits + 1 WHERE version = ? AND key_fp = ?", (version, key_fp))
    return {"answer": json.loads(r["answer"]), "sources": json.loads(r["sources"] or "[]"),
            "model": r["model"], "created_at": r["created_at"]}


def save_cache(con, version, key_fp, answer, sources, model):
    with con:
        con.execute(
            "INSERT INTO answer_cache (version, key_fp, answer, sources, model, created_at, hits) VALUES (?,?,?,?,?,?,0) "
            "ON CONFLICT(version, key_fp) DO UPDATE SET answer=excluded.answer, sources=excluded.sources, "
            "model=excluded.model, created_at=excluded.created_at",
            (version, key_fp, j(answer), j(sources), model, now()))


def drop_old_cache(con, version):
    """판이 바뀌면 옛 판의 재사용 답변을 지운다 (F-06 처리 5, DR-10, TC-35)."""
    with con:
        return con.execute("DELETE FROM answer_cache WHERE version <> ?", (version,)).rowcount


# ── 사용량 (F-18) ──
def spent_today(con):
    r = con.execute("SELECT rerank_cost + answer_cost AS s FROM usage WHERE day = ?", (today(),)).fetchone()
    return float(r["s"]) if r else 0.0


def add_usage(con, rerank_cost=0.0, answer_cost=0.0, new_answer=False, evaluation=False):
    """평가 실행은 하루 전체 비용이 아니라 평가 실행 비용 칸에 따로 센다 (F-18 처리 6)."""
    with con:
        con.execute("INSERT OR IGNORE INTO usage (day) VALUES (?)", (today(),))
        if evaluation:
            con.execute("UPDATE usage SET eval_cost = eval_cost + ? WHERE day = ?", (rerank_cost + answer_cost, today()))
        else:
            con.execute("UPDATE usage SET rerank_cost = rerank_cost + ?, answer_cost = answer_cost + ?, "
                        "new_answers = new_answers + ? WHERE day = ?",
                        (rerank_cost, answer_cost, 1 if new_answer else 0, today()))


# ── 질의 기록 (F-19) ──
QA_COLUMNS = ["at", "question_hash", "question_len", "sources", "no_evidence", "used_prepared", "reused", "evaluation",
              "pii_masked", "term_items", "score_sources", "no_dictionary", "expansion_truncated", "rerank_applied",
              "rerank_ms", "cost", "word_fps"]


def log_query(con, **row):
    """질문 원문, 답변 본문, IP 는 남기지 않는다 (SR-16, SR-23). 받는 칸이 애초에 없다."""
    row.setdefault("at", now())
    extra = set(row) - set(QA_COLUMNS)
    if extra:
        raise ValueError("질의 기록에 없는 칸: %s" % ", ".join(sorted(extra)))
    vals = [j(row[c]) if isinstance(row.get(c), (list, dict)) else row.get(c) for c in QA_COLUMNS]
    with con:
        return con.execute("INSERT INTO qa_log (%s) VALUES (%s)" % (", ".join(QA_COLUMNS), ",".join("?" * len(QA_COLUMNS))),
                           vals).lastrowid


def drop_old_word_fps(con, days=None):
    """질문 낱말 지문은 F-20 이 쓰고 나면 지우고, 안 돌아도 14일이 지나면 지운다 (F-19 처리 4)."""
    days = cfg.WORD_FP_TTL_DAYS if days is None else days
    limit = (datetime.datetime.now(KST) - datetime.timedelta(days=days)).isoformat(timespec="seconds")
    with con:
        return con.execute("UPDATE qa_log SET word_fps = NULL WHERE word_fps IS NOT NULL AND at < ?", (limit,)).rowcount
