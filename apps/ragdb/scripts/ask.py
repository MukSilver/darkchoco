# -*- coding: utf-8 -*-
"""터미널에서 질문 하나를 끝까지 태운다 (로드맵 2단계 관문).

    python scripts/ask.py "BreachForums 지금 살아 있나요?"
    python scripts/ask.py --search "질문"        검색까지만. 모델과 재순위를 부르지 않는다 (0원)
    python scripts/ask.py --visitor "질문"       방문자 질의처럼 센다 (하루 차단기를 거친다)

기본은 관리 질의다. 비용을 평가 실행 비용 칸에 따로 세고 하루 차단기를 거치지 않는다 (F-18 처리 6).
질문은 화면에만 찍고 어디에도 저장하지 않는다 (SR-16).
"""
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import config as cfg          # noqa: E402
from app import pii, pipeline          # noqa: E402
from app.search import Searcher        # noqa: E402


def show_search(q):
    s = Searcher()
    masked, found = pii.mask(q)
    r = s.search(masked)
    print("판     %s" % s.version)
    print("낱말   %s" % " / ".join(r["tokens"]))
    print("종류   %s" % (", ".join(r["kinds"]) or "없음"))
    print("넓히기 %s" % ("사전 없음" if r["no_dictionary"] else
                        ("무게 0 (꺼짐)" if cfg.EXPANSION_WEIGHT <= 0 else
                         ", ".join("%s → %s" % (it["head"], " / ".join(it["forms"])) for it in r["items"]) or "맞은 항목 없음")))
    print("후보   %d개\n" % len(r["candidates"]))
    for i, c in enumerate(r["candidates"][:10], 1):
        print("  %2d. %-24s %-20s 합 %.2f (원 %.2f, 넓힘 %.2f, 종류 %.2f)" % (
            i, (c["title"] or "")[:24], (c["section"] or "")[:20], c["score"], c["bm25"], c["expand"], c["boost"]))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 1
    q = args[0]
    if "--search" in sys.argv:
        show_search(q)
        return 0

    state = {"open": False}

    def on_event(name, value):
        if name == "searching":
            print("(찾는 중)")
        elif name == "text":
            print(value, end="", flush=True)
            state["open"] = True
        elif name == "replace":
            print("\n\n" + value, end="")
        elif name == "error":
            print("\n오류 %s (%s)" % (value.get("status"), value.get("code")))

    out = pipeline.run(q, on_event=on_event, evaluation="--visitor" not in sys.argv)
    print("\n")
    d = out["done"]
    if not d:
        return 1
    label = {"new": "새 답변", "reused": "같은 질문에 앞서 만든 답", "prepared": "사전 답변", "no_evidence": "근거 없음"}[d["kind"]]
    print("── %s · 판 %s%s" % (label, d["version"], " · 개인정보는 가리고 물었음" if d.get("pii_masked") else ""))
    if d.get("truncated"):
        print("   답 길이 상한에 닿아 끊겼다 (ANSWER_MAX_TOKENS)")
    for s in d.get("sentences") or []:
        mark = "".join("[%d]" % n for n in s["sources"]) if s["cited"] else "(출처 없음)"
        print("   %s %s" % (s["text"].replace("\n", " ")[:110], mark))
    if out["sources"]:
        print("\n── 출처")
        for s in out["sources"]:
            print("   [%d] %s / %s · %s · %s %s%s" % (
                s["n"], s["title"], s["section"], s["kind"], s.get("date_label") or "확인일", s["observed_at"] or "없음",
                " · offline" if s.get("status") == "offline" else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
