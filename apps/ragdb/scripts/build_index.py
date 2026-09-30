# -*- coding: utf-8 -*-
"""F-06 색인 생성 — 조각을 BM25 색인으로 만들고 넓히기 사전을 굽는다.

    python scripts/build_index.py            색인을 만들고 곧바로 갈아 끼운다
    python scripts/build_index.py --hold     만들기만 한다. 갈아 끼우기는 refresh.py 가 스냅샷 뒤에 한다

F-06 처리 5 — 제자리에서 덮어쓰지 않는다.
새 판 폴더에 다 만든 뒤 마지막에 current.txt 한 줄만 바꿔 갈아 끼운다.
직전 판은 지우지 않고 다음 배치까지 남긴다.
"""
import datetime
import json
import os
import shutil
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bm25s

import chunk as C
import tokenize_ko as T
import masking as M   # 금지어 규칙. 가리기는 정제 배치가 하고 여기서는 한 번 더 훑기만

from app import config as cfg       # noqa: E402  (chunk 가 ROOT 를 sys.path 에 넣어 둔다)
from app import store               # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 자리는 설정(app/config.py)을 따른다. 질의 쪽과 같은 곳을 봐야 한다
INDEX_ROOT = cfg.INDEX_ROOT
CURRENT = cfg.CURRENT
STD_DIR = C.STD_DIR


def load_staged():
    """배치가 작업 자리에 만들어 둔 조각과 문서 목록 (chunk.py). 없으면 (None, None)."""
    return C.staged()


def has_forbidden(text):
    """금지어(주소, 초대 링크)가 있으면 걸린 글을 돌려준다."""
    for p in M.ADDRESS_PATTERNS:
        m = p.search(text or "")
        if m:
            return m.group(0)
    return None


def bake_guard(out_dir):
    """나가는 글 지킴이가 쓸 목록 (app/guard.py). 가릴 이름과 가리면 안 되는 이름.

    넓히기 사전처럼 이름만 담고 본문을 담지 않는다. 어디로도 내보내지 않는다 (SR-01).
    질의 서버는 답을 내보내기 직전에 이 목록으로 한 번 더 가린다.
    """
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from app import guard

    docs = C.load_docs()
    g, _ = C.load_guard(docs)
    guard.save(os.path.join(out_dir, "guard.json"), g.names, guard.keep_names(docs), g.hidden)
    return g


def bake_terms(out_dir, g=None):
    """넓히기 사전 (F-06 처리 3). 표준 문서의 aliases 와 용어 문서의 다른 표기를 모은다.

    항목: 번호, 대표어, 표기 목록, 원천 document_id, 원천의 반출 여부.
    행위자 문서의 aliases 는 넣지 않는다 (동일인 추정, OI-18). 금지어가 든 표기는 싣지 않는다.
    돌려주는 것: (항목 수, 걸린 시간 초). 실패하면 직전 사전을 복사해 두고 (None, 시간).
    """
    t0 = time.monotonic()
    path = os.path.join(out_dir, "terms.json")
    try:
        items = []
        for fn in sorted(os.listdir(STD_DIR)):
            if not fn.endswith(".json"):
                continue
            with open(os.path.join(STD_DIR, fn), encoding="utf-8") as f:
                d = json.load(f)
            if d["kind"] == "행위자":
                continue
            forms = []
            for a in [d.get("title")] + list(d.get("aliases") or []):
                a = (a or "").strip() if isinstance(a, str) else ""
                if not a or a in forms or has_forbidden(a):
                    continue
                if g is not None and g.clean(a) != a:
                    continue          # 조직 이름이나 도메인으로 가려질 표기는 사전에 싣지 않는다
                forms.append(a)
            if len(forms) < 2:
                continue          # 다른 표기가 없으면 넓힐 것이 없다
            items.append({"id": len(items) + 1, "head": forms[0], "forms": forms,
                          "source": d["document_id"], "visibility": bool(d.get("visibility"))})
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"items": items}, f, ensure_ascii=False)
        return len(items), time.monotonic() - t0
    except (OSError, ValueError, KeyError, TypeError):
        prev = previous_version(os.path.basename(out_dir))
        if prev and os.path.exists(os.path.join(INDEX_ROOT, prev, "terms.json")):
            shutil.copyfile(os.path.join(INDEX_ROOT, prev, "terms.json"), path)
        return None, time.monotonic() - t0


def versions():
    if not os.path.isdir(INDEX_ROOT):
        return []
    return sorted(v for v in os.listdir(INDEX_ROOT) if os.path.isdir(os.path.join(INDEX_ROOT, v)))


def previous_version(version):
    older = [v for v in versions() if v < version]
    return older[-1] if older else None


def activate(version):
    """새 판을 쓰기 시작한다. 여기까지 와야 새 판이 쓰인다. 직전 판까지 둘만 남긴다."""
    tmp = CURRENT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(version)
    os.replace(tmp, CURRENT)
    for old in [v for v in versions() if v != version][:-1]:
        shutil.rmtree(os.path.join(INDEX_ROOT, old), ignore_errors=True)


def build(version=None, hold=False):
    """돌려주는 것: {version, chunks, tokens, excluded, terms, terms_seconds} 또는 None."""
    chunks, doc_rows = load_staged()
    rows = [c for c in chunks or [] if c.get("indexed")]
    if not rows:
        print("색인에 넣을 조각이 없다. 먼저 chunk.py 를 돌린다")
        return None

    # F-06 처리 1 · TC-06 — 나가는 조각에 금지어(주소·링크)가 남았으면 색인을 만들지 않는다.
    # 색인에 안 드는 짧은 조각도 스냅샷으로는 나가므로 같이 본다
    bad = []
    for c in chunks:
        if not c.get("visibility"):
            continue
        hit = has_forbidden("%s %s %s" % (c.get("title") or "", c.get("section") or "", c.get("body") or ""))
        if hit:
            bad.append((c["chunk_id"], hit[:60]))
    if bad:
        print("금지어 검사에서 멈춤 — 반출 조각 %d개에 주소나 링크가 남아 있다 (TC-06). current.txt 는 그대로" % len(bad))
        for cid, hit in bad[:15]:
            print("  %-45s %s" % (cid[:45], hit))
        return None

    # 판 이름은 한국 시간으로 짓는다. 서버의 시간대가 달라도 같은 이름이 나오게 한다
    version = version or datetime.datetime.now(store.KST).strftime("%Y%m%d-%H%M%S")
    out_dir = os.path.join(INDEX_ROOT, version)
    os.makedirs(out_dir, exist_ok=True)

    ids = []
    corpus = []
    for c in rows:
        ids.append({"chunk_id": c["chunk_id"], "document_id": c["document_id"], "kind": c["kind"],
                    "title": c["title"], "section": c["section"], "visibility": bool(c["visibility"]),
                    "status": c.get("status"), "observed_at": c.get("observed_at")})
        # 제목과 소제목도 함께 넣는다 — 본문에 이름이 안 나오는 구간이 있다
        corpus.append(T.tokens("%s %s %s" % (c["title"] or "", c["section"] or "", c["body"] or "")))

    r = bm25s.BM25()
    r.index(corpus, show_progress=False)
    r.save(out_dir, corpus=None)

    def write(name, data):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)

    write("ids.json", ids)
    # 판 폴더는 그 판이 쓰는 것을 전부 담는다. 질의와 스냅샷은 여기만 읽는다 (app/search.py, snapshot.py).
    # 그래서 배치가 도는 중이거나 중간에 멈춰도 지금 판의 답이 바뀌지 않는다
    #   chunks.json      조각 전부 (색인에 안 든 짧은 조각 포함). chunk_id 로 찾는다
    #   documents.json   문서 머리와 내용 해시. document_id 로 찾는다
    write("chunks.json", {c["chunk_id"]: {k: v for k, v in c.items() if k != "chunk_id"} for c in chunks})
    write("documents.json", {d["document_id"]: {k: v for k, v in d.items() if k != "document_id"} for d in doc_rows})

    g = bake_guard(out_dir)
    n_terms, sec = bake_terms(out_dir, g)

    if not hold:
        activate(version)

    return {"version": version, "chunks": len(ids), "tokens": sum(len(c) for c in corpus),
            "excluded": len(chunks) - len(rows), "terms": n_terms, "terms_seconds": round(sec, 3),
            "guard_names": len(g.names)}


if __name__ == "__main__":
    hold = "--hold" in sys.argv
    res = build(hold=hold)
    if res:
        print("판 %s" % res["version"])
        print("  조각 %d개 · 낱말 %d개" % (res["chunks"], res["tokens"]))
        print("  넓히기 사전 %s" % ("굽기 실패, 직전 사전을 씀" if res["terms"] is None else "%d항목" % res["terms"]))
        print("  current.txt %s" % ("는 그대로 (--hold)" if hold else "-> %s" % res["version"]))
        print("  남은 판: %s" % ", ".join(versions()))
