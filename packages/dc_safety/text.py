"""텍스트 살균과 주소 처리. kr-leak-alarm 에서 왔습니다.

수집한 값을 그대로 쓰지 않고 한 번 걸러 냅니다. 길이를 자르고,
제어 문자를 없애고, 주소는 그대로 노출되지 않게 defang 합니다.

VM 탐지와 Tor 게이트 판정은 앱마다 사정이 달라 옮기지 않았습니다.
"""

from __future__ import annotations

import html
import os
import platform
import re
import subprocess
import unicodedata
from typing import Any

# ─────────────────────────────────────────────────────────────
# 1. 텍스트 살균 (sanitization)
# ─────────────────────────────────────────────────────────────

MAX_FIELD_LEN = 2000

# 제어문자 (탭/줄바꿈 제외) + 방향 전환 문자(트로이 소스 공격 방어)
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_BIDI_RE = re.compile(r"[\u202a-\u202e\u2066-\u2069\u200e\u200f\u061c]")
_TAG_RE = re.compile(r"<[^>]{0,400}?>")
_WS_RE = re.compile(r"[ \t\u00a0]{2,}")


def sanitize_text(value: Any, max_len: int = MAX_FIELD_LEN) -> str:
    """외부 소스 문자열을 안전한 평문으로 정규화한다.

    - HTML 태그 제거 후 엔티티 디코드(순서 중요: 디코드 후 재검사)
    - 제어문자 / BiDi override 제거 (터미널·에디터 스푸핑 방어)
    - 유니코드 NFKC 정규화, 길이 제한
    """
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)

    # 태그 제거 → 엔티티 디코드 → 다시 태그 제거 (이중 인코딩 방어)
    text = _TAG_RE.sub(" ", value)
    text = html.unescape(text)
    text = _TAG_RE.sub(" ", text)

    text = _CONTROL_RE.sub("", text)
    text = _BIDI_RE.sub("", text)
    text = unicodedata.normalize("NFKC", text)
    text = _WS_RE.sub(" ", text).strip()

    if len(text) > max_len:
        text = text[:max_len].rstrip() + "…"
    return text


# ─────────────────────────────────────────────────────────────
# 2. URL defang — 실수 클릭으로 인한 접속 사고 방지
# ─────────────────────────────────────────────────────────────

_HTTP_SCHEME_RE = re.compile(r"^(https?)://", re.IGNORECASE)
_ANY_SCHEME_RE = re.compile(r"^([a-z][a-z0-9+.\-]{0,20}):", re.IGNORECASE)


def defang_url(url: Any) -> str:
    """공격자 인프라 URL 을 클릭 불가능한 형태로 변환한다.

    http://evil.onion/x   →  hxxp://evil[.]onion/x
    javascript:alert(1)   →  javascript[:]alert(1)
    data:text/html,...    →  data[:]text/html,...

    http/https 이외의 스킴(javascript:, data:, vbscript:, file: 등)도
    반드시 무력화한다 — 어떤 렌더러에 넘어가도 실행되지 않도록.
    """
    if not url:
        return ""
    url = sanitize_text(url, max_len=500)

    if _HTTP_SCHEME_RE.match(url):
        url = _HTTP_SCHEME_RE.sub(
            lambda m: ("hxxps" if m.group(1).lower() == "https" else "hxxp") + "://", url
        )
    else:
        # 그 외 스킴은 콜론을 무력화한다 (javascript:, data:, vbscript:, file: …)
        url = _ANY_SCHEME_RE.sub(lambda m: f"{m.group(1)}[:]", url)

    return url.replace(".", "[.]")


def defang_domain(domain: Any) -> str:
    if not domain:
        return ""
    return sanitize_text(domain, max_len=253).replace(".", "[.]")


def is_onion(url: Any) -> bool:
    if not url:
        return False
    return ".onion" in str(url).lower()


# ─────────────────────────────────────────────────────────────
# 3. 도메인 추출 / 정규화
# ─────────────────────────────────────────────────────────────

_DOMAIN_RE = re.compile(
    r"\b((?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24})\b", re.IGNORECASE
)


def extract_domain(value: Any) -> str:
    """'www.higen.co.kr', 'https://x.co.kr/a' 등에서 등록 도메인을 뽑는다."""
    if not value:
        return ""
    text = sanitize_text(value, max_len=500).lower()
    text = re.sub(r"^[a-z]+://", "", text)
    text = text.split("/")[0].split("?")[0].split("#")[0]
    text = text.split("@")[-1].split(":")[0]
    m = _DOMAIN_RE.search(text)
    if not m:
        return ""
    domain = m.group(1)
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


# ─────────────────────────────────────────────────────────────
# 4. 가상화 환경 탐지 — Tor 모듈 게이트
# ─────────────────────────────────────────────────────────────

_VMWARE_MARKERS = ("vmware", "vmw")


