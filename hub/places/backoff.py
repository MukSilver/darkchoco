"""죽은 곳을 매 판 두드리지 않습니다.

한 판 53분 중 47분(88%)이 **죽은 주소를 기다리는 시간**입니다. 실측입니다.

    성공 267곳  ×  약 4초   =   18분   ( 6%)
    실패 461곳  × 30~90초   = 4시간 50분 (88%)   ← 여기

어제 죽었으면 오늘도 죽었을 가능성이 큽니다. 그런데 지금은 기억이 없어서
같은 주소를 12시간마다 30초씩 다시 기다립니다.

**영영 안 보는 것이 아닙니다.** 연속으로 실패한 만큼만 쉬고, 최대 두 주가
지나면 다시 봅니다. 부활한 곳을 두 주 안에 잡습니다.

    실패 1번   다음 판에 바로 다시
    실패 2번   하루 쉼
    실패 3번   사흘 쉼
    실패 4번   이레 쉼
    실패 5번~  두 주 쉼 (여기서 안 늘립니다)

**쉰 줄은 노션을 안 건드립니다.** 조사를 안 했으니 확인일도 안 바꿉니다.
「오늘 봤는데 죽어 있었다」와 「오늘 안 봤다」는 다릅니다.

걸린 초도 같이 쌓습니다. 시간 제한(30초·90초)과 동시 수(6)를 지금은
짐작으로 정해 두었는데, 이 숫자가 모이면 재서 정할 수 있습니다.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

__all__ = ["기록", "쉼표", "최대쉼"]

# 연속 실패 횟수 → 며칠 쉬나
쉼표 = {0: 0, 1: 0, 2: 1, 3: 3, 4: 7}
최대쉼 = 14

_하루 = 86400.0

_표 = """
CREATE TABLE IF NOT EXISTS 두드림 (
    갈래       TEXT NOT NULL,
    page_id    TEXT NOT NULL,
    연속실패   INTEGER DEFAULT 0,
    마지막시도 REAL DEFAULT 0,
    마지막성공 REAL DEFAULT 0,
    걸린초     REAL DEFAULT 0,
    PRIMARY KEY (갈래, page_id)
);
"""


def _쉴날(연속실패: int) -> float:
    if 연속실패 <= 0:
        return 0.0
    return float(쉼표.get(연속실패, 최대쉼))


class 기록:
    """두드린 자취. 갈래 하나를 도는 동안 열어 둡니다."""

    def __init__(self, db: Path | str):
        self.db = Path(db)
        self.db.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db))
        self.conn.executescript(_표)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    # ── 물어보기 ────────────────────────────────────────────────
    def 쉬는중(self, 갈래: str, page_id: str, now: float) -> float:
        """아직 쉴 날이 며칠 남았나. 0 이면 지금 두드립니다."""
        cur = self.conn.execute(
            "SELECT 연속실패, 마지막시도 FROM 두드림 WHERE 갈래=? AND page_id=?",
            (갈래, page_id))
        줄 = cur.fetchone()
        if not 줄:
            return 0.0
        실패, 시도 = 줄[0] or 0, 줄[1] or 0.0
        쉴날 = _쉴날(실패)
        if 쉴날 <= 0:
            return 0.0
        남음 = (시도 + 쉴날 * _하루 - now) / _하루
        return max(0.0, 남음)

    def 거를것(self, 갈래: str, 줄들, now: float):
        """(볼것, 쉰것) 으로 가릅니다. 쉰 것은 노션을 안 건드립니다."""
        볼것, 쉰것 = [], []
        for r in 줄들:
            pid = getattr(r, "page_id", "") or ""
            if pid and self.쉬는중(갈래, pid, now) > 0:
                쉰것.append(r)
            else:
                볼것.append(r)
        return 볼것, 쉰것

    # ── 적기 ────────────────────────────────────────────────────
    def 적기(self, 갈래: str, page_id: str, 됐나: bool, now: float,
           걸린초: float = 0.0) -> None:
        if not page_id:
            return
        if 됐나:
            self.conn.execute(
                "INSERT INTO 두드림 (갈래,page_id,연속실패,마지막시도,마지막성공,걸린초) "
                "VALUES (?,?,0,?,?,?) "
                "ON CONFLICT(갈래,page_id) DO UPDATE SET "
                "연속실패=0, 마지막시도=excluded.마지막시도, "
                "마지막성공=excluded.마지막성공, 걸린초=excluded.걸린초",
                (갈래, page_id, now, now, 걸린초))
        else:
            self.conn.execute(
                "INSERT INTO 두드림 (갈래,page_id,연속실패,마지막시도,걸린초) "
                "VALUES (?,?,1,?,?) "
                "ON CONFLICT(갈래,page_id) DO UPDATE SET "
                "연속실패=두드림.연속실패+1, 마지막시도=excluded.마지막시도, "
                "걸린초=excluded.걸린초",
                (갈래, page_id, now, 걸린초))

    def 저장(self) -> None:
        self.conn.commit()

    # ── 재기 ────────────────────────────────────────────────────
    def 걸린초분포(self, 갈래: str = "") -> list[float]:
        """성공한 것들이 몇 초에 답했나. 시간 제한을 정하는 근거입니다."""
        q = ("SELECT 걸린초 FROM 두드림 WHERE 마지막성공 > 0 AND 걸린초 > 0"
             + (" AND 갈래=?" if 갈래 else "") + " ORDER BY 걸린초")
        return [r[0] for r in self.conn.execute(q, (갈래,) if 갈래 else ())]
