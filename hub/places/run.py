"""통합 크롤러. 세 갈래를 한 번에 돕니다.

    python dc.py crawl                  세 갈래 전부 (미리보기)
    python dc.py crawl --apply          실제로 노션에 씁니다
    python dc.py crawl --only telegram  한 갈래만

명부를 읽고, 갈래에 맞는 조사기를 돌리고, 다시 명부에 반영합니다.
갈래가 늘어도 여기는 안 바뀝니다. 조사기 하나와 표 한 줄만 더하면 됩니다.

지키는 것 넷입니다.

  1. 한 갈래가 죽어도 나머지는 돕니다
  2. 주소가 없는 줄은 조사 대상이 아닙니다. 실패로 세지 않습니다
  3. 기본은 미리보기입니다. --apply 를 줘야 씁니다
  4. 숫자는 우리 쪽 SQLite 에 시계열로 쌓습니다
"""

from __future__ import annotations

import sqlite3
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages"))
sys.path.insert(0, str(ROOT))

from hub.places.write import 갈래별_DB, 명부, 반영결과  # noqa: E402
from hub.places.backoff import 기록 as 두드림기록  # noqa: E402
from hub.places.merge import 합치기  # noqa: E402
from hub.places.place import Place  # noqa: E402
from hub.places.extract import links
from hub.places.probe import forum, ransom, telegram  # noqa: E402

__all__ = ["한갈래", "여러갈래", "표로", "기본_표", "갈래들",
           "차례", "됐다고_적기"]

갈래들 = ("telegram", "forum", "ransom")

# 서로 다른 서버를 동시에 몇 개까지 볼까. Tor 회로가 그만큼 늘어납니다.
# 크게 잡으면 오히려 느려지고 출구 하나에서 요청이 몰립니다.
최대동시 = 6

# 갈래마다 주기가 다릅니다. 무거운 것을 자주 돌리지 않습니다.
주기 = {"telegram": 360, "forum": 720, "ransom": 720}   # 분


def 기본_표() -> Path:
    return ROOT / "hub" / "data" / "places.db"


_시계열 = """
CREATE TABLE IF NOT EXISTS 규모 (
    갈래   TEXT NOT NULL,
    이름   TEXT NOT NULL,
    본때   TEXT NOT NULL,
    상태   TEXT,
    회원수 INTEGER, 게시물수 INTEGER, 구독자수 INTEGER, 피해기업수 INTEGER,
    어림수 INTEGER DEFAULT 0,
    PRIMARY KEY (갈래, 이름, 본때)
);
"""


@dataclass
class 갈래결과:
    갈래: str
    본것: int = 0
    못본것: int = 0
    바뀐줄: int = 0
    건너뜀: int = 0          # 주소가 없어 조사 못 한 줄
    쉰것: int = 0            # 연속 실패로 이번 판은 안 두드린 줄
    문제: list = field(default_factory=list)
    상태셈: dict = field(default_factory=dict)   # online 몇 · offline 몇 …
    이유셈: dict = field(default_factory=dict)   # 못 본 까닭별로
    처음본곳: dict = field(default_factory=dict)   # 호스트 → {어디서 봤나}
    오류: str = ""
    초: float = 0.0
    줄별: list = field(default_factory=list)


def _쌓기(db: Path, 갈래: str, 목록: list[Place]) -> None:
    """숫자를 시계열로 남깁니다. 노션은 현재만 담으므로 여기가 기록입니다."""
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db))
    try:
        conn.executescript(_시계열)
        for p in 목록:
            수 = p.숫자들()
            if not 수 and p.상태 == "미확인":
                continue
            conn.execute(
                "INSERT OR REPLACE INTO 규모 "
                "(갈래,이름,본때,상태,회원수,게시물수,구독자수,피해기업수,어림수) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (갈래, p.이름, p.확인일[:10], p.상태,
                 수.get("회원수"), 수.get("게시물수"),
                 수.get("구독자수"), 수.get("피해기업수"), int(p.어림수)))
        conn.commit()
    finally:
        conn.close()


# ── 갈래마다 다른 것은 이 아래 표 하나입니다 ────────────────────────
#
# 예전에는 `_조사()` 안이 if telegram / elif forum / elif ransom 세
# 덩이였고, 랜섬 분기가 나머지 둘을 합친 것보다 길었습니다. 수집기를
# 얹으려면 세 곳에 각각 붙여야 했습니다.
#
# 흐름을 하나로 두고 **갈래 차이를 표로만** 냅니다.
#
#     ① 볼 곳 고르기   write.py 가 노션에서 읽습니다
#     ② 나가는 길      egress.py — 갈래 상관없이 하나
#     ③ 열기           갈래마다 여는 법이 다릅니다   ← 표
#     ④ 뽑기           수집기                        ← 표 (다음 단계)
#     ⑤ 합치기         merge.py
#     ⑥ 쓰기           write.py 관문 다섯
#
# 갈래가 넷째로 늘어도 표에 한 줄만 더합니다.


def _텔레그램_열기(r, 상황):
    return telegram.한곳(r.주소, 상황["마지막"], r.이름,
                       프록시=상황["프록시"], 이음사전=상황["이음사전"])


def _포럼_열기(r, 상황):
    return forum.한곳(r.주소, r.이름, 상황["마지막"], 프록시=상황["프록시"],
                    이음사전=상황["이음사전"],
                    어니언미러=bool(상황["프록시"]),
                    어니언=getattr(r, "어니언", ""))


def _랜섬_열기(r, 상황):
    """랜섬 주소도 포럼 조사기로 엽니다. 뽑는 것이 같습니다.

    어니언 미러 찾기는 안 합니다. 랜섬은 명부에 어니언이 이미 적혀
    있어서 후보를 다시 찾을 이유가 없습니다.
    """
    q = forum.한곳(r.주소, r.이름, 상황["마지막"], 프록시=상황["프록시"],
                 이음사전=상황["이음사전"], 어니언미러=False,
                 어니언=getattr(r, "어니언", ""))
    q.갈래 = "ransom"
    q.출처 = ["직접 확인"]
    return q


def _랜섬_앞선것(줄들, 상황):
    """한 판에 한 번, 목록을 통째로 받습니다.

    그룹 하나씩 조회하면 요청이 폭발합니다. /groups 한 번으로 392개
    상태를 봅니다. 결과는 page_id 로 찾을 수 있게 돌려줍니다.
    """
    이름별 = {r.이름.strip().lower(): r for r in 줄들}
    out = {}
    for p in ransom.조사(limit=상황.get("limit", 0), 프록시=상황["프록시"]):
        r = 이름별.get(p.이름.strip().lower())
        if r is not None:
            out[r.page_id] = p
    return out


# 깊게 보는 판을 돌릴 갈래. 수집기 일곱이 Playwright page 를 받습니다.
#
# **브라우저는 막힌 곳을 뚫는 도구가 아닙니다.** 2026-08-30 에 포럼
# 20줄로 http 와 나란히 재봤습니다.
#
#     둘 다 못 봄 14 · 둘 다 4 · http 만 2 · **browser 만 0**
#
# 브라우저가 더 여는 곳은 하나도 없었고 두 곳에서는 졌습니다 —
# 클라우드플레어가 진짜 헤드리스 크롬을 더 잘 알아봅니다. 「연결이 안
# 됩니다」도 대부분 Tor 터널 실패지 앞단 검사가 아니었습니다.
#
# 그러니 브라우저의 값은 **연 곳을 더 깊게 보는 것**입니다. http 로
# 열린 곳만 다시 열어 수집기를 돌립니다.
깊게볼갈래 = {"forum", "ransom"}

갈래표 = {
    "telegram": {
        "여는법": _텔레그램_열기,
        "앞선것": None,
        # t.me 한 호스트라 동시에 열면 그쪽을 힘들게 합니다.
        "동시": 1,
        "마지막": list,          # 호스트가 하나 — 마지막 시각 한 개
    },
    "forum": {
        "여는법": _포럼_열기,
        "앞선것": None,
        # 269줄이 전부 다른 호스트입니다. 동시에 봐도 어느 한 곳을
        # 힘들게 하지 않습니다. 같은 호스트를 두 번 칠 때는 forum.py 가
        # 간격을 지킵니다.
        "동시": None,            # None 이면 최대동시
        "마지막": dict,          # 호스트마다 따로
    },
    "ransom": {
        "여는법": _랜섬_열기,
        "앞선것": _랜섬_앞선것,
        "동시": None,
        "마지막": dict,
    },
}


def _조사(갈래: str, 줄들, ctx: dict):
    """한 갈래를 돕니다. (줄, Place) 를 내놓습니다.

    **갈래를 보고 가르지 않습니다.** 갈래표에서 여는 법만 꺼내 씁니다.

    프록시는 셋 다 받습니다. 하나라도 빠지면 그 갈래만 우리 IP 로
    나갑니다.
    """
    if 갈래 not in 갈래표:
        raise ValueError(f"모르는 갈래입니다: {갈래}")
    설정 = 갈래표[갈래]
    프록시 = ctx.get("tor")

    상황 = {
        "프록시": 프록시,
        "이음사전": ctx.get("이음사전"),
        "limit": ctx.get("limit", 0),
        "마지막": 설정["마지막"]() if 설정["마지막"] is not dict else {},
    }
    if 설정["마지막"] is list:
        상황["마지막"] = [0.0]

    def _한줄(부르기, r):
        """**한 줄이 죽어도 나머지는 돕니다.**

        조사기 안의 except 는 연결 실패만 잡습니다. 명부에 이상한 값이
        적혀 있으면 ValueError 같은 것이 올라와 판 전체를 죽입니다.
        실제로 "nulled.to" 한 줄이 47분치 작업을 날렸습니다.

        걸린 초도 여기서 잽니다. 조사기마다 재면 세 곳을 고쳐야 하고,
        한 곳을 빠뜨리면 그 갈래만 숫자가 없습니다.
        """
        시작 = time.time()
        try:
            p = 부르기()
        except Exception as e:  # noqa: BLE001
            p = Place(갈래=갈래, 이름=r.이름, 주소=r.주소,
                      못본이유=f"이 줄에서 터졌습니다: {type(e).__name__}: {e}"[:180],
                      받은곳="조사 중 예외")
            p.살펴볼것 = "명부의 값이 이상할 수 있습니다. 주소를 보십시오"
        p.걸린초 = round(time.time() - 시작, 2)
        return p

    # ── ③ 앞선 것. 목록을 통째로 받는 갈래만 있습니다
    미리: dict = {}
    if 설정["앞선것"]:
        try:
            미리 = 설정["앞선것"](줄들, 상황)
        except Exception as e:  # noqa: BLE001
            미리 = {}
            print(f"    앞선 조사가 실패했습니다: {type(e).__name__}: {e}"[:160],
                  flush=True)

    # ── ④ 열 것 고르기. 주소가 아예 없으면 못 엽니다
    열것 = [r for r in 줄들
          if (r.주소 or "").strip() or (getattr(r, "어니언", "") or "").strip()]
    if 미리 and not 프록시:
        열것 = []            # Tor 가 없으면 앞선 것만 냅니다

    def _한곳(r):
        q = _한줄(lambda: 설정["여는법"](r, 상황), r)
        # 조사기가 여럿 붙는 규칙은 merge.py 한 곳에만 둡니다.
        # dls-observatory 가 붙으면 **인자를 하나 더 줍니다.**
        #     return 합치기(q, 미리.get(...), DLS가준것)
        return 합치기(q, 미리.get(r.page_id))

    동시 = 설정["동시"] or 최대동시
    if not 프록시:
        동시 = 1                 # 맨 연결이면 어차피 안 나갑니다

    본것 = set()
    if 동시 <= 1:
        for r in 열것:
            본것.add(r.page_id)
            yield r, _한곳(r)
    else:
        import concurrent.futures as cf

        with cf.ThreadPoolExecutor(max_workers=동시) as 풀:
            일 = {풀.submit(_한곳, r): r for r in 열것}
            for 끝난것 in cf.as_completed(일):
                r = 일[끝난것]
                본것.add(r.page_id)
                yield r, 끝난것.result()

    # ── ⑤ 못 연 줄도 앞선 것이 있으면 그것만이라도 냅니다
    이름별 = {r.page_id: r for r in 줄들}
    for pid, p in 미리.items():
        if pid not in 본것 and pid in 이름별:
            yield 이름별[pid], p


def 깊게(갈래: str, 열린것, ctx: dict):
    """열린 곳만 브라우저로 다시 열어 수집기 일곱을 돌립니다.

    **순차로 돕니다.** Playwright 의 동기 API 는 스레드 안전하지
    않습니다. 여러 스레드에서 같은 세션을 쓰면 조용히 엉킵니다.

    크롬은 한 번만 띄웁니다. 줄마다 띄우면 뜨는 데만 1~2초씩이라
    그것만으로 수십 분이 됩니다.

    (줄, 깊은Place) 를 내놓습니다. 상태는 주장하지 않습니다 — 브라우저가
    403 을 받아도 그 곳이 죽은 것은 아닙니다. 상태는 http 가 정합니다.
    """
    프록시 = ctx.get("tor")
    if 갈래 not in 깊게볼갈래 or not 프록시 or not 열린것:
        return

    from hub.places.collect.모으기 import 모으기          # noqa: PLC0415
    from hub.places.fetch import 브라우저세션, 브라우저없음, 열기  # noqa: PLC0415

    try:
        세션열기 = 브라우저세션(프록시)
    except 브라우저없음:
        return
    try:
        with 세션열기 as 세션:
            for r in 열린것:
                주소 = (r.주소 or "").strip()
                if not 주소:
                    continue
                try:
                    연것 = 열기(주소, 법="browser", 프록시=프록시,
                              timeout=40, 세션=세션)
                    if not 연것.봤나():
                        continue
                    q = 모으기(연것, r.이름, 갈래=갈래)
                except Exception as e:      # noqa: BLE001  한 줄이 죽어도 나머지를 돕니다
                    continue
                # 상태를 안 넘깁니다. 브라우저 403 이 http 200 을 덮으면
                # 살아있는 곳이 미확인이 됩니다.
                q.두드림 = False
                q.상태 = "미확인"
                yield r, q
    except 브라우저없음:
        return


def 이음사전만들기(갈래들목록=None) -> dict:
    """세 명부의 주소를 한 사전으로 모읍니다.

    「연결된 곳」을 채우려면 이것이 필요합니다. 첫 화면에서 찾은 링크가
    **우리 명부에 있는 곳일 때만** 관계로 셉니다. 처음 보는 주소를
    관계로 적으면 그것은 잡음입니다.

    한 판에 한 번만 만듭니다. 노션을 세 번 더 읽지만 그 뒤로는 안
    읽습니다.
    """
    명부들 = {}
    for g in (갈래들목록 or list(갈래들)):
        try:
            명부들[g] = 명부(g).줄들()
        except Exception:  # noqa: BLE001  한 갈래가 안 읽혀도 나머지로 만듭니다
            continue
    return links.이름표만들기(명부들)


def 한갈래(갈래: str, *, apply: bool = False, limit: int = 0,
         db: Path | None = None, tor: str | None = None,
         이음사전: dict | None = None,
         조용히: bool = False) -> 갈래결과:
    """한 갈래를 돕니다. 예외를 밖으로 안 냅니다."""
    r = 갈래결과(갈래=갈래)
    t0 = time.time()
    try:
        m = 명부(갈래)
        줄들 = m.줄들()
    except Exception as e:  # noqa: BLE001
        r.오류 = f"{type(e).__name__}: {e}"[:200]
        r.초 = time.time() - t0
        return r

    # **어니언만 있는 줄도 봅니다.** 포럼 명부 45줄이 클리어넷 주소가
    # 없는데, 그중 37줄에는 어니언이 적혀 있습니다. 지금까지 한 번도
    # 안 봤습니다.
    볼것 = [x for x in 줄들
          if (x.주소 or "").strip() or (getattr(x, "어니언", "") or "").strip()]
    r.건너뜀 = len(줄들) - len(볼것)

    # **연속으로 죽어 있던 곳은 이번 판을 쉽니다.**
    #
    # 한 판 53분 중 47분이 죽은 주소를 기다리는 시간이었습니다. 어제
    # 죽었으면 오늘도 죽었을 가능성이 큽니다. 최대 두 주가 지나면 다시
    # 보므로 부활한 곳을 놓치지 않습니다. 자세한 것은 backoff.py 에.
    #
    # **쉰 줄은 노션을 안 건드립니다.** 확인일도 안 바꿉니다.
    # 「오늘 봤는데 죽어 있었다」와 「오늘 안 봤다」는 다릅니다.
    지금때 = time.time()
    자취 = 두드림기록(db or 기본_표())
    try:
        볼것, 쉰것 = 자취.거를것(갈래, 볼것, 지금때)
    except Exception:  # noqa: BLE001  자취가 깨져도 조사는 돕니다
        쉰것 = []
    r.쉰것 = len(쉰것)

    if limit:
        볼것 = 볼것[:limit]

    본것: list[Place] = []
    셀것 = len(볼것)
    if not 조용히 and 셀것:
        쉼말 = f" (연속 실패로 {r.쉰것}줄은 쉽니다)" if r.쉰것 else ""
        print(f"  {갈래}: {셀것}줄을 봅니다{쉼말}", flush=True)

    ctx = {"tor": tor, "limit": limit, "이음사전": 이음사전}

    # ── 얕은 판. http 로 동시에 봅니다
    #
    # 깊은 판에 넘길 것을 여기서 모읍니다. **열린 곳만** 넘깁니다 —
    # 안 열린 곳을 브라우저로 다시 여는 것은 30초를 두 번 버리는 일입니다.
    깊게볼것: list = []
    얕은것: dict = {}

    for 줄, p in _조사(갈래, 볼것, ctx):
        if p.상태 == "online" and (줄.주소 or "").startswith("http"):
            깊게볼것.append(줄)
            얕은것[줄.page_id] = p
        본것.append(p)
        r.상태셈[p.상태] = r.상태셈.get(p.상태, 0) + 1
        if p.못본이유:
            # 까닭의 앞머리만 셉니다. 뒤에는 예외 이름 같은 것이 붙습니다.
            까닭 = p.못본이유.split(".")[0].split("(")[0].strip()[:38]
            r.이유셈[까닭] = r.이유셈.get(까닭, 0) + 1
        # **끝나야 결과가 나오면 지금 몇 줄째인지 알 수가 없습니다.**
        # 포럼 269줄이 Tor 를 거치면 한 시간 넘게 걸립니다. 사람이 볼
        # 때도, 자동으로 돌 때 로그를 볼 때도 진행이 보여야 합니다.
        n = len(본것)
        if not 조용히 and 셀것 and (n % 10 == 0 or n == 셀것):
            지난 = time.time() - t0
            남은 = 지난 / n * (셀것 - n) if n else 0
            print(f"    {n}/{셀것}줄 · {지난 / 60:.0f}분 지남 · "
                  f"{남은 / 60:.0f}분쯤 남음", flush=True)
        if p.봤나():
            r.본것 += 1
        else:
            r.못본것 += 1
        try:
            자취.적기(갈래, getattr(줄, "page_id", ""), p.봤나(),
                    지금때, getattr(p, "걸린초", 0.0))
        except Exception:  # noqa: BLE001  자취가 깨져도 조사는 돕니다
            pass
        try:
            res = m.반영(줄, p, apply=apply)
        except Exception as e:  # noqa: BLE001  한 줄이 죽어도 나머지는 돕니다
            res = 반영결과(이름=줄.이름, 오류=str(e)[:160])
        r.줄별.append(res)
        if res.오류:
            r.문제.append(f"{res.이름}: {res.오류}")
        if res.건너뛴칸:
            r.문제.append(f"{res.이름}: 스키마에 없는 칸 {res.건너뛴칸}")
        if res.없는옵션:
            # 노션 선택지에 없어 버린 값입니다. 안 올리면 조용히
            # 사라집니다. 포럼의 「압수됨」이 그렇게 사라지고 있었습니다.
            r.문제.append(f"{res.이름}: 선택지에 없어 안 씀 {res.없는옵션}")
        if p.살펴볼것:
            r.문제.append(f"{res.이름}: {p.살펴볼것}")
        if res.사람판정:
            r.문제.append(f"{res.이름}: {res.사람판정}")
        for h in getattr(p, "처음본곳", ()):
            # 여러 곳이 같은 호스트를 걸어 두면 그것이 더 중요한 실마리입니다.
            # setdefault 로 하나만 담으면 그 사실을 원리상 못 셉니다.
            r.처음본곳.setdefault(h, set()).add(res.이름 or p.이름)
        if res.바뀐칸:
            r.바뀐줄 += 1

    # ── 깊은 판. 열린 곳만 브라우저로 다시 열어 수집기 일곱을 돌립니다
    #
    # 순차라 느립니다. 그래서 열린 곳만 봅니다 — 실측으로 20줄 중
    # 4~6곳입니다.
    if 깊게볼것 and not 조용히:
        print(f"    깊게 {len(깊게볼것)}줄 (브라우저)", flush=True)
    깊게샘 = 0
    for 줄, 깊은 in 깊게(갈래, 깊게볼것, ctx):
        앞 = 얕은것.get(줄.page_id)
        # 얕은 것이 바탕입니다. 상태와 규모는 http 가 더 믿을 만합니다.
        # 깊은 것은 빈칸만 채웁니다.
        합친것 = 합치기(앞, 깊은) if 앞 else 깊은
        깊게샘 += 1
        try:
            res = m.반영(줄, 합친것, apply=apply)
        except Exception as e:  # noqa: BLE001
            res = 반영결과(이름=줄.이름, 오류=str(e)[:160])
        r.줄별.append(res)
        if res.바뀐칸:
            r.바뀐줄 += 1
        if 합친것.살펴볼것:
            r.문제.append(f"{res.이름}: {합친것.살펴볼것}")
    if 깊게샘 and not 조용히:
        print(f"    깊게 본 것 {깊게샘}줄", flush=True)

    if apply and 본것:
        # 한갈래() 는 예외를 밖으로 안 냅니다. 이 한 줄만 밖에 있어서,
        # 표가 깨지면 dc.py crawl 과 dc.py auto 가 통째로 죽었습니다.
        # 시계열을 못 쌓는 것과 조사를 못 하는 것은 다른 일입니다.
        try:
            _쌓기(db or 기본_표(), 갈래, 본것)
        except Exception as e:  # noqa: BLE001
            r.문제.append(f"시계열을 못 쌓았습니다: {type(e).__name__}: {e}"[:200])

    # 두드린 자취는 **미리보기에서도 남깁니다.** 노션에 쓰는 것과
    # 두드렸다는 사실은 다른 일입니다. 미리보기로 30초를 기다린 것도
    # 기다린 것이라, 여기서 안 남기면 백오프가 영영 안 걸립니다.
    try:
        자취.저장()
    except Exception as e:  # noqa: BLE001
        r.문제.append(f"두드린 자취를 못 남겼습니다: {type(e).__name__}"[:120])
    finally:
        try:
            자취.close()
        except Exception:  # noqa: BLE001
            pass

    r.초 = time.time() - t0
    return r


# ── 차례표 ─────────────────────────────────────────────────────────
# 수집기가 쓰는 표를 같이 씁니다. 이름만 "crawl:" 을 붙여 갈라 둡니다.
# 표를 따로 두면 언제 무엇이 돌았는지를 두 군데서 봐야 합니다.
def _차례이름(갈래: str) -> str:
    return f"crawl:{갈래}"


def 차례(db: Path | None = None) -> list[tuple[str, str]]:
    """지금 돌 때가 된 갈래들. (갈래, 이유) 입니다."""
    from hub.sched import Sched

    s = Sched(db or 기본_표())
    try:
        나온것 = []
        for 갈래 in 갈래들:
            d = s.언제(_차례이름(갈래), 주기[갈래])
            if d:
                나온것.append((갈래, d.이유))
        return 나온것
    finally:
        s.close()


def 됐다고_적기(결과: list[갈래결과], db: Path | None = None) -> None:
    """돈 결과를 차례표에 적습니다.

    **실패했으면 마지막 시각을 안 건드립니다.** 건드리면 실패 한 번이
    다음 시도를 주기만큼 미룹니다. 12시간짜리는 하루가 되어 사실상
    멈춥니다. Sched 가 대신 짧은 재시도 간격을 씁니다.
    """
    from hub.sched import Sched

    s = Sched(db or 기본_표())
    try:
        for r in 결과:
            이름 = _차례이름(r.갈래)
            if r.오류:
                s.안됐다(이름, r.오류[:200])
            else:
                s.됐다(이름, f"{r.본것}곳 · 바뀐 줄 {r.바뀐줄}")
    finally:
        s.close()


def 여러갈래(대상: list[str] | None = None, *, apply: bool = False,
          limit: int = 0, db: Path | None = None,
          tor: str | None = None, 때된것만: bool = False,
          조용히: bool = False) -> list[갈래결과]:
    """갈래들을 차례로 돕니다.

    때된것만=True 면 주기가 찬 갈래만 돕니다. 스케줄러가 자주 부르는데
    매번 셋을 다 돌면 상대 서버를 힘들게 하고, 랜섬은 한 판에 4분씩
    씁니다.
    """
    if 대상:
        돌것 = 대상
    elif 때된것만:
        돌것 = [g for g, _ in 차례(db)]
    else:
        돌것 = list(갈래들)

    # 「연결된 곳」을 채우려면 세 명부를 다 알아야 합니다. 한 판에 한 번만
    # 만들고 갈래마다 물려 줍니다.
    사전 = 이음사전만들기() if 돌것 else {}
    if 사전 and not 조용히:
        print(f"  명부 {len(사전)}곳을 이음 사전에 담았습니다", flush=True)
    out = []
    for 갈래 in 돌것:
        out.append(한갈래(갈래, apply=apply, limit=limit, db=db, tor=tor,
                        이음사전=사전, 조용히=조용히))
    # 미리보기는 차례를 안 건드립니다. 안 썼는데 돌았다고 적으면
    # 다음 실제 반영이 주기만큼 밀립니다.
    if apply and out:
        됐다고_적기(out, db)
    return out


def 표로(결과: list[갈래결과], *, apply: bool) -> str:
    if not 결과:
        return "  돌린 갈래가 없습니다."
    줄 = []
    for r in 결과:
        이름 = 갈래별_DB.get(r.갈래, (r.갈래,))[0]
        if r.오류:
            줄.append(f"  {이름:<12} 실패 — {r.오류}")
            continue
        # 「본 것」은 못본이유가 없는 줄입니다. 살아있는 것은 봤는데
        # 회원 수를 못 본 줄까지 「못 본 것」에 들어가서, 얼마나 열렸는지가
        # 안 보였습니다. 상태를 따로 셉니다.
        열림 = r.상태셈.get("online", 0)
        조각 = [f"열린 곳 {열림}", f"수치까지 본 것 {r.본것}",
               f"바뀐 줄 {r.바뀐줄}"]
        if r.건너뜀:
            조각.append(f"주소 없음 {r.건너뜀}")
        # 쉰 줄을 안 적으면 「다 봤다」로 읽힙니다. 안 본 것은 안 봤다고
        # 적습니다.
        if r.쉰것:
            조각.append(f"쉰 줄 {r.쉰것}")
        줄.append(f"  {이름:<12} {' · '.join(조각)}  {r.초:.0f}초")
        if r.상태셈:
            셈 = " · ".join(f"{k} {v}" for k, v in
                          sorted(r.상태셈.items(), key=lambda kv: -kv[1]))
            줄.append(f"  {'':<12} 상태  {셈}")
        # 왜 못 봤는지를 까닭별로 셉니다. 한 줄씩 보면 안 보이는 것이
        # 뭉쳐 놓으면 보입니다 — 절반이 같은 이유로 막혔다든가.
        if r.이유셈:
            for 까닭, c in sorted(r.이유셈.items(), key=lambda kv: -kv[1])[:5]:
                줄.append(f"  {'':<12} {c:>4}줄  {까닭}")
        for m in r.문제[:5]:
            줄.append(f"  {'':<12} !! {m}")
    # 명부에 없는 이웃들. 노션에 안 씁니다. 새 곳을 찾는 실마리입니다.
    처음본것: dict = {}
    for r in 결과:
        for h, 어디들 in getattr(r, "처음본곳", {}).items():
            처음본것.setdefault(h, set()).update(
                어디들 if isinstance(어디들, set) else {어디들})
    if 처음본것:
        줄.append("")
        줄.append(f"  명부에 없는 이웃 {len(처음본것)}곳 (노션에 안 씁니다)")
        # 여러 곳이 같이 걸어 둔 것부터 보여 줍니다. 그것이 실마리입니다.
        차례 = sorted(처음본것.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        for h, 어디들 in 차례[:12]:
            딱지 = sorted(어디들)[0]
            더 = f" 외 {len(어디들) - 1}곳" if len(어디들) > 1 else ""
            줄.append(f"    {h:<48} ← {딱지}{더}")
        if len(처음본것) > 12:
            줄.append(f"    … {len(처음본것) - 12}곳 더")

    줄.append("")
    총바뀜 = sum(r.바뀐줄 for r in 결과)
    총문제 = sum(len(r.문제) for r in 결과)
    머리 = "썼습니다" if apply else "미리보기입니다. --apply 를 주면 씁니다"
    줄.append(f"  {머리} — 바뀐 줄 {총바뀜} · 살펴볼 것 {총문제}")
    return "\n".join(줄)
