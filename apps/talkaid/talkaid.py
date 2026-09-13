#!/usr/bin/env python3
"""창을 띄운다. 윈도우 전용.

    python talkaid.py                     창을 띄운다. 이것이 보통 쓰는 법
    python talkaid.py --기계번역           LLM 대신 빠른 기계번역으로 (52ms)
    python talkaid.py --once ko-en        창 없이 클립보드를 한 번만 옮긴다 (시험용)

    Ctrl+Alt+1   고른 한국어 → 영어.  보낼 말. 역번역과 관문이 같이 돈다
    Ctrl+Alt+2   고른 외국어 → 한국어.  읽을 말
    Ctrl+Alt+3   준비해 둔 것 (사이드바) 열고 닫기

쓰는 법은 어디서나 같다. **글을 고르고 Ctrl+C · 단축키 · Ctrl+V.**
텔레그램·메일·Tox·Tor 브라우저가 다 시스템 클립보드를 쓰므로 넷 다 그대로 된다.
화면 글자는 PowerToys 의 Win+Shift+T 로 클립보드에 넣고 Ctrl+Alt+2 를 누르면 된다.

## 안 하는 것

**보내지 않는다.** 클립보드에 놓기만 하고 붙여넣는 것도 보내는 것도 사람이 한다.
팀 규칙이 「AI 가 문안을 정해 바로 달지 않는다」이고, 전송 경로를 안 만들면
도구가 실수로 보낼 길이 아예 없다.

**밖으로 요청을 보내지 않는다.** 번역은 이 PC 안에서만 돈다.
모델을 처음 받을 때만 huggingface.co 에 붙는다.

## 두 경로

    기본     로컬 LLM Qwen3-1.7B.  짧은 문장 1.4~2.2초.  **기계번역보다 뜻이 정확하다**
    --기계번역  OPUS-MT.  52ms.  **GPU 도 큰 모델도 없는 PC 를 위한 안전망**

둘 다 CPU 다. GPU 가 필요 없다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402
import guard as G  # noqa: E402

LLM = "qwen1.7b"


def 규칙() -> tuple[list, dict]:
    """바꿔 쓰기는 **사본을 두지 않는다.** 스킬과 같은 파일을 본다.
    2026-09-02 에 같은 도구가 세 벌이라 24개 중 13개가 갈렸던 일이 있다.
    """
    swaps = []
    for p in (HERE / "en_style.json",
              HERE.parents[1] / "skills" / "skills" / "darkweb-verify-ko"
              / "tools" / "en_style.json"):
        if p.exists():
            swaps = json.loads(p.read_text(encoding="utf-8")).get("바꿔 쓰기", [])
            break
    상용구 = {}
    p = HERE / "snippets.json"
    if p.exists():
        상용구 = json.loads(p.read_text(encoding="utf-8")).get("상용구", {})
    return swaps, 상용구


def 한번(eng: E.Engine, pair: str) -> int:
    """창 없이 클립보드를 한 번만 옮긴다. 시험과 자동화용."""
    import win as W
    src = W.클립보드_읽기().strip()
    if not src:
        print("  클립보드가 비었다.")
        return 1
    if pair == "auto":
        pair = {"zh": "zh-ko", "en": "en-ko"}.get(E.detect_lang(src), "ko-en")
    보낼말 = pair == "ko-en"
    r = eng.run(src, pair, back=보낼말)
    print("\n%s" % r.text)
    if r.back:
        print("\n  역번역  %s" % r.back)
    print("  %.1f초" % (r.ms / 1000))
    if 보낼말:
        v = G.check(r.text)
        if v.막힘:
            print("\n  **클립보드에 안 넣었다** — %s" % v.말.replace("\n", " / "))
            return 1
        if v.경고 or v.못봄:
            print("  %s" % v.말.replace("\n", " / "))
    print("  클립보드에 넣었다." if W.클립보드_쓰기(r.text) else "  클립보드에 못 넣었다.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="클립보드를 옮긴다. 밖으로 요청을 안 보낸다")
    ap.add_argument("--기계번역", action="store_true",
                    help="LLM 대신 OPUS-MT. 빠르지만 뜻이 덜 정확하다")
    ap.add_argument("--once", choices=["ko-en", "en-ko", "zh-ko", "auto"],
                    help="창 없이 클립보드를 한 번만 옮긴다")
    ap.add_argument("--threads", type=int, default=8)
    a = ap.parse_args()

    if sys.platform != "win32":
        raise SystemExit("윈도우 전용이다. 클립보드와 단축키가 Win32 API 다.")

    swaps, 상용구 = 규칙()
    eng = E.Engine(threads=a.threads, swaps=swaps,
                   llm=None if getattr(a, "기계번역") else LLM)

    if a.once:
        return 한번(eng, a.once)

    import ui
    ui.창(eng, 상용구).돌린다()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
