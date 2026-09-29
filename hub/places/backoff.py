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

## 파일을 따로 둡니다 — `hub/data/backoff.db` (2026-09-25)

전에는 `places.db` 안의 표 하나였습니다. GitHub Actions 는 판마다 새 컨테이너라 그 파일이
사라져 **예약 실행에서는 쉬기가 한 번도 안 먹었습니다.** 캐시로 남기지 못한 까닭은 같은 파일의
규모 표가 (갈래, 명부 이름, 본때) 라서 이름이 깃허브에 남기 때문이었습니다.

**이 표에는 이름이 없습니다.** 갈래 · 노션 page_id · 연속 실패 수 · 시각 · 걸린 초뿐입니다.
그래서 이 표만 따로 떼어 캐시로 이어 받습니다(`places.yml`). 로컬의 옛 기록은 새 파일이
비어 있을 때 `옮겨오기()` 가 한 번 가져옵니다.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

__all__ = ["기록", "쉼표", "최대쉼", "옮겨오기"]

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
        try:
            self.conn.executescript(_표)
            self.conn.commit()
        except sqlite3.DatabaseError:
            # 못 여는 파일이면 연결을 닫고 올립니다. 안 닫으면 윈도에서 부르는 쪽이 파일을 못 치웁니다
            self.conn.close()
            raise

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

    def 연속실패(self, 갈래: str, page_id: str) -> int:
        """지금까지 연달아 못 본 횟수. 기록이 없으면 0 입니다.

        run.py 가 online 을 내릴지 정할 때 씁니다(내림연속, 2026-09-29).
        """
        줄 = self.conn.execute(
            "SELECT 연속실패 FROM 두드림 WHERE 갈래=? AND page_id=?",
            (갈래, page_id)).fetchone()
        return int(줄[0] or 0) if 줄 else 0

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

    def 줄수(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM 두드림").fetchone()[0]

    # ── 재기 ────────────────────────────────────────────────────
    def 걸린초분포(self, 갈래: str = "") -> list[float]:
        """성공한 것들이 몇 초에 답했나. 시간 제한을 정하는 근거입니다."""
        q = ("SELECT 걸린초 FROM 두드림 WHERE 마지막성공 > 0 AND 걸린초 > 0"
             + (" AND 갈래=?" if 갈래 else "") + " ORDER BY 걸린초")
        return [r[0] for r in self.conn.execute(q, (갈래,) if 갈래 else ())]


def 옮겨오기(새: 기록, 옛: Path | str) -> int:
    """옛 `places.db` 의 두드림 표를 새 파일로 옮깁니다. **새 파일이 비어 있을 때만.**

    한 번 옮긴 뒤로는 새 파일이 정본이라 다시 안 옮깁니다. 옛 파일이 없거나 표가 없으면
    0 입니다. 옛 파일은 안 건드립니다 — 규모 표와 차례표가 같이 들어 있습니다.
    """
    옛 = Path(옛)
    if 새.줄수() or not 옛.is_file() or 옛.resolve() == 새.db.resolve():
        return 0
    try:
        # 읽기 전용으로 엽니다. Windows 경로(역슬래시 · 한글)는 as_uri() 로 꼴을 맞춥니다
        src = sqlite3.connect(옛.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            줄들 = src.execute(
                "SELECT 갈래, page_id, 연속실패, 마지막시도, 마지막성공, 걸린초 FROM 두드림").fetchall()
        finally:
            src.close()
    except sqlite3.Error:
        return 0
    새.conn.executemany(
        "INSERT OR IGNORE INTO 두드림 (갈래,page_id,연속실패,마지막시도,마지막성공,걸린초) "
        "VALUES (?,?,?,?,?,?)", 줄들)
    새.conn.commit()
    return len(줄들)
