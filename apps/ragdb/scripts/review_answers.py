# -*- coding: utf-8 -*-
"""사전 답변 검토 (F-17 처리 6). 사람이 읽고 통과시킨 것만 방문자에게 나간다.

    python scripts/review_answers.py                       검토 전 목록
    python scripts/review_answers.py show 3                3번 답과 출처를 본다
    python scripts/review_answers.py pass 3 --who 이름      통과시킨다
    python scripts/review_answers.py drop 3 --who 이름      지운다

번호는 목록에 나온 순서다. 누가 통과시켰는지는 확인 기록(review_log)에 남는다.
관리 화면은 만들지 않는다. 검토는 이 스크립트로 한다 (설계서 「운영」).
사전 답변은 운영 기록 저장소(Supabase)에 있다. 어느 기계에서 검토해도 같은 목록을 본다.
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
from app import store                  # noqa: E402


def who():
    for i, a in enumerate(sys.argv):
        if a == "--who" and i + 1 < len(sys.argv):
            return sys.argv[i + 1].strip()
    return ""


def bodies():
    """지금 판의 조각 본문. 출처를 보여 줄 때 쓴다. 판이 없으면 빈 것."""
    try:
        with open(cfg.CURRENT, encoding="utf-8") as f:
            version = f.read().strip()
        with open(os.path.join(cfg.INDEX_ROOT, version, "chunks.json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def main():
    st = store.connect()
    all_rows = st.answers_all()
    args = [a for a in sys.argv[1:] if not a.startswith("--") and a != who()]
    if not args:
        waiting = sum(1 for r in all_rows if not r["reviewed"])
        print("사전 답변 %d개 (검토 전 %d개)\n" % (len(all_rows), waiting))
        for i, r in enumerate(all_rows, 1):
            print("  %3d  %s  %s" % (i, "통과  " if r["reviewed"] else "검토 전", (r["question"] or "")[:70]))
        return 0

    cmd = args[0]
    try:
        r = all_rows[int(args[1]) - 1]
    except (IndexError, ValueError):
        print("번호가 맞지 않는다. 번호 없이 돌려 목록을 본다")
        return 1

    if cmd == "show":
        print("질문   %s" % r["question"])
        print("만든 때 %s · 모델 %s · %s\n" % (r["created_at"], r["model"], "통과" if r["reviewed"] else "검토 전"))
        for s in r["answer"]:
            mark = "".join("[%d]" % n for n in s["sources"]) if s["cited"] else "(출처 없음)"
            print("  %s %s" % (s["text"], mark))
        print()
        text = bodies()
        for s in r["sources"] or []:
            print("  [%d] %s / %s · %s %s" % (s["n"], s["title"], s["section"], s.get("date_label") or "확인일",
                                            s["observed_at"] or "없음"))
            body = (text.get(s["chunk_id"]) or {}).get("body")
            if body:
                print("      %s" % body[:300].replace("\n", " "))
        return 0

    name = who()
    if not name:
        print("--who 로 검토한 사람 이름을 적는다")
        return 1
    if cmd == "pass":
        st.review_answer(r["question_key"], name, passed=True)
        print("통과시켰다. 다음 스냅샷부터 첫 화면의 예시 질문으로 나온다")
        return 0
    if cmd == "drop":
        st.review_answer(r["question_key"], name, passed=False)
        print("지웠다")
        return 0
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
