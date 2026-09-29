"""살아 있는 포럼 첫 화면의 글 제목 때문에 압수 · 파킹 · 검사로 오판하지 않는가 — 시험.

    python packages/tests/test_첫화면오판.py          CI 가 이렇게 돌린다

2026-09-29 인계 H-0 검토. 포럼 조사기(hub/places/probe/forum.py)는 첫 화면 글자 전체에 압수 · 파킹 · 검사
정규식을 걸었다. 게시판 첫 화면에는 최근 글 제목이 뜨므로, 제목에 「domain has been seized」 · 「just a moment」
가 있으면 살아 있는 포럼이 미확인(파킹 꼴이면 offline)이 됐다. #102 는 이 내림을 늦출 뿐 막지 못한다.

**밖에 안 나간다.** 오프너를 갈아 끼워 본문만 바꾼다. 포럼 이름 · 글 제목 · 주소는 지어낸 것이다.
**실행부를 둔다.** CI 는 이 폴더를 `python 파일` 로 돌린다.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packages"))

from hub.places.probe import forum  # noqa: E402


def _한판(본문: str, code: int = 200):
    class 응답:
        status = code
        url = "https://f.example.test/"

        def read(self, n):
            return 본문.encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class 오프너:
        def open(self, req, timeout=0):
            return 응답()

    옛 = forum.오프너
    forum.오프너 = lambda 프록시=None, 갈래="": 오프너()
    try:
        return forum.한곳("https://f.example.test/", "지어낸포럼", [0.0])
    finally:
        forum.오프너 = 옛


# MyBB 꼴 게시판 목록 넷. 살아 있는 포럼 첫 화면이다
게시판 = "".join(
    f'<a href="forumdisplay.php?fid={i}">{이름}</a>'
    for i, 이름 in enumerate(["Databases", "Combolists", "Marketplace", "Tutorials"], 1))


def _포럼(최근글: str, 쪽제목: str = "Fake Forum") -> str:
    return (f"<html><head><title>{쪽제목}</title></head><body>{게시판}"
            f'<div class="latest"><a href="showthread.php?tid=9">{최근글}</a></div>'
            "Members: 12,000 Posts: 50,000</body></html>")


def test_최근_글_제목에_압수_문구가_있어도_살아_있다():
    p = _한판(_포럼("News: domain has been seized by the FBI — what now?"))
    assert p.상태 == "online", (p.상태, p.못본이유)
    assert not p.못본이유


def test_최근_글_제목에_just_a_moment_가_있어도_살아_있다():
    p = _한판(_포럼("Just a moment... new dump incoming"))
    assert p.상태 == "online", (p.상태, p.못본이유)


def test_최근_글_제목에_도메인_판매가_있어도_살아_있다():
    p = _한판(_포럼("[WTS] premium domain for sale, cheap"))
    assert p.상태 == "online", (p.상태, p.못본이유)


def test_게시판이_있어도_쪽_제목이_압수면_압수다():
    p = _한판(_포럼("anything", 쪽제목="THIS DOMAIN HAS BEEN SEIZED"))
    assert p.상태 == "미확인" and "압수" in p.못본이유, (p.상태, p.못본이유)


def test_게시판이_없는_압수_배너는_그대로_압수다():
    p = _한판("<html><body>THIS HIDDEN SITE HAS BEEN SEIZED by the Federal Bureau of "
             "Investigation</body></html>")
    assert p.상태 == "미확인" and "압수" in p.못본이유, (p.상태, p.못본이유)


def test_게시판이_없는_검사_화면은_그대로_검사다():
    p = _한판("<html><head><title>Just a moment...</title></head><body>"
             "Checking your browser</body></html>")
    assert p.상태 == "미확인" and "뒤에 있습니다" in p.못본이유, (p.상태, p.못본이유)


def test_게시판이_둘뿐이면_예전처럼_문구로_본다():
    둘 = ('<a href="forumdisplay.php?fid=1">Databases</a>'
          '<a href="forumdisplay.php?fid=2">Combolists</a>')
    p = _한판(f"<html><body>{둘} Buy this domain. The owner is offering it for sale.</body></html>")
    assert p.상태 == "offline", (p.상태, p.못본이유)


def test_살아_있는_포럼의_로그인_벽은_그대로_읽는다():
    p = _한판(_포럼("You must be registered to view this. domain has been seized"))
    assert p.상태 == "online" and p.가입필요 is True, (p.상태, p.가입필요)


if __name__ == "__main__":
    시험들 = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    실패 = 0
    for 이름, f in 시험들:
        try:
            f()
            print("  OK  %s" % 이름)
        except Exception as e:  # noqa: BLE001
            실패 += 1
            print("  !!  %s — %s: %s" % (이름, type(e).__name__, e))
    print("\n%d개 중 %d개 실패" % (len(시험들), 실패))
    sys.exit(1 if 실패 else 0)
