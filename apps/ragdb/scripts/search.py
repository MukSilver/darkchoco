# -*- coding: utf-8 -*-
"""F-12 조각 검색 — 지금은 처리 1 · 4 · 6 · 7만. 넓히기와 재순위는 아직 안 붙였다.

    python scripts/search.py "브리치드 아직 살아있어?"

명세 F-12 처리 1 — 질의를 시작할 때 current.txt를 한 번 읽어 그 판을 끝까지 쓴다.
"""
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bm25s

import chunk as C
import tokenize_ko as T

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_ROOT = os.path.join(ROOT, "data", "bm25_index")
CURRENT = os.path.join(ROOT, "data", "current.txt")

# OI-02 미결. 후보 M · 최종 K
M = int(os.getenv("CANDIDATE_M", "50"))
K = int(os.getenv("FINAL_K", "5"))


class Searcher:
    def __init__(self):
        """판을 고정해 읽는다. 도중에 배치가 갈아도 한 질의 안에서는 안 바뀐다."""
        with open(CURRENT, encoding="utf-8") as f:
            self.version = f.read().strip()
        d = os.path.join(INDEX_ROOT, self.version)
        self.bm25 = bm25s.BM25.load(d, load_corpus=False)
        with open(os.path.join(d, "ids.json"), encoding="utf-8") as f:
            self.ids = json.load(f)

    def search(self, question, m=M, k=K, exported_only=True):
        """처리 1 반출 거르기 → 4 BM25 → 7 후보 M개.
        재순위(처리 8)가 아직 없어 후보 앞 k개를 그대로 최종으로 쓴다."""
        toks = T.tokens(question)
        if not toks:
            return [], toks
        n = min(m, len(self.ids))
        idx, sc = self.bm25.retrieve([toks], k=n, show_progress=False)

        out = []
        for i, s in zip(idx[0], sc[0]):
            meta = dict(self.ids[int(i)])
            if exported_only and not meta["visibility"]:
                continue          # 명세 F-12 처리 1 · SR-01
            meta["score"] = float(s)
            out.append(meta)
        return out[:k], toks


def body_of(chunk_id):
    con = C.connect()
    r = con.execute("SELECT body FROM chunks WHERE chunk_id = ?", (chunk_id,)).fetchone()
    con.close()
    return r[0] if r else ""


if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "브리치드 아직 살아있어?"
    only_exported = "--all" not in sys.argv

    s = Searcher()
    hits, toks = s.search(q, exported_only=only_exported)

    print("질문   %s" % q)
    print("낱말   %s" % " · ".join(toks))
    print("판     %s" % s.version)
    print("거름   %s\n" % ("반출 통과분만" if only_exported else "전부 (--all)"))

    if not hits:
        print("  근거를 찾지 못했다 (F-15)")
        if only_exported:
            print("  「DB 반영」이 켜진 줄이 없어서다. --all 로 다시 보면 색인 자체는 확인된다")
        sys.exit(0)

    for i, h in enumerate(hits, 1):
        print("  %d. %-16s %-18s %.2f" % (i, h["title"][:16], h["section"][:18], h["score"]))
        print("     %s" % body_of(h["chunk_id"])[:96].replace("\n", " "))
