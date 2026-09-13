#!/usr/bin/env python3
"""쓰기 전에 한 번 돌린다. 모델을 받고 실제로 도는지 본다.

    python setup.py            받고 확인한다
    python setup.py --check    받지 않고 무엇이 없는지만 본다

모델 셋을 합쳐 약 1.2GB 다. `~/.cache/huggingface` 에 들어간다.
**GPU 가 필요 없다.** CPU int8 로 문장 하나에 50~90 ms 다 (2026-09-13 실측).
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# 윈도우에서 개발자 모드가 꺼져 있으면 huggingface_hub 가 심볼릭 링크를 못 만들어
# WinError 1314 로 죽는다. 링크 대신 복사하게 한다. **import 보다 먼저 해야 한다**
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")

import engine as E  # noqa: E402


def 있나(이름: str) -> bool:
    try:
        __import__(이름)
        return True
    except ImportError:
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description="모델을 받고 도는지 본다")
    ap.add_argument("--check", action="store_true", help="받지 않고 무엇이 없는지만 본다")
    a = ap.parse_args()

    print("\n  talkaid 처음 설정\n")

    없는것 = [n for n in ("ctranslate2", "sentencepiece", "huggingface_hub") if not 있나(n)]
    for n in ("ctranslate2", "sentencepiece", "huggingface_hub"):
        print("  %-18s %s" % (n, "있다" if 있나(n) else "**없다**"))
    if 없는것:
        print("\n  먼저 깔아야 한다:\n      python -m pip install %s\n" % " ".join(없는것))
        return 1

    if sys.platform != "win32":
        print("\n  알림 — 상주 프로그램은 윈도우 전용이다. 엔진은 어디서나 돈다.")

    if a.check:
        print("\n  --check 라 여기까지만 본다.\n")
        return 0

    print("\n  모델을 받는다. 처음 한 번만 걸린다 (합쳐 약 1.2GB)\n")
    eng = E.Engine()
    실패 = []
    for pair in E.MODELS:
        print("  %-8s %-44s " % (pair, E.MODELS[pair]), end="", flush=True)
        t0 = time.perf_counter()
        try:
            eng.load(pair)
            print("됐다 (%.1f초)" % (time.perf_counter() - t0))
        except Exception as e:
            print("**실패** %s: %s" % (type(e).__name__, str(e)[:60]))
            실패.append(pair)
    if 실패:
        print("\n  못 받은 것: %s\n" % " · ".join(실패))
        return 1

    print("\n  실제로 옮겨 본다\n")
    r = eng.run("지금도 신규 어피실리에이트를 받고 있나요?", "ko-en")
    print("     한국어  지금도 신규 어피실리에이트를 받고 있나요?")
    print("     영어    %s" % r.text)
    print("     역번역  %s" % r.back)
    print("     %.0f ms" % r.ms)

    if "affiliate" not in r.text.lower():
        print("\n  **용어 치환이 안 먹었다.** terms.json 을 확인한다.")
        return 1

    print("\n  됐다. 이제 `python talkaid.py` 로 띄워 두면 된다.")
    print("  나가면 안 되는 말 목록을 두려면 ~/.config/darkchoco/talkaid_block 을 만든다.")
    print("  화면 글자를 옮기려면 PowerToys 의 Text Extractor (Win+Shift+T) 를 켠다.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
