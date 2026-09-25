"""예약 실행에서도 「죽은 곳 쉬기」 가 먹는가 — 시험. **밖에 안 나가고 노션에 안 붙습니다.**

    python packages/tests/test_쉬기캐시.py          CI 가 이렇게 돌린다

2026-09-25 최현서 승인 (인계 C). 백오프의 두드림 표가 `places.db` 안에 있어서, 판마다 새
컨테이너인 GitHub Actions 에서는 한 번도 안 먹었다. 캐시로 못 남긴 까닭은 같은 파일의 규모
표에 명부 이름이 있어서였다. 두드림 표만 `backoff.db` 로 떼어 그 파일만 캐시로 이어 받는다.

**가장 중요한 것은 캐시 파일에 이름이 없는 것이다.** 레포가 공개라 포크 PR 이 기본 가지
캐시를 읽을 수 있다.

**실행부를 둔다.** CI 는 이 폴더를 `python 파일` 로 돌린다.
"""
from __future__ import annotations

import re
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packages"))

from hub.places import backoff  # noqa: E402

워크플로 = ROOT / ".github" / "workflows" / "places.yml"
두드림칸 = {"갈래", "page_id", "연속실패", "마지막시도", "마지막성공", "걸린초"}


def _표들(f: Path) -> dict[str, set[str]]:
    c = sqlite3.connect(str(f))
    try:
        이름들 = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        return {t: {r[1] for r in c.execute(f"PRAGMA table_info({t})")} for t in 이름들}
    finally:
        c.close()


def test_쉬기_파일에는_두드림_표만_있고_이름_칸이_없다():
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "backoff.db"
        with backoff.기록(f) as k:
            k.적기("forum", "11111111111111111111111111111111", False, 1000.0, 3.0)
            k.저장()
        표 = _표들(f)
        assert set(표) == {"두드림"}, 표
        assert 표["두드림"] == 두드림칸, 표["두드림"]


def test_옛_places_db_의_두드림만_옮기고_규모는_안_옮긴다():
    with tempfile.TemporaryDirectory() as d:
        옛 = Path(d) / "places.db"
        c = sqlite3.connect(str(옛))
        c.executescript(backoff._표)
        c.execute("CREATE TABLE 규모 (갈래 TEXT, 이름 TEXT, 본때 TEXT)")
        c.execute("INSERT INTO 규모 VALUES ('forum', '지어낸포럼', '2026-09-25')")
        c.execute("INSERT INTO 두드림 VALUES ('forum', 'p1', 3, 100.0, 0, 30.0)")
        c.execute("INSERT INTO 두드림 VALUES ('ransom', 'p2', 0, 100.0, 100.0, 2.0)")
        c.commit()
        c.close()

        새 = Path(d) / "backoff.db"
        with backoff.기록(새) as k:
            assert backoff.옮겨오기(k, 옛) == 2
            # 한 번 옮긴 뒤로는 새 파일이 정본이다. 다시 안 옮긴다
            assert backoff.옮겨오기(k, 옛) == 0
            assert k.쉬는중("forum", "p1", 100.0 + 3600) > 0, "옮긴 실패 기록이 안 먹는다"
        assert set(_표들(새)) == {"두드림"}, "규모 표가 딸려 왔다"
        assert "지어낸포럼".encode("utf-8") not in 새.read_bytes(), "이름이 캐시 파일에 들어갔다"
        # 옛 파일은 안 건드린다
        assert set(_표들(옛)) == {"두드림", "규모"}


def test_옛_파일이_없어도_죽지_않는다():
    with tempfile.TemporaryDirectory() as d:
        with backoff.기록(Path(d) / "backoff.db") as k:
            assert backoff.옮겨오기(k, Path(d) / "없는.db") == 0


def test_조사기가_기본으로_쉬기_파일을_쓴다():
    글 = (ROOT / "hub" / "places" / "run.py").read_text(encoding="utf-8")
    assert "두드림기록(db or 기본_두드림())" in 글, "한갈래() 가 아직 places.db 에 두드림을 쓴다"
    assert 'return ROOT / "hub" / "data" / "backoff.db"' in 글


def _단계들(글: str, 잡: str) -> dict[str, str]:
    """잡 하나의 단계를 {이름: 단계 글} 로. **yaml 없이 읽는다** — CI 시험 잡에 pyyaml 이 없다."""
    m = re.search(r"^  %s:\n(.*?)(?=^  [\w-]+:\n|\Z)" % re.escape(잡), 글, re.S | re.M)
    assert m, "%s 잡을 못 찾았다" % 잡
    밖, 차례 = {}, []
    for 덩이 in re.split(r"(?m)^      - ", m.group(1))[1:]:
        n = re.match(r"name: (.+)", 덩이)
        if n:
            밖[n.group(1).strip()] = 덩이
            차례.append(n.group(1).strip())
    밖["__차례__"] = 차례
    return 밖


def test_워크플로가_쉬기_파일만_캐시로_이어_받는다():
    글 = 워크플로.read_text(encoding="utf-8")
    열쇠들 = []
    for 잡, 이름 in (("crawl-tor", "tor"), ("crawl-telegram", "telegram")):
        단계 = _단계들(글, 잡)
        차례 = 단계["__차례__"]
        i, j, k = (차례.index("죽은 곳 쉬기 기록 꺼내기"), 차례.index("명부 조사"),
                   차례.index("죽은 곳 쉬기 기록 넣어 두기"))
        assert i < j < k, 차례
        꺼냄, 넣음 = 단계["죽은 곳 쉬기 기록 꺼내기"], 단계["죽은 곳 쉬기 기록 넣어 두기"]
        assert "uses: actions/cache/restore@" in 꺼냄 and "uses: actions/cache/save@" in 넣음
        for s in (꺼냄, 넣음):
            # **places.db 를 캐시에 넣으면 안 된다.** 규모 표에 명부 이름이 있다
            assert re.findall(r"path: (\S+)", s) == ["hub/data/backoff.db"], s
        # 캐시는 한 번 넣으면 못 덮어쓴다. 판마다 새 열쇠로 넣고, 잡마다 열쇠를 가른다
        열쇠 = "places-backoff-%s-${{ github.run_id }}" % 이름
        assert "key: " + 열쇠 in 넣음 and "key: " + 열쇠 in 꺼냄, 넣음
        assert "restore-keys: places-backoff-%s-\n" % 이름 in 꺼냄, 꺼냄
        assert re.search(r"if: always\(\)", 넣음), "조사가 실패하면 기록을 안 넣는다"
        열쇠들.append(열쇠)
    assert len(set(열쇠들)) == 2, "두 잡이 같은 열쇠를 쓴다"
    assert "places.db" not in "".join(re.findall(r"path: (\S+)", 글)), "places.db 가 캐시 경로에 있다"


if __name__ == "__main__":
    시험들 = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    실패 = 0
    for 이름, f in 시험들:
        try:
            f()
            print("  OK  %s" % 이름)
        except Exception as e:  # noqa: BLE001
            실패 += 1
            print("  !!  %s — %s: %s" % (이름, type(e).__name__, e))
    print("\n%d개 중 %d개 실패" % (len(시험들), 실패))
    sys.exit(1 if 실패 else 0)
