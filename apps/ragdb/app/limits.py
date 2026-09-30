# -*- coding: utf-8 -*-
"""F-18 사용량 제한 가운데 서버 안에서 세는 둘 — 사람별 짧은 간격 제한과 하루 차단기.

사람 확인(Turnstile)은 질의 서버가 요청을 받는 자리에서 한다. 여기에는 없다.

사람별 제한은 값이 0 이면 쓰지 않는다. 2026-09-30 김무근 결정으로 기본값이 0 이다(사람별 제한 없이
하루 차단기만). 설계서 「비용 지키기」 에 그렇게 적혀 있다. 아래 Limiter 는 값을 넣으면 켜지는 채로 남겨 두었다.
"""
import collections
import datetime
import hashlib
import hmac
import os
import threading
import time

from . import config as cfg
from . import store


class Limiter:
    """IP 해시마다 새 답변을 센다. 셈은 메모리에만 둔다. 재기동하면 처음부터 센다 (F-18 처리 3)."""

    def __init__(self, concurrent=None, per_minute=None, per_hour=None):
        self.concurrent = cfg.RATE_CONCURRENT if concurrent is None else concurrent
        self.per_minute = cfg.RATE_PER_MINUTE if per_minute is None else per_minute
        self.per_hour = cfg.RATE_PER_HOUR if per_hour is None else per_hour
        self._lock = threading.Lock()
        self._times = collections.defaultdict(collections.deque)
        self._running = collections.Counter()
        self._salt = (None, None)

    def ip_hash(self, ip):
        """날마다 바뀌는 소금으로 해시한다. IP 원문은 저장하지도 기록하지도 않는다 (SR-23)."""
        day = datetime.datetime.now(store.KST).strftime("%Y-%m-%d")
        with self._lock:
            if self._salt[0] != day:
                self._salt = (day, os.urandom(32))
                self._times.clear()
            salt = self._salt[1]
        return hmac.new(salt, (ip or "").encode("utf-8"), hashlib.sha256).hexdigest()

    def enter(self, who):
        """새 답변을 시작해도 되는가. (허용, 다시 해 볼 때까지 초)"""
        if not (self.concurrent or self.per_minute or self.per_hour):
            return True, 0
        now = time.monotonic()
        with self._lock:
            q = self._times[who]
            while q and now - q[0] > 3600:
                q.popleft()
            if self.concurrent and self._running[who] >= self.concurrent:
                return False, 5
            if self.per_minute:
                recent = [t for t in q if now - t <= 60]
                if len(recent) >= self.per_minute:
                    return False, int(60 - (now - recent[0])) + 1
            if self.per_hour and len(q) >= self.per_hour:
                return False, int(3600 - (now - q[0])) + 1
            q.append(now)
            self._running[who] += 1
            return True, 0

    def leave(self, who):
        with self._lock:
            if self._running[who] > 0:
                self._running[who] -= 1


def budget_allows(con, max_cost):
    """하루 차단기 (F-18 처리 4). 이번 호출의 최대 비용을 더해도 한도 안인가."""
    return store.spent_today(con) + max_cost <= cfg.DAILY_BUDGET_USD
