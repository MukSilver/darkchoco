# -*- coding: utf-8 -*-
"""F-05 조각 분할 — 표준 문서를 검색 단위로 자른다.

    python scripts/chunk.py --dry     자르기만 하고 보여준다
    python scripts/chunk.py           SQLite chunks에 넣는다

명세 F-05
  1. 줄 하나를 속성 조각 하나로, 본문 구간마다 조각 하나로 만든다.
     kind = 용어 문서는 조각으로 만들지 않는다 — 검색 대상이 아니라 넓히기 사전의 원천이다
  2. 본문 길이가 기준(OI-03) 미만인 조각은 색인에서 제외하고 따로 센다
     — BM25가 짧은 글을 과대평가해 「미확인」 한 줄이 실제 답을 밀어낸다
  3. 내용 해시가 바뀐 문서만 다시 만든다

OI-03(최소 본문 길이)은 아직 미결이다. 여기서 정하지 않고 설정에서 읽는다.
"""
import argparse
import json
import os
import sqlite3
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv

load_dotenv()

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STD_DIR = os.path.join(ROOT, "data", "standard")
DB_PATH = os.getenv("SQLITE_PATH", os.path.join(ROOT, "data", "ragdb.sqlite"))

# OI-03 미결. 정해지기 전까지 설정에서 읽고, 없으면 아래 값으로 시작한다
MIN_BODY = int(os.getenv("MIN_BODY_CHARS", "40"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
  chunk_id     TEXT PRIMARY KEY,
  document_id  TEXT NOT NULL,
  kind         TEXT,
  title        TEXT,
  section      TEXT,
  body         TEXT,
  visibility   INTEGER,
  observed_at  TEXT,
  status       TEXT,
  images       TEXT,
  indexed      INTEGER,
  related      TEXT
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_indexed ON chunks(indexed, visibility);

CREATE TABLE IF NOT EXISTS documents (
  document_id  TEXT PRIMARY KEY,
  kind         TEXT,
  title        TEXT,
  summary      TEXT,
  visibility   INTEGER,
  status       TEXT,
  observed_at  TEXT,
  content_hash TEXT,
  updated_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_documents_list ON documents(kind, status, observed_at DESC);
"""


def connect():
    """명세 DR-09 — WAL · busy_timeout 5초 · synchronous NORMAL."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=5)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=5000")
    c.execute("PRAGMA synchronous=NORMAL")
    c.executescript(SCHEMA)
    return c


def attr_body(doc):
    """속성 조각의 본문. 칸 값을 「이름: 값」 줄로 편다.
    본문에 이미 있는 것을 다시 쓰지 않는다 (명세 DR-03)."""
    lines = ["%s: %s" % (doc["kind"], doc["title"])]
    if doc.get("summary"):
        lines.append(doc["summary"])
    for k, v in (doc.get("metadata") or {}).items():
        if isinstance(v, list):
            v = " · ".join(str(x) for x in v)
        lines.append("%s: %s" % (k, v))
    return "\n".join(lines)


def split(doc):
    """표준 문서 하나 → 조각 목록."""
    if doc["kind"] == "용어":
        return []          # 검색 대상이 아니다 (명세 F-05 처리 1)

    md = doc.get("metadata") or {}
    common = {
        "document_id": doc["document_id"],
        "kind": doc["kind"],
        "title": doc["title"],
        "observed_at": md.get("확인일") or md.get("공표 시점") or md.get("수집일"),
        "status": md.get("상태"),
        "related": json.dumps(
            [x.strip() for x in str(md.get("연결된 곳", "")).split("·") if x.strip()],
            ensure_ascii=False),
    }

    out = [dict(common,
                chunk_id="%s#s0" % doc["document_id"],
                section="속성",
                body=attr_body(doc),
                visibility=doc["visibility"],
                images=json.dumps([], ensure_ascii=False))]

    for i, s in enumerate(doc.get("sections") or [], 1):
        body = s.get("body") or ""
        out.append(dict(common,
                        chunk_id="%s#s%d" % (doc["document_id"], i),
                        section=s.get("heading") or ("문단 %d" % i),
                        body=body,
                        visibility=doc["visibility"] and s.get("visibility", True),
                        images=json.dumps(s.get("images") or [], ensure_ascii=False)))

    # 처리 2 — 짧은 조각은 색인에서 뺀다. 속성 조각은 길이와 무관하게 넣는다
    for ch in out:
        ch["indexed"] = 1 if (ch["section"] == "속성" or len(ch["body"]) >= MIN_BODY) else 0
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    if not os.path.isdir(STD_DIR) or not os.listdir(STD_DIR):
        print("data/standard 가 비었다. 먼저 fetch_docs.py 로 표준 문서를 받는다")
        return 1

    docs = []
    for fn in sorted(os.listdir(STD_DIR)):
        if fn.endswith(".json"):
            with open(os.path.join(STD_DIR, fn), encoding="utf-8") as f:
                docs.append(json.load(f))

    total = short = 0
    rows = []
    for d in docs:
        cs = split(d)
        rows.extend(cs)
        total += len(cs)
        short += sum(1 for c in cs if not c["indexed"])

    print("문서 %d개 → 조각 %d개 (색인 제외 %d개, 최소 %d자 기준)\n" % (len(docs), total, short, MIN_BODY))
    for d in docs[:8]:
        cs = split(d)
        if not cs:
            print("  %-30s 조각 없음 (용어)" % d["title"][:30])
            continue
        chars = sum(len(c["body"]) for c in cs)
        print("  %-30s 조각 %2d · %5d자 · 제외 %d" % (
            d["title"][:30], len(cs), chars, sum(1 for c in cs if not c["indexed"])))

    if a.dry:
        print("\n  --dry 라 쓰지 않았다")
        return 0

    con = connect()
    with con:
        for c in rows:
            con.execute("""INSERT INTO chunks
              (chunk_id, document_id, kind, title, section, body, visibility, observed_at, status, images, indexed, related)
              VALUES (:chunk_id,:document_id,:kind,:title,:section,:body,:visibility,:observed_at,:status,:images,:indexed,:related)
              ON CONFLICT(chunk_id) DO UPDATE SET
                body=excluded.body, section=excluded.section, visibility=excluded.visibility,
                observed_at=excluded.observed_at, status=excluded.status,
                images=excluded.images, indexed=excluded.indexed, related=excluded.related""", c)
        for d in docs:
            md = d.get("metadata") or {}
            con.execute("""INSERT INTO documents
              (document_id, kind, title, summary, visibility, status, observed_at, content_hash, updated_at)
              VALUES (?,?,?,?,?,?,?,?,?)
              ON CONFLICT(document_id) DO UPDATE SET
                title=excluded.title, summary=excluded.summary, visibility=excluded.visibility,
                status=excluded.status, observed_at=excluded.observed_at,
                content_hash=excluded.content_hash, updated_at=excluded.updated_at""",
                (d["document_id"], d["kind"], d["title"], d.get("summary"),
                 1 if d["visibility"] else 0, md.get("상태"),
                 md.get("확인일") or md.get("공표 시점") or md.get("수집일"),
                 d["revision"]["content_hash"], d["revision"]["notion_edited"]))
        # 정리 — 이번 표준 문서에 없는 문서와 조각은 지운다 (명세 F-06 처리 6 의 뜻).
        # 덮어쓰기만 하면 「DB 반영」이 꺼진 줄, 이름이 바뀐 문서, 줄어든 구간의 조각이 색인에 남는다
        con.execute("CREATE TEMP TABLE keep_c (chunk_id TEXT PRIMARY KEY)")
        con.executemany("INSERT OR IGNORE INTO keep_c VALUES (?)", [(c["chunk_id"],) for c in rows])
        con.execute("CREATE TEMP TABLE keep_d (document_id TEXT PRIMARY KEY)")
        con.executemany("INSERT OR IGNORE INTO keep_d VALUES (?)", [(d["document_id"],) for d in docs])
        gone_c = con.execute("DELETE FROM chunks WHERE chunk_id NOT IN (SELECT chunk_id FROM keep_c)").rowcount
        gone_d = con.execute("DELETE FROM documents WHERE document_id NOT IN (SELECT document_id FROM keep_d)").rowcount
        con.execute("DROP TABLE keep_c")
        con.execute("DROP TABLE keep_d")
        if gone_c or gone_d:
            print("  지운 것: 조각 %d개 · 문서 %d개 (표준 문서에 더 없음)" % (gone_c, gone_d))
    n = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    con.close()
    print("\n  %s 에 조각 %d개" % (DB_PATH, n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
