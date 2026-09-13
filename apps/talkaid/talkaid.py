#!/usr/bin/env python3
"""상주하면서 전역 단축키로 클립보드를 옮긴다. 윈도우 전용.

    python talkaid.py                한 번 띄워 두고 계속 쓴다
    python talkaid.py --once ko-en   단축키 없이 클립보드를 한 번만 옮긴다 (시험용)

    Ctrl+Alt+1   고른 한국어 → 영어.  보낼 말. 역번역과 검사가 같이 돈다
    Ctrl+Alt+2   고른 외국어 → 한국어.  읽을 말. 영어·중국어를 알아서 가른다
    Ctrl+Alt+3   상용구 목록

쓰는 법은 어디서나 같다. **글을 고르고 Ctrl+C · 단축키 · Ctrl+V.**
텔레그램·메일·Tox·Tor 브라우저가 다 시스템 클립보드를 쓰므로 넷 다 그대로 된다.
화면 글자는 PowerToys 의 Win+Shift+T 로 클립보드에 넣고 Ctrl+Alt+2 를 누르면 된다.

## 안 하는 것

**보내지 않는다.** 클립보드에 놓기만 하고 붙여넣는 것도 보내는 것도 사람이 한다.
팀 규칙이 「AI 가 문안을 정해 바로 달지 않는다」이고, 전송 경로를 안 만들면
도구가 실수로 보낼 길이 아예 없다.

**붙여넣기를 대신 하지 않는다.** SendInput 으로 Ctrl+V 를 쏘면 엉뚱한 창에 붙는다.

**밖으로 요청을 보내지 않는다.** 번역은 이 PC 안에서만 돈다.

## 왜 RegisterHotKey 인가

`pynput` 이나 `keyboard` 는 저수준 키보드 훅이라 **모든 키 입력을 가로챈다.**
보안 팀이 쓰는 PC 에서 백신이 키로거로 볼 여지가 있고 애초에 필요 이상의 권한이다.
`RegisterHotKey` 는 정해진 조합만 등록하고, 다른 프로그램이 이미 쓰고 있으면
등록이 실패해 그 사실을 알려 준다.

## 창을 띄워 두는 것이 설계다

**역번역을 사람이 반드시 봐야 한다.** 기계번역은 스무 문장 중 넷의 뜻이 틀린다.
창이 보여야 그것을 본다. 트레이로 숨기지 않는다.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import sys
from ctypes import wintypes
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402
import guard as G  # noqa: E402

# ── 윈도우 API ───────────────────────────────────
user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
MOD_ALT, MOD_CONTROL, MOD_NOREPEAT = 0x0001, 0x0002, 0x4000
WM_HOTKEY = 0x0312

kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalLock.restype = wintypes.LPVOID
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
user32.GetClipboardData.restype = wintypes.HANDLE
user32.SetClipboardData.restype = wintypes.HANDLE
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]


def 클립보드_읽기() -> str:
    """못 읽으면 빈 글을 낸다. 다른 프로그램이 잡고 있으면 실패할 수 있다."""
    for _ in range(5):
        if user32.OpenClipboard(None):
            break
        ctypes.windll.kernel32.Sleep(30)
    else:
        return ""
    try:
        h = user32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return ""
        p = kernel32.GlobalLock(h)
        if not p:
            return ""
        try:
            return ctypes.c_wchar_p(p).value or ""
        finally:
            kernel32.GlobalUnlock(h)
    finally:
        user32.CloseClipboard()


def 클립보드_쓰기(text: str) -> bool:
    for _ in range(5):
        if user32.OpenClipboard(None):
            break
        ctypes.windll.kernel32.Sleep(30)
    else:
        return False
    try:
        user32.EmptyClipboard()
        buf = ctypes.create_unicode_buffer(text)
        n = ctypes.sizeof(buf)
        h = kernel32.GlobalAlloc(GMEM_MOVEABLE, n)
        if not h:
            return False
        p = kernel32.GlobalLock(h)
        ctypes.memmove(p, buf, n)
        kernel32.GlobalUnlock(h)
        # 성공하면 소유권이 넘어가므로 우리가 풀지 않는다
        return bool(user32.SetClipboardData(CF_UNICODETEXT, h))
    finally:
        user32.CloseClipboard()


# ── 화면 ─────────────────────────────────────────
줄 = "─" * 66


def 낸다(제목: str, r, v) -> None:
    print("\n" + 줄)
    print("  %s   (%.0f ms)" % (제목, r.ms))
    print(줄)
    print(r.text)
    if r.back:
        print("\n  ── 역번역 (뜻이 살았는지 본다) " + "─" * 30)
        print("  " + r.back)
    if r.terms:
        print("\n  용어 %s" % " · ".join(sorted(set(r.terms.values()))))
    if r.swapped:
        print("  다듬음 %s" % " · ".join(r.swapped))
    if v is not None and (v.막은것 or v.경고 or v.못봄):
        print("\n  " + v.말.replace("\n", "\n  "))
    print(줄)


def 옮긴다(pair: str, eng: "E.Engine", 검사: bool):
    src = 클립보드_읽기().strip()
    if not src:
        print("\n  클립보드가 비었다. 글을 고르고 Ctrl+C 를 먼저 누른다.")
        return
    if len(src) > 4000:
        print("\n  너무 길다 (%d자). 4000자까지만 한 번에 옮긴다." % len(src))
        return

    if pair == "auto":
        말 = E.detect_lang(src)
        pair = {"zh": "zh-ko", "en": "en-ko"}.get(말, "ko-en")

    try:
        r = eng.run(src, pair, back=검사)
    except Exception as e:
        print("\n  못 옮겼다: %s: %s" % (type(e).__name__, e))
        return

    v = G.check(r.text) if 검사 else None
    낸다({"ko-en": "한국어 → 영어  (보낼 말)"}.get(pair, "→ 한국어  (읽을 말)"), r, v)

    if v is not None and v.막힘:
        print("  **클립보드에 안 넣었다.** 위에 걸린 것을 고치고 다시 누른다.")
        return
    print("  클립보드에 넣었다." if 클립보드_쓰기(r.text) else "  클립보드에 못 넣었다.")


def 상용구():
    p = HERE / "snippets.json"
    if not p.exists():
        print("\n  snippets.json 이 없다.")
        return
    d = json.loads(p.read_text(encoding="utf-8"))
    print("\n" + 줄)
    for 갈래, 목록 in d.get("상용구", {}).items():
        print("  [%s]" % 갈래)
        for s in 목록:
            print("     %-46s %s" % (s.get("영어", ""), s.get("한국어", "")))
    print(줄)


# ── 상주 ─────────────────────────────────────────
KEYS = [
    (1, ord("1"), "Ctrl+Alt+1", "한국어 → 영어 (보낼 말)"),
    (2, ord("2"), "Ctrl+Alt+2", "외국어 → 한국어 (읽을 말)"),
    (3, ord("3"), "Ctrl+Alt+3", "상용구 목록"),
]


def 돈다(eng: "E.Engine") -> int:
    잡은것 = []
    for hid, vk, 이름, 설명 in KEYS:
        if user32.RegisterHotKey(None, hid, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, vk):
            잡은것.append(hid)
            print("  %-12s %s" % (이름, 설명))
        else:
            print("  %-12s **등록 실패.** 다른 프로그램이 이미 쓰고 있다" % 이름)
    if not 잡은것:
        print("\n  단축키를 하나도 못 잡았다. 끝낸다.")
        return 1

    print("\n  글을 고르고 Ctrl+C · 단축키 · Ctrl+V.  끝내려면 Ctrl+C 두 번 또는 창을 닫는다.")
    msg = wintypes.MSG()
    try:
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY:
                w = msg.wParam
                if w == 1:
                    옮긴다("ko-en", eng, 검사=True)
                elif w == 2:
                    옮긴다("auto", eng, 검사=False)
                elif w == 3:
                    상용구()
    except KeyboardInterrupt:
        print("\n  끝.")
    finally:
        for hid in 잡은것:
            user32.UnregisterHotKey(None, hid)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="클립보드를 옮긴다. 밖으로 요청을 안 보낸다")
    ap.add_argument("--once", choices=["ko-en", "en-ko", "zh-ko", "auto"],
                    help="단축키 없이 클립보드를 한 번만 옮긴다")
    ap.add_argument("--threads", type=int, default=8)
    a = ap.parse_args()

    if sys.platform != "win32":
        raise SystemExit("윈도우 전용이다. 단축키와 클립보드가 Win32 API 다.")

    # 바꿔 쓰기 규칙은 **사본을 두지 않는다.** 스킬과 같은 파일을 본다.
    # 2026-09-02 에 같은 도구가 세 벌이라 24개 중 13개가 갈렸던 일이 있다
    swaps = []
    for 쪽 in (HERE / "en_style.json",
               HERE.parents[1] / "skills" / "skills" / "darkweb-verify-ko"
               / "tools" / "en_style.json"):
        if 쪽.exists():
            swaps = json.loads(쪽.read_text(encoding="utf-8")).get("바꿔 쓰기", [])
            break
    else:
        print("  알림 — en_style.json 을 못 찾았다. 번역투를 안 걷는다.")

    eng = E.Engine(threads=a.threads, swaps=swaps)

    if a.once:
        옮긴다(a.once, eng, 검사=(a.once == "ko-en"))
        return 0

    print("\n  talkaid — 클립보드 번역.  **밖으로 아무것도 안 보낸다**\n")
    print("  모델을 올리는 중...", end="", flush=True)
    eng.load("ko-en")
    print(" 됐다\n")
    return 돈다(eng)


if __name__ == "__main__":
    raise SystemExit(main())
