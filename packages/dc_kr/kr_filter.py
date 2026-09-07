"""
kr_filter.py — 한국 관련 피해자 판별 엔진.

4단계 등급으로 분류한다. 등급이 높을수록 확실하다.

  confirmed (100) : 애그리게이터가 country=KR 로 태깅
  strong    (80)  : 피해자 도메인이 .kr / .co.kr 계열
  likely     (60) : 한국 대기업·기관명 매칭, 또는 한글 포함
  review     (30) : 약한 신호만 존재 (설명문에 'Korea' 언급 등) → 사람이 확인 필요
  none        (0) : 한국 무관

북한(DPRK) 관련 항목은 다른 KR 신호가 없으면 제외한다.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

TIER_ORDER = ["none", "review", "likely", "strong", "confirmed"]
TIER_SCORE = {"none": 0, "review": 30, "likely": 60, "strong": 80, "confirmed": 100}

_HANGUL_RE = re.compile(r"[가-힣ᄀ-ᇿ㄰-㆏]")
_KEYWORD_PATH = Path(__file__).parent / "data" / "kr_keywords.json"

# exclude 목록에서 '북한' 을 가리키는 항목만 골라내는 패턴.
# exclude_north_korea 스위치는 이름 그대로 북한 제외어만 켜고 꺼야 한다.
# 전에는 이 스위치가 exclude 목록 전체를 껐다 — koreatown·korea town·kia ora·
# hyundai motor america dealership directory 까지 같이 꺼져서, 설정을 끄는 사람이
# 무엇을 끄는지 알 수 없었다. 그래서 북한 항목만 여기서 가려낸다.
_NK_TERM_RE = re.compile(
    r"north\s+korea|korea\s*,\s*north|dprk|democratic people's republic|pyongyang",
    re.IGNORECASE,
)


def _load_keywords() -> dict[str, list[str]]:
    try:
        with _KEYWORD_PATH.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        log.error("키워드 파일 로드 실패(%s) — 기본값으로 계속합니다.", exc)
        data = {}
    return {
        "kr_tlds": data.get("kr_tlds", [".kr"]),
        "conglomerates": [k.lower() for k in data.get("conglomerates", [])],
        "entities": [k.lower() for k in data.get("entities", [])],
        "weak_signals": [k.lower() for k in data.get("weak_signals", [])],
        "exclude": [k.lower() for k in data.get("exclude", [])],
    }


def _compile_boundary(terms: list[str]) -> list[tuple[str, re.Pattern[str]]]:
    """단어 경계 매칭 패턴을 만든다. 'kia' 가 'nokia' 에 걸리지 않게 한다."""
    out: list[tuple[str, re.Pattern[str]]] = []
    for term in terms:
        term = term.strip().lower()
        if not term:
            continue
        escaped = re.escape(term)
        # 한글은 \b 가 제대로 동작하지 않으므로 경계 조건을 분기
        if _HANGUL_RE.search(term):
            pattern = escaped
        else:
            pattern = rf"(?<![a-z0-9]){escaped}(?![a-z0-9])"
        try:
            out.append((term, re.compile(pattern, re.IGNORECASE)))
        except re.error:
            continue
    return out


class KrClassifier:
    def __init__(self, cfg: dict[str, Any] | None = None):
        cfg = cfg or {}
        kw = _load_keywords()

        extra = [str(k).lower() for k in cfg.get("extra_keywords", []) if k]
        excl = [str(k).lower() for k in cfg.get("exclude_keywords", []) if k]

        self.kr_tlds = tuple(t.lower() for t in kw["kr_tlds"])
        # 설명문 **안에서** 한국 도메인을 찾는 패턴. `website` 칸은 위 tuple 로 보는데,
        # 그 칸이 빈 글(포럼·텔레그램 게시물)은 도메인이 제목이나 본문에만 있다.
        # 긴 것부터 대야 `.co.kr` 이 `.kr` 에 먼저 먹히지 않는다.
        _꼬리 = "|".join(re.escape(t.lstrip(".")) for t in
                       sorted(self.kr_tlds, key=len, reverse=True))
        self.kr_domain_re = re.compile(
            r"(?<![\w.-])[\w-]+(?:\.[\w-]+)*\.(?:%s)(?![\w-])" % _꼬리, re.IGNORECASE)
        self.conglomerates = _compile_boundary(kw["conglomerates"] + extra)
        self.entities = _compile_boundary(kw["entities"])
        self.weak = _compile_boundary(kw["weak_signals"])
        self.exclude = _compile_boundary(kw["exclude"] + excl)
        # 이 중 북한 항목만 exclude_north_korea 스위치의 대상이다. 나머지는 항상 적용된다.
        self.exclude_nk_terms = {term for term, _ in self.exclude if _NK_TERM_RE.search(term)}

        self.exclude_nk = bool(cfg.get("exclude_north_korea", True))
        self.min_tier = cfg.get("min_tier_to_report", "likely")
        if self.min_tier not in TIER_ORDER:
            self.min_tier = "likely"

    # ── 판별 ────────────────────────────────────────────────
    def classify(self, record: Any) -> tuple[str, int, list[str]]:
        """(tier, score, reasons) 반환."""
        victim = (record.victim or "").lower()
        website = (record.website or "").lower()
        desc = (record.description or "").lower()
        country = (record.country or "").upper()
        sector = (record.sector or "").lower()

        name_blob = f"{victim} {website} {sector}"
        full_blob = f"{name_blob} {desc}"

        reasons: list[str] = []
        tier = "none"

        # ── 1) country 태그 (가장 확실) ──
        if country == "KR":
            tier = "confirmed"
            reasons.append("소스 country=KR")
        elif country == "KP":
            return "none", 0, ["country=KP (북한) — 대상 아님"]

        # ── 2) 한국 도메인 ──
        matched_tld = next((t for t in self.kr_tlds if website.endswith(t)), None)
        # safety.extract_domain() 은 ASCII 도메인만 뽑는다. 그래서 '.한국' 같은
        # 한글 TLD 는 website 가 빈 문자열이 되고, kr_tlds 에 값이 있어도 위 줄에
        # 절대 걸리지 않았다. 피해자명 원문에서도 같은 목록으로 한 번 더 본다.
        # (전에는 여기서 '.kr' 하나만 하드코딩으로 봤다.)
        victim_tld = None
        if not matched_tld and victim.strip():
            victim_tail = victim.rstrip()
            victim_tld = next((t for t in self.kr_tlds if victim_tail.endswith(t)), None)
        if matched_tld:
            reasons.append(f"한국 도메인({matched_tld})")
            tier = _max_tier(tier, "strong")
        elif victim_tld:
            reasons.append(f"피해자명이 {victim_tld} 도메인")
            tier = _max_tier(tier, "strong")

        # ── 3) 한국 기업·기관명 ──
        for term, pat in self.conglomerates:
            if pat.search(name_blob):
                reasons.append(f"한국 기업명 '{term}'")
                tier = _max_tier(tier, "likely")
                break

        if tier in ("none", "review"):
            for term, pat in self.entities:
                if pat.search(name_blob):
                    reasons.append(f"한국 기관/지명 '{term}'")
                    tier = _max_tier(tier, "likely")
                    break

        # ── 4) 한글 포함 ──
        if _HANGUL_RE.search(record.victim or ""):
            reasons.append("피해자명에 한글 포함")
            tier = _max_tier(tier, "likely")

        # ── 5) 약한 신호 (설명문에만 존재) ──
        #
        # 2026-09-07. conglomerates 를 여기에 더했다. 전에는 기업명을 name_blob
        # (피해자·주소·업종) 에서만 찾아서, 피해자 칸이 빈 글은 제목에 대기업 이름이
        # 그대로 있어도 none 이 됐다. 랜섬 집계는 피해자 칸이 늘 차 있어 안 드러났는데,
        # 텔레그램 감시 채널과 포럼 킷이 가져오는 글은 회사 이름이 칸이 아니라 문장으로만
        # 있다. 「Samsung Electronics database」 같은 제목이 통째로 빠져나갔다.
        #
        # **등급은 review 로 둔다.** 글에서 이름을 봤다는 것이 그 회사가 피해자라는
        # 뜻은 아니다 — 파는 사람이 남의 이름을 대는 글도 있다. 사람이 볼 목록에는
        # 올리되 확정으로 세지 않는다. 문턱이 likely 인 쪽(알림)은 이 변화의 영향을 안 받는다.
        if tier == "none":
            # 설명문 안의 한국 도메인. 위 2) 는 `website` 칸만 보는데, 포럼·텔레그램
            # 게시물은 그 칸이 비고 도메인이 제목이나 본문에 글로만 있다.
            # 「treethink.kr full dump」 같은 제목이 통째로 빠져나갔다 (2026-09-07).
            m = self.kr_domain_re.search(full_blob)
            if m:
                reasons.append(f"설명문에 한국 도메인 '{m.group(0).lower()}' (검토 필요)")
                tier = "review"

            for term, pat in self.conglomerates + self.entities + self.weak:
                if tier != "none":
                    break
                if pat.search(full_blob):
                    reasons.append(f"설명문에 '{term}' 언급 (검토 필요)")
                    tier = "review"
                    break
            if tier == "none" and _HANGUL_RE.search(record.description or ""):
                reasons.append("설명문에 한글 포함 (검토 필요)")
                tier = "review"

        # ── 6) 제외 규칙 ──
        if tier != "none":
            for term, pat in self.exclude:
                # 북한 제외어만 exclude_north_korea 로 끌 수 있다.
                # koreatown·kia ora 같은 나머지 제외어는 스위치와 무관하게 항상 적용한다.
                if term in self.exclude_nk_terms and not self.exclude_nk:
                    continue
                if pat.search(full_blob):
                    # country=KR 처럼 강한 증거가 있으면 제외어가 있어도 유지
                    if tier == "confirmed":
                        reasons.append(f"제외어 '{term}' 감지되었으나 country=KR 이므로 유지")
                        break
                    return "none", 0, [f"제외어 매칭 '{term}'"]

        return tier, TIER_SCORE[tier], reasons

    def meets_threshold(self, tier: str) -> bool:
        try:
            return TIER_ORDER.index(tier) >= TIER_ORDER.index(self.min_tier)
        except ValueError:
            return False


def _max_tier(a: str, b: str) -> str:
    return a if TIER_ORDER.index(a) >= TIER_ORDER.index(b) else b
