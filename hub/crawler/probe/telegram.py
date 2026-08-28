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
# t.me 는 수를 축약해 보냅니다. "8.12K subscribers" 처럼입니다.
# 축약값은 정확하지 않으므로 그대로 쓰지 않고 어림수임을 밝힙니다.
_구독자 = re.compile(
    r'counter_value"[^>]*>\s*([\d\s,\.]+[KMkm]?)\s*</span>\s*'
    r'<span class="counter_type">\s*(?:subscriber|member)', re.I)
_구독자2 = re.compile(
    r'tgme_(?:header_counter|page_extra)"[^>]*>\s*([\d\s,\.]+[KMkm]?)\s*'
    r'(?:subscriber|member|명)', re.I)
_제목 = re.compile(r'<div class="tgme_(?:page|channel_info_header)_title"[^>]*>([^<]+)')
_소개 = re.compile(r'<div class="tgme_page_description"[^>]*>(.*?)</div>', re.S)
_마지막글 = re.compile(r'datetime="([\dT:\-\+]+)"')
_미리보기꺼짐 = re.compile(r'tgme_page_context_link|preview is not available', re.I)


def _숫자(s: str) -> tuple[int | None, bool]:
    """(수, 어림수인가) 를 돌려줍니다.

    t.me 가 8.12K 처럼 줄여 보냅니다. 그것을 8,120 으로 펴면 실제와
    다를 수 있습니다. 그래서 어림수임을 같이 돌려줍니다.
    """
    s = (s or "").strip().replace(" ", "").replace(",", "")
    if not s:
        return None, False
    m = re.fullmatch(r"([\d.]+)\s*([KMkm]?)", s)
    if not m:
        숫자 = re.sub(r"[^\d]", "", s)
        return (int(숫자), False) if 숫자 else (None, False)
    값, 배 = m.group(1), m.group(2).upper()
    try:
        n = float(값)
    except ValueError:
        return None, False
    if 배 == "K":
        return int(n * 1_000), True
    if 배 == "M":
        return int(n * 1_000_000), True
    return int(n), False


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


def _채널이름(값: str) -> tuple[str, str]:
    """주소에서 채널 이름을 뽑습니다. (이름, 못 볼 이유) 를 돌려줍니다.

    명부에 적힌 주소 꼴이 제각각입니다. 실제로 이런 것들이 있습니다.

        https://t.me/leakforumio          보통
        t.me/cyberbreachio                프로토콜 없음
        @projectwwh                       골뱅이
        https://t.me/+LV-lyCog6r42OWM0    초대 링크. 공개 미리보기가 없습니다
        https://nulledbb.com/discord      텔레그램이 아닙니다
    """
    값 = (값 or "").strip().rstrip("/")
    if not 값:
        return "", "주소가 비어 있습니다"

    낮 = 값.lower()
    # 주소 꼴이면 t.me 여야 합니다. 채널 이름만 준 것은 그대로 받습니다.
    if "://" in 값 or "." in 값.split("/")[0]:
        if "t.me" not in 낮:
            return "", f"텔레그램 주소가 아닙니다: {값[:48]}"

    for 앞 in ("https://t.me/s/", "http://t.me/s/", "https://t.me/",
               "http://t.me/", "t.me/s/", "t.me/", "@"):
        if 낮.startswith(앞):
            값 = 값[len(앞):]
            break
    값 = 값.strip("/")

    if 값.startswith("+") or 값.lower().startswith("joinchat"):
        return "", "초대 링크입니다. 공개 미리보기가 없어 실계정으로 봐야 합니다"
    if not 값:
        return "", "주소에서 채널 이름을 못 뽑았습니다"
    return 값, ""


def 한곳(채널: str, 마지막: list[float], 이름표: str = "") -> Place:
    """채널 하나를 봅니다. 못 봤으면 왜인지 적습니다."""
    이름, 못볼이유 = _채널이름(채널)
    p = Place(갈래="telegram", 이름=이름표 or 이름 or 채널[:40],
              주소=f"https://t.me/{이름}" if 이름 else 채널,
              확인일=지금(), 출처=["직접 확인"], 받은곳="t.me 공개 미리보기")
    if 못볼이유:
        p.못본이유 = 못볼이유
        # 텔레그램 주소가 아니면 명부가 틀린 것입니다. 채널 상태가 아닙니다.
        p.주소이상 = "텔레그램 주소가 아닙니다" in 못볼이유 or "비어 있" in 못볼이유
        return p

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

    수, 어림 = None, False
    for rx in (_구독자, _구독자2):
        m = rx.search(body)
        if m:
            수, 어림 = _숫자(m.group(1))
            if 수:
                break
    if 수:
        p.구독자수 = 수
        p.어림수 = 어림

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


def 조사(채널들: list, *, dry: bool = False, limit: int = 0) -> Iterator[Place]:
    """채널들은 주소 문자열이거나 {"이름": ..., "주소": ...} 입니다."""
    if dry or not 채널들:
        return
    마지막 = [0.0]
    for i, c in enumerate(채널들):
        if limit and i >= limit:
            return
        if isinstance(c, dict):
            yield 한곳(c.get("주소") or "", 마지막, c.get("이름") or "")
        else:
            yield 한곳(c, 마지막)
