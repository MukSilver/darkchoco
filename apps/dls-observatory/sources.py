"""
DLS 정보 수집 소스 (ransomware.live v2 API / ransomlook.io API).

두 API 모두 공개 엔드포인트이며 인증이 필요 없습니다.
- ransomware.live v2 : 무료 티어 rate limit이 "엔드포인트당 1req/분"이라 매우 빡빡합니다.
  그래서 이 모듈은 **대량(bulk) 엔드포인트만** 호출하고 결과를 디스크에 캐시합니다.
- ransomlook.io      : 명시된 제한은 없지만 예의상 요청 간 딜레이를 둡니다.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

# 주소는 packages/dc_ransomfeed 한곳에서 관리합니다.
# API 가 개편되면 거기만 고치면 kr-leak-alarm 과 같이 따라갑니다.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages"))
from dc_ransomfeed import RANSOMLOOK as LOOK_BASE  # noqa: E402
from dc_ransomfeed import RANSOMWARE_LIVE as RL_BASE  # noqa: E402

USER_AGENT = "notion-dls-filler/1.0 (research; +https://github.com/)"


# --------------------------------------------------------------------------
# 저수준 HTTP + 캐시
# --------------------------------------------------------------------------
class Fetcher:
    def __init__(self, cache_dir: str = ".cache", cache_hours: int = 72,
                 verbose: bool = True, timeout: int = 60):
        self.cache_dir = cache_dir
        self.cache_ttl = timedelta(hours=cache_hours)
        self.verbose = verbose
        self.timeout = timeout
        os.makedirs(cache_dir, exist_ok=True)
        self._last_call: dict[str, float] = {}

    def _log(self, msg: str) -> None:
        if not self.verbose:
            return
        try:
            print(msg, flush=True)
        except UnicodeEncodeError:
            # 윈도우 cp949 콘솔 대비 — 출력할 수 없는 문자는 '?' 로 대체
            enc = getattr(sys.stdout, "encoding", None) or "utf-8"
            print(msg.encode(enc, "replace").decode(enc, "replace"), flush=True)

    def _cache_path(self, url: str) -> str:
        safe = urllib.parse.quote(url, safe="")[:180]
        return os.path.join(self.cache_dir, safe + ".json")

    def get_json(self, url: str, *, throttle_key: str | None = None,
                 min_interval: float = 0.0, default: Any = None) -> Any:
        """캐시 → 없으면 HTTP GET. 실패하면 default 반환(스크립트를 죽이지 않음)."""
        path = self._cache_path(url)
        if os.path.exists(path):
            age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(path))
            if age < self.cache_ttl:
                self._log(f"  [cache] {url}")
                with open(path, encoding="utf-8") as fh:
                    return json.load(fh)

        if throttle_key and min_interval:
            last = self._last_call.get(throttle_key)
            if last is not None:
                wait = min_interval - (time.time() - last)
                if wait > 0:
                    self._log(f"  [대기]  {wait:.0f}초 — 차단된 게 아니라, "
                              f"무료 API 제한(1req/분)에 걸리지 않으려 "
                              f"미리 쉬는 중입니다")
                    time.sleep(wait)

        오프너, 어떻게 = _나가는길()
        self._log(f"  [http]  {url}  ({어떻게})")
        req = urllib.request.Request(url, headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        })
        try:
            with 오프너.open(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as exc:
            self._log(f"  [!]     HTTP {exc.code} — {url}")
            return default
        except Exception as exc:  # noqa: BLE001
            self._log(f"  [!]     실패 ({exc.__class__.__name__}: {exc}) — {url}")
            return default
        finally:
            if throttle_key:
                self._last_call[throttle_key] = time.time()

        _strip_heavy(data)  # base64 스크린샷 등은 캐시에 저장하지 않는다
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
        return data


# --------------------------------------------------------------------------
# 이름 정규화 / 매칭 키
# --------------------------------------------------------------------------

# ── 밖으로 나가는 길 ────────────────────────────────────────────────
_오프너캐시: list = []


def _나가는길():
    """(오프너, 어떻게 나가나) 를 돌려줍니다.

    **hub 크롤러와 같은 규칙을 지킵니다.** 그 쪽은 Tor 없이는 아예 안
    나갑니다(hub/crawler/probe/_나가기.py). 여기만 맨 IP 로 나가면
    같은 ransomware.live 를 두 도구가 다른 주소로 치게 됩니다.
    규칙이 도구마다 다르면 반드시 빠뜨립니다.

    다만 여기서 막지는 않습니다. 이 앱은 사람이 손으로도 돌리는 것이고,
    막아 버리면 Tor 없는 자리에서 아무것도 못 합니다. 대신 **어느 길로
    나갔는지를 매 줄에 적습니다.** 나중에 로그를 보면 압니다.
    """
    if _오프너캐시:
        return _오프너캐시[0]

    프록시 = (os.environ.get("TOR_SOCKS_PROXY") or "").strip()
    if 프록시 and not 프록시.startswith("socks"):
        # https 만 걸어 줍니다. 이 앱이 치는 곳은 전부 https 이고,
        # http 는 CONNECT 를 안 써서 Tor 가 끊습니다.
        것 = (urllib.request.build_opener(
            urllib.request.ProxyHandler({"https": 프록시})), "Tor")
    elif 프록시:
        것 = (urllib.request.build_opener(), "맨 연결 — SOCKS 는 못 탑니다")
    else:
        것 = (urllib.request.build_opener(), "맨 연결 — TOR_SOCKS_PROXY 없음")
    _오프너캐시.append(것)
    return 것


def _strip_heavy(obj) -> None:
    """응답 안의 base64 스크린샷('screen')처럼 큰 필드를 재귀적으로 제거."""
    if isinstance(obj, dict):
        obj.pop("screen", None)
        obj.pop("screenshot_b64", None)
        for v in obj.values():
            _strip_heavy(v)
    elif isinstance(obj, list):
        for v in obj:
            _strip_heavy(v)


def norm(name: str | None) -> str:
    if not name:
        return ""
    return "".join(ch for ch in name.lower() if ch.isalnum())


_PAREN = re.compile(r"[(\[{][^)\]}]*[)\]}]")
# 이름 뒤에 붙는 분류용 꼬리표. 이것만으로 이름이 되는 경우는 없다고 보고 제거.
_NOISE = ("market", "markets", "shop", "store", "forum", "leaks", "leak",
          "deep", "dark", "onion", "site", "mirror", "official")


def norm_loose(name: str | None) -> str:
    """'HYDRA (Deep)' → 'hydra' 처럼 괄호 주석과 분류 꼬리표를 떼고 정규화."""
    if not name:
        return ""
    s = _PAREN.sub(" ", name)
    words = [w for w in re.split(r"[\s_\-·,/|]+", s.lower()) if w]
    while len(words) > 1 and words[-1].strip("0123456789") in _NOISE:
        words.pop()
    return norm(" ".join(words))


def domain_label(url: str | None) -> str:
    """'https://savastan0.tools/' → 'savastan0'. onion 주소는 빈 문자열."""
    if not url:
        return ""
    v = url.strip().lower()
    for pre in ("http://", "https://"):
        if v.startswith(pre):
            v = v[len(pre):]
    v = v.split("/")[0].split("?")[0].split(":")[0]
    if v.startswith("www."):
        v = v[4:]
    if not v or v.endswith(".onion"):
        return ""
    return norm(v.split(".")[0])


def onion_key(value: str | None) -> str:
    """URL이든 fqdn이든 'xxxx.onion' 형태의 호스트만 뽑아 소문자로."""
    if not value:
        return ""
    v = value.strip().lower()
    v = v.replace("http://", "").replace("https://", "")
    v = v.split("/")[0].split("?")[0].strip()
    return v if v.endswith(".onion") else ""


# --------------------------------------------------------------------------
# ransomware.live
# --------------------------------------------------------------------------
class RansomwareLive:
    """대량 엔드포인트만 사용해서 rate limit(1req/분/엔드포인트)을 견딘다."""

    def __init__(self, fetcher: Fetcher, months: int = 6, min_interval: float = 62.0):
        self.f = fetcher
        self.months = months
        self.min_interval = min_interval
        self.groups_by_name: dict[str, dict] = {}
        self.groups_by_loose: dict[str, dict] = {}
        self.groups_by_onion: dict[str, dict] = {}
        self.victims: list[dict] = []
        self.kr_victims: list[dict] = []

    # -- 수집 ------------------------------------------------------------
    def load(self) -> None:
        print("[ransomware.live] 그룹 목록 수집")
        groups = self.f.get_json(f"{RL_BASE}/groups", throttle_key="rl:groups",
                                 min_interval=self.min_interval, default=[]) or []
        for g in groups:
            key = norm(g.get("name"))
            if key:
                self.groups_by_name[key] = g
            # ransomware.live/group/<slug> 형태의 slug도 키로 등록
            url = g.get("url") or ""
            if "/group/" in url:
                self.groups_by_name.setdefault(norm(url.rsplit("/", 1)[-1]), g)
            if g.get("altname"):
                self.groups_by_name.setdefault(norm(g["altname"]), g)
                self.groups_by_loose.setdefault(norm_loose(g["altname"]), g)
            for lk in (norm_loose(g.get("name")),
                       norm_loose(url.rsplit("/", 1)[-1]) if "/group/" in url else ""):
                if lk:
                    self.groups_by_loose.setdefault(lk, g)
            for loc in g.get("locations") or []:
                k = onion_key(loc.get("fqdn") or loc.get("slug"))
                if k:
                    self.groups_by_onion[k] = g
        print(f"[ransomware.live] 그룹 {len(groups)}개, onion 주소 {len(self.groups_by_onion)}개 인덱싱")

        print("[ransomware.live] 한국(KR) 피해자 수집")
        self.kr_victims = self.f.get_json(f"{RL_BASE}/countryvictims/KR",
                                          throttle_key="rl:countryvictims",
                                          min_interval=self.min_interval, default=[]) or []
        print(f"[ransomware.live] KR 피해자 {len(self.kr_victims)}건")

        print(f"[ransomware.live] 최근 {self.months}개월 피해자 수집")
        seen: set[tuple] = set()
        cur = datetime.now(timezone.utc)
        for i in range(self.months):
            y, m = cur.year, cur.month - i
            while m <= 0:
                m += 12
                y -= 1
            batch = self.f.get_json(f"{RL_BASE}/victims/{y}/{m}",
                                    throttle_key="rl:victims",
                                    min_interval=self.min_interval, default=[]) or []
            for v in batch:
                sig = (v.get("victim"), v.get("group") or v.get("group_name"),
                       v.get("discovered"))
                if sig not in seen:
                    seen.add(sig)
                    self.victims.append(v)
        print(f"[ransomware.live] 피해자 {len(self.victims)}건")

    # -- 조회 ------------------------------------------------------------
    def find(self, name: str, onion: str | None = None) -> dict | None:
        hit, self.last_match = self._find(name, onion)
        return hit

    def _find(self, name: str, onion: str | None) -> tuple[dict | None, str]:
        if onion:
            h = self.groups_by_onion.get(onion_key(onion))
            if h:
                return h, "onion 주소"
        h = self.groups_by_name.get(norm(name))
        if h:
            return h, "이름 일치"
        h = self.groups_by_loose.get(norm_loose(name))
        if h:
            return h, f"꼬리표 제거 후 일치({norm_loose(name)})"
        lbl = domain_label(onion)
        if lbl:
            h = self.groups_by_name.get(lbl) or self.groups_by_loose.get(lbl)
            if h:
                return h, f"도메인 이름 일치({lbl})"
        return None, ""

    def suggest(self, name: str, n: int = 3) -> list[str]:
        import difflib
        keys = set(self.groups_by_name) | set(self.groups_by_loose)
        return difflib.get_close_matches(norm_loose(name) or norm(name),
                                         list(keys), n=n, cutoff=0.72)

    def group_victims(self, group_name: str) -> list[dict]:
        key = norm(group_name)
        return [v for v in self.victims
                if norm(v.get("group") or v.get("group_name")) == key]

    def group_kr_victims(self, group_name: str) -> list[dict]:
        key = norm(group_name)
        return [v for v in self.kr_victims
                if norm(v.get("group_name") or v.get("group")) == key]


# --------------------------------------------------------------------------
# ransomlook.io
# --------------------------------------------------------------------------
class RansomLook:
    """그룹/마켓/포럼 이름 목록을 받아두고, 매칭될 때만 상세를 조회한다."""

    def __init__(self, fetcher: Fetcher, min_interval: float = 0.4):
        self.f = fetcher
        self.min_interval = min_interval
        self.index: dict[str, tuple[str, str]] = {}   # norm(name)       -> (kind, 원래 이름)
        self.loose: dict[str, tuple[str, str]] = {}   # norm_loose(name) -> (kind, 원래 이름)
        self.calls = 0
        self.last_match = ""

    # ransomlook 은 목록 엔드포인트로 /api/groups 와 /api/markets 만 제공한다.
    # (/api/forums, /api/telegram 등은 404 — 있으면 자동으로 잡히고 없으면 조용히 넘어감)
    LIST_ENDPOINTS = (("group", "groups"), ("market", "markets"))

    def load(self) -> None:
        for kind, path in self.LIST_ENDPOINTS:
            names = self.f.get_json(f"{LOOK_BASE}/{path}", throttle_key="look",
                                    min_interval=self.min_interval, default=[]) or []
            if isinstance(names, dict):
                names = list(names.keys())
            for n in names:
                if isinstance(n, str):
                    self.index.setdefault(norm(n), (kind, n))
                    if norm_loose(n):
                        self.loose.setdefault(norm_loose(n), (kind, n))
            print(f"[ransomlook.io] {path}: {len(names)}개")

    def lookup(self, name: str, url: str | None = None) -> tuple[str, str] | None:
        """(kind, 원래 이름) 반환. HTTP 호출 없음."""
        h = self.index.get(norm(name))
        if h:
            self.last_match = "이름 일치"
            return h
        h = self.loose.get(norm_loose(name))
        if h:
            self.last_match = f"꼬리표 제거 후 일치({norm_loose(name)})"
            return h
        lbl = domain_label(url)
        if lbl:
            h = self.index.get(lbl) or self.loose.get(lbl)
            if h:
                self.last_match = f"도메인 이름 일치({lbl})"
                return h
        self.last_match = ""
        return None

    def kind_of(self, name: str, url: str | None = None) -> str | None:
        """상세 조회 없이 종류만 확인 (HTTP 호출 없음)."""
        h = self.lookup(name, url)
        return h[0] if h else None

    def suggest(self, name: str, n: int = 3) -> list[str]:
        import difflib
        keys = set(self.index) | set(self.loose)
        return difflib.get_close_matches(norm_loose(name) or norm(name),
                                         list(keys), n=n, cutoff=0.72)

    def find(self, name: str, url: str | None = None) -> tuple[str, dict] | None:
        """(kind, detail) 반환. 이름이 인덱스에 없으면 None. HTTP 호출 1회."""
        hit = self.lookup(name, url)
        if not hit:
            return None
        kind, real = hit
        self.calls += 1
        detail = self.f.get_json(
            f"{LOOK_BASE}/{kind}/{urllib.parse.quote(real)}",
            throttle_key="look", min_interval=self.min_interval, default=None)
        if not isinstance(detail, dict):
            return None
        # 용량 큰 base64 스크린샷은 버린다
        for loc in detail.get("locations") or []:
            loc.pop("screen", None)
        return kind, detail


# --------------------------------------------------------------------------
# 피해자 통계 헬퍼
# --------------------------------------------------------------------------
def victim_stats(victims: list[dict]) -> dict[str, Any]:
    """피해 대상 / 규모 / 최근 활동에 쓸 요약."""
    if not victims:
        return {}
    sectors = Counter(v.get("activity") for v in victims
                      if v.get("activity") and v["activity"] not in ("Not Found", "N/A"))
    countries = Counter(v.get("country") for v in victims if v.get("country"))
    dates = []
    for v in victims:
        for field in ("discovered", "attackdate", "published"):
            raw = v.get(field)
            if raw:
                try:
                    dates.append(datetime.fromisoformat(raw.replace("Z", "+00:00")))
                except ValueError:
                    pass
                break
    return {
        "count": len(victims),
        "sectors": sectors.most_common(5),
        "countries": countries.most_common(8),
        "latest": max(dates) if dates else None,
        "names": [v.get("victim") or v.get("post_title") for v in victims][:10],
    }
