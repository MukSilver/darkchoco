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

from hub.crawler.notion import 갈래별_DB, 명부, 반영결과  # noqa: E402
from hub.crawler.place import Place  # noqa: E402
from hub.crawler.probe import forum, ransom, telegram  # noqa: E402

__all__ = ["한갈래", "여러갈래", "표로", "기본_표", "갈래들",
           "차례", "됐다고_적기"]

갈래들 = ("telegram", "forum", "ransom")

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
    문제: list = field(default_factory=list)
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


def _조사(갈래: str, 줄들, ctx: dict):
    """갈래에 맞는 조사기를 돌립니다. (줄, Place) 를 내놓습니다.

    프록시는 셋 다 받습니다. 하나라도 빠지면 그 갈래만 우리 IP 로
    나갑니다.
    """
    프록시 = ctx.get("tor")
    if 갈래 == "telegram":
        마지막 = [0.0]
        for r in 줄들:
            yield r, telegram.한곳(r.주소, 마지막, r.이름, 프록시=프록시)

    elif 갈래 == "forum":
        마지막 = [0.0]
        for r in 줄들:
            yield r, forum.한곳(r.주소, r.이름, 마지막, 프록시=프록시)

    elif 갈래 == "ransom":
        # 랜섬은 목록을 통째로 받습니다. 그룹 하나씩 조회하면 요청이 폭발합니다.
        이름별 = {r.이름.strip().lower(): r for r in 줄들}
        for p in ransom.조사(limit=ctx.get("limit", 0), 프록시=프록시):
            r = 이름별.get(p.이름.strip().lower())
            if r is not None:
                yield r, p
    else:
        raise ValueError(f"모르는 갈래입니다: {갈래}")


def 한갈래(갈래: str, *, apply: bool = False, limit: int = 0,
         db: Path | None = None, tor: str | None = None,
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

    볼것 = [x for x in 줄들 if (x.주소 or "").strip()]
    r.건너뜀 = len(줄들) - len(볼것)
    if limit:
        볼것 = 볼것[:limit]

    본것: list[Place] = []
    for 줄, p in _조사(갈래, 볼것, {"tor": tor, "limit": limit}):
        본것.append(p)
        if p.봤나():
            r.본것 += 1
        else:
            r.못본것 += 1
        try:
            res = m.반영(줄, p, apply=apply)
        except Exception as e:  # noqa: BLE001  한 줄이 죽어도 나머지는 돕니다
            res = 반영결과(이름=줄.이름, 오류=str(e)[:160])
        r.줄별.append(res)
        if res.오류:
            r.문제.append(f"{res.이름}: {res.오류}")
        if res.건너뛴칸:
            r.문제.append(f"{res.이름}: 스키마에 없는 칸 {res.건너뛴칸}")
        if res.바뀐칸:
            r.바뀐줄 += 1

    if apply and 본것:
        _쌓기(db or 기본_표(), 갈래, 본것)
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
          tor: str | None = None, 때된것만: bool = False) -> list[갈래결과]:
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

    out = []
    for 갈래 in 돌것:
        out.append(한갈래(갈래, apply=apply, limit=limit, db=db, tor=tor))
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
        조각 = [f"본 것 {r.본것}", f"못 본 것 {r.못본것}",
               f"바뀐 줄 {r.바뀐줄}"]
        if r.건너뜀:
            조각.append(f"주소 없음 {r.건너뜀}")
        줄.append(f"  {이름:<12} {' · '.join(조각)}  {r.초:.0f}초")
        for m in r.문제[:5]:
            줄.append(f"  {'':<12} !! {m}")
    줄.append("")
    총바뀜 = sum(r.바뀐줄 for r in 결과)
    총문제 = sum(len(r.문제) for r in 결과)
    머리 = "썼습니다" if apply else "미리보기입니다. --apply 를 주면 씁니다"
    줄.append(f"  {머리} — 바뀐 줄 {총바뀜} · 살펴볼 것 {총문제}")
    return "\n".join(줄)
