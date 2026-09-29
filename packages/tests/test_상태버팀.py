"""online 을 한 번 못 봤다고 내리지 않는가 — 시험. **밖에 안 나가고 노션에 안 붙습니다.**

    python packages/tests/test_상태버팀.py          CI 가 이렇게 돌린다

2026-09-29 인계 H-0. 9/29 09:36 UTC 판에서 포럼 29줄이 HTTP 403 을 받았고, 403 은 「응답을
받았다」 로 쳐서 상태 미확인이 노션에 갔다. 지도에서 포럼 한 곳의 영토와 사건 51건이 같이
빠졌다. 이제 노션이 online 인 포럼 · 랜섬 줄은 연달아 `내림연속`(3) 번 못 봐야 내린다.

명부와 조사기는 가짜로 바꿔 끼운다. 이름과 주소는 지어낸 것이다.

**실행부를 둔다.** CI 는 이 폴더를 `python 파일` 로 돌린다.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packages"))

from hub.places import backoff, run  # noqa: E402
from hub.places.place import Place  # noqa: E402
from hub.places.write import 반영결과, 줄 as 명부줄  # noqa: E402


def _막힘(갈래="forum", 상태="미확인", 까닭="HTTP 403. 클라우드플레어") -> Place:
    p = Place(갈래=갈래, 이름="지어낸포럼", 주소="https://example-forum.test")
    p.두드림, p.상태, p.못본이유 = True, 상태, 까닭
    return p


def _열림(갈래="forum") -> Place:
    p = Place(갈래=갈래, 이름="지어낸포럼", 주소="https://example-forum.test")
    p.두드림, p.상태 = True, "online"
    return p


class _자취:
    def __init__(self, n):
        self.n = n

    def 연속실패(self, 갈래, page_id):
        if isinstance(self.n, Exception):
            raise self.n
        return self.n


def _줄(상태="online", pid="p1") -> 명부줄:
    return 명부줄(page_id=pid, 이름="지어낸포럼", 주소="https://example-forum.test", 상태=상태)


# ── 1. 언제 버티나 ─────────────────────────────────────────────
def test_online_을_한두_번_못_보면_버틴다():
    for n in (0, 1, 2):
        assert run.버텨야하나("forum", _줄(), _막힘(), _자취(n)), n


def test_연달아_세_번_못_보면_내린다():
    assert run.내림연속 == 3
    assert not run.버텨야하나("forum", _줄(), _막힘(), _자취(3))
    assert not run.버텨야하나("forum", _줄(), _막힘(), _자취(7))


def test_5xx_로_offline_이_되는_것도_버틴다():
    assert run.버텨야하나("ransom", _줄(), _막힘("ransom", "offline", "HTTP 522"), _자취(1))


def test_노션이_online_이_아니면_안_버틴다():
    for 상태 in ("미확인", "offline", "압수됨", ""):
        assert not run.버텨야하나("forum", _줄(상태), _막힘(), _자취(1)), 상태


def test_봤으면_안_버틴다():
    assert not run.버텨야하나("forum", _줄(), _열림(), _자취(1))


def test_두드리지도_못했으면_버틸_것이_없다():
    # 노션값() 이 이미 빈 것을 낸다. 여기서 셀 까닭이 없다
    p = _막힘()
    p.두드림 = False
    assert not run.버텨야하나("forum", _줄(), p, _자취(1))


def test_텔레그램은_안_버틴다():
    # 미리보기가 꺼진 채널은 한 번 봐도 확실한 미확인이다
    assert not run.버텨야하나("telegram", _줄(), _막힘("telegram", "미확인", "미리보기가 꺼져 있습니다"), _자취(1))


def test_기록을_못_읽으면_안_덮는다():
    assert run.버텨야하나("forum", _줄(), _막힘(), _자취(RuntimeError("깨짐")))


def test_버틴_줄은_노션값이_빈다():
    # 한갈래 가 버틴 줄을 두드리지 못한 줄처럼 만든다. 그러면 상태도 확인일도 안 간다
    p = _막힘()
    p.두드림, p.상태 = False, "미확인"
    assert p.노션값({"상태": "online"}) == {}


# ── 2. 한 판씩 돌려 본다 ───────────────────────────────────────
class _가짜명부:
    def __init__(self, 줄들):
        self._줄들 = 줄들
        self.쓴값: list[tuple[str, dict]] = []

    def 줄들(self):
        return list(self._줄들)

    def 반영(self, 줄, p, *, apply=False, 칸만=None):
        self.쓴값.append((줄.page_id, p.노션값(dict(줄.현재, 상태=줄.상태))))
        return 반영결과(이름=줄.이름)


def _한판(명부, 결과들, db: Path, **kw):
    """명부와 조사기를 바꿔 끼우고 한갈래 를 한 번 돈다."""
    옛명부, 옛조사 = run.명부, run._조사
    run.명부 = lambda 갈래: 명부
    run._조사 = lambda 갈래, 줄들, ctx: ((x, 결과들[x.page_id]()) for x in 줄들)
    try:
        return run.한갈래("forum", apply=False, db=db, tor=None, 조용히=True, **kw)
    finally:
        run.명부, run._조사 = 옛명부, 옛조사


def test_세_판째에야_미확인을_쓴다():
    with tempfile.TemporaryDirectory() as d:
        db = Path(d) / "backoff.db"
        명부 = _가짜명부([_줄()])
        판들 = []
        for _ in range(3):
            r = _한판(명부, {"p1": _막힘}, db, page="p1")   # page 로 쉬기를 건너뛰어 세 판을 잇는다
            판들.append(r.버팀)
        assert 판들 == [1, 1, 0], 판들
        값들 = [v for _, v in 명부.쓴값]
        assert 값들[0] == {} and 값들[1] == {}, 값들
        assert 값들[2].get("상태") == "미확인", 값들[2]


def test_한_번_보면_다시_셈을_시작한다():
    with tempfile.TemporaryDirectory() as d:
        db = Path(d) / "backoff.db"
        명부 = _가짜명부([_줄()])
        for 결과 in (_막힘, _막힘, _열림, _막힘):
            r = _한판(명부, {"p1": 결과}, db, page="p1")
        assert r.버팀 == 1, r.버팀
        with backoff.기록(db) as k:
            assert k.연속실패("forum", "p1") == 1


def test_page_는_그_줄만_보고_쉬는_줄이라도_본다():
    with tempfile.TemporaryDirectory() as d:
        db = Path(d) / "backoff.db"
        with backoff.기록(db) as k:
            # p2 는 네 번 잇달아 실패해 이레를 쉬는 중이다
            for _ in range(4):
                k.적기("forum", "p2", False, run.time.time())
            k.저장()
        명부 = _가짜명부([_줄(pid="p1"), _줄(pid="p2")])
        r = _한판(명부, {"p1": _열림, "p2": _열림}, db, page="p2")
        assert [pid for pid, _ in 명부.쓴값] == ["p2"], 명부.쓴값
        assert r.쉰것 == 0

        # page 없이 돌면 p2 는 쉰다
        명부2 = _가짜명부([_줄(pid="p1"), _줄(pid="p3")])
        with backoff.기록(db) as k:
            for _ in range(4):
                k.적기("forum", "p3", False, run.time.time())
            k.저장()
        r2 = _한판(명부2, {"p1": _열림, "p3": _열림}, db)
        assert [pid for pid, _ in 명부2.쓴값] == ["p1"], 명부2.쓴값
        assert r2.쉰것 == 1


def test_page_는_대시와_대소문자를_가리지_않는다():
    with tempfile.TemporaryDirectory() as d:
        db = Path(d) / "backoff.db"
        pid = "3b9b6f60-4db9-81db-0000-000000000000"
        명부 = _가짜명부([_줄(pid=pid)])
        _한판(명부, {pid: _열림}, db, page=pid.replace("-", "").upper())
        assert len(명부.쓴값) == 1


def test_요약에_버틴_줄_수가_나오고_이름은_안_나온다():
    r = run.갈래결과(갈래="forum", 버팀=2)
    r.상태셈 = {"미확인": 2}
    글 = run.표로([r], apply=True, 요약만=True)
    assert "online 그대로 둔 줄 2" in 글, 글
    assert "지어낸포럼" not in 글


# ── 3. 2026-09-30 검토 뒤 ─────────────────────────────────────
def _랜섬한판(명부, 우리, 집계처, db: Path, *, apply=False, page="p1", 셈=None):
    """갈래표의 랜섬 여는 법 · 앞선 것만 가짜로. 합치기 · 버팀 · 쓰기는 진짜로 돈다."""
    옛명부, 옛표 = run.명부, dict(run.갈래표["ransom"])

    def 앞선것(줄들, 상황):
        if 셈 is not None:
            셈.append(len(줄들))
        return {x.page_id: 집계처() for x in 줄들} if 집계처 else {}

    run.명부 = lambda 갈래: 명부
    run.갈래표["ransom"].update({"여는법": lambda r, 상황: 우리(), "앞선것": 앞선것, "동시": 1})
    try:
        return run.한갈래("ransom", apply=apply, db=db, tor="socks5h://127.0.0.1:9",
                         조용히=True, page=page)
    finally:
        run.명부 = 옛명부
        run.갈래표["ransom"].clear()
        run.갈래표["ransom"].update(옛표)


def _연결실패():
    p = Place(갈래="ransom", 이름="지어낸그룹", 주소="http://g.example.test")
    p.못본이유 = "연결이 안 됩니다(TimeoutError)"
    return p


def _집계처(상태):
    def 만들기():
        p = Place(갈래="ransom", 이름="지어낸그룹")
        p.두드림, p.상태 = True, 상태
        return p
    return 만들기


def test_집계처가_offline_이라_하면_버티지_않는다():
    """merge.py 는 집계처 판정을 우리 연결 실패보다 믿는다. #102 전처럼 바로 쓴다."""
    with tempfile.TemporaryDirectory() as d:
        명부 = _가짜명부([_줄()])
        r = _랜섬한판(명부, _연결실패, _집계처("offline"), Path(d) / "b.db")
        assert r.버팀 == 0, r.버팀
        assert 명부.쓴값[0][1].get("상태") == "offline", 명부.쓴값


def test_집계처가_없고_우리_5xx_면_버틴다():
    def 우리():
        p = Place(갈래="ransom", 이름="지어낸그룹", 주소="http://g.example.test")
        p.두드림, p.상태, p.못본이유 = True, "offline", "HTTP 503"
        return p
    with tempfile.TemporaryDirectory() as d:
        명부 = _가짜명부([_줄()])
        r = _랜섬한판(명부, 우리, None, Path(d) / "b.db")
        assert r.버팀 == 1, r.버팀
        assert 명부.쓴값[0][1] == {}, 명부.쓴값


def test_버텨도_시계열에는_본_값이_남는다():
    """버틴 줄은 사본으로 쓴다. p 를 고치면 _쌓기 가 본 offline 대신 미확인을 건너뛴다.

    _쌓기 를 가짜로 바꿔 넘어온 상태만 본다. 시험은 db 하나를 쉬기 기록과 시계열이 같이 써서
    진짜 _쌓기 는 잠긴다(실제 판은 파일이 따로다).
    """
    받음: list = []
    with tempfile.TemporaryDirectory() as d:
        명부 = _가짜명부([_줄()])
        옛명부, 옛조사, 옛쌓기 = run.명부, run._조사, run._쌓기
        run.명부 = lambda 갈래: 명부
        run._조사 = lambda 갈래, 줄들, ctx: ((x, _막힘(상태="offline", 까닭="HTTP 522")) for x in 줄들)
        run._쌓기 = lambda db, 갈래, 목록: 받음.extend((p.상태, p.두드림) for p in 목록)
        try:
            r = run.한갈래("forum", apply=True, db=Path(d) / "b.db", tor=None, 조용히=True, page="p1")
        finally:
            run.명부, run._조사, run._쌓기 = 옛명부, 옛조사, 옛쌓기
    assert r.버팀 == 1 and 명부.쓴값[0][1] == {}, (r.버팀, 명부.쓴값)
    assert 받음 == [("offline", True)], 받음


def test_page_가_이_갈래_줄이_아니면_조사기를_안_부른다():
    """랜섬은 앞선 것만 불러도 집계처를 여덟 번 친다."""
    셈: list = []
    with tempfile.TemporaryDirectory() as d:
        명부 = _가짜명부([_줄(pid="p1")])
        r = _랜섬한판(명부, _연결실패, _집계처("offline"), Path(d) / "b.db", page="다른줄", 셈=셈)
    assert 셈 == [], 셈
    assert 명부.쓴값 == [] and r.본것 == 0 and r.못본것 == 0


def test_page_입력이_틀리면_워크플로가_멈추고_텔레그램에도_넘긴다():
    글 = (ROOT / ".github" / "workflows" / "places.yml").read_text(encoding="utf-8")
    assert "주소 전체를 넣지 마십시오\"; exit 1" in 글, "틀린 page 로 전체 판이 돈다"
    assert "버리고 전부 봅니다" not in 글
    assert 글.count("${PAGE:+--page=$PAGE}") == 4, "포럼 · 랜섬 · 텔레그램 잡 모두 page 를 넘겨야 한다"


def test_crawl_에_page_가_있다():
    글 = (ROOT / "dc.py").read_text(encoding="utf-8")
    assert '"--page"' in 글 and "page=(args.page" in 글


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
