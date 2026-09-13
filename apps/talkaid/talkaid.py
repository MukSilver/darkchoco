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
화면 글자는 Win+Shift+S 로 캡처해 「텍스트 작업」으로 복사한 뒤 Ctrl+Alt+2 를 누른다.

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
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402
import guard as G  # noqa: E402

LLM = "qwen1.7b"

# **TEMP 에 두지 않는다.** 이 PC 에서 tempfile.gettempdir() 이
# C:\Users\Public\Documents\ESTsoft\CreatorTemp 였다 — 압축 프로그램이 TMP 를
# 바꿔 놓은 것인데 거기는 **다른 사용자도 읽는 자리**다. 로그에는 옮긴 말이 남는다.
# guard 가 쓰는 설정 자리와 같은 곳에 둔다. 홈 밑이라 남이 못 본다
로그파일 = G.CONF / "talkaid.log"


def 출력자리_만들기() -> None:
    """pythonw 로 띄우면 stdout·stderr 가 None 이다. 그대로 두면 `print` 한 줄에
    프로그램이 죽고 **창이 뜨기 전에 난 탈은 아무 데도 안 남는다.**

    파일로 돌려 둔다. 창이 뜨면 ui 가 이것을 감싸서 화면 로그에도 같이 보낸다.
    """
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        로그파일.parent.mkdir(parents=True, exist_ok=True)
        f = open(로그파일, "a", encoding="utf-8", buffering=1)
    except Exception:
        f = open(os.devnull, "w", encoding="utf-8")
    if sys.stdout is None:
        sys.stdout = f
    if sys.stderr is None:
        sys.stderr = f


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
    출력자리_만들기()
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
    # 시작 줄은 창이 출력을 가로챈 뒤에 찍어야 창 안 로그에도 남는다
    ui.창(eng, 상용구).돌린다(
        시작말="[시작] talkaid · %s · 로그도 %s 에 쌓인다"
               % ("기계번역" if getattr(a, "기계번역") else "LLM", 로그파일))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
