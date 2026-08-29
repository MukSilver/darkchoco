"""속도 제한을 지키는 가져오기 계층.

dls-observatory 의 Fetcher 와 kr-leak-alarm 의 SafeHttpClient 를 겹쳐
놓으면, 전자는 출처별 간격 조절이 있고 후자는 허용목록 차단이 있습니다.
둘 다 필요하므로 SafeHttpClient 위에 간격 조절을 얹었습니다.

같은 데이터를 두 앱이 따로 받던 문제는 캐시로 줄입니다. 같은 주소를
짧은 시간 안에 다시 부르면 받아 둔 것을 돌려줍니다.
"""

from __future__ import annotations

import json
import time
from typing import Any

from dc_safety import NotFoundError, SafeHttpClient

# 출처별 최소 간격(초). 상대 서버를 힘들게 하지 않기 위한 값입니다.
# 실측으로 알아낸 값입니다. dls-observatory 가 대량 엔드포인트에서
# 1req/분/엔드포인트 를 확인했습니다 (apps/dls-observatory/sources.py:174).
# 그보다 빠르게 치면 막힙니다. kr-leak-alarm 은 어제 실제로 IP 가 막혔습니다
# (apps/kr-leak-alarm/collector/sources/ransomware_live.py:110).
#
# 지금 이 Fetcher 를 쓰는 앱은 없습니다. 두 앱 모두 각자 판을 쓰고 여기서는
# 주소 상수만 가져갑니다. 새로 쓸 때를 위해 값만 실측에 맞춰 둡니다.
THROTTLE = {
    "ransomware.live": 62.0,
    "ransomlook.io": 1.5,
    "ransomfeed.it": 2.0,
}

DEFAULT_GAP = 1.0
CACHE_TTL = 300.0          # 5분. 두 앱이 연달아 같은 것을 받는 것을 막습니다.


def _key_for(url: str) -> str:
    for host in THROTTLE:
        if host in url:
            return host
    return "기타"


class Fetcher:
    """출처별 간격을 지키고 짧게 캐시합니다.

        f = Fetcher()
        groups = f.get_json(rl_groups())
    """

    def __init__(self, client: SafeHttpClient | None = None,
                 cache_ttl: float = CACHE_TTL, verbose: bool = False):
        self._client = client or SafeHttpClient()
        self._owns = client is None
        self._last: dict[str, float] = {}
        self._cache: dict[str, tuple[float, Any]] = {}
        self._ttl = cache_ttl
        self.verbose = verbose

    def close(self) -> None:
        if self._owns:
            self._client.close()

    def __enter__(self) -> "Fetcher":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _wait(self, url: str) -> None:
        key = _key_for(url)
        gap = THROTTLE.get(key, DEFAULT_GAP)
        elapsed = time.time() - self._last.get(key, 0.0)
        if elapsed < gap:
            time.sleep(gap - elapsed)
        self._last[key] = time.time()

    def get_json(self, url: str, default: Any = None, use_cache: bool = True) -> Any:
        """JSON 을 받습니다. 404 는 예외가 아니라 default 를 돌려줍니다."""
        now = time.time()
        if use_cache and url in self._cache:
            at, value = self._cache[url]
            if now - at < self._ttl:
                if self.verbose:
                    print(f"  [fetch] 캐시 사용 {url}")
                return value

        self._wait(url)
        try:
            raw = self._client.get_bytes(url)
        except NotFoundError:
            return default
        value = json.loads(raw.decode("utf-8", "replace"))
        if use_cache:
            self._cache[url] = (time.time(), value)
        return value

    def get_text(self, url: str) -> str:
        self._wait(url)
        return self._client.get_bytes(url).decode("utf-8", "replace")
