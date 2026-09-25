"""
sources/ransomware_live.py — ransomware.live v2 공개 API 어댑터 (1차 소스).

이 소스는 country 필드(ISO-2)를 제공하므로 KR 판별 정확도가 가장 높다.
API 는 HTTPS 이며 인증이 필요 없다. .onion 에는 우리가 접속하지 않는다 —
ransomware.live 가 이미 수집한 결과만 받아온다.

응답 필드: activity, country, data_size, description, discovered,
           group_name, post_title, post_url, published, ransom, website
"""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable
from urllib.parse import quote

from ..http_client import NotFoundError
from .base import LeakRecord, Source, parse_timestamp

log = logging.getLogger(__name__)

from dc_ransomfeed import RANSOMWARE_LIVE as BASE   # packages/dc_ransomfeed


class RansomwareLiveSource(Source):
    name = "ransomware.live"

    def __init__(self, client, cfg):
        super().__init__(client, cfg)
        self._last_call_failed = False   # 직전 호출이 실패했는지 (회로 차단기용)
        self.rate_limited = False        # 레이트리밋으로 판단되는 상태인지

    def fetch(self) -> Iterable[LeakRecord]:
        modes = self.cfg.get("modes") or ["country", "recent"]
        records: list[LeakRecord] = []

        core_ok = 0      # 핵심 조회(국가/최근)가 몇 개나 성공했나
        core_tried = 0

        if "country" in modes:
            for code in self.cfg.get("country_codes") or ["KR"]:
                code = str(code).strip().upper()[:2]
                if not code.isalpha():
                    log.warning("잘못된 국가 코드 무시: %r", code)
                    continue
                core_tried += 1
                got = self._fetch_country(code)
                records.extend(got)
                if not self._last_call_failed:
                    core_ok += 1

        if "recent" in modes:
            core_tried += 1
            got = self._fetch_recent()
            records.extend(got)
            if not self._last_call_failed:
                core_ok += 1

        # ── ★ 회로 차단기 ──────────────────────────────────────
        # 핵심 조회가 전부 실패했다면 서버가 우리를 막고 있다는 뜻이다.
        # 이 상태에서 벤더 검색 수십 건을 더 쏘면 차단만 길어진다.
        if "vendor_search" in modes:
            if core_tried and core_ok == 0:
                log.warning(
                    "[%s] 핵심 조회가 모두 실패해 벤더 검색을 건너뜁니다. "
                    "(레이트리밋일 가능성이 높습니다 — 요청을 더 보내지 않습니다)",
                    self.name,
                )
                self.rate_limited = True
            elif self.cfg.get("_skip_vendor_search"):
                log.info("[%s] 벤더 검색 비활성화됨 (--no-vendor-search)", self.name)
            else:
                records.extend(self._fetch_vendor_slice())

        return records

    # ── 벤더 순회 검색 ─────────────────────────────────────────
    #  핵심 벤더는 '최근 100건' 피드에 안 잡힐 수 있다(몇 주 전 사고).
    #  매 실행마다 목록의 일부만 검색하고, 실행마다 다른 구간을 돌려
    #  레이트리밋 없이 며칠에 걸쳐 전체를 훑는다.
    def _fetch_vendor_slice(self) -> list[LeakRecord]:
        terms: list[str] = [str(t).strip() for t in (self.cfg.get("vendor_terms") or []) if str(t).strip()]
        if not terms:
            return []

        per_run = max(1, int(self.cfg.get("vendor_search_per_run", 8)))
        delay = max(0.0, float(self.cfg.get("vendor_search_delay_seconds", 1.5)))
        cursor = int(self.cfg.get("_vendor_cursor", 0))

        terms = sorted(set(terms))
        total = len(terms)
        start = cursor % total
        slice_ = [terms[(start + i) % total] for i in range(min(per_run, total))]
        self.next_vendor_cursor = (start + len(slice_)) % total

        log.info(
            "[%s] 벤더 순회 검색 %d/%d개 (커서 %d → %d)",
            self.name, len(slice_), total, start, self.next_vendor_cursor,
        )

        out: list[LeakRecord] = []
        seen: set[str] = set()
        empty = failed = consecutive_fail = 0

        for idx, term in enumerate(slice_):
            # ★ 연속 3회 실패하면 즉시 중단한다. 차단당한 상태에서 계속 쏘면
            #    차단 기간만 길어진다 (어제 이 방어가 없어서 IP 가 막혔다).
            if consecutive_fail >= 3:
                log.warning("[%s] 벤더 검색 연속 실패 — 남은 %d개를 건너뜁니다.",
                            self.name, len(slice_) - idx)
                self.rate_limited = True
                self.next_vendor_cursor = (start + idx) % total   # 실패 지점부터 재개
                break
            if idx:
                time.sleep(delay)
            try:
                payload = self.client.get_json(f"{BASE}/searchvictims/{quote(term, safe='')}")
                consecutive_fail = 0
            except NotFoundError:
                # ★ ransomware.live 는 '검색 결과 없음'을 404 로 응답한다.
                #   벤더 대부분은 피해자 목록에 없는 게 정상이므로 오류가 아니다.
                empty += 1
                continue
            except Exception as exc:
                failed += 1
                consecutive_fail += 1
                log.debug("[%s] 벤더 검색 오류(%s): %s", self.name, term, exc)
                continue

            for item in _as_list(payload):
                rec = self._to_record(item)
                key = hashlib.sha256(f"{rec.group_key}{rec.victim_key}".encode()).hexdigest()
                if key in seen:
                    continue
                seen.add(key)
                out.append(rec)

        # 개별 실패는 로그를 도배하지 않고 한 줄로 요약한다
        log.info(
            "[%s] 벤더 검색 완료 — 결과 %d건 (조회 %d개 중 해당없음 %d · 오류 %d)",
            self.name, len(out), len(slice_), empty, failed,
        )
        if failed:
            self.note_error(f"벤더 검색 {failed}/{len(slice_)}개 오류")
        return out

    # ── 국가 단위 조회: KR 태깅된 건을 확실히 잡는다 ────────────
    def _fetch_country(self, code: str) -> list[LeakRecord]:
        url = f"{BASE}/countryvictims/{code}"
        self._last_call_failed = False
        try:
            payload = self.client.get_json(url)
        except NotFoundError:
            # 이 엔드포인트가 404 라는 건 결과 없음이 아니라 차단 신호에 가깝다
            self._last_call_failed = True
            self.note_error(f"countryvictims/{code}: 404")
            log.error("[%s] countryvictims/%s → 404. 정상이라면 수백 건이 나와야 합니다.", self.name, code)
            return []
        except Exception as exc:
            self._last_call_failed = True
            self.note_error(f"countryvictims/{code}: {exc}")
            log.error("[%s] 국가 조회 실패(%s): %s", self.name, code, exc)
            return []
        items = _as_list(payload)
        log.info("[%s] countryvictims/%s → %d건", self.name, code, len(items))
        return [self._to_record(it) for it in items]

    # ── 최근 전체 조회: country 가 비어 있는 한국 기업을 도메인/키워드로 잡는다 ──
    def _fetch_recent(self) -> list[LeakRecord]:
        self._last_call_failed = False
        try:
            payload = self.client.get_json(f"{BASE}/recentvictims")
        except NotFoundError as exc:
            # 이 엔드포인트는 항상 결과가 있어야 하므로 404 는 진짜 이상 신호다
            self._last_call_failed = True
            self.note_error(f"recentvictims: {exc} (레이트리밋 또는 일시 장애)")
            log.error("[%s] 최근 조회 404 — 레이트리밋 가능성이 높습니다.", self.name)
            return []
        except Exception as exc:
            self._last_call_failed = True
            self.note_error(f"recentvictims: {exc}")
            log.error("[%s] 최근 조회 실패: %s", self.name, exc)
            return []

        items = _as_list(payload)
        lookback = int(self.cfg.get("recent_lookback_days", 30))
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback)

        out: list[LeakRecord] = []
        for it in items:
            rec = self._to_record(it)
            stamp = rec.discovered or rec.published
            if stamp:
                try:
                    if datetime.fromisoformat(stamp) < cutoff:
                        continue
                except ValueError:
                    pass
            out.append(rec)
        log.info("[%s] recentvictims → %d건 (최근 %d일 %d건)", self.name, len(items), lookback, len(out))
        return out

    def _to_record(self, item: dict[str, Any]) -> LeakRecord:
        """★ 엔드포인트마다 필드 이름이 다르므로 양쪽을 모두 받아준다.

            /countryvictims/<code>  →  post_title · group_name · website · post_url · published
            /recentvictims          →  victim     · group      · domain  · claim_url · attackdate

        예전에는 post_title/website/post_url 만 읽어서, recentvictims 로 들어온 건은
        도메인과 원문 URL 이 통째로 비었다. 그러면 '.kr 도메인' 판별이 동작하지 않아
        country 태그가 없는 한국 기업을 놓치게 된다.
        """
        if not isinstance(item, dict):
            item = {}

        def pick(*keys: str) -> Any:
            for key in keys:
                val = item.get(key)
                if val:
                    return val
            return ""

        return LeakRecord(
            victim=pick("post_title", "victim", "name"),
            group=pick("group_name", "group"),
            country=pick("country"),
            sector=pick("activity", "sector"),
            website=pick("website", "domain", "url"),
            description=pick("description"),
            published=parse_timestamp(pick("published", "attackdate", "date")),
            discovered=parse_timestamp(pick("discovered", "attackdate")),
            post_url=pick("post_url", "claim_url", "link"),
            source=self.name,
            # 응답에 있는데 여태 안 읽던 둘이다. 머리 주석의 필드 목록에도 적혀 있다.
            data_size=str(pick("data_size") or ""),
            ransom=str(pick("ransom") or ""),
        ).finalize()


def _as_list(payload: Any) -> list[dict[str, Any]]:
    """API 가 list 또는 {'data':[...]} 를 반환하는 경우를 모두 처리."""
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("data", "victims", "results", "items"):
            val = payload.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
    return []
