"""게시판 이름에서 유통 자리와 개인정보 근거를 읽는지 봅니다.

포럼이 스스로 붙인 게시판 이름은 그 곳이 무엇을 다루는지에 대한 가장
좋은 증거입니다. 우리가 추측하는 것이 아니라 그 쪽이 적어 둔 것입니다.

**증거가 없으면 빈 값입니다.** 269줄이 전부 「모름」 이 되면 그 칸이
아무것도 말하지 못합니다. 지어내느니 비워 둡니다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages"))
sys.path.insert(0, str(ROOT))

from dc_console import use_utf8  # noqa: E402

use_utf8()

from hub.crawler.probe._게시판 import (  # noqa: E402
    개인정보증거, 게시판이름들, 유통자리)

# MyBB 꼴. bf.st 같은 곳이 이렇습니다.
_마이비비 = '''
<a href="forumdisplay.php?fid=3">Leaks &amp; Databases</a>
<a href="forumdisplay.php?fid=9">Combolists</a>
<a href="forumdisplay.php?fid=4">Marketplace</a>
<a href="forumdisplay.php?fid=7">Cracking Tutorials</a>
<a href="forumdisplay.php?fid=1">Announcements</a>
<a href="member.php?action=login">Login</a>
<a href="forumdisplay.php?fid=12">Fullz &amp; SSN</a>
'''


def test_게시판_이름을_읽는다():
    이름 = 게시판이름들(_마이비비)
    assert "Leaks & Databases" in 이름, 이름
    assert "Combolists" in 이름
    assert "Fullz & SSN" in 이름


def test_어디에나_있는_링크는_안_센다():
    """Login · Register · Search 는 게시판이 아닙니다."""
    이름 = 게시판이름들(_마이비비)
    낮 = [n.lower() for n in 이름]
    for 아닌것 in ("login", "register", "search", "help", "faq"):
        assert 아닌것 not in 낮, f"{아닌것} 을 게시판으로 셌다"


def test_유통_자리를_고른다():
    이름 = 게시판이름들(_마이비비)
    자리 = 유통자리(이름)
    assert set(자리) == {"최초 유출", "재배포", "되팔이", "수법 공유"}, 자리


def test_노션_선택지에_있는_값만_쓴다():
    """없는 값을 보내면 노션이 400 을 냅니다."""
    스키마 = json.loads((HERE / "노션스키마.json").read_text(encoding="utf-8"))
    있는것 = set(스키마["forum"]["선택지"]["유통 자리"])
    나오는것 = set(유통자리(게시판이름들(_마이비비)))
    assert 나오는것 <= 있는것, f"선택지에 없는 값: {나오는것 - 있는것}"
    # 세 갈래 모두에 있어야 합니다.
    for 갈래 in ("telegram", "forum", "ransom"):
        assert 나오는것 <= set(스키마[갈래]["선택지"]["유통 자리"]), 갈래


def test_증거가_없으면_비워_둔다():
    """모름 을 안 씁니다. 269줄이 전부 모름 이면 칸이 죽습니다."""
    이름 = ["Announcements", "Introductions", "Off Topic"]
    assert 유통자리(이름) == [], 유통자리(이름)
    assert 개인정보증거(이름) == ""
    assert 게시판이름들("") == []
    assert 유통자리([]) == []


def test_개인정보_근거는_그_쪽_이름_그대로_적는다():
    """해석을 안 붙입니다. 무엇을 뜻하는지는 사람이 봅니다."""
    글 = 개인정보증거(게시판이름들(_마이비비))
    assert 글.startswith("게시판 이름: "), 글
    assert "Fullz & SSN" in 글
    # 우리가 지어낸 말이 안 들어갑니다.
    for 말 in ("추정", "것으로 보입니다", "가능성"):
        assert 말 not in 글, 글


def test_게시글_제목은_안_읽는다():
    """유출 게시물 제목에는 피해 기업 이름이 들어갑니다 (SECURITY.md)."""
    본문 = ('<a href="showthread.php?tid=99">Acme Corp 500k rows leaked</a>'
          '<a href="forumdisplay.php?fid=3">Leaks</a>')
    이름 = 게시판이름들(본문)
    assert "Leaks" in 이름
    assert not any("Acme" in n for n in 이름), 이름


def test_nav_에서도_읽는다():
    """게시판 목록이 nav 안에 있는 판도 있습니다."""
    본문 = ('<nav><a href="/x">Databases</a>'
          '<a href="/y">Tutorials</a><a href="/z">Login</a></nav>')
    이름 = 게시판이름들(본문)
    assert "Databases" in 이름 and "Tutorials" in 이름
    assert "Login" not in 이름


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_"):
            v()
            print(f"  OK  {k}")
            n += 1
    print(f"\n{n}개 통과")
