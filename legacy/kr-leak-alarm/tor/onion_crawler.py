"""
tor/onion_crawler.py — [위험 모듈] .onion DLS 직접 수집.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠  이 모듈은 랜섬웨어 조직이 운영하는 서버에 직접 접속합니다.
   호스트 PC 에서 실행하지 마십시오. 실행 전 3중 게이트를 모두 통과해야 합니다.

     게이트 1  config.json → tor.enabled = true
     게이트 2  실행 시 --i-understand-the-risk 플래그
     게이트 3  VMware 가상머신에서 실행 중일 것 (tor.require_vmware)

   추가로 이 모듈은 다음을 강제합니다:
     · .onion 호스트로만 요청 (clearnet 요청 시도 시 즉시 차단)
     · 모든 트래픽은 SOCKS5h 프록시 경유 — DNS 도 Tor 가 처리(로컬 DNS 유출 없음)
     · 응답 크기 상한 / 타임아웃 / Content-Type 검사
     · HTML 은 텍스트만 추출하고 즉시 폐기 (기본값). 파일 다운로드·실행 절대 없음
     · 링크 추적(crawl depth) 없음 — 설정된 목록 페이지만 조회
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

import html
import logging
import re
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from collector.config import resolve_path
from collector.export import export
from collector.kr_filter import TIER_SCORE, KrClassifier
from collector.safety import TorGateError, assert_tor_allowed, defang_url, sanitize_text
from collector.sources.base import LeakRecord, parse_timestamp
from collector.store import Store
from collector.supply_filter import TIER_SCORE as SUPPLY_SCORE
from collector.supply_filter import SupplyClassifier

log = logging.getLogger(__name__)

MAX_BYTES = 4 * 1024 * 1024          # onion 페이지 4MiB 상한
ALLOWED_CTYPES = ("text/html", "application/xhtml+xml", "text/plain", "application/json")

_SCRIPT_RE = re.compile(r"(?is)<(script|style|noscript|iframe|object|embed|svg)\b.*?</\1\s*>")
_TAG_RE = re.compile(r"(?s)<[^>]{0,500}?>")
_WS_RE = re.compile(r"\s{2,}")


# ─────────────────────────────────────────────────────────────
# 프록시 점검
# ─────────────────────────────────────────────────────────────

def _check_socks_reachable(proxy_url: str) -> tuple[bool, str]:
    parsed = urlparse(proxy_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 9050
    if host not in ("127.0.0.1", "localhost", "::1"):
        return False, f"SOCKS 프록시는 로컬호스트여야 합니다: {host}"
    try:
        with socket.create_connection((host, port), timeout=5):
            return True, f"{host}:{port} 연결 확인"
    except OSError as exc:
        return False, f"{host}:{port} 연결 실패 ({exc}) — Tor 데몬/Tor Browser 가 떠 있는지 확인하세요."


def _build_session(proxy_url: str) -> Any:
    import requests

    try:
        import socks  # noqa: F401  (PySocks 존재 확인)
    except ImportError as exc:
        raise RuntimeError(
            "PySocks 가 없습니다. VM 안에서 `pip install -r requirements-tor.txt` 를 실행하세요."
        ) from exc

    sess = requests.Session()
    sess.proxies = {"http": proxy_url, "https": proxy_url}
    sess.headers.update({
        # 브라우저 지문을 흉내내지 않고, 자동화임을 숨기지도 않는다
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:115.0) Gecko/20100101 Firefox/115.0",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "close",
        "DNT": "1",
    })
    sess.max_redirects = 2
    return sess


# ─────────────────────────────────────────────────────────────
# 안전 페치
# ─────────────────────────────────────────────────────────────

def _fetch_onion(sess: Any, url: str, timeout: int = 90) -> str:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()

    # ★ .onion 이외 호스트로는 절대 요청하지 않는다 (clearnet 유출·피벗 차단)
    if not hostname.endswith(".onion"):
        raise ValueError(f".onion 이 아닌 호스트 차단: {hostname!r}")
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"허용되지 않은 스킴: {parsed.scheme!r}")

    resp = sess.get(url, timeout=timeout, stream=True, allow_redirects=False)
    try:
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code}")

        ctype = (resp.headers.get("Content-Type") or "text/html").split(";")[0].strip().lower()
        if not any(ctype.startswith(a) for a in ALLOWED_CTYPES):
            raise RuntimeError(f"허용되지 않은 Content-Type 차단: {ctype!r}")

        buf = bytearray()
        for chunk in resp.iter_content(65536):
            if not chunk:
                continue
            buf.extend(chunk)
            if len(buf) > MAX_BYTES:
                raise RuntimeError("응답 크기 상한 초과 — 스트림 중단")
        return bytes(buf).decode("utf-8", errors="replace")
    finally:
        resp.close()


def html_to_text(raw_html: str) -> str:
    """스크립트/스타일을 통째로 제거한 뒤 태그를 벗겨 평문만 남긴다."""
    text = _SCRIPT_RE.sub(" ", raw_html)
    text = re.sub(r"(?is)<br\s*/?>|</(p|div|li|tr|h[1-6])\s*>", "\n", text)
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = _WS_RE.sub(" ", text)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


# ─────────────────────────────────────────────────────────────
# 진입점
# ─────────────────────────────────────────────────────────────

def run_tor_scan(cfg: dict[str, Any], *, acknowledged: bool, dry_run: bool = False) -> int:
    tor_cfg = cfg.get("tor", {}) or {}

    # ── 3중 게이트 ──
    try:
        env = assert_tor_allowed(cfg, acknowledged)
    except TorGateError as exc:
        print("\n" + "=" * 72)
        print("  ⛔ Tor 직접 크롤링이 차단되었습니다.")
        print("=" * 72)
        print(f"\n{exc}\n")
        return 3

    print("\n" + "=" * 72)
    print("  ⚠ Tor 직접 크롤링 모드 — 랜섬웨어 인프라에 직접 접속합니다.")
    print("=" * 72)
    print(f"  실행 환경: {env['system']} / {env['vendor']} / {env['product']}")
    print(f"  VMware 확인: {env['is_vmware']}")

    proxy = tor_cfg.get("socks_proxy", "socks5h://127.0.0.1:9050")
    ok, detail = _check_socks_reachable(proxy)
    print(f"  SOCKS 프록시: {detail}")
    if not ok:
        return 4

    targets = [t for t in (tor_cfg.get("targets") or []) if isinstance(t, dict)]
    print(f"  대상 페이지: {len(targets)}개")
    for t in targets:
        print(f"    · {t.get('group','?')} → {defang_url(t.get('url',''))}")

    if dry_run:
        print("\n  --dry-run: 게이트 검사만 수행하고 종료합니다.\n")
        return 0
    if not targets:
        print("\n  config.json 의 tor.targets 가 비어 있습니다. "
              '형식: [{"group":"이름","url":"http://xxx.onion/"}]\n')
        return 0

    try:
        sess = _build_session(proxy)
    except RuntimeError as exc:
        print(f"\n  {exc}\n")
        return 5

    # main.py 의 run 경로와 같은 두 축을 쓴다. 전에는 여기서 한국 축만 돌려서
    # tor-scan 을 한 번 돌리면 공급망 판정이 빠진 산출물이 나왔다.
    classifier = KrClassifier(cfg.get("kr_detection", {}))
    supply = SupplyClassifier(cfg.get("supply_detection", {}), root=Path(cfg["_root"]))
    delay = max(2, int(tor_cfg.get("delay_seconds", 5)))
    save_raw = bool(tor_cfg.get("save_raw_html"))
    capture_dir = Path(cfg["_root"]) / "tor" / "captures"

    records: list[LeakRecord] = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for idx, target in enumerate(targets):
        url = str(target.get("url", ""))
        group = sanitize_text(target.get("group") or urlparse(url).hostname or "unknown", 100)
        if idx:
            time.sleep(delay)
        try:
            body = _fetch_onion(sess, url)
        except Exception as exc:
            log.error("[tor] %s 실패: %s", group, exc)
            continue

        text = html_to_text(body)
        log.info("[tor] %s → %d자 추출", group, len(text))

        if save_raw:
            # 원문 저장은 명시적 opt-in. .gitignore 로 커밋이 차단되어 있음.
            capture_dir.mkdir(parents=True, exist_ok=True)
            safe_name = re.sub(r"[^a-z0-9_-]+", "_", group.lower())[:60]
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            (capture_dir / f"{safe_name}_{stamp}.txt").write_text(text, encoding="utf-8")

        for line in _candidate_lines(text):
            records.append(
                LeakRecord(
                    victim=line,
                    group=group,
                    country="",
                    sector="",
                    website=line,
                    description="",
                    published="",
                    discovered=parse_timestamp(now_iso),
                    post_url=url,
                    source=f"tor:{group}",
                ).finalize()
            )

    # ── 두 축 판별 후 저장 (main.py 와 같은 OR 규칙) ──
    matched = []
    kr_hits = supply_hits = 0
    for rec in records:
        tier, score, reasons = classifier.classify(rec)
        rec.kr_tier, rec.kr_score, rec.kr_reasons = tier, score, reasons

        s_tier, s_score, s_reasons = supply.classify(rec)
        rec.supply_tier, rec.supply_score, rec.supply_reasons = s_tier, s_score, s_reasons

        kr_ok = classifier.meets_threshold(tier)
        supply_ok = supply.enabled and supply.meets_threshold(s_tier)
        if kr_ok:
            kr_hits += 1
        if supply_ok:
            supply_hits += 1
        if kr_ok or supply_ok:
            matched.append(rec)

    print(f"\n  후보 {len(records)}건 → 저장 대상 {len(matched)}건 "
          f"(한국 관련 {kr_hits} · 공급망 {supply_hits}, 중복 포함)")

    min_score = TIER_SCORE.get(classifier.min_tier, 60)
    # export 의 min_supply_score 기본값은 999 다. 안 넘기면 DB 에 이미 들어 있던
    # 공급망 건까지 대시보드 산출물에서 통째로 빠진다. main.py 와 같은 값을 넘긴다.
    min_supply = SUPPLY_SCORE.get(supply.min_tier, 50) if supply.enabled else 10_000
    with Store(resolve_path(cfg, "database")) as store:
        newly = store.upsert_many(matched)
        export(store, resolve_path(cfg, "web_data_dir"),
               min_score=min_score, min_supply_score=min_supply)
    print(f"  신규 {len(newly)}건 저장 완료.\n")
    return 0


_NOISE = re.compile(
    r"^(home|blog|news|contact|about|faq|leaks?|posts?|search|login|next|prev|page \d+|"
    r"published|updated|copyright|all rights reserved|\d{1,4}([-/.]\d{1,2}){0,2})$",
    re.IGNORECASE,
)


def _candidate_lines(text: str) -> list[str]:
    """추출한 평문에서 '회사명일 법한' 줄만 골라낸다. 보수적으로 필터링."""
    out: list[str] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip(" \t-–—•|·")
        if not (3 <= len(line) <= 120):
            continue
        if _NOISE.match(line):
            continue
        if line.count(" ") > 12:      # 문장일 가능성이 큼
            continue
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(sanitize_text(line, 120))
    return out[:800]
