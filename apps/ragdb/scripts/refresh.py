# -*- coding: utf-8 -*-
"""수집 배치와 색인 배치를 한 번에 (명세 2.1). 새 판이 없으면 아무것도 하지 않는다.

    .venv\\Scripts\\python scripts\\refresh.py            받기 → 조각 → 색인
    .venv\\Scripts\\python scripts\\refresh.py --force    판이 같아도 다시

색인(bm25s, kiwipiepy)이 .venv 에만 있으므로 .venv 의 python 으로 돌린다.
"""
import argparse
import os
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))


def run(name, *args):
    return subprocess.run([sys.executable, os.path.join(HERE, name), *args]).returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    got = run("fetch_docs.py", *(["--force"] if a.force else []))
    if got == 10:
        return 0
    if got != 0:
        return got
    for step in ("chunk.py", "build_index.py"):
        rc = run(step)
        if rc != 0:
            print("%s 가 실패했다 (%d). 색인은 직전 판 그대로다" % (step, rc))
            return rc
    return 0


if __name__ == "__main__":
    sys.exit(main())
