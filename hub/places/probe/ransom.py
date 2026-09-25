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
from datetime import date, timedelta
from pathlib import Path
from typing import Iterator

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "packages"))

# 주소는 손으로 붙이지 않고 dc_ransomfeed 가 만들어 주는 것을 씁니다.
# 그 패키지를 만든 이유가 「API 가 개편되면 여기만 고칩니다」인데,
# /groups 만 f-string 으로 붙이고 있어서 반쯤 무너져 있었습니다.
from dc_ransomfeed import rl_groups, rl_victims  # noqa: E402

from hub.places.place import Place, 지금
from hub.places.place import 오늘 as _오늘  # noqa: E402
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
#
# ## 2026-09-25 — 달력 여섯 달 합계에서 「최근 180일 월평균」 으로 (최현서 승인, 인계 A)
#
# 달력 여섯 달 합계는 **이번 달이 덜 찬 채로** 셌습니다. 매달 1일에 가득 찬 가장 오래된
# 달이 빠지고 거의 빈 새 달이 들어와, 숫자가 뚝 떨어졌다가 한 달 동안 다시 오르는 톱니가
# 됐습니다. 칸 글자에 기간이 없어 누적 건수처럼 읽히기도 했습니다. 이름만 「평균」 으로
# 바꾸면 톱니는 그대로라 **세는 구간을 바꿉니다.**
#
#   세는 구간   게시일(attackdate, 없으면 discovered)이 오늘부터 거슬러 180일 안인 건
#   받는 달     180일을 덮으려면 일곱 달입니다. 요청 간격 62초는 그대로라 1분 늘어납니다
#   규모        「피해 월평균 N건 (최근 180일) (날짜 기준)」. N 은 180일 건수 ÷ 6
#   나머지      피해 대상 · 한국 관련 유출 · 최근 활동도 같은 180일로 셉니다
#
# 못 받은 달이 있으면 네 칸을 안 쓰는 규칙(2026-09-25)은 그대로 먹습니다.
개월 = 7
창 = 180            # 일. 이 안에 게시된 피해만 셉니다
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

# 「국가」 이름표(_나라)와 `막힘` 예외를 여기서 지웠습니다. 2026-09-01.
#
#   _나라   정의만 있고 부르는 데가 없었습니다. 「국가」는 기계칸이 아니라
#           (place.py 의 기계칸 목록에 없습니다) 이 조사기가 채울 수 없는
#           칸입니다. 국가를 채우기로 정하면 그때 다시 넣습니다
#   막힘    아무 데서도 raise 하지 않았습니다. 연속 실패로 멈추는 자리는
#           _피해모으기() 안이고, 거기서는 예외를 올리지 않고 못본달 에
#           「연속 실패로 멈춤」을 적고 break 합니다. 예외를 잡으려고
#           import 하는 데도 없었습니다(레포 전체 확인)
#
# 안 쓰는 이름이 남아 있으면 다음 사람이 「국가도 채우는구나」,
# 「막힘을 잡아야겠구나」로 읽습니다.


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
    """(대표 주소, 나머지 DLS 미러) 를 돌려줍니다.

    **type 이 DLS 인 것만 대표 후보로 둡니다.** 원본
    (apps/dls-observatory/dls_fill.py:235-244)의 규칙인데 옮겨 오면서
    빠져 있었습니다. 2026-09-01 에 되살립니다.

    빠뜨리면 안 되는 이유가 있습니다. 랜섬 그룹은 DLS 옆에 협상용 Chat
    미러를 같이 걸어 둡니다. type 을 안 보면 그 Chat 이 살아있다는
    이유만으로 대표가 되고, 「주소」는 덮어쓰는칸(place.py)이라 사람이
    적어 둔 DLS 주소 위에 그대로 덮입니다.

    DLS 가 하나도 없으면 전체를 후보로 씁니다. 「DLS 가 없다」와
    「위치가 없다」는 다릅니다.

    slug 가 스킴까지 붙은 주소입니다. fqdn 은 호스트만이라 노션 url 칸에
    넣으면 링크가 안 걸립니다. slug 가 없으면 http:// 를 붙여 보고,
    그래도 http 로 시작하지 않으면 **대표로 안 씁니다.** 예전에는 이
    설명을 적어 놓고 fqdn 을 그대로 넣고 있었습니다.

    미러 쪽은 slug 를 먼저 씁니다. 원본은 fqdn 만 적었는데, 스킴이 붙은
    편이 사람이 그대로 눌러 볼 수 있습니다.

    **DLS 가 아닌 위치는 미러로 안 냅니다.** 「이전 주소」는 이 DLS 가
    옮겨 다닌 자취를 적는 칸이고, 협상용 Chat 은 그것이 아닙니다. 섞어
    두면 다음 사람이 Chat 을 옛 DLS 주소로 읽습니다.

    원본은 그것을 「연결된 곳」에 "Chat: xxx.onion" 꼴로 적었습니다.
    여기서는 안 적습니다 — place.py 의 자동금지칸 주석이 「연결된 곳」을
    **우리 명부에 있는 곳일 때만** 쓰는 조건으로 빈칸만칸에 두었는데,
    이 Chat 주소는 명부에 없는 값입니다. 어디에 적을지는 팀이 정할
    일이라 남겨 둡니다.
    """
    locs = [loc for loc in (g.get("locations") or []) if isinstance(loc, dict)]
    후보 = [loc for loc in locs
          if str(loc.get("type") or "").upper() == "DLS"] or locs

    대표, 미러 = "", []
    if 후보:
        # 살아있는 것을 먼저. 없으면 첫째를 씁니다(원본과 같습니다).
        으뜸 = next((loc for loc in 후보 if loc.get("available")), 후보[0])
        슬러그 = str(으뜸.get("slug") or "").strip()
        호스트 = str(으뜸.get("fqdn") or "").strip()
        주소 = 슬러그 or (f"http://{호스트}" if 호스트 else "")
        if 주소.startswith("http"):
            대표 = 주소
        for loc in 후보:
            if loc is 으뜸:
                continue
            x = str(loc.get("slug") or loc.get("fqdn") or "").strip()
            if x and x not in 미러:
                미러.append(x)

    if not 대표 and not 미러:
        # 쓸 만한 위치가 하나도 없을 때만 /groups 의 url 로 물러납니다.
        return str(g.get("url") or ""), ""
    return 대표, " · ".join(미러[:5])


# ── 월별 피해 목록으로 세기 ────────────────────────────────────────
def _달들(n: int) -> list[tuple[int, int]]:
    """이번 달부터 거슬러 n 달."""
    오늘 = _오늘()          # 기계 시간대가 아니라 한국 기준입니다
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
    없습니다. 한 달에 한 요청입니다. 기본은 위 `개월` 이 정하고 지금은
    여섯이라 **여섯 요청**입니다. 「기본 세 달」이라고 적혀 있던 것은
    2026-08-30 에 개월이 0 → 6 으로 바뀌기 전 설명입니다.
    """
    모음: dict = {}
    못본달: list[str] = []
    # 180일 창의 첫날. 이 날부터 오늘까지 게시된 것만 셉니다
    시작 = (_오늘() - timedelta(days=창 - 1)).isoformat()
    실패 = 0
    달들 = list(_달들(개월수))
    # **진행을 찍습니다.** 62초 간격이라 여섯 달이면 6분 넘게 걸리는데, 그동안
    # 화면에 아무것도 안 나와 멈춘 것으로 읽힙니다. 2026-09-22 첫 CI 판에서
    # 「ransom: 508줄을 봅니다」 뒤가 7분 비어 사람이 실제로 그렇게 봤습니다.
    # 간격은 저쪽 rate limit(1req/분)이라 줄이지 않습니다. 보이게만 합니다
    print(f"    집계처에서 피해 {len(달들)}달치를 받습니다 "
          f"(요청 사이 {간격:.0f}초라 {len(달들) * 간격 / 60:.0f}분쯤 걸립니다)",
          flush=True)
    for i, (년, 월) in enumerate(달들, 1):
        try:
            건들 = _받기(rl_victims(년, 월), 마지막, op)
            실패 = 0
            print(f"      {i}/{len(달들)}  {년}-{월:02d}  {len(건들) if isinstance(건들, list) else 0}건",
                  flush=True)
        except (urllib.error.URLError, OSError, ValueError) as e:
            못본달.append(f"{년}-{월:02d}({type(e).__name__})")
            실패 += 1
            if 실패 >= 연속실패_상한:
                # 멈추면 뒤의 달은 안 물었다. 그것도 못 받은 달로 적어야 「N달 중 M달」 이
                # 맞게 나온다. 안 적으면 하나도 못 받은 판이 반쯤 받은 판으로 보였다(2026-09-25 검토)
                못본달 += [f"{y}-{m:02d}(안 물음)" for y, m in 달들[i:]]
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
            # **180일 창 밖이면 안 셉니다.** 받는 달이 일곱이라 첫 달 앞쪽은 창 밖입니다.
            # 날짜가 없는 건은 어느 창에 드는지 몰라 안 셉니다
            when = str(v.get("attackdate") or v.get("discovered") or "")[:10]
            if not when or when < 시작:
                continue
            d = 모음.setdefault(g, {"건수": 0, "마지막": "",
                                   "업종": collections.Counter(), "한국": 0})
            d["건수"] += 1
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

    요청 수는 1 + 개월수 입니다. **개월수 기본값이 6**(위 `개월`)이라
    실제로는 일곱 번 나가고, 62초 간격이라 한 판에 6분쯤 더 걸립니다.

    「기본은 개월수가 0 이라 한 번입니다. 피해 집계는 dls_fill 소관입니다」
    라고 적혀 있었습니다. 2026-08-30 에 개월을 0 → 6 으로 올리고 피해
    집계를 이쪽으로 가져오면서(위 `개월` 주석) 이 설명만 안 고쳤습니다.
    이 설명을 믿고 요청 수를 1로 잡으면 6분을 모르고 씁니다.
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

    print("    집계처에서 그룹 목록을 받습니다", flush=True)
    try:
        그룹들 = _받기(rl_groups(), 마지막, op)
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
    # 받는 달 수와 세는 구간은 다릅니다. 일곱 달을 받아 180일만 셉니다
    기간 = f"최근 {창}일" if 개월수 > 0 else ""
    if 못본달:
        # 대시보드 로그 요약이 이 줄을 집습니다 (worker.js 요약무늬). 문구를 바꾸면 거기도 봅니다
        print(f"    피해 목록 {개월수}달 중 {len([x for x in 못본달 if '(' in x])}달을 못 받아 "
              "규모 · 피해 대상 · 한국 관련 유출 · 최근 활동은 이번 판에 안 씁니다", flush=True)

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

        # **못 받은 달이 있으면 피해 목록으로 센 네 칸을 안 채웁니다** (2026-09-25 최현서 결정).
        #
        # 규모 · 피해 대상 · 한국 관련 유출 · 최근 활동은 6달치를 다 받아야 맞는 숫자입니다.
        # 한 달이 빠진 채로 쓰면 노션 숫자가 내려갔다가 다음 판에 돌아옵니다. 9/23 미리보기가
        # 2026-06 을 못 받아 규모 52 · 피해 대상 46 줄이 바뀐다고 나왔는데, 다 받은 판은
        # 14 · 9 였습니다.
        #
        # 값을 안 채우면 노션값() 이 그 칸을 안 냅니다. 노션의 지금 값이 그대로 남습니다.
        # 상태 · 확인일 · 주소는 그룹 목록에서 오므로 그대로 씁니다.
        if d and not 못본달:
            p.피해기업수 = d["건수"]          # 180일 건수. 시계열 표에 쌓습니다
            p.피해월평균 = round(d["건수"] / (창 / 30), 1)
            p.피해기간 = 기간
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
