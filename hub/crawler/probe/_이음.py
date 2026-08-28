"""받아 온 쪽에서 다른 명부의 곳을 찾습니다.

생태계 지도의 선이 여기서 나옵니다. 포럼이 자기 텔레그램 채널을 걸어
두고, 텔레그램 채널이 포럼 주소를 걸어 둡니다. 그 선을 모으면 어느
무리가 함께 움직이는지가 보입니다.

**명부에 이미 있는 곳만 적습니다.** 첫 화면에는 광고와 남의 링크가
잔뜩 있습니다. 처음 보는 주소를 「연결된 곳」에 적으면 그것은 관계가
아니라 잡음입니다. 우리가 아는 곳끼리의 선만 긋습니다.

**글 본문은 안 봅니다.** 호스트 이름만 뽑습니다. 여기는 명부를 채우는
자리이고, 게시물 수집은 다른 일입니다.

표준 라이브러리만 씁니다.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

__all__ = ["호스트", "이름표만들기", "찾기"]

# href="..." · src 는 안 봅니다(이미지·스크립트는 관계가 아닙니다).
# 태그 밖에 맨 글자로 적힌 주소도 봅니다. 포럼 첫 화면에 흔합니다.
_링크 = re.compile(r'href=["\']([^"\']{4,300})["\']', re.I)
_맨주소 = re.compile(
    r'(?:https?://)?(?:t\.me|telegram\.me)/(?:s/)?([A-Za-z0-9_]{4,40})', re.I)
_어니언 = re.compile(r'\b([a-z2-7]{16}|[a-z2-7]{56})\.onion\b', re.I)

# 이런 곳은 명부에 있어도 관계로 안 셉니다. 어느 쪽이나 걸어 두는
# 것이라 선을 그으면 온 세상이 이어집니다.
_흔한곳 = {
    "t.me", "telegram.me", "twitter.com", "x.com", "youtube.com",
    "youtu.be", "discord.com", "discord.gg", "github.com", "google.com",
    "facebook.com", "instagram.com", "reddit.com", "cloudflare.com",
    "archive.org", "wikipedia.org", "bit.ly", "imgur.com", "gitlab.com",
    "vk.com", "medium.com", "linkedin.com", "tiktok.com",
}


def 호스트(값: str) -> str:
    """주소에서 호스트만 뽑아 맞춥니다. 못 뽑으면 빈 글자입니다.

    www. 를 떼고 소문자로 맞춥니다. 명부에 적힌 꼴이 제각각이라
    그대로 대조하면 같은 곳을 다른 곳으로 봅니다.
    """
    값 = (값 or "").strip()
    if not 값:
        return ""
    if "://" not in 값:
        값 = "http://" + 값.lstrip("/")
    try:
        h = (urlparse(값).hostname or "").lower()
    except ValueError:
        return ""
    h = h[4:] if h.startswith("www.") else h
    # 점이 없으면 호스트가 아닙니다. 명부에 "@projectwwh" 처럼 주소가
    # 아닌 값이 적힌 줄이 있어서, 그것이 사전에 들어가면 엉뚱한 링크와
    # 맞을 수 있습니다.
    return h if "." in h else ""


def 이름표만들기(명부들: dict) -> dict[str, str]:
    """호스트 → 사람이 읽을 이름표. 세 명부를 한 사전으로 만듭니다.

    명부들 은 {갈래: [줄, ...]} 입니다. 줄은 이름·주소·어니언을 갖습니다.
    텔레그램은 주소가 t.me/<채널> 이라 호스트가 다 같습니다. 그래서
    채널 이름을 열쇠로 씁니다.
    """
    사전: dict[str, str] = {}
    이름 = {"telegram": "텔레그램 DB", "forum": "포럼 DB",
           "ransom": "랜섬웨어 DB"}
    for 갈래, 줄들 in 명부들.items():
        딱지 = 이름.get(갈래, 갈래)
        for r in 줄들:
            보임 = (getattr(r, "이름", "") or "").strip()
            if not 보임:
                continue
            표 = f"{딱지}: {보임}"
            for 주소 in (getattr(r, "주소", ""), getattr(r, "어니언", "")):
                h = 호스트(주소)
                if not h or h in _흔한곳:
                    # t.me 는 호스트가 다 같아 채널 이름으로 겁니다.
                    if h in ("t.me", "telegram.me"):
                        조각 = (주소 or "").rstrip("/").split("/")
                        if 조각 and 조각[-1]:
                            사전.setdefault(
                                f"t.me/{조각[-1].lower()}", 표)
                    continue
                사전.setdefault(h, 표)
    return 사전


def 찾기(본문: str, 사전: dict[str, str], 나: str = "",
        최대: int = 8) -> str:
    """본문에서 명부에 있는 곳을 찾아 한 줄로 만듭니다.

    나 는 지금 보고 있는 곳의 이름표입니다. 자기 자신은 안 셉니다.
    못 찾으면 빈 글자를 돌려줍니다. 억지로 채우지 않습니다.
    """
    if not 본문 or not 사전:
        return ""

    나온것: list[str] = []

    def 담기(표: str) -> None:
        if 표 and 표 != 나 and 표 not in 나온것:
            나온것.append(표)

    for m in _링크.finditer(본문):
        h = 호스트(m.group(1))
        if h and h not in _흔한곳:
            담기(사전.get(h, ""))
        if len(나온것) >= 최대:
            break

    # 텔레그램 채널은 호스트가 다 같아 따로 봅니다.
    for m in _맨주소.finditer(본문):
        담기(사전.get(f"t.me/{m.group(1).lower()}", ""))
        if len(나온것) >= 최대:
            break

    # 어니언은 호스트만으로 걸립니다.
    for m in _어니언.finditer(본문):
        담기(사전.get(f"{m.group(1).lower()}.onion", ""))
        if len(나온것) >= 최대:
            break

    return " · ".join(나온것[:최대])
