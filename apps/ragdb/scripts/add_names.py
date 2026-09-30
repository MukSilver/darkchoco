# -*- coding: utf-8 -*-
"""사람이 찾은 가릴 이름을 더한다. 모델(find_names.py)이 놓친 표기를 채우는 자리다.

    python scripts/add_names.py                      손으로 더한 이름이 몇 개인지
    python scripts/add_names.py 이름 [이름 ...]        더한다
    python scripts/add_names.py --remove 이름 ...     뺀다

더한 이름은 찾아 둔 조직 표기와 같은 곳(Supabase rag.found_names 의 「_수동」 줄)에 들어간다.
피해 조직 이름 그 자체라 저장소에 넣지 않는다. 더한 뒤에는 refresh.py --local 로 다시 만들어야 가려진다.
공개 전 표본 읽기에서 찾은 것을 여기에 넣는다 (설계서 「가리기」).
"""
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import find_names as F                  # noqa: E402
from app import store                   # noqa: E402

KEY = "_수동"          # 문서가 아닌 줄. 밑줄로 시작하는 줄은 find_names.py 가 지우지 않는다


def main():
    args = [a for a in sys.argv[1:] if a != "--remove"]
    remove = "--remove" in sys.argv
    state = F.load()
    have = state["docs"].get(KEY) or {"hash": None, "names": []}
    names = list(have.get("names") or [])
    if not args:
        print("손으로 더한 이름 %d개" % len(names))
        return 0
    before = json.loads(json.dumps(state["docs"], ensure_ascii=False))
    if remove:
        names = [n for n in names if n not in args]
    else:
        names += [a.strip() for a in args if a.strip() and a.strip() not in names]
    state["docs"][KEY] = {"hash": None, "names": names}
    F.save(state)
    F.push(before, state)
    print("손으로 더한 이름 %d개. refresh.py --local 로 다시 만들어야 가려진다" % len(names))
    return 0


if __name__ == "__main__":
    sys.exit(main())
