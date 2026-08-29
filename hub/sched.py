"""무엇이 언제 도는지 표에 적어 둡니다.

주기를 코드에 두면 프로세스가 다시 뜰 때마다 차례가 흔들립니다. 표에
두면 언제 마지막으로 돌았는지가 남아, 껐다 켜도 이어집니다.

**실패했을 때 마지막 시각을 갱신하지 않습니다.** 갱신하면 실패 한 번이
다음 시도를 주기만큼 미룹니다. 6시간짜리는 18시간, 하루짜리는 사흘이
되어 사실상 멈춥니다. 대신 짧은 재시도 간격을 따로 두고, 연달아 실패해도
끄지 않고 간격만 늘립니다.

    5분 → 10분 → 20분 → 40분 → 1시간(상한)
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

__all__ = ["Sched", "Due"]

재시도_처음 = 5 * 60          # 초
재시도_상한 = 60 * 60

_표 = """
CREATE TABLE IF NOT EXISTS sched (
    name      TEXT PRIMARY KEY,
    last_ok   REAL DEFAULT 0,   -- 마지막으로 성공한 때. 실패는 안 건드립니다
    last_try  REAL DEFAULT 0,   -- 마지막으로 시도한 때
    fails     INTEGER DEFAULT 0,
    note      TEXT DEFAULT ''
);
"""


@dataclass
class Due:
    """지금 돌아야 하는 것 하나."""

    name: str
    이유: str          # 사람에게 보일 한 줄
    처음인가: bool = False


class Sched:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_표)
        self.conn.commit()

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:  # noqa: BLE001
            pass

    def _줄(self, name: str) -> sqlite3.Row | None:
        cur = self.conn.execute("SELECT * FROM sched WHERE name = ?", (name,))
        return cur.fetchone()

    def 언제(self, name: str, every_min: int, now: float | None = None) -> Due | None:
        """지금 돌아야 하면 Due, 아니면 None 입니다."""
        now = now if now is not None else time.time()
        r = self._줄(name)

        if r is None:
            return Due(name, "처음입니다", 처음인가=True)

        if r["fails"]:
            # 실패 중입니다. 짧은 간격으로 다시 봅니다.
            간격 = min(재시도_처음 * (2 ** (r["fails"] - 1)), 재시도_상한)
            지난 = now - (r["last_try"] or 0)
            if 지난 >= 간격:
                return Due(name, f"{r['fails']}번 실패해 다시 해 봅니다")
            남은 = int((간격 - 지난) / 60)
            return None if 남은 else Due(name, "재시도할 때가 됐습니다")

        if not every_min:
            return None                      # 부를 때만 도는 어댑터입니다

        지난 = now - (r["last_ok"] or 0)
        if 지난 >= every_min * 60:
            return Due(name, f"{int(지난/60)}분 지났습니다")
        return None

    def 다음까지(self, name: str, every_min: int, now: float | None = None) -> int:
        """다음에 돌 때까지 남은 분. 지금 돌아야 하면 0 입니다."""
        now = now if now is not None else time.time()
        r = self._줄(name)
        if r is None or not every_min:
            return 0 if r is None else -1
        if r["fails"]:
            간격 = min(재시도_처음 * (2 ** (r["fails"] - 1)), 재시도_상한)
            return max(0, int((간격 - (now - (r["last_try"] or 0))) / 60))
        return max(0, int((every_min * 60 - (now - (r["last_ok"] or 0))) / 60))

    def 됐다(self, name: str, note: str = "", now: float | None = None) -> None:
        now = now if now is not None else time.time()
        self.conn.execute(
            "INSERT INTO sched (name, last_ok, last_try, fails, note) VALUES (?,?,?,0,?) "
            "ON CONFLICT(name) DO UPDATE SET last_ok=?, last_try=?, fails=0, note=?",
            (name, now, now, note, now, now, note))
        self.conn.commit()

    def 안됐다(self, name: str, note: str = "", now: float | None = None) -> None:
        """실패했습니다. **last_ok 는 안 건드립니다.**"""
        now = now if now is not None else time.time()
        self.conn.execute(
            "INSERT INTO sched (name, last_ok, last_try, fails, note) VALUES (?,0,?,1,?) "
            "ON CONFLICT(name) DO UPDATE SET last_try=?, fails=fails+1, note=?",
            (name, now, note, now, note))
        self.conn.commit()

    def 상태(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM sched ORDER BY name")]
