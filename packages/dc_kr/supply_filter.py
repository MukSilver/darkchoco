"""
supply_filter.py — 공급망(supply chain) 위험 판별 엔진.

kr_filter.py 와 **독립된 두 번째 축**이다. 한국 기업이 직접 털리지 않아도,
그 기업이 쓰는 해외 벤더가 털리면 한국까지 번진다(MOVEit·SolarWinds·Snowflake 사례).
기존 구조는 country=KR 이 아니면 통째로 버려서 이 경로를 전부 놓치고 있었다.

4단계 등급:

  direct     (100) : 사용자가 vendors.json 에 등록한 실제 거래처 → 즉시 대응 대상
  critical    (80) : 글로벌 핵심 벤더 워치리스트(MFT·RMM·IdP·보안장비·반도체 장비 등)
  korea_ops   (65) : 국가는 해외지만 한국 법인/사업장으로 보이는 기업
  sector      (50) : 설명문·업종에 공급망 증폭 지표(MSP·3PL·파운드리 등)가 있는 기업
  none         (0) : 무관

★ 중요: 벤더명은 **피해 기업명·도메인·업종·설명문**에만 매칭한다.
  랜섬웨어 그룹명에는 절대 매칭하지 않는다 — 실제로 Barracuda, Titan, Nova 등은
  보안 벤더명이면서 동시에 랜섬웨어 그룹명이라 여기서 섞이면 전수 오탐이 난다.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

TIER_ORDER = ["none", "sector", "korea_ops", "critical", "direct"]
TIER_SCORE = {"none": 0, "sector": 50, "korea_ops": 65, "critical": 80, "direct": 100}
TIER_LABEL = {
    "direct": "직거래",
    "critical": "핵심벤더",
    "korea_ops": "한국진출",
    "sector": "업종위험",
    "none": "무관",
}

_DATA_PATH = Path(__file__).parent / "data" / "supply_keywords.json"
_KOREA_RE = re.compile(r"(?<![a-z])korea(n)?(?![a-z])", re.IGNORECASE)


# ─────────────────────────────────────────────────────────────
# 데이터 로드
# ─────────────────────────────────────────────────────────────

def _load_dataset() -> dict[str, Any]:
    try:
        with _DATA_PATH.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        log.error("공급망 키워드 파일 로드 실패(%s) — 공급망 판별이 비활성화됩니다.", exc)
        return {}


def load_vendors(root: Path) -> list[dict[str, Any]]:
    """vendors.json (사용자 소유 협력사 목록)을 읽는다. 없으면 빈 목록."""
    path = Path(root) / "vendors.json"
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        log.error("vendors.json 파싱 실패 — 무시하고 계속합니다: %s", exc)
        return []

    out: list[dict[str, Any]] = []
    for entry in data.get("vendors", []) or []:
        if not isinstance(entry, dict):
            continue
        names = [str(n).strip().lower() for n in (entry.get("names") or []) if str(n).strip()]
        domains = [
            str(d).strip().lower().lstrip(".").removeprefix("www.")
            for d in (entry.get("domains") or [])
            if str(d).strip()
        ]
        if not names and not domains:
            continue
        # 너무 짧은 이름은 오탐 폭탄이라 거른다
        names = [n for n in names if len(n) >= 4]
        out.append(
            {
                "name": str(entry.get("name") or names[0] if names else domains[0])[:120],
                "names": names,
                "domains": domains,
                "tier": str(entry.get("tier") or "")[:40],
                "note": str(entry.get("note") or "")[:300],
            }
        )
    log.info("vendors.json: 협력사 %d곳 로드", len(out))
    return out


def _compile_terms(terms: list[str]) -> list[tuple[str, re.Pattern[str]]]:
    """단어 경계 매칭 패턴. 'kla' 가 'oklahoma' 에 걸리지 않게 한다."""
    out: list[tuple[str, re.Pattern[str]]] = []
    for term in terms:
        term = str(term).strip().lower()
        if len(term) < 3:
            continue
        try:
            out.append(
                (term, re.compile(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", re.IGNORECASE))
            )
        except re.error:
            continue
    return out


# ─────────────────────────────────────────────────────────────
# 판별기
# ─────────────────────────────────────────────────────────────

class SupplyClassifier:
    def __init__(self, cfg: dict[str, Any] | None = None, root: Path | None = None):
        cfg = cfg or {}
        data = _load_dataset()

        # 카테고리별로 보관 — 어느 계층 벤더인지 근거에 표시하기 위함
        self.vendor_groups: dict[str, list[tuple[str, re.Pattern[str]]]] = {}
        for category, terms in (data.get("critical_vendors", {}) or {}).items():
            if category.startswith("_") or not isinstance(terms, list):
                continue
            compiled = _compile_terms(terms)
            if compiled:
                self.vendor_groups[category] = compiled

        extra = cfg.get("extra_critical_vendors", []) or []
        if extra:
            self.vendor_groups["user_added"] = _compile_terms(extra)

        self.indicators = _compile_terms(
            (data.get("supply_chain_indicators", {}) or {}).get("terms", [])
        )
        self.korea_hints = _compile_terms(
            (data.get("korea_presence_hints", {}) or {}).get("terms", [])
        )
        self.excludes = _compile_terms(
            list((data.get("exclude", {}) or {}).get("terms", []))
            + list(cfg.get("exclude_keywords", []) or [])
        )

        self.vendors = load_vendors(root) if root else []

        self.min_tier = cfg.get("min_tier_to_store", "sector")
        if self.min_tier not in TIER_ORDER:
            self.min_tier = "sector"

        self.enabled = bool(cfg.get("enabled", True))

    # ── 판별 ────────────────────────────────────────────────
    def classify(self, record: Any) -> tuple[str, int, list[str]]:
        """(tier, score, reasons) 반환. 그룹명은 절대 참조하지 않는다."""
        if not self.enabled:
            return "none", 0, []

        victim = (record.victim or "").lower()
        website = (record.website or "").lower()
        sector = (record.sector or "").lower()
        desc = (record.description or "").lower()
        country = (record.country or "").upper()

        # ★ 그룹명(record.group)은 의도적으로 제외한다.
        name_blob = f"{victim} {website}"
        wide_blob = f"{victim} {website} {sector} {desc}"

        for term, pat in self.excludes:
            if pat.search(name_blob):
                return "none", 0, [f"공급망 제외어 '{term}'"]

        reasons: list[str] = []

        # ── 1) 우리 회사 실제 거래처 (최우선) ──
        hit = self._match_vendor(victim, website)
        if hit:
            label = f"직거래 협력사 '{hit['name']}'"
            if hit.get("tier"):
                label += f" [{hit['tier']}]"
            reasons.append(label)
            if hit.get("note"):
                reasons.append(f"영향: {hit['note']}")
            return "direct", TIER_SCORE["direct"], reasons

        # ── 2) 글로벌 핵심 벤더 ──
        for category, patterns in self.vendor_groups.items():
            for term, pat in patterns:
                if pat.search(name_blob):
                    reasons.append(f"글로벌 핵심 벤더 '{term}' ({_category_ko(category)})")
                    return "critical", TIER_SCORE["critical"], reasons

        # ── 3) 해외 기업의 한국 법인/사업장 ──
        #     KR 축에서 이미 잡히는 건 제외 — 여기선 country 가 KR 이 아닌 것만 본다.
        if country and country != "KR":
            if _KOREA_RE.search(victim):
                reasons.append(f"해외({country}) 기업이지만 사명에 Korea 포함 — 한국 법인/사업장 가능성")
                return "korea_ops", TIER_SCORE["korea_ops"], reasons
            for term, pat in self.korea_hints:
                if pat.search(wide_blob):
                    reasons.append(f"해외({country}) 기업의 한국 거점 단서 '{term}'")
                    return "korea_ops", TIER_SCORE["korea_ops"], reasons

        # ── 4) 공급망 증폭 업종 ──
        for term, pat in self.indicators:
            if pat.search(wide_blob):
                reasons.append(f"공급망 증폭 업종 지표 '{term}'")
                return "sector", TIER_SCORE["sector"], reasons

        return "none", 0, []

    def _match_vendor(self, victim: str, website: str) -> dict[str, Any] | None:
        """도메인 우선 정확 매칭 → 회사명 단어경계 매칭."""
        for vendor in self.vendors:
            for domain in vendor["domains"]:
                if website == domain or website.endswith("." + domain):
                    return vendor
            for name in vendor["names"]:
                pattern = rf"(?<![a-z0-9]){re.escape(name)}(?![a-z0-9])"
                if re.search(pattern, victim, re.IGNORECASE):
                    return vendor
        return None

    def meets_threshold(self, tier: str) -> bool:
        try:
            return TIER_ORDER.index(tier) >= TIER_ORDER.index(self.min_tier)
        except ValueError:
            return False


def _category_ko(key: str) -> str:
    return {
        "managed_file_transfer": "파일전송 솔루션",
        "remote_access_rmm": "원격관리/RMM",
        "identity_pam": "계정·인증",
        "network_security_appliance": "네트워크·보안장비",
        "cloud_data_platform": "클라우드·데이터",
        "erp_business_software": "ERP·업무SW",
        "dev_supply_chain": "개발 공급망",
        "communications_saas": "커뮤니케이션 SaaS",
        "msp_it_services": "MSP·IT서비스",
        "payroll_hr_finance": "급여·금융인프라",
        "logistics_freight": "물류·포워딩",
        "semiconductor_supply": "반도체 공급망",
        "automotive_tier1": "자동차 1차 협력사",
        "chemical_materials": "화학·소재",
        "healthcare_pharma_supply": "의료·제약 유통",
        "user_added": "사용자 추가",
    }.get(key, key)
