"""게시처 깊은 판만 따로 돌기(`hub/places/deep.py`) — 시험. **노션에도 밖에도 안 붙습니다.**

    python packages/tests/test_깊은판.py          CI 가 이렇게 돌린다

2026-09-29 최현서 결정(인계 H-4): 깊은 판을 Actions 의 따로 된 잡으로 뗀다. 얕은 판이 정한 상태를
믿고 **빈칸만 채우는 칸과 이어 붙이는 칸만** 쓴다. 사람 값 덮어쓰기는 0 이어야 한다.
로그에는 건수만 — 게시처 이름을 찍지 않는다.

**실행부를 둔다.** CI 는 이 폴더를 `python 파일` 로 돌린다.
"""
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packages"))

from hub.places import deep, write  # noqa: E402
from hub.places.place import Place, 빈칸만칸, 이어붙이는칸  # noqa: E402

스키마 = {"포럼 이름": "title", "주소": "url", "상태": "select", "확인일": "date",
        "규모": "rich_text", "사용 언어": "rich_text", "연결된 곳": "rich_text",
        "이전 이름·별칭": "rich_text", "이전 주소": "rich_text", "어떤 곳인지": "rich_text"}
가짜이름 = "가상포럼-QZX"


def _글(v: str) -> list:
    return [{"plain_text": v}] if v else []


def _쪽(pid: str, *, 주소="http://a.example", 상태="online", 언어="", 연결="", 별칭="") -> dict:
    return {"id": pid, "properties": {
        "포럼 이름": {"type": "title", "title": _글(가짜이름)},
        "주소": {"type": "url", "url": 주소 or None},
        "상태": {"type": "select", "select": {"name": 상태} if 상태 else None},
        "확인일": {"type": "date", "date": {"start": "2026-09-20"}},
        "규모": {"type": "rich_text", "rich_text": _글("")},
        "사용 언어": {"type": "rich_text", "rich_text": _글(언어)},
        "연결된 곳": {"type": "rich_text", "rich_text": _글(연결)},
        "이전 이름·별칭": {"type": "rich_text", "rich_text": _글(별칭)},
        "이전 주소": {"type": "rich_text", "rich_text": _글("")},
        "어떤 곳인지": {"type": "rich_text", "rich_text": _글("")},
    }}


class _가짜노션:
    def __init__(self, 쪽들: list):
        self.쪽들, self.고친것 = 쪽들, []

    def data_sources(self, db):
        return [{"id": "ds-가짜"}]

    def schema(self, ds):
        return dict(스키마)

    def query_all(self, ds):
        return list(self.쪽들)

    def update_page(self, pid, props):
        self.고친것.append((pid, props))
        return {}

    def request(self, method, path, body=None):
        if method == "GET" and path.startswith("/data_sources/"):
            return {"properties": {"상태": {"type": "select", "select": {
                "options": [{"name": x} for x in ("online", "offline", "미확인")]}}}}
        raise AssertionError(f"모르는 요청 {method} {path}")


def _명부(가짜):
    옛 = write.Notion
    write.Notion = lambda verbose=False: 가짜
    try:
        return write.명부("forum")
    finally:
        write.Notion = 옛


def _깊은것(**kw) -> Place:
    """깊게() 가 내놓는 꼴. 상태는 미확인 · 두드림 꺼짐으로 온다(run.py)."""
    기본 = dict(갈래="forum", 이름=가짜이름, 주소="http://a.example", 상태="미확인", 두드림=False,
              확인일="2026-09-29", 언어="en", 연결된곳="다른포럼", 이전이름="옛이름")
    기본.update(kw)
    return Place(**{k: v for k, v in 기본.items() if k in Place.__dataclass_fields__})


# ── 칸만: 반영이 쓸 칸을 좁힌다 ─────────────────────────────────────
def test_깊은판칸은_빈칸만칸과_이어붙이는칸이다():
    assert deep.깊은판칸 == frozenset(빈칸만칸 | 이어붙이는칸)
    for 칸 in ("상태", "확인일", "규모", "주소", "최근 활동"):
        assert 칸 not in deep.깊은판칸, 칸


def test_칸만을_주면_그_칸만_쓴다():
    가짜 = _가짜노션([_쪽("p1")])
    m = _명부(가짜)
    p = Place(갈래="forum", 이름=가짜이름, 주소="http://a.example", 상태="offline", 두드림=True,
              확인일="2026-09-29", 언어="en")
    r = m.반영(m.줄들()[0], p, apply=True, 칸만={"사용 언어"})
    assert list(r.바뀐칸) == ["사용 언어"], r.바뀐칸
    assert 가짜.고친것 and set(가짜.고친것[0][1]) == {"사용 언어"}, 가짜.고친것


def test_칸만으로_바뀔_것이_없으면_안_쓴다():
    가짜 = _가짜노션([_쪽("p1", 언어="en")])
    m = _명부(가짜)
    p = Place(갈래="forum", 이름=가짜이름, 주소="http://a.example", 상태="online", 두드림=True,
              확인일="2026-09-29", 언어="en")
    r = m.반영(m.줄들()[0], p, apply=True, 칸만={"사용 언어"})
    assert r.안바뀜 and not 가짜.고친것, 가짜.고친것


# ── 고르기 ──────────────────────────────────────────────────────────
def test_online_이고_http_주소인_줄만_고른다():
    가짜 = _가짜노션([_쪽("p1"), _쪽("p2", 상태="offline"), _쪽("p3", 주소=""),
                    _쪽("p4", 상태="미확인"), _쪽("p5", 주소="http://b.example")])
    m = _명부(가짜)
    assert [x.page_id for x in deep.고르기(m.줄들())] == ["p1", "p5"]


# ── 한 갈래 ─────────────────────────────────────────────────────────
def _돌리기(쪽들, 내놓을, *, apply):
    """가짜 명부 · 가짜 깊게() 로 한갈래 를 돌린다. (결과, 가짜, 찍은 글)"""
    가짜 = _가짜노션(쪽들)
    m = _명부(가짜)

    def 가짜깊게(갈래, 열린것, ctx):
        assert ctx["tor"], "Tor 없이 깊게를 불렀다"
        for 줄 in 열린것:
            q = 내놓을.get(줄.page_id)
            if q is not None:
                yield 줄, q

    버퍼 = io.StringIO()
    with contextlib.redirect_stdout(버퍼):
        r = deep.한갈래("forum", apply=apply, tor="http://127.0.0.1:9080", 명부=m, 깊게=가짜깊게)
        print(deep.요약(r))
    return r, 가짜, 버퍼.getvalue()


def test_미리보기는_안_쓰고_셈만_낸다():
    쪽들 = [_쪽("p1"), _쪽("p2"), _쪽("p3"), _쪽("p4", 상태="offline")]
    내놓을 = {"p1": _깊은것(), "p2": _깊은것(못본이유="크롤이 중단됐습니다: 챌린지")}
    r, 가짜, 글 = _돌리기(쪽들, 내놓을, apply=False)
    assert not 가짜.고친것
    assert (r.대상, r.봄, r.챌린지, r.못엶) == (3, 1, 1, 1), r
    assert r.칸별["연결된 곳"] == 1 and r.칸별["이전 이름·별칭"] == 1 and r.칸별["사용 언어"] == 1, r.칸별
    assert r.덮어쓰기 == 0 and r.바뀐줄 == 1
    assert 가짜이름 not in 글, "로그에 게시처 이름을 찍었다"


def test_적용하면_상태를_안_건드리고_빈칸만_채운다():
    쪽들 = [_쪽("p1", 연결="사람이 적은 곳")]
    r, 가짜, _ = _돌리기(쪽들, {"p1": _깊은것()}, apply=True)
    assert len(가짜.고친것) == 1
    쓴칸 = set(가짜.고친것[0][1])
    assert not (쓴칸 & {"상태", "확인일", "규모", "주소"}), 쓴칸
    assert "연결된 곳" not in 쓴칸, "사람 값을 덮었다"
    assert {"사용 언어", "이전 이름·별칭"} <= 쓴칸, 쓴칸
    assert r.덮어쓰기 == 0 and r.사람값이라_안씀 == 1, r


def test_괜찮나는_잡제한_덮어쓰기_안열림을_본다():
    """최현서 9/29 기준: 잡 제한 안 · 사람 값 덮어쓰기 0 · 실패로 안 멈춤. 하나라도 어긋나면 안 켠다."""
    좋은 = deep.깊은판결과(갈래="forum", 대상=10, 봄=4, 초=30 * 60)
    assert deep.괜찮나([좋은], 잡제한분=240) == (True, [])
    for 나쁜 in (dataclasses_replace(좋은, 초=250 * 60), dataclasses_replace(좋은, 덮어쓰기=1),
                dataclasses_replace(좋은, 봄=0), dataclasses_replace(좋은, 읽기오류="x")):
        assert deep.괜찮나([나쁜], 잡제한분=240)[0] is False, 나쁜


def dataclasses_replace(x, **kw):
    import dataclasses
    return dataclasses.replace(x, **kw)


def test_예약은_랜섬만_돌고_노션에_쓴다():
    """2026-09-30. 랜섬 미리보기만 기준을 맞췄다. 포럼은 고르기 순서를 돌리기 전에는 예약에 안 넣는다."""
    import re
    글 = (ROOT / ".github" / "workflows" / "places-deep.yml").read_text(encoding="utf-8")
    # CI 에 yaml 부품이 없다. 글자로 본다
    assert re.findall(r'(?m)^\s*- cron: "([^"]+)"', 글) == ["0 19 * * *"], "예약 시각이 바뀌었다"
    assert "github.event_name == 'schedule' && 'ransom'" in 글, "예약이 포럼까지 돈다"
    assert "github.event_name == 'schedule' && 'yes'" in 글, "예약이 노션에 안 쓴다"
    assert re.search(r"(?m)^concurrency:\s*\n\s+group: places\s*$", 글), "얕은 판과 동시에 쓸 수 있다"


if __name__ == "__main__":
    시험 = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    실패 = 0
    for 이름, f in 시험:
        try:
            f()
            print("  통과  %s" % 이름)
        except AssertionError as e:  # noqa: PERF203
            실패 += 1
            print("  실패  %s  %s" % (이름, e))
        except Exception as e:  # noqa: BLE001
            실패 += 1
            print("  오류  %s  %s: %s" % (이름, type(e).__name__, e))
    print("%d개 중 %d개 실패" % (len(시험), 실패))
    raise SystemExit(1 if 실패 else 0)
