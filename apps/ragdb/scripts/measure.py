# -*- coding: utf-8 -*-
"""예비 측정 (설계서 「검증」) — 문제집이 없는 동안 확인용 질문으로 검색 쪽 방향만 본다.

    python scripts/measure.py                 넓히기 무게를 바꿔 가며 잰다 (0원. 모델과 재순위를 부르지 않는다)
    python scripts/measure.py --offline 0.7,0.85,1 --boost 0,0.1,0.2

확인용 질문은 받아 둔 표준 문서에서 그때그때 만든다. 파일로 남기지 않는다. 별칭이 들어 있어
저장소(공개)에 두면 안 된다 (TC-22).

  이름 질문    「{명칭} 지금 상태 알려줘」        기준선. 이름 그대로 물었을 때 그 문서가 드는가
  별칭 질문    「{별칭} 어떤 곳이야」            넓히기. 자료에 없는 표기로 물었을 때 드는가 (TC-20)

정답은 문서 하나(그 이름의 문서)다. 후보 M개에 든 비율과 낱말 점수 앞 K개에 든 비율을 센다.
되돌리는 조건은 이 측정으로 판정하지 않는다. 문제집을 받은 뒤 다시 잰다.
"""
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app import config as cfg          # noqa: E402
from app.normalize import norm         # noqa: E402
from app.search import Searcher        # noqa: E402

STD_DIR = os.path.join(ROOT, "data", "standard")


def questions():
    names, aliases = [], []
    for fn in sorted(os.listdir(STD_DIR)):
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(STD_DIR, fn), encoding="utf-8") as f:
            d = json.load(f)
        if d["kind"] not in ("포럼", "텔레그램", "랜섬웨어") or not d.get("visibility"):
            continue
        names.append(("%s 지금 상태 알려줘" % d["title"], d["document_id"]))
        for a in d.get("aliases") or []:
            if isinstance(a, str) and norm(a) and norm(a) != norm(d["title"]):
                aliases.append(("%s 어떤 곳이야" % a, d["document_id"]))
    return names, aliases


def rate(searcher, qs, k, **kw):
    in_m = in_k = 0
    for q, want in qs:
        docs = [c["document_id"] for c in searcher.search(q, **kw)["candidates"]]
        in_m += want in docs
        in_k += want in docs[:k]
    n = max(len(qs), 1)
    return in_m / n, in_k / n


def floats(name, default):
    for i, a in enumerate(sys.argv):
        if a == name and i + 1 < len(sys.argv):
            return [float(x) for x in sys.argv[i + 1].split(",")]
    return default


def main():
    s = Searcher()
    names, aliases = questions()
    print("판 %s · 이름 질문 %d개 · 별칭 질문 %d개 · 넓히기 사전 %s항목 · M %d · K %d\n" % (
        s.version, len(names), len(aliases), "없음" if s.terms is None else len(s.terms), cfg.CANDIDATE_M, cfg.FINAL_K))

    print("넓히기 무게 (종류 가산 %.2f, offline 곱 %.2f)" % (cfg.KIND_BOOST, cfg.OFFLINE_FACTOR))
    print("  무게    이름 M    이름 K    별칭 M    별칭 K")
    for w in floats("--weight", [0.0, 0.3, 0.5, 0.7, 0.9]):
        a = rate(s, names, cfg.FINAL_K, weight=w)
        b = rate(s, aliases, cfg.FINAL_K, weight=w)
        print("  %.1f    %.3f    %.3f    %.3f    %.3f" % (w, a[0], a[1], b[0], b[1]))

    w = cfg.EXPANSION_WEIGHT
    offs, boosts = floats("--offline", []), floats("--boost", [])
    if offs:
        print("\noffline 곱 (넓히기 무게 %.1f)" % w)
        print("  곱      이름 M    이름 K")
        keep = cfg.OFFLINE_FACTOR
        for o in offs:
            cfg.OFFLINE_FACTOR = o
            a = rate(s, names, cfg.FINAL_K, weight=w)
            print("  %.2f    %.3f    %.3f" % (o, a[0], a[1]))
        cfg.OFFLINE_FACTOR = keep
    if boosts:
        print("\n종류 가산 (넓히기 무게 %.1f). 이름 질문에는 종류 낱말이 없어 값이 같아야 한다" % w)
        print("  가산    이름 M    이름 K")
        for b in boosts:
            a = rate(s, names, cfg.FINAL_K, weight=w, kind_boost=b)
            print("  %.2f    %.3f    %.3f" % (b, a[0], a[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
