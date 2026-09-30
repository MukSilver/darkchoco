# -*- coding: utf-8 -*-
"""평가 질문을 파일로 받아 고치고 다시 올린다 (설계서 「검증」).

    python scripts/question_set.py                  지금 평가 질문이 몇 문항인지
    python scripts/question_set.py pull 파일.json    저장소의 평가 질문을 파일로 받는다
    python scripts/question_set.py push 파일.json    파일의 평가 질문으로 통째로 바꾼다

평가 질문은 운영 기록 저장소(Supabase 의 rag.questions)에 있다. 파일 모양은 app/questions.py 맨 위에 적혀 있다.
파일은 깃허브 저장소 밖에 둔다. 반출하지 않는 줄의 이름이 들어 있다.
올린 뒤에는 scripts/evaluate.py 로 다시 재고, scripts/prepare_answers.py 로 사전 답변을 다시 만든다.
"""
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app import questions, store          # noqa: E402


def inside_repo(path):
    """깃허브 저장소 안의 자리인가. data/ 아래는 저장소에 올라가지 않으므로 괜찮다."""
    p = os.path.abspath(path)
    repo = os.path.dirname(os.path.dirname(ROOT))
    data = os.path.join(ROOT, "data")
    return p.startswith(repo + os.sep) and not p.startswith(data + os.sep)


def main():
    st = store.connect()
    args = sys.argv[1:]
    if not args:
        qs = questions.load(st)
        print("평가 질문 %d문항 (답 없음이 정답인 것 %d)" % (len(qs), sum(1 for q in qs if q["none"])))
        return 0
    if len(args) != 2 or args[0] not in ("pull", "push"):
        print(__doc__)
        return 1
    cmd, path = args
    if inside_repo(path):
        print("깃허브 저장소 안에는 두지 않는다. data/ 아래나 저장소 밖의 자리를 준다")
        return 1
    if cmd == "pull":
        qs = questions.load(st)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"questions": qs}, f, ensure_ascii=False, indent=1)
        print("받았다: %d문항" % len(qs))
        return 0
    qs = questions.from_file(path)
    if not qs:
        print("파일에 문항이 없다. 올리지 않았다")
        return 1
    ids = [q["id"] for q in qs]
    if len(set(ids)) != len(ids):
        print("번호(id)가 겹친다. 올리지 않았다")
        return 1
    st.replace_questions(qs)
    print("올렸다: %d문항" % len(qs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
