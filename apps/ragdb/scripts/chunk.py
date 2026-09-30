# -*- coding: utf-8 -*-
"""F-05 조각 분할 — 표준 문서를 검색 단위로 자른다.

    python scripts/chunk.py --dry     자르기만 하고 보여준다
    python scripts/chunk.py           작업 자리(data/staging)에 쓴다

F-05
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
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import config as cfg       # noqa: E402  (.env 도 여기서 읽힌다)

# 자리는 설정(app/config.py)을 따른다. 전에는 여기서 따로 정해서, .env 의 상대 경로가 돌리는 자리에 따라
# 다른 곳을 가리켰다 (2026-09-30 검토에서 찾음)
STD_DIR = os.path.join(cfg.DATA_DIR, "standard")
# 만든 조각과 문서 목록을 두는 작업 자리. 색인(build_index.py)이 여기서 읽어 판 폴더로 굽는다.
# 질의는 여기를 읽지 않는다. 판 폴더만 읽는다. SQLite 는 쓰지 않는다 (2026-09-30)
STAGING = cfg.STAGING_DIR

# OI-03 첫 값. 설정에서 읽는다
MIN_BODY = cfg.MIN_BODY_CHARS

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

VERDICT_KEYS = ["검증 분류", "진위 판정", "신규성 판정", "판정 신뢰도"]      # 검증 네 축


def staged():
    """작업 자리에 만들어 둔 것을 읽는다. (조각 목록, 문서 목록). 없으면 (None, None)."""
    try:
        with open(os.path.join(STAGING, "chunks.json"), encoding="utf-8") as f:
            chunks = json.load(f)
        with open(os.path.join(STAGING, "documents.json"), encoding="utf-8") as f:
            docs = json.load(f)
        return chunks, docs
    except (OSError, ValueError):
        return None, None


def attr_body(doc):
    """속성 조각의 본문. 칸 값을 「이름: 값」 줄로 편다.
    본문에 이미 있는 것을 다시 쓰지 않는다 (DR-03)."""
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
        return []          # 검색 대상이 아니다 (F-05 처리 1)

    md = doc.get("metadata") or {}
    common = {
        "document_id": doc["document_id"],
        "kind": doc["kind"],
        "title": doc["title"],
        "observed_at": md.get("확인일") or md.get("공표 시점") or md.get("수집일") or md.get("검증일"),
        "status": md.get("상태"),
        "related": [x.strip() for x in str(md.get("연결된 곳", "")).split("·") if x.strip()],
    }

    out = [dict(common,
                chunk_id="%s#s0" % doc["document_id"],
                section="속성",
                body=attr_body(doc),
                visibility=bool(doc["visibility"]),
                images=[])]

    for i, s in enumerate(doc.get("sections") or [], 1):
        body = s.get("body") or ""
        out.append(dict(common,
                        chunk_id="%s#s%d" % (doc["document_id"], i),
                        section=s.get("heading") or ("문단 %d" % i),
                        body=body,
                        visibility=bool(doc["visibility"] and s.get("visibility", True)),
                        images=s.get("images") or []))

    # 처리 2 — 짧은 조각은 색인에서 뺀다. 속성 조각은 길이와 무관하게 넣는다
    for ch in out:
        ch["indexed"] = 1 if (ch["section"] == "속성" or len(ch["body"]) >= MIN_BODY) else 0
    return out


REQUIRE_NAME_CHECK = (os.getenv("REQUIRE_NAME_CHECK") or "1").strip() not in ("0", "false", "no")
# 개인정보 꼴이 남은 문서를 어떻게 할지. mask: 그 자리만 가리고 문서는 둔다. exclude: 문서를 통째로 뺀다.
# 2026-09-30 부터 기본값은 mask 다. 노션 원본을 고쳐 줄 조사팀이 따로 없어 exclude 로 두면 그 문서가 영영 빠진다
PII_POLICY = (os.getenv("PII_POLICY") or "mask").strip()
NAMES_FILE = os.path.join(cfg.DATA_DIR, "names.json")


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


def pii_masked(doc):
    """개인정보 꼴을 자리 표시([IP], [이메일] 등)로 바꾼 사본. 제목은 건드리지 않는다."""
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from app import pii

    def m(v):
        if isinstance(v, list):
            return [pii.mask(x)[0] if isinstance(x, str) else x for x in v]
        return pii.mask(v)[0] if isinstance(v, str) else v

    out = dict(doc)
    out["summary"] = m(doc.get("summary"))
    out["metadata"] = {k: m(v) for k, v in (doc.get("metadata") or {}).items()}
    out["sections"] = [dict(s, heading=m(s.get("heading")), body=m(s.get("body"))) for s in doc.get("sections") or []]
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
    rows, kept, excluded, covered, terms = [], [], [], [], 0
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
        if hits and PII_POLICY == "mask":
            d = pii_masked(d)
            covered.append({"document_id": d["document_id"], "kind": d["kind"], "hits": hits})
            hits = pii_hits(d)          # 가린 뒤에도 남았으면 뺀다
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
    if covered:
        say("  개인정보 꼴이 남아 그 자리를 가린 문서 %d개 (F-03). 노션 원본에서 가리는 것이 맞다" % len(covered))
        for e in covered:
            say("    %-28s %s" % (e["document_id"][:28], ", ".join("%s %s" % (h["where"], h["what"]) for h in e["hits"][:4])))
    if masked:
        say("  개인정보 꼴이 남아 뺀 문서 %d개 (F-03). 노션 원본에서 가린 뒤 다시 들어온다" % len(masked))
        for e in masked:
            say("    %-28s %s" % (e["document_id"][:28], ", ".join("%s %s" % (h["where"], h["what"]) for h in e["hits"][:4])))

    stats = {"documents": len(kept), "terms": terms, "chunks": total, "not_indexed": short,
             "excluded": excluded, "pii_masked": covered,
             "dropped_columns": {"%s.%s" % k: n for k, n in sorted(dropped.items())}}
    if dry:
        say("\n  --dry 라 쓰지 않았다")
        return stats

    flat = lambda v: " · ".join(str(x) for x in v) if isinstance(v, list) else v
    doc_rows = []
    for d in kept:
        md = d.get("metadata") or {}
        verdict = {k: md[k] for k in VERDICT_KEYS if md.get(k)} if d["kind"] == "판정" else {}
        doc_rows.append({
            "document_id": d["document_id"], "kind": d["kind"], "title": d["title"], "summary": d.get("summary"),
            "visibility": bool(d["visibility"]), "status": md.get("상태"),
            "observed_at": md.get("확인일") or md.get("공표 시점") or md.get("수집일") or md.get("검증일"),
            "content_hash": d["revision"]["content_hash"], "updated_at": d["revision"]["notion_edited"],
            "country": flat(md.get("국가")), "signup": flat(md.get("가입 필요")), "related": flat(md.get("연결된 곳")),
            "verdict": verdict or None})

    # 작업 자리를 통째로 새로 쓴다. 이번에 만들지 않은 문서와 조각(꺼진 줄, 이름이 바뀐 문서, 줄어든 구간)은 남지 않는다
    os.makedirs(STAGING, exist_ok=True)
    for name, data in (("chunks.json", rows), ("documents.json", doc_rows)):
        tmp = os.path.join(STAGING, name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, os.path.join(STAGING, name))
    say("  %s 에 조각 %d개, 문서 %d개" % (STAGING, len(rows), len(doc_rows)))
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    return 0 if run(dry=a.dry) is not None else 1


if __name__ == "__main__":
    sys.exit(main())
