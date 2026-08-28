"""포럼 명부를 조사합니다.

무엇을 알아내나 — 지금 살아있나, 회원과 게시물이 몇인가.

**가벼운 확인만 합니다.** 로그인이나 게시판 순회는 여기서 안 합니다.
그것은 apps/forum-crawler 가 도커 안에서 하는 일이고, 사람이 챌린지를
풀어야 해서 자주 돌릴 수 없습니다.

명부의 `상태` 와 `규모` 는 자주 봐야 하는데, 그것만 보는 데는 첫 화면
하나면 됩니다. 그래서 둘로 나눕니다.

    가벼운 확인 (여기)      자주. 첫 화면만. 상태 · 회원수 · 게시물수
    깊은 조사 (forum-crawler) 가끔. 도커 · 로그인 · 게시판 구조

어니언 주소는 Tor 를 거쳐야 합니다. TOR_SOCKS_PROXY 가 없으면 그 줄은
"못 봄(Tor 없음)" 으로 남깁니다. 빈칸으로 두지 않습니다.

표준 라이브러리만 씁니다. Tor 는 SOCKS 프록시 주소만 받습니다.
"""

from __future__ import annotations

import html
import re
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterator
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "packages"))

from hub.crawler.place import Place, 지금  # noqa: E402

__all__ = ["조사", "한곳", "NEEDS_PACKAGES"]

NEEDS_PACKAGES: list[str] = []

간격 = 3.0
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# 포럼 소프트웨어마다 첫 화면에 적는 꼴이 다릅니다. 흔한 것부터 봅니다.
# XenForo · MyBB · vBulletin · phpBB 를 덮습니다.
_회원 = [
    re.compile(r'(?:members|Members|회원)[^\d<]{0,20}([\d,\.\s]{2,15})', re.I),
    re.compile(r'([\d,\.\s]{2,15})[^\d<]{0,12}(?:members|registered users)', re.I),
]
_게시물 = [
    re.compile(r'(?:messages|posts|Posts|게시물)[^\d<]{0,20}([\d,\.\s]{2,15})', re.I),
    re.compile(r'([\d,\.\s]{2,15})[^\d<]{0,12}(?:messages|posts)', re.I),
]
_제목 = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)


def _숫자(s: str) -> int | None:
    s = re.sub(r"[^\d]", "", s or "")
    if not s or len(s) > 12:
        return None
    n = int(s)
    return n if 10 <= n < 10_000_000_000 else None


def _찾기(본문: str, 규칙들) -> int | None:
    for rx in 규칙들:
        m = rx.search(본문)
        if m:
            n = _숫자(m.group(1))
            if n:
                return n
    return None


def _오프너(프록시: str | None):
    """Tor SOCKS 프록시를 거치는 오프너. 없으면 그냥 엽니다.

    socks 라이브러리를 안 씁니다. 받을 것을 늘리지 않으려는 것입니다.
    프록시가 필요하면 HTTP CONNECT 를 지원하는 tor 의 HTTPTunnelPort 를
    쓰거나, 프록시 주소를 http:// 로 줍니다.
    """
    if not 프록시:
        return urllib.request.build_opener()
    if 프록시.startswith("socks"):
        # SOCKS 는 표준 라이브러리로 못 탑니다. 쓰는 쪽에 알려 줍니다.
        return None
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": 프록시, "https": 프록시}))


def 한곳(주소: str, 이름: str, 마지막: list[float], *,
        프록시: str | None = None) -> Place:
    """포럼 한 곳의 첫 화면만 봅니다."""
    p = Place(갈래="forum", 이름=이름, 확인일=지금(),
              출처=["직접 확인"], 받은곳="첫 화면 확인")

    host = urlparse(주소).hostname or ""
    어니언 = host.endswith(".onion")
    if 어니언:
        p.어니언 = 주소
    else:
        p.주소 = 주소

    if 어니언 and not 프록시:
        p.못본이유 = "Tor 가 없습니다. TOR_SOCKS_PROXY 를 주면 봅니다"
        return p

    opener = _오프너(프록시 if 어니언 else None)
    if opener is None:
        p.못본이유 = ("SOCKS 프록시는 표준 라이브러리로 못 탑니다. "
                   "tor 의 HTTPTunnelPort 주소를 주십시오")
        return p

    지난 = time.time() - 마지막[0]
    if 지난 < 간격:
        time.sleep(간격 - 지난)

    req = urllib.request.Request(주소, headers={
        "User-Agent": UA, "Accept": "text/html", "Accept-Language": "en"})
    try:
        with opener.open(req, timeout=30) as r:
            code = r.status
            본문 = r.read(1_500_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        code, 본문 = e.code, ""
    except (urllib.error.URLError, socket.timeout, OSError) as e:
        p.상태 = "offline"
        p.못본이유 = f"안 열립니다: {type(e).__name__}"
        return p
    finally:
        마지막[0] = time.time()

    if code >= 500:
        p.상태 = "offline"
        p.못본이유 = f"HTTP {code}"
        return p
    if code >= 400:
        # 403 은 클라우드플레어 검사일 수 있습니다. 죽은 것과 다릅니다.
        p.상태 = "미확인"
        p.못본이유 = (f"HTTP {code}. 앞단 검사에 막혔을 수 있습니다. "
                   "깊은 조사는 forum-crawler 로 합니다")
        return p

    p.상태 = "online"
    m = _제목.search(본문)
    if m:
        제목 = re.sub(r"\s+", " ", html.unescape(m.group(1))).strip()
        if 제목 and not p.이름:
            p.이름 = 제목[:80]

    p.회원수 = _찾기(본문, _회원)
    p.게시물수 = _찾기(본문, _게시물)
    if p.회원수 is None and p.게시물수 is None:
        p.못본이유 = "살아있는 것은 봤는데 회원·게시물 수는 첫 화면에 없습니다"
    if "cf-browser-verification" in 본문 or "Just a moment" in 본문:
        p.못본이유 = "클라우드플레어 검사 화면입니다. 깊은 조사가 필요합니다"
    return p


def 조사(대상: list[dict], *, dry: bool = False, limit: int = 0,
        프록시: str | None = None) -> Iterator[Place]:
    """대상은 [{"이름": ..., "주소": ...}, ...] 입니다."""
    if dry or not 대상:
        return
    마지막 = [0.0]
    for i, d in enumerate(대상):
        if limit and i >= limit:
            return
        주소 = (d.get("주소") or d.get("url") or "").strip()
        if not 주소:
            continue
        yield 한곳(주소, (d.get("이름") or d.get("name") or "").strip(),
                  마지막, 프록시=프록시)
