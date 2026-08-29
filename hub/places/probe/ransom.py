"""랜섬웨어 그룹 명부를 조사합니다.

무엇을 알아내나 — 그룹이 지금 살아있나, 피해 기업이 몇이나 올라왔나,
어떤 업종이 당했나, 한국 피해가 몇 건인가, 마지막 활동이 언제인가.

원본은 apps/dls-observatory/sources.py 의 RansomwareLive 입니다. 그 파일의
방어를 그대로 옮겼습니다.

  · 대량 엔드포인트만 씁니다. 그룹 하나씩 조회하면 392 요청이 됩니다
  · 62초 간격. 그 API 의 rate limit 이 1req/분/엔드포인트 입니다.
    실측으로 알아낸 값이고, 그보다 빠르게 치면 막힙니다
  · 연속 세 번 실패하면 멈춥니다. 차단당한 상태에서 계속 쏘면 차단
    기간만 길어집니다. kr-leak-alarm 에서 실제로 IP 가 막힌 적이 있습니다

**응답 구조를 실측으로 맞췄습니다.** 예전 코드는 victims · type · lastseen
을 찾고 있었는데 /groups 응답에 그런 칸이 없습니다. 그래서 피해기업수와
형식과 최근활동이 늘 비어 있었고, 상태는 대부분 「미확인」이 나왔습니다.
그 미확인이 노션으로 갔으면 사람이 조사해 둔 508줄을 덮었습니다.

    /groups              name · altname · description · url
                         locations[] = {available, enabled, fqdn, slug,
                                        title, type}
    /victims/{년}/{월}    group · country · activity · attackdate ·
                         domain · description  (한 달에 900건 안팎)

살아있는지는 locations[].available 에, 형식은 locations[].type 에
있습니다. 피해 건수는 /groups 에 아예 없어서 월별 피해 목록을 받아
그룹별로 셉니다.

**Tor 를 거칩니다.** ransomware.live 는 연구자용 공개 API 지만, 우리가
어느 그룹을 보고 있는지가 우리 주소와 함께 남을 이유가 없습니다.

표준 라이브러리만 씁니다.
"""

from __future__ import annotations

import collections
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from typing import Iterator

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "packages"))

from dc_ransomfeed import RANSOMWARE_LIVE, rl_victims  # noqa: E402

from hub.places.place import Place, 지금  # noqa: E402
from hub.places.egress import 보호없음, 오프너  # noqa: E402

__all__ = ["조사", "NEEDS_PACKAGES"]

NEEDS_PACKAGES: list[str] = []      # 표준 라이브러리만 씁니다

간격 = 62.0          # 초. 1req/분/엔드포인트 (실측)
연속실패_상한 = 3
# 피해 목록을 몇 달치 받나. **여섯 달을 받습니다.**
#
# 예전에는 0(안 받음)이었습니다. apps/dls-observatory/dls_fill.py 가 같은
# 칸을 채우는데 꼴이 달라 서로 갈아 끼우지 못하고 373줄에 뜻이 겹치는
# 줄이 하나씩 더 붙었기 때문입니다.
#
#     dls_fill   "피해자 12건 (최근 6개월)"
#     여기       "피해 기업 40 (2026-08-30 기준)"
#
# 2026-08-30 에 둘을 갈랐습니다.
#
#   · dls-observatory 는 개인정보 유출DB팀 대시보드 재료로만 씁니다.
#     dls_fill.py --apply 로 노션에 쓰지 않습니다. 22칸 중 21칸을
#     크롤러가 이미 채워서, 그래도 비는 칸이 안 생깁니다.
#   · 그래도 누가 --apply 를 주면 겹칠 수 있어, place.py 의
#     기계가_쓴_줄() 이 dls_fill 의 꼴도 알아보게 했습니다. 쌓이지 않고
#     갈아 끼워집니다.
#
# 여섯 달인 이유는 한 달에 한 요청이고 62초 간격이라, 여섯이면 한 판에
# 6분쯤 더 걸리기 때문입니다. 열둘이면 12분입니다. 백오프로 줄인 시간
# 안에서 감당되는 값으로 잡았습니다.
개월 = 6
UA = "darkchoco-research/1.0 (WHS4; read-only)"

# locations[].type 을 노션 「형식」 칸 값으로 옮깁니다.
# 노션 선택지에 없는 값은 명부 쪽에서 걸러 내고 알려 줍니다.
_형식 = {
    "dls": "DLS", "ransomware": "RaaS", "raas": "RaaS", "maas": "MaaS",
    "extortion": "데이터 갈취", "dataleak": "데이터 갈취",
    "market": "포럼·마켓", "forum": "포럼·마켓",
    "stealer": "스틸러/로그", "iab": "IAB", "initial access": "초기 접근",
    "carding": "카딩",
}

# 노션 「국가」 칸이 받는 이름입니다. 여기 없는 코드는 안 씁니다.
_나라 = {"KR": "한국", "US": "미국", "JP": "일본", "CN": "중국",
        "RU": "러시아", "TR": "터키", "IN": "인도", "BR": "브라질",
        "GB": "영국", "DE": "독일", "FR": "프랑스", "VN": "베트남",
        "ID": "인도네시아", "TW": "대만"}


class 막힘(Exception):
    """연속으로 실패해 멈췄습니다. 차단 기간을 늘리지 않으려는 것입니다."""


def _받기(url: str, 마지막: list[float], op=None) -> object:
    """간격을 지켜 한 번 받습니다."""
    지난 = time.time() - 마지막[0]
    if 지난 < 간격:
        time.sleep(간격 - 지난)
    op = op or 오프너(갈래="ransom")          # Tor 가 없으면 여기서 보호없음 이 납니다
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "application/json"})
    try:
        with op.open(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    finally:
        마지막[0] = time.time()


# ── 응답에서 값 뽑기 ───────────────────────────────────────────────
def _형식으로(locs: list) -> str:
    for loc in locs:
        v = str((loc or {}).get("type") or "").lower()
        for 조각, 값 in _형식.items():
            if 조각 in v:
                return 값
    return ""


def _상태로(g: dict) -> tuple[str, bool]:
    """(상태, 정했나) 를 돌려줍니다.

    ransomware.live 는 살아있는지를 locations[].available 에 담습니다.
    최상위만 보면 대부분 못 읽고, 그 미확인이 노션의 508줄을 덮습니다.

    미러가 여럿이면 **하나라도 살아 있으면 online** 입니다. 그룹이
    살아있는지를 묻는 칸이지 미러 하나를 묻는 칸이 아닙니다.
    """
    본것 = [loc["available"] for loc in (g.get("locations") or [])
           if isinstance(loc, dict) and isinstance(loc.get("available"), bool)]
    if 본것:
        return ("online" if any(본것) else "offline"), True

    # 압수 안내로 바뀐 곳입니다. 죽은 것과 다릅니다.
    for loc in (g.get("locations") or []):
        t = str((loc or {}).get("title") or "").lower()
        if "seiz" in t or "law enforcement" in t or "operation " in t:
            return "압수됨", True

    for k in ("available", "online", "up", "status"):
        v = g.get(k)
        if isinstance(v, bool):
            return ("online" if v else "offline"), True
        if isinstance(v, str):
            s = v.lower()
            if s in ("online", "up", "active", "true"):
                return "online", True
            if s in ("offline", "down", "inactive", "false"):
                return "offline", True
            if "seiz" in s or "takedown" in s:
                return "압수됨", True
    return "미확인", False


def _주소들(g: dict) -> tuple[str, str]:
    """(대표 주소, 나머지 미러) 를 돌려줍니다.

    slug 가 스킴까지 붙은 주소입니다. fqdn 은 호스트만이라 노션 url 칸에
    넣으면 링크가 안 걸립니다. 살아있는 미러를 대표로 씁니다.
    """
    사는것, 죽은것 = [], []
    for loc in (g.get("locations") or []):
        if not isinstance(loc, dict):
            continue
        주소 = str(loc.get("slug") or loc.get("fqdn") or "").strip()
        if not 주소:
            continue
        (사는것 if loc.get("available") else 죽은것).append(주소)
    전부 = 사는것 + 죽은것
    if not 전부:
        return str(g.get("url") or ""), ""
    return 전부[0], " · ".join(전부[1:6])


# ── 월별 피해 목록으로 세기 ────────────────────────────────────────
def _달들(n: int) -> list[tuple[int, int]]:
    """이번 달부터 거슬러 n 달."""
    오늘 = date.today()
    년, 월 = 오늘.year, 오늘.month
    out = []
    for _ in range(n):
        out.append((년, 월))
        월 -= 1
        if 월 == 0:
            년, 월 = 년 - 1, 12
    return out


def _피해모으기(마지막: list[float], 개월수: int, op=None) -> tuple[dict, list[str]]:
    """그룹 이름 → {건수, 마지막활동, 업종, 한국건수} 로 모읍니다.

    /groups 에는 피해 건수가 없습니다. 월별 목록을 받아 세는 수밖에
    없습니다. 한 달에 한 요청이라 기본 세 달이면 세 요청입니다.
    """
    모음: dict = {}
    못본달: list[str] = []
    실패 = 0
    for 년, 월 in _달들(개월수):
        try:
            건들 = _받기(rl_victims(년, 월), 마지막, op)
            실패 = 0
        except (urllib.error.URLError, OSError, ValueError) as e:
            못본달.append(f"{년}-{월:02d}({type(e).__name__})")
            실패 += 1
            if 실패 >= 연속실패_상한:
                못본달.append("연속 실패로 멈춤")
                break
            continue
        if not isinstance(건들, list):
            못본달.append(f"{년}-{월:02d}(꼴이 바뀜)")
            continue
        for v in 건들:
            if not isinstance(v, dict):
                continue
            g = str(v.get("group") or "").strip()
            if not g:
                continue
            d = 모음.setdefault(g, {"건수": 0, "마지막": "",
                                   "업종": collections.Counter(), "한국": 0})
            d["건수"] += 1
            when = str(v.get("attackdate") or v.get("discovered") or "")[:10]
            if when > d["마지막"]:
                d["마지막"] = when
            업종 = str(v.get("activity") or "").strip()
            if 업종 and 업종.lower() not in ("not found", "unknown", "none"):
                d["업종"][업종] += 1
            if str(v.get("country") or "").upper() == "KR":
                d["한국"] += 1
    return 모음, 못본달


def _업종줄(c: collections.Counter) -> str:
    """가장 많이 당한 업종 넷. 출처가 쓴 이름을 그대로 둡니다.

    옮겨 적으면 원문과 대조가 안 됩니다.
    """
    if not c:
        return ""
    return " · ".join(f"{이름} {수}" for 이름, 수 in c.most_common(4))


# ── 조사 ───────────────────────────────────────────────────────────
def 조사(*, dry: bool = False, limit: int = 0,
        개월수: int = 개월, 프록시: str | None = None) -> Iterator[Place]:
    """랜섬 그룹 명부를 한 바퀴 봅니다.

    요청 수는 1 + 개월수 입니다. 기본은 개월수가 0 이라 한 번입니다.
    피해 집계는 dls_fill 소관입니다. 위 주석을 보십시오.
    """
    if dry:
        return

    마지막 = [0.0]

    try:
        op = 오프너(프록시, 갈래="ransom")
    except 보호없음 as e:
        yield Place(갈래="ransom", 이름="(그룹 목록)",
                    못본이유=f"Tor 가 없어 안 나갔습니다. {str(e).splitlines()[0]}",
                    받은곳="ransomware.live/groups")
        return

    try:
        그룹들 = _받기(f"{RANSOMWARE_LIVE}/groups", 마지막, op)
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

    피해, 못본달 = _피해모으기(마지막, 개월수, op) if 개월수 > 0 else ({}, [])
    기간 = f"최근 {개월수}달" if 개월수 > 0 else ""

    본것 = 0
    for g in 그룹들:
        if not isinstance(g, dict):
            continue
        이름 = str(g.get("name") or g.get("group") or "").strip()
        if not 이름:
            continue

        상태, 정함 = _상태로(g)
        주소, 미러 = _주소들(g)
        locs = [x for x in (g.get("locations") or []) if isinstance(x, dict)]
        d = 피해.get(이름) or 피해.get(이름.lower()) or {}

        p = Place(
            갈래="ransom",
            이름=이름,
            주소=주소,
            상태=상태,
            두드림=정함,
            확인일=지금(),
            형식=_형식으로(locs),
            종류="group",
            이전이름=str(g.get("altname") or "").strip(),
            이전주소=미러,
            어떤곳=str(g.get("description") or "").strip()[:1800],
            출처=["ransomware.live"],
            받은곳="ransomware.live/groups",
        )

        if d:
            p.피해기업수 = d["건수"]
            if d["마지막"]:
                p.최근활동 = d["마지막"]
            업종 = _업종줄(d["업종"])
            if 업종:
                p.피해대상 = f"{기간} {업종}"
            # 이름은 안 적습니다. 건수만 남깁니다(SECURITY.md).
            if d["한국"]:
                p.한국유출 = f"{기간} 한국 피해 {d['한국']}건"

        if 못본달:
            # 그룹은 봤습니다. 피해 목록의 한 달을 못 받았을 뿐입니다.
            # 못본이유에 넣으면 노션값() 이 알아낸 것을 전부 버립니다.
            p.받은곳 += f" (피해 목록 일부 못 받음: {' · '.join(못본달[:3])})"

        yield p
        본것 += 1
        if limit and 본것 >= limit:
            return
