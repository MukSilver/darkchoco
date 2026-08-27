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
        self.conglomerates = _compile_boundary(kw["conglomerates"] + extra)
        self.entities = _compile_boundary(kw["entities"])
        self.weak = _compile_boundary(kw["weak_signals"])
        self.exclude = _compile_boundary(kw["exclude"] + excl)

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
        if matched_tld:
            reasons.append(f"한국 도메인({matched_tld})")
            tier = _max_tier(tier, "strong")
        elif f" {victim}".rstrip().endswith(".kr"):
            reasons.append("피해자명이 .kr 도메인")
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
        if tier == "none":
            for term, pat in self.entities + self.weak:
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
                if pat.search(full_blob):
                    # country=KR 처럼 강한 증거가 있으면 제외어가 있어도 유지
                    if tier == "confirmed":
                        reasons.append(f"제외어 '{term}' 감지되었으나 country=KR 이므로 유지")
                        break
                    if self.exclude_nk:
                        return "none", 0, [f"제외어 매칭 '{term}'"]

        return tier, TIER_SCORE[tier], reasons

    def meets_threshold(self, tier: str) -> bool:
        try:
            return TIER_ORDER.index(tier) >= TIER_ORDER.index(self.min_tier)
        except ValueError:
            return False


def _max_tier(a: str, b: str) -> str:
    return a if TIER_ORDER.index(a) >= TIER_ORDER.index(b) else b
