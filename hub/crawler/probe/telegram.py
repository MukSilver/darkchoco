"""텔레그램 채널 명부를 조사합니다.

무엇을 알아내나 — 채널이 지금 살아있나, 구독자가 몇인가, 미리보기가
켜져 있나, 마지막 글이 언제인가.

지금 저장소에 이 일을 하는 도구가 없었습니다. 텔레그램 DB 28줄 중
23줄이 8월 4~5일에 멈춰 있는 이유입니다.

`t.me/s/<채널>` 공개 미리보기를 봅니다. 계정으로 들어가지 않으므로 그
계정이 무엇을 봤는지가 남지 않습니다. 미리보기가 꺼진 채널은 `t.me/<채널>`
소개 쪽에서 구독자 수만 봅니다.

**글 본문은 안 가져옵니다.** 여기는 명부를 채우는 자리입니다. 게시물
수집은 다른 일이고 skills/collect 가 합니다.

표준 라이브러리만 씁니다.
"""

from __future__ import annotations

import html
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterator

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "packages"))

from hub.crawler.place import Place, 지금  # noqa: E402

__all__ = ["조사", "NEEDS_PACKAGES"]

NEEDS_PACKAGES: list[str] = []

간격 = 2.5
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# t.me 소개 쪽의 구독자 수. "1 234 subscribers" 처럼 빈칸이 섞입니다.
_구독자 = re.compile(
    r'<div class="tgme_page_extra">([^<]*?)(?:subscriber|members|명)', re.I)
_구독자2 = re.compile(
    r'"tgme_header_counter">\s*([\d\s,\.]+)\s*(?:subscriber|members)', re.I)
_제목 = re.compile(r'<div class="tgme_(?:page|channel_info_header)_title"[^>]*>([^<]+)')
_소개 = re.compile(r'<div class="tgme_page_description"[^>]*>(.*?)</div>', re.S)
_마지막글 = re.compile(r'datetime="([\dT:\-\+]+)"')
_미리보기꺼짐 = re.compile(r'tgme_page_context_link|preview is not available', re.I)


def _숫자(s: str) -> int | None:
    s = re.sub(r"[^\d]", "", s or "")
    return int(s) if s else None


def _글자(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def _받기(url: str, 마지막: list[float]) -> tuple[int, str]:
    지난 = time.time() - 마지막[0]
    if 지난 < 간격:
        time.sleep(간격 - 지난)
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "text/html", "Accept-Language": "en"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read(2_000_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    finally:
        마지막[0] = time.time()


def _채널이름(값: str) -> str:
    값 = (값 or "").strip().rstrip("/")
    for 앞 in ("https://t.me/s/", "https://t.me/", "http://t.me/", "t.me/s/", "t.me/", "@"):
        if 값.startswith(앞):
            값 = 값[len(앞):]
            break
    return 값.strip("/")


def 한곳(채널: str, 마지막: list[float]) -> Place:
    """채널 하나를 봅니다. 못 봤으면 왜인지 적습니다."""
    이름 = _채널이름(채널)
    p = Place(갈래="telegram", 이름=이름,
              주소=f"https://t.me/{이름}", 확인일=지금(),
              출처=["직접 확인"], 받은곳="t.me 공개 미리보기")

    try:
        code, body = _받기(f"https://t.me/s/{이름}", 마지막)
    except (urllib.error.URLError, OSError) as e:
        p.못본이유 = f"요청 실패: {e}"
        return p

    if code == 404:
        p.상태 = "offline"
        p.못본이유 = "404. 채널이 없거나 이름이 바뀌었습니다"
        return p
    if code != 200 or not body:
        p.못본이유 = f"HTTP {code}"
        return p

    # 미리보기가 꺼져 있으면 소개 쪽으로 한 번 더 갑니다.
    if _미리보기꺼짐.search(body) and "tgme_widget_message" not in body:
        try:
            code2, body2 = _받기(f"https://t.me/{이름}", 마지막)
            if code2 == 200 and body2:
                body = body2
                p.받은곳 = "t.me 소개 쪽 (미리보기 꺼짐)"
        except (urllib.error.URLError, OSError):
            pass

    m = _제목.search(body)
    if m:
        p.이름 = _글자(m.group(1)) or 이름

    수 = None
    for rx in (_구독자2, _구독자):
        m = rx.search(body)
        if m:
            수 = _숫자(m.group(1))
            if 수:
                break
    if 수:
        p.구독자수 = 수

    글들 = _마지막글.findall(body)
    if 글들:
        p.최근활동 = sorted(글들)[-1][:19]

    if 수 or 글들:
        p.상태 = "online"
    else:
        p.상태 = "미확인"
        p.못본이유 = ("미리보기가 꺼져 있고 소개 쪽에서도 수를 못 봤습니다. "
                   "실계정으로 봐야 합니다")
    return p


def 조사(채널들: list[str], *, dry: bool = False, limit: int = 0) -> Iterator[Place]:
    if dry or not 채널들:
        return
    마지막 = [0.0]
    for i, c in enumerate(채널들):
        if limit and i >= limit:
            return
        yield 한곳(c, 마지막)
