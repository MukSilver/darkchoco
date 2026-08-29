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

**전부 Tor 를 거칩니다.** 어니언만이 아닙니다. 평범한 도메인이라도
다크웹 포럼의 쪽을 여는 일은 저쪽 로그에 우리 주소를 남기는 일입니다.
나가는 길은 egress.py 한 곳뿐이고, Tor 가 없으면 안 나갑니다.

표준 라이브러리만 씁니다.
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

from hub.places.place import Place, 덧붙임, 지금  # noqa: E402
from hub.places.egress import 보호없음, 오프너  # noqa: E402
from hub.places.extract.lang import 글자만, 언어판별  # noqa: E402
from hub.places.extract import boards, links  # noqa: E402

__all__ = ["조사", "한곳", "NEEDS_PACKAGES"]

NEEDS_PACKAGES: list[str] = []

# **같은 호스트를 연달아 칠 때만 기다립니다.**
#
# 간격은 상대 서버를 힘들게 하지 않으려는 것입니다. 그런데 포럼 명부
# 224줄이 전부 서로 다른 호스트입니다 — 겹치는 것이 하나도 없습니다.
# 서로 다른 서버 사이에 3초를 기다리면 아무도 안 도와주면서 13분을
# 씁니다. 각 서버는 우리 요청을 딱 한 번 받습니다.
#
# 그래서 간격을 호스트마다 따로 셉니다. 같은 곳을 두 번 칠 때(어니언
# 미러 확인처럼)만 기다립니다.
간격 = 3.0
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# 포럼 소프트웨어마다 총계를 적는 꼴이 다릅니다. **총계인지가 중요합니다.**
#
# 첫 화면에는 총계 말고도 숫자가 잔뜩 있습니다. bf.st 첫 화면에서 실제로
# 이런 것들이 같이 나옵니다.
#
#     873955 Total Posts        ← 총계
#     857 Threads 4584 Posts    ← 게시판 하나의 수
#     182 users active           ← 지금 접속자
#     14,829 Most Online         ← 최고 기록
#
# 예전 정규식은 이 사이에서 아무 숫자나 집어 「회원 45」를 만들었습니다.
# 실제 회원은 367,224 명입니다. 틀린 값이 사람이 조사한 규모 줄을 갈아
# 끼우기 때문에 느슨하게 잡으면 안 됩니다.
#
# 태그를 걷어낸 글에서 찾습니다. 마크업은 판마다 바뀌는데 글은 덜 바뀝니다.
# K·M·B 접미사를 값에 포함해 잡습니다. 안 그러면 24.3K 에서 24 만 잡고
# 그것을 243 으로 읽습니다.
_수 = r"[\d,\.   ]{1,18}[KkMmBb]?"

# **이름이 앞에 오는 꼴을 먼저 봅니다.**
#
# 두 꼴이 한 화면에 같이 있으면 서로 훔칩니다.
#
#     Total members: 24.3K Total posts: 1.6M
#                    ^^^^^ ^^^^^^^^^^^
#     「N Total Posts」 규칙이 24.3K 를 글 수로 읽습니다
#
# 이름이 앞에 오는 꼴(Total posts: N)이 더 확실하므로 먼저 봅니다.
# 뒤에 오는 꼴(N Total Posts)은 앞에 콜론이 없을 때만 씁니다.
_회원 = [
    re.compile(rf"Total\s+members\s*[:•·∙]\s*({_수})", re.I),        # phpBB
    re.compile(rf"(?:We (?:currently )?have)\s+({_수})\s+members", re.I),
    re.compile(rf"\bMembers\s*:\s*({_수})", re.I),                  # vBulletin
    re.compile(rf"(?<![:：])\s*({_수})\s*Total\s+Members", re.I),    # MyBB
    re.compile(rf"\bMembers\s+({_수})(?:\s|$)", re.I),               # XenForo
]
_게시물 = [
    re.compile(rf"Total\s+(?:posts|messages)\s*[:•·∙]\s*({_수})", re.I),
    re.compile(rf"total of\s+({_수})\s+posts", re.I),
    re.compile(rf"\b(?:Posts|Messages)\s*:\s*({_수})", re.I),
    re.compile(rf"(?<![:：])\s*({_수})\s*Total\s+Posts", re.I),
    re.compile(rf"\b(?:Posts|Messages)\s+({_수})(?:\s|$)", re.I),
]

# 이 말이 앞에 있으면 총계가 아닙니다. 지금 접속자거나 오늘 것이거나
# 최고 기록입니다.
_총계아님 = re.compile(
    r"(?:online|active|today|newest|most|record|staff|team|birthday|"
    r"guest|visitor|접속|오늘|최고)\D{0,24}$", re.I)

_제목 = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
_소개 = re.compile(
    r'<meta[^>]+name=."?description"?.[^>]+content="([^"]{4,400})"',
    re.S | re.I)

# 첫 화면이 포럼이 아닌 경우들입니다. 살아있는 것으로 세면 안 됩니다.
#
#   압수    수사기관 배너로 바뀐 곳. 죽은 것과 다릅니다
#   파킹    도메인이 팔려 광고 쪽이 된 곳. 이름만 같습니다
#   검사    클라우드플레어 같은 앞단 검사. 포럼은 그 뒤에 있습니다
_압수 = re.compile(
    r"this (?:hidden )?site has been seized|domain has been seized|"
    r"operation\s+\w+.{0,40}law enforcement|"
    r"이 사이트는 압수|federal bureau of investigation", re.I)
_파킹 = re.compile(
    r"buy this domain|domain (?:is )?for sale|parkingcrew|sedoparking|"
    r"이 도메인은 판매", re.I)
_검사 = re.compile(
    r"cf-browser-verification|just a moment|checking your browser|"
    r"ddos-guard|__cf_chl|attention required", re.I)

# 가입해야 안이 보이는 곳. 링크가 있는 것과 다릅니다. 「가입하세요」 링크는
# 어느 포럼에나 있습니다. 여기서는 막혔다고 **말한** 경우만 셉니다.
_로그인벽 = re.compile(
    r"you must be (?:logged in|registered)|must (?:log ?in|register) to view|"
    r"members only|login required|please log ?in to (?:view|continue)|"
    r"로그인.{0,6}(?:해야|후에).{0,10}(?:볼|이용)", re.I)


# 자리를 나누는 데 쓰는 빈칸들입니다. 좁은 빈칸(U+202F)과 안 나뉘는
# 빈칸(U+00A0)으로 "185 091" 처럼 적는 포럼이 있습니다.
_빈칸들 = "     "


def _숫자(s: str) -> tuple[int | None, bool]:
    """(수, 어림수인가) 를 돌려줍니다.

    **1.6M 을 16 으로 읽던 버그를 고쳤습니다.** 점을 그냥 지워서
    "Total posts: 1.6M" 이 16 이 되고 "24.3K" 가 243 이 됐습니다.
    실제로는 160만과 24,300 입니다. 그 값이 사람이 조사한 규모 줄을
    갈아 끼우고 있었습니다.

    K·M·B 가 붙으면 곱하고 어림수로 표시합니다. 붙은 값은 정확하지
    않으므로 규모줄() 이 「안팎」 을 붙입니다.
    """
    s = (s or "").strip()
    if not s:
        return None, False
    for c in _빈칸들:
        s = s.replace(c, "")

    m = re.fullmatch(r"([\d.,]+)\s*([KkMmBb])?", s)
    if not m:
        숫자 = re.sub(r"[^\d]", "", s)
        if not 숫자 or len(숫자) > 12:
            return None, False
        n = int(숫자)
        return (n, False) if 1 <= n < 10_000_000_000 else (None, False)

    값, 배 = m.group(1), (m.group(2) or "").upper()
    if 배:
        # 1.6M · 24.3K — 점은 소수점입니다. 지우면 안 됩니다.
        try:
            f = float(값.replace(",", ""))
        except ValueError:
            return None, False
        곱 = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[배]
        n = int(f * 곱)
        return (n, True) if 1 <= n < 10_000_000_000 else (None, False)

    # 접미사가 없으면 점과 쉼표는 자리 구분입니다.
    숫자 = re.sub(r"[^\d]", "", 값)
    if not 숫자 or len(숫자) > 12:
        return None, False
    n = int(숫자)
    return (n, False) if 1 <= n < 10_000_000_000 else (None, False)


def _제목뽑기(본문: str) -> str:
    m = _제목.search(본문 or "")
    if not m:
        return ""
    return re.sub(r"\s+", " ", html.unescape(m.group(1))).strip()


def _닮았나(가: str, 나: str) -> bool:
    """두 제목이 같은 곳의 것인가.

    글자 그대로 같기를 바라면 안 됩니다. 어니언 쪽 제목에 " - Tor" 가
    붙거나 순서가 다를 수 있습니다. 낱말을 견줍니다.
    """
    def 낱말(t):
        return {w for w in re.findall(r"[A-Za-z0-9가-힣]{3,}", (t or "").lower())
                if w not in ("the", "and", "for", "com", "www", "forum",
                             "forums", "index", "home", "page", "tor",
                             "onion", "mirror", "official")}
    a, b = 낱말(가), 낱말(나)
    if not a or not b:
        return False
    겹침 = len(a & b)
    return 겹침 >= 2 or (겹침 >= 1 and 겹침 == min(len(a), len(b)))


def 어니언확인(어니언: str, 원래제목: str, 마지막, *,
           프록시: str | None = None) -> tuple[bool, str]:
    """첫 화면에서 본 어니언이 정말 같은 곳인지 열어서 봅니다.

    (같은가, 왜) 를 돌려줍니다. **추측하지 않습니다.** 남의 어니언이
    광고로 걸려 있을 수 있어서, 열어 보고 제목을 견주는 것 말고는
    같은 곳이라고 말할 근거가 없습니다.

    Tor 가 있어야 합니다. 없으면 (False, 이유) 입니다.
    """
    if not 어니언 or not 원래제목:
        return False, "견줄 것이 없습니다"
    try:
        opener = 오프너(프록시, 갈래="forum")
    except 보호없음:
        return False, "Tor 가 없어 못 열어 봤습니다"

    _기다리기(마지막, 어니언)
    req = urllib.request.Request(
        어니언, headers={"User-Agent": UA, "Accept": "text/html"})
    try:
        with opener.open(req, timeout=45) as r:
            본문 = r.read(400_000).decode("utf-8", "replace")
    except (urllib.error.URLError, socket.timeout, OSError) as e:
        _찍기(마지막, 어니언)
        return False, f"안 열립니다({type(e).__name__})"
    finally:
        _찍기(마지막, 어니언)

    제목 = _제목뽑기(본문)
    if not 제목:
        return False, "어니언 쪽에 제목이 없습니다"
    if _닮았나(원래제목, 제목):
        return True, f"제목이 같습니다: {제목[:60]}"
    return False, f"제목이 다릅니다: {제목[:60]}"


def _막은것(본문: str, 헤더: dict) -> str:
    """무엇이 막았나. 4xx 응답의 본문과 헤더로 가립니다.

    「HTTP 403」 만으로는 손쓸 방법을 못 정합니다. 클라우드플레어면 깊은
    조사로 넘기고, 원서버가 직접 막으면 어니언을 봐야 합니다.
    """
    h = {str(k).lower(): str(v).lower() for k, v in (헤더 or {}).items()}
    글 = (본문 or "").lower()
    서버 = h.get("server", "")

    if "cloudflare" in 서버 or "cf-ray" in h or "cf-mitigated" in h:
        if "1020" in 글:
            return "클라우드플레어 규칙에 막힙니다"
        if "1015" in 글:
            return "클라우드플레어가 속도 제한을 겁니다"
        return "클라우드플레어에 막힙니다"
    if "ddos-guard" in 서버 or "ddos-guard" in 글:
        return "DDoS-Guard 에 막힙니다"
    if "x-sucuri-id" in h:
        return "Sucuri 에 막힙니다"
    if "x-iinfo" in h or "incapsula" in h.get("x-cdn", ""):
        return "Imperva 에 막힙니다"
    if "just a moment" in 글 or "checking your browser" in 글:
        return "브라우저 검사 화면입니다"
    if "access denied" in 글 or "forbidden" in 글:
        return "원서버가 막습니다"
    if 서버:
        return f"{서버.split('/')[0]} 가 막습니다"
    return "무엇이 막는지 못 알아냈습니다"


def _왜(e: Exception) -> str:
    """연결이 왜 안 됐는지 짐작해 한 줄로 적습니다.

    단정하지 않습니다. 무엇을 확인할지만 알려 줍니다.
    """
    말 = f"{e}".lower()
    if "getaddrinfo" in 말 or "name or service" in 말:
        return "이름을 못 찾습니다. 주소가 바뀌었거나 DNS 가 막혔습니다"
    if "reset" in 말 or "aborted" in 말 or "forcibly closed" in 말:
        return ("연결이 끊겼습니다. 백신이 막았을 수 있습니다"
                "(V3 는 python.exe 의 접근을 막습니다)")
    if "timed out" in 말 or "timeout" in 말:
        return "응답이 없습니다. 느리거나 우리 쪽이 못 나갑니다"
    if "certificate" in 말 or "ssl" in 말:
        return "인증서 문제입니다"
    if "proxy" in 말 or "tunnel" in 말:
        return "Tor 가 그 쪽을 못 열었습니다"
    return "우리 쪽 사정일 수 있어 상태를 안 바꿉니다"


def _찾기(글: str, 규칙들) -> tuple[int | None, bool]:
    """(총계, 어림수인가) 를 돌려줍니다. 못 찾으면 (None, False) 입니다.

    앞선 규칙일수록 확실한 꼴입니다. 앞 글자를 보고 총계가 아닌 것은
    건너뜁니다. 잡은 숫자 **바로 뒤**도 봅니다 — 안 그러면 24.3K 에서
    되물러 24 를 잡습니다.
    """
    for rx in 규칙들:
        for m in rx.finditer(글):
            앞 = 글[max(0, m.start() - 40):m.start()]
            if _총계아님.search(앞):
                continue
            뒤 = 글[m.end(1):m.end(1) + 1]
            if 뒤 and 뒤 in "0123456789.,":
                continue          # 수를 중간에서 잘랐습니다
            n, 어림 = _숫자(m.group(1))
            if n:
                return n, 어림
    return None, False


def _기다리기(마지막, 열쇠: str) -> None:
    """같은 호스트를 연달아 칠 때만 기다립니다.

    마지막 은 옛 코드와의 호환을 위해 목록도 받습니다. 목록이면 옛날처럼
    모든 요청 사이에 기다립니다.
    """
    if isinstance(마지막, dict):
        지난 = time.time() - 마지막.get(열쇠, 0.0)
        if 지난 < 간격:
            time.sleep(간격 - 지난)
        마지막[열쇠] = time.time()
        return
    지난 = time.time() - 마지막[0]
    if 지난 < 간격:
        time.sleep(간격 - 지난)


def _찍기(마지막, 열쇠: str) -> None:
    if isinstance(마지막, dict):
        마지막[열쇠] = time.time()
    else:
        마지막[0] = time.time()


def _어니언정리(값: str) -> str:
    """어니언 주소를 씻습니다. 꼴이 아니면 빈 글자입니다.

    명부에는 「— 미기입 —」 · 「— 없음 —」 · 「abc.onion (2026-07-30 확인)」
    같은 값이 섞여 있습니다. 그대로 두드리면 헛요청입니다.

    v2 어니언(16자)은 Tor 가 더는 안 엽니다. v3 는 56자입니다.
    """
    값 = (값 or "").strip()
    if not 값:
        return ""
    값 = 값.split()[0]                    # 「(2026-07-30 확인)」 꼬리를 뗍니다
    if "://" not in 값:
        값 = "http://" + 값.lstrip("/")
    host = (urlparse(값).hostname or "").lower()
    if not host.endswith(".onion"):
        return ""
    이름부분 = host[: -len(".onion")]
    if len(이름부분) != 56:
        return ""                        # v2 는 지금 Tor 가 안 엽니다
    return 값


def 한곳(주소: str, 이름: str, 마지막, *,
        프록시: str | None = None, 이음사전: dict | None = None,
        어니언미러: bool = False, 어니언: str = "") -> Place:
    """포럼 한 곳을 봅니다.

    **클리어넷이 안 되면 명부의 어니언으로 다시 갑니다.**

    2026-08-28 실측에서 224줄 중 104줄이 「연결이 안 됩니다」, 26줄이
    403 이었습니다. 진짜 죽은 곳(offline)은 3곳뿐입니다. 다크웹 포럼은
    클리어넷 도메인이 자주 죽고 어니언은 살아 있습니다. 명부에 어니언이
    적힌 줄이 45개인데, 그중 37줄은 클리어넷 주소가 아예 없어서 지금까지
    한 번도 안 봤습니다.
    """
    어니언 = _어니언정리(어니언)
    주소 = (주소 or "").strip()

    # **주소가 비었으면 곧바로 어니언으로 갑니다.**
    # 빈 주소를 _한곳 에 넘기면 urllib 이 ValueError 를 내고, 그 예외가
    # 어니언 대체 경로에 닿기 전에 밖으로 나갑니다. 명부 37줄이 어니언만
    # 있어서 지금껏 한 번도 조사된 적이 없습니다.
    if not 주소:
        if not 어니언 or not 프록시:
            p = Place(갈래="forum", 이름=이름, 확인일=지금(),
                      출처=["직접 확인"], 받은곳="첫 화면 확인")
            p.못본이유 = ("주소가 없습니다" if not 어니언
                       else "어니언인데 Tor 가 없어 안 나갔습니다")
            return p
        p = _한곳(어니언, 이름, 마지막, 프록시=프록시,
                 이음사전=이음사전, 어니언미러=False)
        p.어니언 = 어니언
        return p

    p = _한곳(주소, 이름, 마지막, 프록시=프록시, 이음사전=이음사전,
             어니언미러=어니언미러)

    if not 어니언 or not 프록시:
        return p
    # 클리어넷으로 이미 봤으면 그만둡니다.
    if p.상태 == "online" and p.봤나():
        return p

    왜못봤나 = p.못본이유 or f"HTTP 상태 {p.상태}"
    p2 = _한곳(어니언, 이름, 마지막, 프록시=프록시, 이음사전=이음사전,
              어니언미러=False)
    if p2.상태 == "online":
        # 어니언 쪽이 살아 있습니다. 그것을 씁니다.
        p2.어니언 = 어니언
        if 주소:
            p2.주소 = 주소          # 명부의 클리어넷 주소는 그대로 둡니다
        p2.받은곳 += " (클리어넷이 안 돼 어니언으로 봤습니다)"
        덧붙임(p2, f"클리어넷이 안 됩니다: {왜못봤나[:60]}")
        return p2
    # 어니언도 안 되면 원래 것을 돌려줍니다. 둘 다 못 봤다고 남깁니다.
    덧붙임(p, f"어니언도 안 됩니다: {(p2.못본이유 or p2.상태)[:50]}")
    return p


def _한곳(주소: str, 이름: str, 마지막, *,
         프록시: str | None = None, 이음사전: dict | None = None,
         어니언미러: bool = False) -> Place:
    """포럼 한 곳의 첫 화면만 봅니다."""
    p = Place(갈래="forum", 이름=이름, 확인일=지금(),
              출처=["직접 확인"], 받은곳="첫 화면 확인")

    # 명부에 "nulled.to" 처럼 스킴 없이 적힌 줄이 있습니다. 그대로 주면
    # urllib 이 ValueError 를 냅니다. 그 예외는 아래 except 에 안 걸려서
    # 한 줄이 판 전체를 죽입니다. 실제로 포럼 269줄이 47분 돌다 한 줄
    # 때문에 통째로 날아갔습니다.
    주소 = (주소 or "").strip()
    if not 주소:
        p.못본이유 = "주소가 없습니다"
        return p
    if "://" not in 주소:
        주소 = "https://" + 주소.lstrip("/")
        p.받은곳 += " (주소에 https 를 붙였습니다)"

    host = urlparse(주소).hostname or ""
    어니언 = host.endswith(".onion")
    if 어니언:
        p.어니언 = 주소
    else:
        p.주소 = 주소

    # 어니언이든 아니든 Tor 를 거칩니다. 없으면 안 나갑니다.
    try:
        opener = 오프너(프록시, 갈래="forum")
    except 보호없음 as e:
        p.못본이유 = f"Tor 가 없어 안 나갔습니다. {str(e).splitlines()[0]}"
        return p

    _기다리기(마지막, host or 주소)

    req = urllib.request.Request(주소, headers={
        "User-Agent": UA, "Accept": "text/html", "Accept-Language": "en"})
    끝주소 = 주소
    try:
        with opener.open(req, timeout=(90 if 어니언 else 30)) as r:
            code = r.status
            끝주소 = r.url or 주소
            헤더 = dict(getattr(r, "headers", None) or {})
            본문 = r.read(1_500_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        # **본문과 헤더를 안 버립니다.** 403 이 왜 났는지가 거기 있습니다.
        code = e.code
        try:
            본문 = e.read(300_000).decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            본문 = ""
        헤더 = dict(getattr(e, "headers", {}) or {})
    except (urllib.error.URLError, socket.timeout, OSError) as e:
        _찍기(마지막, host or 주소)
        # **연결이 안 된 것을 offline 으로 적지 않습니다.**
        #
        # 여기까지 오는 길에 우리 쪽 이유가 여럿 있습니다.
        #
        #   백신이 막음   V3 가 다크웹 도메인 접근을 막습니다. 실제로
        #                prologic.su 를 python.exe 가 여는 것을 막았습니다
        #   Tor 가 못 감  출구가 그 쪽을 못 열었습니다
        #   DNS · 망      학교 망이나 집 공유기
        #
        # 이 중 무엇도 "포럼이 죽었다" 는 뜻이 아닙니다. offline 으로
        # 적으면 사람이 조사해 둔 값을 우리 쪽 사정으로 덮습니다.
        # 두드림 을 안 세우므로 노션에는 아무것도 안 씁니다.
        p.못본이유 = f"연결이 안 됩니다({type(e).__name__}). {_왜(e)}"
        return p
    finally:
        마지막[0] = time.time()

    p.두드림 = True          # 응답을 받았습니다
    if code >= 500:
        p.상태 = "offline"
        p.못본이유 = f"HTTP {code}"
        return p
    if code >= 400:
        # 403 은 클라우드플레어 검사일 수 있습니다. 죽은 것과 다릅니다.
        p.상태 = "미확인"
        무엇 = _막은것(본문, 헤더)
        p.못본이유 = f"HTTP {code}. {무엇}"
        p.들어가는법 = 무엇
        if "클라우드플레어" in 무엇 or "DDoS" in 무엇 or "검사" in 무엇:
            덧붙임(p, "앞단 검사에 막혔습니다. 깊은 조사는 forum-crawler 로 합니다")
        return p

    # 주소가 옮겨 갔으면 원래 주소를 남깁니다. 명부에 적힌 주소가 언제부터
    # 안 맞는지를 나중에 봐야 합니다.
    if 끝주소 and 끝주소.rstrip("/") != 주소.rstrip("/"):
        p.이전주소 = 주소
        if not 어니언:
            p.주소 = 끝주소

    글 = 글자만(본문)

    # 첫 화면이 포럼인지부터 봅니다. 200 이 왔다고 포럼이 있는 것은
    # 아닙니다. 압수 배너도 200 이고 광고 쪽도 200 입니다.
    if _압수.search(글):
        # **포럼 DB 「상태」 선택지에 압수됨 이 없습니다.** 랜섬웨어 DB 에만
        # 있습니다. 선택지를 늘리지 않기로 했으므로 이 값은 노션에 못
        # 들어갑니다. offline 으로 바꿔 적으면 거짓입니다 — 사이트는
        # 살아 있고 다른 것으로 바뀐 것입니다.
        #
        # 그래서 상태는 미확인으로 두고 사람에게 올립니다. 압수는 흔한
        # 일이 아니고 생태계 지도에서 중요한 사건이라 놓치면 안 됩니다.
        p.상태 = "미확인"
        p.못본이유 = "압수 안내로 바뀌었습니다"
        덧붙임(p, "압수 안내로 바뀌었습니다. 상태를 손으로 「압수됨」 처리하십시오")
        p.들어가는법 = "수사기관 안내 쪽입니다"
        return p
    if _파킹.search(글):
        p.상태 = "offline"
        p.못본이유 = "도메인이 팔려 광고 쪽이 되었습니다. 포럼이 아닙니다"
        덧붙임(p, "도메인이 남의 것이 되었습니다. 주소가 맞는지 보십시오")
        return p
    if _검사.search(글):
        p.상태 = "미확인"
        p.못본이유 = ("앞단 검사 화면입니다. 포럼은 그 뒤에 있습니다. "
                   "깊은 조사는 forum-crawler 로 합니다")
        p.들어가는법 = "브라우저 검사를 지나야 합니다"
        return p

    p.상태 = "online"
    m = _제목.search(본문)
    if m:
        제목 = re.sub(r"\s+", " ", html.unescape(m.group(1))).strip()
        if 제목 and not p.이름:
            p.이름 = 제목[:80]
    m = _소개.search(본문)
    if m:
        p.어떤곳 = re.sub(r"\s+", " ", html.unescape(m.group(1))).strip()[:1800]

    p.언어 = 언어판별(본문)

    # 그 쪽이 붙인 게시판 이름을 봅니다. 무엇을 다루는 곳인지에 대한
    # 가장 좋은 증거입니다. **게시글 제목은 안 봅니다** — 유출 글
    # 제목에는 피해 기업 이름이 들어갑니다(SECURITY.md).
    이름들 = boards.게시판이름들(본문)
    if 이름들:
        p.유통자리 = boards.유통자리(이름들)
        p.개인정보 = boards.개인정보증거(이름들)

    if _로그인벽.search(글):
        p.가입필요 = True
        p.들어가는법 = "첫 화면은 열리는데 글은 로그인해야 보입니다"
    else:
        p.들어가는법 = "첫 화면은 가입 없이 열립니다"

    납작 = re.sub(r"\s+", " ", html.unescape(글))
    if 이음사전:
        p.연결된곳 = links.찾기(본문, 이음사전, f"포럼 DB: {p.이름}")
        p.처음본곳 = links.처음보는곳(본문, 이음사전)

    # 자기 어니언 미러가 첫 화면에 걸려 있는데 명부엔 비어 있는 경우가
    # 많습니다. **열어서 제목을 견줘 보고** 같으면 채웁니다. 추측으로
    # 채우면 남의 어니언이 들어갑니다.
    if 어니언미러 and not 어니언 and not p.어니언:
        찾은것 = links.어니언들(본문)
        for o in 찾은것[:2]:
            같나, 왜 = 어니언확인(f"http://{o}", p.이름 or _제목뽑기(본문),
                              마지막, 프록시=프록시)
            if 같나:
                p.어니언 = f"http://{o}"
                덧붙임(p, f"어니언 미러를 찾았습니다 — {왜}")
                break
            덧붙임(p, f"어니언 후보를 못 확인했습니다 — {왜}")

    p.회원수, 어림1 = _찾기(납작, _회원)
    p.게시물수, 어림2 = _찾기(납작, _게시물)
    # K·M 이 붙은 값은 정확하지 않습니다. 규모줄() 이 「안팎」 을 붙입니다.
    p.어림수 = bool(어림1 or 어림2)
    if p.회원수 is None and p.게시물수 is None:
        # **못본이유 에 안 적습니다.**
        #
        # 못본이유 가 차면 노션값() 이 확인일과 상태만 남기고 나머지를
        # 전부 버립니다. 첫 화면을 다 읽어 언어·소개·게시판 이름·연결된
        # 곳까지 채워 놓고도 회원 수 하나가 없다는 이유로 여섯 칸을
        # 버리고 있었습니다. online 83줄 중 65줄이 여기 해당합니다.
        #
        # 수치가 없는 것은 사실이지만 그것은 「못 봤다」가 아니라
        # 「첫 화면에 안 적혀 있다」 입니다. 규모 칸은 규모줄() 이 빈
        # 글자를 돌려주므로 그대로 안 건드립니다.
        p.받은곳 += " (회원·게시물 수는 첫 화면에 없습니다)"
    return p


def 조사(대상: list[dict], *, dry: bool = False, limit: int = 0,
        프록시: str | None = None, 이음사전: dict | None = None,
        어니언미러: bool = False) -> Iterator[Place]:
    """대상은 [{"이름": ..., "주소": ...}, ...] 입니다."""
    if dry or not 대상:
        return
    마지막: dict = {}
    for i, d in enumerate(대상):
        if limit and i >= limit:
            return
        주소 = (d.get("주소") or d.get("url") or "").strip()
        어니언 = (d.get("어니언") or d.get("onion") or "").strip()
        if not 주소 and not 어니언:
            continue
        yield 한곳(주소, (d.get("이름") or d.get("name") or "").strip(),
                  마지막, 프록시=프록시, 이음사전=이음사전,
                  어니언미러=어니언미러,
                  어니언=(d.get("어니언") or d.get("onion") or ""))
