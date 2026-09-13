#!/usr/bin/env python3
"""윈도우에만 있는 것들. 클립보드 · 전역 단축키 · 화면 배율.

    from win import 클립보드_읽기, 클립보드_쓰기, 단축키, dpi_켜기

**표준 라이브러리만 쓴다.** `ctypes` 로 Win32 를 직접 부른다.
`pyperclip` 도 `pynput` 도 안 쓴다.

## 왜 RegisterHotKey 인가

`pynput` 이나 `keyboard` 는 저수준 키보드 훅(`WH_KEYBOARD_LL`)이라 **모든 키 입력을
가로챈다.** 보안 팀이 쓰는 PC 에서 백신이 키로거로 볼 여지가 있고, 애초에 필요 이상의
권한이다. `RegisterHotKey` 는 정해진 조합만 등록하고, 다른 프로그램이 이미 쓰고 있으면
등록이 실패해 그 사실을 반환값으로 알려 준다.

## 단축키는 왜 딴 실 (thread) 인가

`RegisterHotKey(None, ...)` 는 **부른 실의 메시지 큐**로 `WM_HOTKEY` 를 보낸다.
tkinter 는 자기 루프를 돌리므로 같은 실에서 `GetMessage` 를 돌릴 수 없다.
그래서 단축키만 딴 실에 두고, 눌리면 부름말(callback)로 알린다.
**부름말은 그 딴 실에서 불린다.** tkinter 는 실 안전하지 않으므로 받는 쪽에서
큐에 넣고 `after()` 로 꺼내야 한다.
"""
from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_NOREPEAT = 0x0001, 0x0002, 0x0004, 0x4000
WM_HOTKEY, WM_QUIT = 0x0312, 0x0012

kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalLock.restype = wintypes.LPVOID
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
user32.GetClipboardData.restype = wintypes.HANDLE
user32.SetClipboardData.restype = wintypes.HANDLE
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]


# ── 클립보드 ─────────────────────────────────────
def _열기() -> bool:
    """다른 프로그램이 잡고 있으면 실패한다. 몇 번 다시 해 본다."""
    for _ in range(5):
        if user32.OpenClipboard(None):
            return True
        kernel32.Sleep(30)
    return False


def 클립보드_읽기() -> str:
    """못 읽으면 빈 글을 낸다."""
    if not _열기():
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
    if not _열기():
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
        # 성공하면 소유권이 넘어간다. 우리가 풀지 않는다
        return bool(user32.SetClipboardData(CF_UNICODETEXT, h))
    finally:
        user32.CloseClipboard()


# ── 화면 배율 ────────────────────────────────────
def dpi_켜기() -> str:
    """고해상도 화면에서 글씨가 흐려지는 것을 막는다.

    안 하면 윈도우가 창을 늘려서 보여 주므로 글씨가 뭉갠다.
    CPython 이슈 #119459 에 「HiDPI 에서 tkinter 쓰는 모든 창이 흐리다」가 열려 있다.
    **창을 만들기 전에 불러야 한다.**
    """
    try:  # Per-Monitor v2. 윈도우 10 1703 이상
        ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)
        return "Per-Monitor v2"
    except Exception:
        pass
    try:  # 그 전 판
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return "Per-Monitor"
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
        return "System"
    except Exception:
        return "못 켬"


# ── 전역 단축키 ──────────────────────────────────
class 단축키:
    """딴 실에서 전역 단축키를 잡는다.

        키 = 단축키({1: ("ctrl+alt", ord("1")), 2: ("ctrl+alt", ord("2"))})
        못잡은것 = 키.켜기(눌림)      # 눌림(hid) 이 **딴 실에서** 불린다
        ...
        키.끄기()

    **눌림은 tkinter 를 직접 건드리면 안 된다.** 큐에 넣고 after() 로 꺼낸다.
    """

    수식 = {"ctrl": MOD_CONTROL, "alt": MOD_ALT, "shift": MOD_SHIFT}

    def __init__(self, 키들: dict[int, tuple[str, int]]):
        self.키들 = 키들
        self._실: threading.Thread | None = None
        self._실id = 0
        self._준비 = threading.Event()
        self.못잡은것: list[int] = []

    def _돈다(self, 눌림):
        self._실id = kernel32.GetCurrentThreadId()
        잡은것 = []
        for hid, (수식들, vk) in self.키들.items():
            m = MOD_NOREPEAT
            for w in 수식들.split("+"):
                m |= self.수식.get(w.strip().lower(), 0)
            if user32.RegisterHotKey(None, hid, m, vk):
                잡은것.append(hid)
            else:
                self.못잡은것.append(hid)
        self._준비.set()
        if not 잡은것:
            return
        msg = wintypes.MSG()
        try:
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY:
                    try:
                        눌림(int(msg.wParam))
                    except Exception:
                        pass  # 부름말이 죽어도 단축키는 계속 돈다
        finally:
            for hid in 잡은것:
                user32.UnregisterHotKey(None, hid)

    def 켜기(self, 눌림) -> list[int]:
        """못 잡은 단축키 번호를 낸다. 빈 목록이면 다 잡았다."""
        self._실 = threading.Thread(target=self._돈다, args=(눌림,), daemon=True)
        self._실.start()
        self._준비.wait(timeout=3)
        return list(self.못잡은것)

    def 끄기(self) -> None:
        if self._실id:
            user32.PostThreadMessageW(self._실id, WM_QUIT, 0, 0)
            self._실id = 0
