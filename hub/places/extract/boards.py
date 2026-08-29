"""첫 화면에 걸린 게시판 이름을 읽습니다.

포럼이 스스로 붙인 게시판 이름은 그 곳이 무엇을 다루는지에 대한 가장
좋은 증거입니다. 우리가 추측하는 것이 아니라 그 쪽이 적어 둔 것입니다.

    Leaks · Databases        최초 유출
    Combolists · Requests    재배포
    Marketplace · Shop       되팔이
    Tutorials · Cracking     수법 공유

**게시글 제목은 안 읽습니다.** 유출 게시물 제목에는 피해 기업 이름이
들어갑니다(SECURITY.md). 게시판 이름은 그 곳의 구조이지 사건이 아닙니다.

**로그인 안 합니다.** 첫 화면에 보이는 것만 봅니다. 로그인 뒤와 게시판
순회는 apps/forum-crawler 가 하는 일입니다.

표준 라이브러리만 씁니다.
"""

from __future__ import annotations

import html
import re

__all__ = ["게시판이름들", "유통자리", "개인정보증거"]

# 게시판을 가리키는 링크 꼴입니다. 포럼 소프트웨어마다 다릅니다.
#   MyBB        forumdisplay.php?fid=3
#   XenForo     /forums/general.3/
#   phpBB       viewforum.php?f=3
#   vBulletin   forumdisplay.php?f=3
#   Discourse   /c/general/5
#   Flarum      /t/  (글이라 안 씁니다)
_게시판링크 = re.compile(
    r'<a[^>]+href="([^"]*(?:forumdisplay|viewforum|/forums?/|/board/|'
    r'/c/|\bfid=|\bf=)[^"]*)"[^>]*>(.{2,90}?)</a>', re.S | re.I)

# nav · 사이드 메뉴 안의 링크도 봅니다. 게시판 목록이 거기 있는 판도 있습니다.
_nav안 = re.compile(r"<nav\b.*?</nav>", re.S | re.I)
_a = re.compile(r"<a[^>]*>(.{2,90}?)</a>", re.S | re.I)

# 게시판 이름이 아닌 것들입니다. 어느 포럼에나 있습니다.
_아닌것 = {
    "home", "forum", "forums", "index", "search", "login", "log in",
    "register", "sign up", "sign in", "logout", "members", "help",
    "faq", "rules", "contact", "about", "portal", "calendar", "chat",
    "profile", "settings", "upgrade", "donate", "shop", "store",
    "mark all read", "today's posts", "new posts", "what's new",
    "홈", "로그인", "회원가입", "검색", "도움말", "공지",
}


def _글자(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def 게시판이름들(본문: str, 최대: int = 40) -> list[str]:
    """첫 화면에 걸린 게시판 이름들. 못 찾으면 빈 목록입니다."""
    나온것: list[str] = []

    def 담기(글: str) -> None:
        글 = _글자(글)
        if not (2 <= len(글) <= 46):
            return
        if 글.lower() in _아닌것:
            return
        if 글.isdigit():
            return
        if 글 not in 나온것:
            나온것.append(글)

    for m in _게시판링크.finditer(본문 or ""):
        담기(m.group(2))
        if len(나온것) >= 최대:
            return 나온것

    for nav in _nav안.finditer(본문 or ""):
        for m in _a.finditer(nav.group(0)):
            담기(m.group(1))
            if len(나온것) >= 최대:
                return 나온것
    return 나온것


# 게시판 이름 → 노션 「유통 자리」 선택지.
# 선택지는 최초 유출 · 재배포 · 되팔이 · 수법 공유 · 해당 없음 · 모름 ·
# 미기입 뿐입니다. 없는 값을 만들면 안 됩니다.
#
# 낱말은 좁게 잡습니다. "market" 하나로 되팔이라고 하면 "Marketing" 게시판도
# 걸립니다. 그래서 앞뒤를 붙여 봅니다.
_자리 = [
    ("최초 유출", (
        "leak", "leaks", "leaked", "breach", "breaches", "database",
        "databases", "db leak", "dumps", "data dump", "유출", "디비")),
    ("재배포", (
        "combo", "combolist", "combolists", "reupload", "re-upload",
        "mirror", "request", "requests", "sharing", "share", "공유")),
    ("되팔이", (
        "marketplace", "market place", "buy", "sell", "selling", "vendor",
        "vendors", "shop section", "for sale", "auction", "trade",
        "판매", "거래")),
    ("수법 공유", (
        "tutorial", "tutorials", "guide", "guides", "cracking", "crack",
        "method", "methods", "how to", "howto", "course", "courses",
        "tool", "tools", "config", "configs", "강좌", "수법")),
]


def 유통자리(이름들: list[str]) -> list[str]:
    """게시판 이름에서 「유통 자리」 를 고릅니다.

    **못 찾으면 빈 목록입니다.** 「모름」 을 안 씁니다. 269줄이 전부
    「모름」 이 되면 그 칸이 아무것도 말하지 못합니다.
    """
    나온것: list[str] = []
    낱말들 = [n.lower() for n in 이름들]
    for 값, 조각들 in _자리:
        for 이름 in 낱말들:
            if any(조각 in 이름 for 조각 in 조각들):
                if 값 not in 나온것:
                    나온것.append(값)
                break
    return 나온것


# 「개인정보 유출」 칸의 근거가 되는 낱말입니다. 이것이 게시판 이름에
# 있으면 그 곳이 개인 신상을 다룬다고 그 쪽이 스스로 밝힌 것입니다.
_개인정보 = (
    "fullz", "ssn", "dox", "doxx", "doxbin", "combolist", "combo list",
    "database", "databases", "identity", "id card", "passport",
    "credit card", "cvv", "carding", "bank log", "banklogs",
    "personal info", "pii", "주민", "신상", "개인정보",
)


def 개인정보증거(이름들: list[str], 최대: int = 6) -> str:
    """개인 신상을 다룬다는 근거가 되는 게시판 이름들.

    **해석을 안 붙입니다.** 그 쪽이 붙인 이름을 그대로 적습니다. 그것이
    근거이고, 무엇을 뜻하는지는 사람이 판단합니다.
    """
    걸린것 = [n for n in 이름들
            if any(조각 in n.lower() for 조각 in _개인정보)]
    if not 걸린것:
        return ""
    return "게시판 이름: " + " · ".join(걸린것[:최대])
