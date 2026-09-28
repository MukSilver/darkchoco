#!/usr/bin/env python3
"""수집기가 밖에 요청을 걸 때 쓰는 유일한 통로.

**요청은 전부 여기를 지난다.** 다른 자리에서 직접 requests 를 부르지 않는다.
간격과 상한을 한 곳에 모아 두어야 지켜지는지 확인할 수 있다.

## 왜 이렇게 빡빡한가

2026-08-26 에 팀원이 포럼을 반복 조회하다 IP 밴을 당했다.
우리 규칙은 이렇다.

    요청 간격을 두고 병렬 요청을 하지 않는다
    흔적을 남기는 행위를 하지 않는다. 읽기만 한다

그래서 아래를 코드로 막는다. 설정으로도 못 푼다.

| 막는 것 | 어떻게 |
|---|---|
| 병렬 요청 | 잠금 하나로 직렬화한다. 동시에 하나만 나간다 |
| 짧은 간격 | 호스트마다 하한이 있다. 그 밑으로는 안 내려간다 |
| 무한 재시도 | 호스트마다 실패 상한이 있다. 넘으면 그 호스트를 끈다 |
| 쓰기 | GET 과 HEAD 만 있다. POST 메서드가 없다 |
| 큰 응답 | 상한을 넘으면 끊는다 |
| 이상한 종류 | 헤더가 없거나 비어도 검사한다. 건너뛰지 않는다 |

**404 를 오류로 세지 않는다.** 팀원 레포에서 404 를 재시도해 요청이 폭증한 적이 있다.
"""
from __future__ import annotations

import json
import random
import re
import threading
import time
import urllib.parse
from dataclasses import dataclass, field

import requests

# 호스트마다 이 간격 밑으로는 안 내려간다. 초 단위 (하한, 상한)
GAP = {
    "_기본": (2.5, 5.0),
    # 공개 애그리게이터. 문서에 상한이 적혀 있지만 넉넉히 둔다
    "api.ransomware.live": (3.0, 6.0),
    "www.ransomlook.io": (3.0, 6.0),
    "ransomfeed.it": (3.0, 6.0),
    # 텔레그램 공개 미리보기
    "t.me": (2.5, 5.0),
    # X 를 읽는 Jina Reader (2026-09-26). 키 없는 한도가 20 RPM 이라 기본 2.5초(24 RPM)면 넘는다.
    # 키가 있어도 같은 간격을 둔다 — 한 판에 부르는 수가 적어 늦어질 것이 없다
    "r.jina.ai": (3.5, 6.0),
}

FLOOR = 2.0             # 어떤 호스트도 이 밑으로는 못 간다
FAIL_MAX = 3            # 한 호스트에서 이만큼 실패하면 그 호스트를 끈다
TIMEOUT = 20            # 초
MAX_BYTES = 8 << 20     # 8 MiB. 넘으면 끊는다
UA = "darkchoco-research/1.0 (WHS4; read-only)"

OK_TYPES = ("application/json", "application/xml", "text/xml",
            "application/rss", "text/html", "text/plain")


class Blocked(Exception):
    """이 호스트는 더 두드리지 않는다."""


class TooBig(Exception):
    """응답이 상한을 넘었다."""


class BadType(Exception):
    """받기로 한 종류가 아니다."""


@dataclass
class Host:
    last: float = 0.0
    fails: int = 0
    off: str = ""           # 껐으면 이유
    calls: int = 0


@dataclass
class Fetcher:
    """호스트별 간격과 실패를 들고 있는다. 하나만 만들어 돌려 쓴다."""
    hosts: dict = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)
    sess: requests.Session = field(default_factory=requests.Session)
    dry: bool = False       # 참이면 요청을 안 보내고 무엇을 할지만 적는다
    log: list = field(default_factory=list)
    # 403 · 429 · 5xx 때 본문에 적힌 오류 **이름**만. 본문은 버린다 (2026-09-26).
    # Jina 는 차단 사유 문구에 제3자 계정 주소를 넣으므로 문구는 안 남긴다
    last_err: str = ""

    def _gap(self, host: str) -> float:
        lo, hi = GAP.get(host, GAP["_기본"])
        lo = max(lo, FLOOR)
        hi = max(hi, lo)
        return lo + random.random() * (hi - lo)

    def state(self, host: str) -> Host:
        return self.hosts.setdefault(host, Host())

    def get(self, url: str, params: dict | None = None,
            accept: str = "application/json",
            headers: dict | None = None) -> tuple[int, bytes, str]:
        """한 번 받는다. 재시도하지 않는다.

        재시도는 부르는 쪽이 정한다. 여기서 돌리면 상한이 흐려진다.
        돌려주는 것은 (상태코드, 몸통, Content-Type) 이다.

        `headers` 는 더 실을 머리다(인증 등). **로그에 안 남긴다.** UA 와 Accept 는
        여기서 정한 값이 이긴다 — 부르는 쪽이 UA 를 바꿔 다른 도구인 척하지 않게 한다."""
        host = urllib.parse.urlparse(url).netloc.lower()
        st = self.state(host)
        if st.off:
            raise Blocked("%s 는 껐다: %s" % (host, st.off))
        머리 = {**(headers or {}), "User-Agent": UA, "Accept": accept}
        self.last_err = ""

        with self.lock:                      # 동시에 하나만 나간다
            wait = self._gap(host) - (time.monotonic() - st.last)
            if wait > 0:
                if self.dry:
                    self.log.append("%s 를 %.1f초 기다린다" % (host, wait))
                else:
                    time.sleep(wait)
            st.last = time.monotonic()
            st.calls += 1

            if self.dry:
                self.log.append("GET %s" % url)
                return 200, b"", "application/json"

            try:
                r = self.sess.get(
                    url, params=params, timeout=TIMEOUT, stream=True,
                    allow_redirects=True,
                    headers=머리)
            except requests.RequestException as e:
                st.fails += 1
                if st.fails >= FAIL_MAX:
                    st.off = "요청이 %d번 실패했다" % st.fails
                raise

            try:
                # 404 는 오류가 아니다. 없는 것이다. 실패로 세지 않는다
                if r.status_code >= 500 or r.status_code in (403, 429):
                    st.fails += 1
                    if st.fails >= FAIL_MAX:
                        st.off = "%d 이 %d번 왔다" % (r.status_code, st.fails)
                    self.last_err = _오류이름(r)
                    return r.status_code, b"", ""

                ctype = (r.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                # 헤더가 없거나 비어도 건너뛰지 않는다. 모르면 안 받는다
                if not any(ctype.startswith(t) for t in OK_TYPES):
                    raise BadType("%s 가 %r 를 보냈다" % (host, ctype or "(빈 Content-Type)"))

                buf = bytearray()
                for chunk in r.iter_content(64 << 10):
                    buf += chunk
                    if len(buf) > MAX_BYTES:
                        raise TooBig("%s 가 %d 바이트를 넘겼다" % (host, MAX_BYTES))
                st.fails = 0
                return r.status_code, bytes(buf), ctype
            finally:
                r.close()

    def report(self) -> str:
        out = ["호스트별 상태", ""]
        for h, s in sorted(self.hosts.items()):
            lo, hi = GAP.get(h, GAP["_기본"])
            out.append("  %-26s 요청 %3d · 간격 %.1f~%.1f초 · 실패 %d%s"
                       % (h, s.calls, max(lo, FLOOR), hi, s.fails,
                          ("  [꺼짐: %s]" % s.off) if s.off else ""))
        return "\n".join(out)


def _오류이름(r) -> str:
    """실패한 응답에서 오류 **이름**만 꺼낸다. 4 KiB 까지만 읽고, 못 읽으면 빈 글자.

    JSON 봉투의 `name`(Jina 의 `AbuseAlleviationError` 등)이 있으면 그것, 없으면 빈 글자다.
    사유 문구(`message`)는 안 꺼낸다 — 제3자 계정 주소나 우리 계정 id 가 들어 있다."""
    try:
        buf = b""
        for chunk in r.iter_content(4096):
            buf += chunk
            break
        d = json.loads(buf.decode("utf-8", "replace"))
    except (ValueError, requests.RequestException, TypeError):
        return ""
    이름 = d.get("name") if isinstance(d, dict) else ""
    return 이름 if isinstance(이름, str) and re.fullmatch(r"[A-Za-z]{1,60}", 이름) else ""


# 쓰기 메서드를 아예 두지 않는다. post 나 put 이 없는 것이 방어다.
assert not hasattr(Fetcher, "post"), "쓰기 메서드를 만들지 마라"
assert not hasattr(Fetcher, "put"), "쓰기 메서드를 만들지 마라"
