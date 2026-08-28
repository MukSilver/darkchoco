"""랜섬웨어 그룹 명부를 조사합니다.

무엇을 알아내나 — 그룹이 지금 살아있나, 피해 기업이 몇이나 올라왔나,
어떤 형식인가(RaaS · IAB · DLS …), 마지막 활동이 언제인가.

원본은 apps/dls-observatory/sources.py 의 RansomwareLive 입니다. 그 파일의
방어를 그대로 옮겼습니다.

  · 대량 엔드포인트만 씁니다. 그룹 하나씩 조회하면 요청 수가 폭발합니다
  · 62초 간격. 그 API 의 rate limit 이 1req/분/엔드포인트 입니다.
    실측으로 알아낸 값이고, 그보다 빠르게 치면 막힙니다
  · 연속 세 번 실패하면 멈춥니다. 차단당한 상태에서 계속 쏘면 차단
    기간만 길어집니다. kr-leak-alarm 에서 실제로 IP 가 막힌 적이 있습니다

표준 라이브러리만 씁니다.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterator

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "packages"))

from dc_ransomfeed import RANSOMLOOK, RANSOMWARE_LIVE  # noqa: E402

from hub.crawler.place import Place, 지금  # noqa: E402

__all__ = ["조사", "NEEDS_PACKAGES"]

NEEDS_PACKAGES: list[str] = []      # 표준 라이브러리만 씁니다

간격 = 62.0          # 초. 1req/분/엔드포인트 (실측)
연속실패_상한 = 3
UA = "darkchoco-research/1.0 (WHS4; read-only)"

# ransomware.live 가 주는 값을 노션 「형식」 칸 값으로 옮깁니다.
_형식 = {
    "ransomware": "RaaS", "raas": "RaaS", "maas": "MaaS",
    "extortion": "데이터 갈취", "dataleak": "데이터 갈취",
    "market": "포럼·마켓", "forum": "포럼·마켓",
    "stealer": "스틸러/로그", "iab": "IAB", "initial access": "초기 접근",
    "carding": "카딩", "dls": "DLS",
}


class 막힘(Exception):
    """연속으로 실패해 멈췄습니다. 차단 기간을 늘리지 않으려는 것입니다."""


def _받기(url: str, 마지막: list[float]) -> object:
    """간격을 지켜 한 번 받습니다."""
    지난 = time.time() - 마지막[0]
    if 지난 < 간격:
        time.sleep(간격 - 지난)
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    finally:
        마지막[0] = time.time()


def _수(g: dict, *키) -> int | None:
    for k in 키:
        v = g.get(k)
        if isinstance(v, int):
            return v
        if isinstance(v, str) and v.isdigit():
            return int(v)
    return None


def _형식으로(g: dict) -> str:
    for k in ("type", "kind", "category", "meta"):
        v = str(g.get(k) or "").lower()
        for 조각, 값 in _형식.items():
            if 조각 in v:
                return 값
    return ""


def _상태로(g: dict) -> str:
    """살아있나. 값이 없으면 단정하지 않고 미확인으로 둡니다."""
    for k in ("available", "online", "up", "status"):
        v = g.get(k)
        if isinstance(v, bool):
            return "online" if v else "offline"
        if isinstance(v, str):
            s = v.lower()
            if s in ("online", "up", "active", "true"):
                return "online"
            if s in ("offline", "down", "inactive", "false"):
                return "offline"
            if "seiz" in s or "takedown" in s:
                return "압수됨"
    return "미확인"


def 조사(*, dry: bool = False, limit: int = 0) -> Iterator[Place]:
    """랜섬 그룹 명부를 한 바퀴 봅니다."""
    if dry:
        return

    마지막 = [0.0]
    실패 = 0

    try:
        그룹들 = _받기(f"{RANSOMWARE_LIVE}/groups", 마지막)
    except (urllib.error.URLError, OSError, ValueError) as e:
        yield Place(갈래="ransom", 이름="(그룹 목록)",
                    못본이유=f"그룹 목록을 못 받았습니다: {e}",
                    받은곳="ransomware.live/groups")
        return

    if not isinstance(그룹들, list):
        yield Place(갈래="ransom", 이름="(그룹 목록)",
                    못본이유="그룹 목록이 배열이 아닙니다. 응답 꼴이 바뀌었을 수 있습니다",
                    받은곳="ransomware.live/groups")
        return

    본것 = 0
    for g in 그룹들:
        if not isinstance(g, dict):
            continue
        이름 = str(g.get("name") or g.get("group") or "").strip()
        if not 이름:
            continue

        주소 = ""
        for loc in (g.get("locations") or []):
            if isinstance(loc, dict) and loc.get("fqdn"):
                주소 = str(loc["fqdn"])
                break
        if not 주소:
            주소 = str(g.get("url") or "")

        yield Place(
            갈래="ransom",
            이름=이름,
            주소=주소,
            상태=_상태로(g),
            확인일=지금(),
            피해기업수=_수(g, "victims", "victim_count", "count"),
            형식=_형식으로(g),
            종류="group",
            최근활동=str(g.get("lastseen") or g.get("last_seen") or "")[:19],
            출처=["ransomware.live"],
            받은곳="ransomware.live/groups",
        )
        본것 += 1
        if limit and 본것 >= limit:
            return
