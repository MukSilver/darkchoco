"""
sources/base.py — 소스 공통 인터페이스와 정규화 레코드 정의.

각 소스는 서로 다른 스키마를 쓰므로, 여기서 하나의 정규 스키마(LeakRecord)로
변환한 뒤 이후 파이프라인(중복제거 → KR 판별 → 저장 → 알림)이 동작한다.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Iterable

from ..safety import extract_domain, sanitize_text

# 회사명 정규화 시 제거할 법인격 접미어 (중복 제거 정확도 향상)
_LEGAL_SUFFIXES = (
    "co ltd", "co. ltd", "coltd", "company limited", "corporation", "corp",
    "incorporated", "inc", "limited", "ltd", "llc", "llp", "plc", "gmbh",
    "s a s", "sas", "s r l", "srl", "sa", "nv", "bv", "ag", "ab", "oy", "as",
    "pty", "pte", "kk", "k k", "co", "group", "holdings", "holding",
    "주식회사", "㈜", "유한회사", "재단법인", "사단법인",
)
_NONALNUM_RE = re.compile(r"[^0-9a-z가-힣]+")
_URLISH_RE = re.compile(r"^(https?://)?(www\.)?[a-z0-9-]+(\.[a-z0-9-]+)+/?$", re.IGNORECASE)


@dataclass
class LeakRecord:
    """모든 소스가 이 형태로 변환된다."""

    victim: str = ""
    group: str = ""
    country: str = ""
    sector: str = ""
    website: str = ""
    description: str = ""
    published: str = ""      # ISO-8601 UTC
    discovered: str = ""     # ISO-8601 UTC
    post_url: str = ""       # 원문 URL (대개 .onion) — 출력 시 defang 처리됨
    source: str = ""

    # 파이프라인이 채우는 필드
    uid: str = ""
    victim_key: str = ""
    group_key: str = ""

    # 축 1: 한국 관련성
    kr_tier: str = ""
    kr_score: int = 0
    kr_reasons: list[str] = field(default_factory=list)

    # 축 2: 공급망 위험 (한국 관련성과 독립적으로 평가된다)
    supply_tier: str = ""
    supply_score: int = 0
    supply_reasons: list[str] = field(default_factory=list)

    def finalize(self) -> "LeakRecord":
        """살균 + 파생 키 계산. 소스 어댑터는 반드시 이걸 호출해야 한다."""
        self.victim = sanitize_text(self.victim, 300)
        self.group = sanitize_text(self.group, 100)
        self.country = sanitize_text(self.country, 8).upper()
        self.sector = sanitize_text(self.sector, 120)
        self.description = sanitize_text(self.description, 2000)
        self.source = sanitize_text(self.source, 50)
        self.post_url = sanitize_text(self.post_url, 500)

        self.website = extract_domain(self.website) or extract_domain(self.victim)

        self.group_key = normalize_group(self.group)
        self.victim_key = normalize_victim(self.victim, self.website)
        self.uid = make_uid(self.group_key, self.victim_key)
        return self

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ─────────────────────────────────────────────────────────────
# 정규화 헬퍼
# ─────────────────────────────────────────────────────────────

def normalize_group(name: str) -> str:
    key = _NONALNUM_RE.sub("", (name or "").lower())
    # 같은 그룹의 표기 흔들림 통합
    aliases = {
        "lockbit3": "lockbit", "lockbit30": "lockbit", "lockbit2": "lockbit",
        "lockbit4": "lockbit", "lockbit5": "lockbit",
        "alphv": "blackcat", "alphvblackcat": "blackcat",
        "clop": "cl0p", "cl0pleaks": "cl0p",
        "blackbasta": "basta",
        "ransomhouse": "ransomhouse",
    }
    return aliases.get(key, key)


def normalize_victim(name: str, website: str = "") -> str:
    """중복 제거용 키. 도메인이 있으면 도메인을 우선한다(가장 안정적)."""
    if website:
        return website.lower()

    raw = (name or "").strip().lower()
    if _URLISH_RE.match(raw):
        d = extract_domain(raw)
        if d:
            return d

    # 괄호 주석 제거: "SAMPLEMOTOR MOTOR(critical data)" → "SAMPLEMOTOR MOTOR"
    raw = re.sub(r"[\(\[（【].{0,80}?[\)\]）】]", " ", raw)
    # 백슬래시/파이프로 나열된 별칭은 첫 번째만 사용
    raw = re.split(r"[\\|]", raw)[0]

    tokens = _NONALNUM_RE.sub(" ", raw).split()
    while tokens and " ".join(tokens[-2:]) in _LEGAL_SUFFIXES:
        tokens = tokens[:-2]
    while tokens and tokens[-1] in _LEGAL_SUFFIXES:
        tokens = tokens[:-1]
    return "".join(tokens)


def make_uid(group_key: str, victim_key: str) -> str:
    return hashlib.sha256(f"{group_key}\x1f{victim_key}".encode("utf-8")).hexdigest()[:32]


def parse_timestamp(value: Any) -> str:
    """다양한 소스 포맷을 ISO-8601 UTC 문자열로 통일. 실패 시 빈 문자열."""
    if not value:
        return ""
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
        except (ValueError, OSError, OverflowError):
            return ""

    text = str(value).strip()
    if not text or text.lower() in ("none", "null", "n/a"):
        return ""

    # ISO-8601 (Z 접미사 포함)
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except ValueError:
        pass

    # RFC-822 (RSS) — 'Fri, 14 Aug 2026 11:21:21 CEST'
    try:
        from email.utils import parsedate_to_datetime

        dt = parsedate_to_datetime(text)
        if dt is not None:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError, IndexError):
        pass

    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            continue
    return ""


# ─────────────────────────────────────────────────────────────
# 소스 인터페이스
# ─────────────────────────────────────────────────────────────

class Source:
    """모든 수집 소스의 기반 클래스.

    어댑터는 내부 오류를 삼키더라도 반드시 self.errors 에 기록해야 한다.
    그래야 '네트워크 장애로 0건'과 '실제로 신규 0건'을 구분할 수 있다.
    """

    name = "base"

    def __init__(self, client: Any, cfg: dict[str, Any]):
        self.client = client
        self.cfg = cfg or {}
        self.errors: list[str] = []

    def note_error(self, message: str) -> None:
        self.errors.append(str(message)[:500])

    def fetch(self) -> Iterable[LeakRecord]:
        raise NotImplementedError
