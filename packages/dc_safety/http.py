"""안전한 HTTP 클라이언트. kr-leak-alarm 에서 왔습니다.

셋 중 가장 잘 되어 있어 이것을 표준으로 삼았습니다.

  · HTTPS 가 아니면 차단합니다
  · 허용목록에 없는 호스트는 차단합니다 — 실수로 엉뚱한 곳에 붙는 것을 막습니다
  · 쿠키를 전부 거부합니다 — 추적당하지 않습니다
  · 응답 크기와 Content-Type 을 확인합니다

새 데이터 출처를 붙이려면 ALLOWED_HOSTS 에 먼저 넣어야 합니다.
그 자체가 검토 지점입니다.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any
from urllib.parse import urlparse

import requests

log = logging.getLogger(__name__)

# ★ 이 목록에 없는 호스트로는 어떤 경우에도 요청하지 않는다.
ALLOWED_HOSTS: frozenset[str] = frozenset(
    {
        "api.ransomware.live",
        "www.ransomware.live",
        "ransomware.live",
        "www.ransomlook.io",
        "ransomlook.io",
        "ransomfeed.it",
        "www.ransomfeed.it",
        "raw.githubusercontent.com",  # ransomwatch 아카이브(선택)
    }
)

ALLOWED_CONTENT_TYPES = (
    "application/json",
    "text/json",
    "application/xml",
    "text/xml",
    "application/rss+xml",
    "text/plain",
)

DEFAULT_MAX_BYTES = 32 * 1024 * 1024  # 32 MiB


class FetchError(RuntimeError):
    pass


class BlockedHostError(FetchError):
    pass


class HttpStatusError(FetchError):
    """4xx/5xx 응답. status 로 재시도 여부를 판단한다."""

    def __init__(self, status: int, message: str = ""):
        self.status = int(status)
        super().__init__(message or f"HTTP {status}")


class NotFoundError(HttpStatusError):
    """404. ransomware.live 는 '검색 결과 없음'도 404 로 응답하므로
    호출부에서 오류가 아닌 '빈 결과'로 해석할 수 있어야 한다."""

    def __init__(self, message: str = "HTTP 404 (결과 없음)"):
        super().__init__(404, message)


def _check_host(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise BlockedHostError(f"HTTPS 가 아닌 요청 차단: {parsed.scheme}://…")
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_HOSTS:
        raise BlockedHostError(
            f"허용목록에 없는 호스트 차단: {host!r}\n"
            "  packages/dc_safety/http.py 의 ALLOWED_HOSTS 를 검토 후 추가하십시오."
        )
    return host


class SafeHttpClient:
    def __init__(self, network_cfg: dict[str, Any] | None = None):
        cfg = network_cfg or {}
        self.timeout = int(cfg.get("timeout_seconds", 30))
        self.max_bytes = int(cfg.get("max_response_bytes", DEFAULT_MAX_BYTES))
        self.retries = max(0, int(cfg.get("retries", 2)))
        self.user_agent = cfg.get("user_agent") or "Kr-Leak-alarm/1.0"

        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept": "application/json, application/xml;q=0.9, text/plain;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "close",
            }
        )
        # 쿠키를 보관하지 않는다 — 추적/상태 오염 방지
        self._session.cookies.set_policy(_RejectAllCookies())

    def close(self) -> None:
        try:
            self._session.close()
        except Exception:
            pass

    def __enter__(self) -> "SafeHttpClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ── 저수준 ──────────────────────────────────────────────
    def get_bytes(self, url: str, *, extra_headers: dict[str, str] | None = None) -> bytes:
        _check_host(url)

        last_err: Exception | None = None
        for attempt in range(self.retries + 1):
            if attempt:
                backoff = min(2 ** attempt, 15)
                log.info("재시도 %d/%d — %.0fs 대기", attempt, self.retries, backoff)
                time.sleep(backoff)
            try:
                return self._get_once(url, extra_headers)
            except BlockedHostError:
                raise  # 보안 차단은 재시도하지 않는다
            except HttpStatusError as exc:
                # ★ 4xx 는 영구적 실패다. 429(레이트리밋)만 재시도할 가치가 있다.
                #   404 를 3번씩 재시도하면 10초를 버리고 API 를 괴롭히기만 한다.
                if 400 <= exc.status < 500 and exc.status != 429:
                    raise
                last_err = exc
                log.warning("요청 실패(%s): %s", urlparse(url).path, exc)
            except (requests.RequestException, FetchError) as exc:
                last_err = exc
                log.warning("요청 실패(%s): %s", urlparse(url).path, exc)
        raise FetchError(f"{self.retries + 1}회 시도 모두 실패: {last_err}")

    def _get_once(self, url: str, extra_headers: dict[str, str] | None) -> bytes:
        resp = self._session.get(
            url,
            timeout=self.timeout,
            stream=True,
            allow_redirects=False,  # 리다이렉트를 수동 검증
            headers=extra_headers or {},
        )

        # 리다이렉트는 허용목록 재검증 후 1회만 따라간다
        hops = 0
        while resp.is_redirect or resp.is_permanent_redirect:
            hops += 1
            if hops > 3:
                resp.close()
                raise FetchError("리다이렉트 횟수 초과")
            location = resp.headers.get("Location", "")
            resp.close()
            if not location:
                raise FetchError("Location 헤더 없는 리다이렉트")
            if location.startswith("/"):
                p = urlparse(url)
                location = f"{p.scheme}://{p.netloc}{location}"
            _check_host(location)  # ← 여기서 목록 밖이면 차단
            url = location
            resp = self._session.get(
                url,
                timeout=self.timeout,
                stream=True,
                allow_redirects=False,
                headers=extra_headers or {},   # 최초 요청과 같은 헤더를 유지한다
            )

        try:
            if resp.status_code == 404:
                raise NotFoundError()
            if resp.status_code == 429:
                raise HttpStatusError(429, "429 Rate limit — 잠시 후 재시도")
            if resp.status_code >= 400:
                raise HttpStatusError(resp.status_code)

            ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if ctype and not any(ctype.startswith(a) for a in ALLOWED_CONTENT_TYPES):
                raise FetchError(f"허용되지 않은 Content-Type 차단: {ctype!r}")

            declared = resp.headers.get("Content-Length")
            if declared and declared.isdigit() and int(declared) > self.max_bytes:
                raise FetchError(f"응답 크기 상한 초과(선언값 {declared}B)")

            buf = bytearray()
            for chunk in resp.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                buf.extend(chunk)
                if len(buf) > self.max_bytes:
                    raise FetchError(f"응답 크기 상한 {self.max_bytes}B 초과 — 스트림 중단")
            return bytes(buf)
        finally:
            resp.close()

    # ── 고수준 ──────────────────────────────────────────────
    def get_json(self, url: str) -> Any:
        raw = self.get_bytes(url)
        if not raw.strip():
            raise FetchError("빈 응답")
        try:
            return json.loads(raw.decode("utf-8", errors="replace"))
        except json.JSONDecodeError as exc:
            raise FetchError(f"JSON 파싱 실패: {exc}") from exc

    def get_text(self, url: str) -> str:
        return self.get_bytes(url).decode("utf-8", errors="replace")


class _RejectAllCookies:
    """모든 쿠키를 거부하는 최소 정책 객체."""

    def set_ok(self, cookie: Any, request: Any) -> bool:  # noqa: D102
        return False

    def return_ok(self, cookie: Any, request: Any) -> bool:  # noqa: D102
        return False

    def domain_return_ok(self, domain: Any, request: Any) -> bool:  # noqa: D102
        return False

    def path_return_ok(self, path: Any, request: Any) -> bool:  # noqa: D102
        return False

    netscape = True
    rfc2965 = False
    hide_cookie2 = False
