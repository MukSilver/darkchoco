"""수집기 일곱을 차례로 돌려 Place 하나로 만듭니다.

수집기는 **이미 노션 칸 이름으로** 돌려줍니다.

    result["어니언 주소"] = {"value": ..., "observed_at": ..., "source": ...}
    result["최근 게시일"] = {...}
    result["_들어가는_법_가입폼"] = {...}      밑줄로 시작하면 조각입니다

그래서 여기가 하는 일은 셋뿐입니다.

    1. 차례대로 부르고, 하나가 죽어도 나머지를 돕니다
    2. 칸 이름을 Place 의 이름으로 옮깁니다
    3. **못 돈 수집기를 적습니다.** 조용히 빠뜨리면 나중에 왜 칸이
       비었는지 못 찾습니다

page 가 없으면(=http 로 열었으면) 다섯은 못 돕니다. 그것도 적습니다.
"""

from __future__ import annotations

from hub.places import collect as C
from hub.places.place import Place, 덧붙임

__all__ = ["모으기", "칸이름"]

# 노션 칸 이름 → Place 의 칸 이름
칸이름 = {
    "어니언 주소": "어니언",
    "사용 언어": "언어",
    "들어가는 법": "들어가는법",
    "이전 주소": "이전주소",
    "이전 이름·별칭": "이전이름",
    "어떤 곳인지": "어떤곳",
    "가입 필요": "가입필요",
    "피해 대상": "피해대상",
    "한국 관련 유출": "한국유출",
    "연락수단": "연락수단",
    "연결된 곳": "연결된곳",
    "유통 자리": "유통자리",
    "개인정보 유출": "개인정보",
    "최근 활동": "최근활동",
    "최근 게시일": "최근활동",
    "주소": "주소",
    "상태": "상태",
}

# 밑줄로 시작하는 조각을 어느 칸에 합치나
조각 = {"_들어가는_법": "들어가는법", "_어떤_곳인지": "어떤곳",
      "_유통_자리": "유통자리", "_개인정보": "개인정보"}


def _값(v):
    """{"value": ...} 또는 {"state": "CONFIRMED_ABSENT"} 입니다."""
    if not isinstance(v, dict):
        return v
    if v.get("state") == "CONFIRMED_ABSENT":
        return None                 # 없는 것을 확인한 것입니다. 안 씁니다
    return v.get("value")


def _조각칸(키: str) -> str | None:
    for 앞, 칸 in 조각.items():
        if 키.startswith(앞):
            return 칸
    return None


def 모으기(연것, 이름: str, *, 갈래: str = "forum",
        source: dict | None = None) -> Place:
    """한 곳을 깊게 봅니다.

    연것 은 fetch.열기() 가 돌려준 것입니다. page 가 있으면 일곱을 다
    돌리고, 없으면 글자만으로 되는 것만 돌립니다.
    """
    p = Place(갈래=갈래, 이름=이름, 주소=연것.최종주소 or 연것.주소)
    src = dict(source or {})
    src.setdefault("name", 이름)
    src.setdefault("url", 연것.주소)

    if not 연것.봤나():
        p.못본이유 = 연것.못본이유
        return p

    p.두드림 = True
    글모음 = {"첫 화면": 연것.본문}
    게시글: list = []
    못돈것: list[str] = []

    for 수집기이름 in C.차례:
        필요 = C.필요한것.get(수집기이름, "page")
        if 필요 == "page" and 연것.page is None:
            못돈것.append(수집기이름)
            continue
        try:
            mod = __import__(f"hub.places.collect.{수집기이름}",
                             fromlist=["run"])
            if 필요 == "본문":
                결과 = mod.run(글모음, src)
            elif 필요 == "게시글":
                결과 = mod.run(게시글, src)
            else:
                결과 = mod.run(연것.page, src)
        except Exception as e:      # noqa: BLE001  하나가 죽어도 나머지를 돕니다
            못돈것.append(f"{수집기이름}({type(e).__name__})")
            continue

        if not isinstance(결과, dict):
            continue
        for 키, 값 in 결과.items():
            v = _값(값)
            if v in (None, "", [], {}):
                continue
            if 키 == "posts" or 키 == "게시글":
                if isinstance(v, list):
                    게시글 = v
                continue
            칸 = 칸이름.get(키) or _조각칸(키)
            if not 칸:
                continue
            옛 = getattr(p, 칸, None)
            if 칸 == "유통자리":
                이제 = list(옛 or [])
                for x in (v if isinstance(v, list) else [v]):
                    if x not in 이제:
                        이제.append(x)
                setattr(p, 칸, 이제)
            elif isinstance(옛, str) and 옛:
                if str(v) not in 옛:
                    setattr(p, 칸, f"{옛} · {v}")
            else:
                setattr(p, 칸, v if not isinstance(v, list) else " · ".join(map(str, v)))

    p.받은곳 = f"수집기 {len(C.차례) - len(못돈것)}/{len(C.차례)} ({연것.여는법})"
    if 못돈것:
        # **조용히 빠뜨리지 않습니다.** 왜 칸이 비었는지 나중에 찾을 수
        # 있어야 합니다.
        덧붙임(p, "못 돈 수집기: " + ", ".join(못돈것))
    return p
