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

속성 조각은 반출하는 칸 목록(export_columns.json, 넣는 목록)에 적힌 칸으로만 만든다 (DR-07).
조각 본문은 바깥 사업자와 스냅샷으로 나가므로 반출 경계가 여기다. 목록에 없는 칸은 세어서 알린다.
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

EXPORT_COLUMNS = os.path.join(ROOT, "export_columns.json")
_columns = None


def export_columns():
    """{종류: [반출하는 칸, ...]}. 파일이 없으면 아무 칸도 내보내지 않는다 (기본값은 안 내보냄)."""
    global _columns
    if _columns is None:
        try:
            with open(EXPORT_COLUMNS, encoding="utf-8") as f:
                _columns = {k: v for k, v in json.load(f).items() if isinstance(v, list)}
        except (OSError, ValueError):
            _columns = {}
    return _columns


def exported_metadata(doc):
    """반출하는 칸만 남긴 metadata 와, 목록에 없어 뺀 칸 이름."""
    allow = export_columns().get(doc["kind"], [])
    md = doc.get("metadata") or {}
    return {k: v for k, v in md.items() if k in allow}, [k for k in md if k not in allow]

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

# 명세 3.4 documents 의 나머지 칸. 먼저 만든 DB 에는 없으므로 없을 때만 더한다
MORE_COLUMNS = [("country", "TEXT"), ("signup", "TEXT"), ("related", "TEXT"), ("verdict", "TEXT")]
VERDICT_KEYS = ["검증 분류", "진위 판정", "신규성 판정", "판정 신뢰도"]      # 검증 네 축 (명세 1.3)


def connect():
    """명세 DR-09 — WAL · busy_timeout 5초 · synchronous NORMAL."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = sqlite3.connect(DB_PATH, timeout=5)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=5000")
    c.execute("PRAGMA synchronous=NORMAL")
    c.executescript(SCHEMA)
    have = {r[1] for r in c.execute("PRAGMA table_info(documents)")}
    for name, typ in MORE_COLUMNS:
        if name not in have:
            c.execute("ALTER TABLE documents ADD COLUMN %s %s" % (name, typ))
    return c


def attr_body(doc):
    """속성 조각의 본문. 칸 값을 「이름: 값」 줄로 편다.
    본문에 이미 있는 것을 다시 쓰지 않는다 (명세 DR-03)."""
    lines = ["%s: %s" % (doc["kind"], doc["title"])]
    if doc.get("summary"):
        lines.append(doc["summary"])
    for k, v in exported_metadata(doc)[0].items():
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
        "observed_at": md.get("확인일") or md.get("공표 시점") or md.get("수집일") or md.get("검증일"),
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


REQUIRE_NAME_CHECK = (os.getenv("REQUIRE_NAME_CHECK") or "1").strip() not in ("0", "false", "no")
NAMES_FILE = os.path.join(ROOT, "data", "names.json")


def load_guard(docs):
    """(지킴이, {document_id: 이름 찾기를 거친 내용 해시}). 찾아 둔 이름이 없으면 도메인만 가린다."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from app import guard

    names, checked = set(), {}
    try:
        with open(NAMES_FILE, encoding="utf-8") as f:
            for did, v in (json.load(f).get("docs") or {}).items():
                names.update(v.get("names") or [])
                checked[did] = v.get("hash")
    except (OSError, ValueError, AttributeError):
        pass
    return guard.Guard(sorted(names), guard.keep_names(docs), guard.hidden_names(docs)), checked


def cleaned(doc, g):
    """조직 이름, 도메인, 행위자의 다른 이름을 가린 사본. 장소와 행위자의 이름은 가리지 않는 목록에 있어 그대로 남는다."""
    out = dict(doc)
    out["title"] = g.clean(doc.get("title"))
    out["summary"] = g.clean(doc.get("summary"))
    out["metadata"] = {k: g.clean_value(v) for k, v in (doc.get("metadata") or {}).items()}
    out["sections"] = [dict(s, heading=g.clean(s.get("heading")), body=g.clean(s.get("body")))
                       for s in doc.get("sections") or []]
    return out


def pii_hits(doc):
    """F-03 가리기 검사 — 나갈 글에 개인정보 꼴 여섯이 남았는지. 걸린 자리와 꼴을 돌려준다 (값은 돌려주지 않는다).

    가리기는 노션 원본에서 끝내야 하고 이 검사는 이중 안전장치다. 걸린 문서는 통째로 뺀다.
    한 군데가 안 가려졌으면 그 문서는 확인을 덜 거친 것이라 다른 값도 남았을 수 있다.
    """
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from app import pii      # 질문 가리기(SR-24)와 같은 꼴 여섯을 쓴다

    parts = [("제목", doc.get("title") or ""), ("요약", doc.get("summary") or "")]
    for k, v in exported_metadata(doc)[0].items():
        parts.append(("칸 " + k, " ".join(str(x) for x in v) if isinstance(v, list) else str(v)))
    for i, s in enumerate(doc.get("sections") or [], 1):
        parts.append(("본문 %d" % i, "%s %s" % (s.get("heading") or "", s.get("body") or "")))
    hits = []
    for where, text in parts:
        label = pii.has_pii(text)
        if label:
            hits.append({"where": where, "what": label})
    return hits


def load_docs():
    docs = []
    for fn in sorted(os.listdir(STD_DIR)):
        if fn.endswith(".json"):
            with open(os.path.join(STD_DIR, fn), encoding="utf-8") as f:
                docs.append(json.load(f))
    return docs


def run(dry=False, quiet=False):
    """조각과 목록을 만든다. 돌려주는 것은 배치 기록에 남길 값이다. 표준 문서가 없으면 None."""
    say = (lambda *a: None) if quiet else print
    if not os.path.isdir(STD_DIR) or not os.listdir(STD_DIR):
        say("data/standard 가 비었다. 먼저 fetch_docs.py 로 표준 문서를 받는다")
        return None

    docs = load_docs()
    g, checked = load_guard(docs)
    total = short = 0
    rows, kept, excluded, terms = [], [], [], 0
    dropped = {}
    for d in docs:
        if d["kind"] == "용어":
            terms += 1          # 조각도 목록도 만들지 않는다. 넓히기 사전의 원천일 뿐이다 (F-05 처리 1, QR-05)
            continue
        if REQUIRE_NAME_CHECK and checked.get(d["document_id"]) != d["revision"]["content_hash"]:
            # 조직 이름 찾기를 거치지 않은 글은 내보내지 않는다 (find_names.py 를 먼저 돌린다)
            excluded.append({"document_id": d["document_id"], "kind": d["kind"],
                             "hits": [{"where": "문서", "what": "이름 찾기 전"}]})
            continue
        if g.leaks(d["document_id"]):
            # 장소 이름 자체에 조직 이름이 든 경우다. 제목은 가릴 수 있어도 문서 ID 와 주소에 이름이 남는다
            excluded.append({"document_id": "(가림)", "kind": d["kind"],
                             "hits": [{"where": "문서 ID", "what": "조직 이름"}]})
            continue
        d = cleaned(d, g)
        hits = pii_hits(d)
        if hits:
            excluded.append({"document_id": d["document_id"], "kind": d["kind"], "hits": hits})
            continue
        cs = split(d)
        rows.extend(cs)
        kept.append(d)
        total += len(cs)
        short += sum(1 for c in cs if not c["indexed"])
        for k in exported_metadata(d)[1]:
            dropped[(d["kind"], k)] = dropped.get((d["kind"], k), 0) + 1

    say("문서 %d개 (용어 %d개는 사전으로만) → 조각 %d개 (색인 제외 %d개, 최소 %d자 기준)" % (
        len(docs), terms, total, short, MIN_BODY))
    if dropped:
        say("  반출하는 칸 목록에 없어 뺀 칸: %s" % ", ".join(
            "%s.%s(%d)" % (k[0], k[1], n) for k, n in sorted(dropped.items())))
    waiting = [e for e in excluded if e["hits"][0]["what"] == "이름 찾기 전"]
    named = [e for e in excluded if e["hits"][0]["where"] == "문서 ID"]
    masked = [e for e in excluded if e not in waiting and e not in named]
    if named:
        say("  이름에 조직 이름이 들어 있어 뺀 문서 %d개 (%s)" % (len(named), ", ".join(e["kind"] for e in named)))
    if waiting:
        say("  조직 이름 찾기를 안 거쳐 뺀 문서 %d개. find_names.py 를 돌리면 들어온다" % len(waiting))
    if masked:
        say("  개인정보 꼴이 남아 뺀 문서 %d개 (F-03). 노션 원본에서 가린 뒤 다시 들어온다" % len(masked))
        for e in masked:
            say("    %-28s %s" % (e["document_id"][:28], ", ".join("%s %s" % (h["where"], h["what"]) for h in e["hits"][:4])))

    stats = {"documents": len(kept), "terms": terms, "chunks": total, "not_indexed": short,
             "excluded": excluded, "dropped_columns": {"%s.%s" % k: n for k, n in sorted(dropped.items())}}
    if dry:
        say("\n  --dry 라 쓰지 않았다")
        return stats

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
        flat = lambda v: " · ".join(str(x) for x in v) if isinstance(v, list) else v
        for d in kept:
            md = d.get("metadata") or {}
            verdict = {k: md[k] for k in VERDICT_KEYS if md.get(k)} if d["kind"] == "판정" else {}
            con.execute("""INSERT INTO documents
              (document_id, kind, title, summary, visibility, status, observed_at, content_hash, updated_at,
               country, signup, related, verdict)
              VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
              ON CONFLICT(document_id) DO UPDATE SET
                title=excluded.title, summary=excluded.summary, visibility=excluded.visibility,
                status=excluded.status, observed_at=excluded.observed_at,
                content_hash=excluded.content_hash, updated_at=excluded.updated_at,
                country=excluded.country, signup=excluded.signup, related=excluded.related, verdict=excluded.verdict""",
                (d["document_id"], d["kind"], d["title"], d.get("summary"),
                 1 if d["visibility"] else 0, md.get("상태"),
                 md.get("확인일") or md.get("공표 시점") or md.get("수집일") or md.get("검증일"),
                 d["revision"]["content_hash"], d["revision"]["notion_edited"],
                 flat(md.get("국가")), flat(md.get("가입 필요")), flat(md.get("연결된 곳")),
                 json.dumps(verdict, ensure_ascii=False) if verdict else None))
        # 정리 — 이번에 만들지 않은 문서와 조각은 지운다 (명세 F-06 처리 6 의 뜻).
        # 덮어쓰기만 하면 「DB 반영」이 꺼진 줄, 이름이 바뀐 문서, 줄어든 구간, 가리기 검사에 걸린 문서의 조각이 남는다
        con.execute("CREATE TEMP TABLE keep_c (chunk_id TEXT PRIMARY KEY)")
        con.executemany("INSERT OR IGNORE INTO keep_c VALUES (?)", [(c["chunk_id"],) for c in rows])
        con.execute("CREATE TEMP TABLE keep_d (document_id TEXT PRIMARY KEY)")
        con.executemany("INSERT OR IGNORE INTO keep_d VALUES (?)", [(d["document_id"],) for d in kept])
        gone_c = con.execute("DELETE FROM chunks WHERE chunk_id NOT IN (SELECT chunk_id FROM keep_c)").rowcount
        gone_d = con.execute("DELETE FROM documents WHERE document_id NOT IN (SELECT document_id FROM keep_d)").rowcount
        con.execute("DROP TABLE keep_c")
        con.execute("DROP TABLE keep_d")
        if gone_c or gone_d:
            say("  지운 것: 조각 %d개 · 문서 %d개" % (gone_c, gone_d))
    n = con.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    con.close()
    say("  %s 에 조각 %d개" % (DB_PATH, n))
    stats.update(removed_chunks=gone_c, removed_documents=gone_d)
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    return 0 if run(dry=a.dry) is not None else 1


if __name__ == "__main__":
    sys.exit(main())
