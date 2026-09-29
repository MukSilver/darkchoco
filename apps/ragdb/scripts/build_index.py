# -*- coding: utf-8 -*-
"""F-06 색인 생성 — 조각을 BM25 색인으로 만든다.

    python scripts/build_index.py

명세 F-06 처리 5 — 제자리에서 덮어쓰지 않는다.
새 판 폴더에 다 만든 뒤 마지막에 current.txt 한 줄만 바꿔 갈아 끼운다.
직전 판은 지우지 않고 다음 배치까지 남긴다.
"""
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
import masking as M   # 금지어 규칙. 가리기는 정제 배치가 하고 여기서는 한 번 더 훑기만 (판 1.6)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_ROOT = os.path.join(ROOT, "data", "bm25_index")
CURRENT = os.path.join(ROOT, "data", "current.txt")


def load_indexed():
    """색인에 넣을 조각. indexed=1 인 것만 (명세 F-05 처리 2)."""
    con = C.connect()
    rows = con.execute(
        "SELECT chunk_id, document_id, kind, title, section, body, visibility "
        "FROM chunks WHERE indexed = 1"
    ).fetchall()
    con.close()
    return rows


def build(version=None):
    rows = load_indexed()
    if not rows:
        print("색인에 넣을 조각이 없다. 먼저 chunk.py 를 돌린다")
        return None

    # 명세 F-06 처리 1 · TC-06 — 반출 조각에 금지어(주소·링크)가 남았으면 색인을 만들지 않는다
    bad = []
    for cid, did, kind, title, section, body, vis in rows:
        if not vis:
            continue
        text = "%s %s %s" % (title or "", section or "", body or "")
        for p in M.ADDRESS_PATTERNS:
            m = p.search(text)
            if m:
                bad.append((cid, m.group(0)[:60]))
                break
    if bad:
        print("금지어 검사에서 멈춤 — 반출 조각 %d개에 주소나 링크가 남아 있다 (TC-06). current.txt 는 그대로" % len(bad))
        for cid, hit in bad[:15]:
            print("  %-45s %s" % (cid[:45], hit))
        return None

    version = version or time.strftime("%Y%m%d-%H%M%S")
    out_dir = os.path.join(INDEX_ROOT, version)
    os.makedirs(out_dir, exist_ok=True)

    ids = []
    corpus = []
    for cid, did, kind, title, section, body, vis in rows:
        ids.append({"chunk_id": cid, "document_id": did, "kind": kind,
                    "title": title, "section": section, "visibility": bool(vis)})
        # 제목과 소제목도 함께 넣는다 — 본문에 이름이 안 나오는 구간이 있다
        corpus.append(T.tokens("%s %s %s" % (title or "", section or "", body or "")))

    r = bm25s.BM25()
    r.index(corpus, show_progress=False)
    r.save(out_dir, corpus=None)

    with open(os.path.join(out_dir, "ids.json"), "w", encoding="utf-8") as f:
        json.dump(ids, f, ensure_ascii=False)

    # 마지막에 표시 파일을 바꾼다. 여기까지 와야 새 판이 쓰인다
    with open(CURRENT, "w", encoding="utf-8") as f:
        f.write(version)

    # 직전 판까지 둘만 남긴다
    vers = sorted(v for v in os.listdir(INDEX_ROOT)
                  if os.path.isdir(os.path.join(INDEX_ROOT, v)))
    for old in vers[:-2]:
        shutil.rmtree(os.path.join(INDEX_ROOT, old), ignore_errors=True)

    return version, len(ids), sum(len(c) for c in corpus)


if __name__ == "__main__":
    res = build()
    if res:
        v, n, toks = res
        print("판 %s" % v)
        print("  조각 %d개 · 낱말 %d개" % (n, toks))
        print("  current.txt -> %s" % v)
        print("  남은 판: %s" % ", ".join(sorted(os.listdir(INDEX_ROOT))))
