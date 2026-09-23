"""명부 조사가 사람 줄을 안 고치고 자동 줄로 쓰는가 — 시험. **노션에 안 붙습니다.**

    python packages/tests/test_명부자동줄.py          CI 가 이렇게 돌린다
    python -m pytest packages/tests/test_명부자동줄.py

2026-09-23 최현서 결정이다.

    사람 줄     한 글자도 안 쓴다
    자동 줄     기계가 본 값이 사람 줄과 다를 때만 새로 만든다 (담당자 「자동」 · DB 반영 끔)
    그 뒤       자동 줄이 있으면 그 줄만 고친다

전에는 조사 값을 사람 줄에 바로 썼다. 예약 실행 두 판이 승인 없이 595줄에 썼다.

**실행부를 둔다.** CI 는 이 폴더를 `python 파일` 로 돌린다. 실행부가 없으면 함수만
정의하고 아무 시험도 안 돈 채 통과한다.

**가짜를 꼭 되돌린다.** 모듈을 불러오는 순간 가짜를 심으면 pytest 로 여럿을 같이
돌릴 때 다른 시험이 떨어진다.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packages"))

from hub.places import write  # noqa: E402
from hub.places.place import Place  # noqa: E402

사람 = "11111111-1111-1111-1111-111111111111"
자동 = "22222222-2222-2222-2222-222222222222"

스키마 = {"포럼 이름": "title", "주소": "url", "상태": "select", "확인일": "date",
        "담당자": "select", "비고": "rich_text", "DB 반영": "checkbox",
        "어니언 주소": "rich_text", "규모": "rich_text"}


def _글(v: str) -> list:
    return [{"plain_text": v}] if v else []


def _쪽(pid: str, 이름: str, *, 상태: str = "online", 담당자: str = "", 비고: str = "",
       확인일: str = "2026-09-20", 규모: str = "") -> dict:
    return {"id": pid, "properties": {
        "포럼 이름": {"type": "title", "title": _글(이름)},
        "주소": {"type": "url", "url": "http://a.example"},
        "상태": {"type": "select", "select": {"name": 상태} if 상태 else None},
        "확인일": {"type": "date", "date": {"start": 확인일}},
        "담당자": {"type": "select", "select": {"name": 담당자} if 담당자 else None},
        "비고": {"type": "rich_text", "rich_text": _글(비고)},
        "DB 반영": {"type": "checkbox", "checkbox": True},
        "어니언 주소": {"type": "rich_text", "rich_text": []},
        "규모": {"type": "rich_text", "rich_text": _글(규모)},
    }}


class _가짜노션:
    def __init__(self, 쪽들: list, 담당자선택지=("최현서", "자동")):
        self.쪽들 = 쪽들
        self.선택지 = 담당자선택지
        self.고친것: list = []      # (page id, 속성)
        self.만든것: list = []      # 요청 본문

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
            return {"properties": {
                "담당자": {"type": "select", "select": {
                    "options": [{"name": x} for x in self.선택지]}},
                "상태": {"type": "select", "select": {
                    "options": [{"name": x} for x in ("online", "offline", "미확인")]}},
            }}
        if method == "POST" and path == "/pages":
            self.만든것.append(body)
            return {"id": "33333333-3333-3333-3333-%012d" % len(self.만든것)}
        raise AssertionError(f"모르는 요청 {method} {path}")


def _명부(가짜: _가짜노션):
    """가짜 노션을 물린 명부. **돌려받은 되돌리기를 꼭 부른다.**"""
    옛 = write.Notion
    write.Notion = lambda verbose=False: 가짜
    try:
        m = write.명부("forum")
    finally:
        write.Notion = 옛
    return m


def _본것(상태: str, 확인일: str = "2026-09-23") -> Place:
    return Place(갈래="forum", 이름="가", 주소="http://a.example", 상태=상태,
                 두드림=True, 확인일=확인일)


def _사람줄에_썼나(가짜: _가짜노션) -> bool:
    return any(pid == 사람 for pid, _ in 가짜.고친것)


# ── 시험 ───────────────────────────────────────────────────────────
def test_같으면_아무것도_안_쓴다():
    가짜 = _가짜노션([_쪽(사람, "가", 상태="online")])
    m = _명부(가짜)
    줄 = m.사람줄(m.줄들())[0]
    r = m.반영(줄, _본것("online"), apply=True)
    assert not 가짜.만든것 and not 가짜.고친것, (가짜.만든것, 가짜.고친것)
    assert r.안바뀜 and r.자동줄 == ""


def test_확인일만_다르면_자동_줄을_안_만든다():
    """확인일은 판마다 다르다. 이것까지 치면 모든 줄에 자동 줄이 생긴다."""
    가짜 = _가짜노션([_쪽(사람, "가", 상태="online", 확인일="2026-09-01")])
    m = _명부(가짜)
    m.반영(m.사람줄(m.줄들())[0], _본것("online", "2026-09-23"), apply=True)
    assert not 가짜.만든것 and not 가짜.고친것


def test_다르면_자동_줄을_새로_만든다():
    가짜 = _가짜노션([_쪽(사람, "가", 상태="online")])
    m = _명부(가짜)
    r = m.반영(m.사람줄(m.줄들())[0], _본것("offline"), apply=True)
    assert r.자동줄 == "새로" and "상태" in r.바뀐칸, r
    assert not _사람줄에_썼나(가짜), "사람 줄에 썼다"
    assert len(가짜.만든것) == 1, 가짜.만든것
    본문 = 가짜.만든것[0]
    assert 본문["parent"] == {"type": "data_source_id", "data_source_id": "ds-가짜"}
    p = 본문["properties"]
    assert p["포럼 이름"]["title"][0]["text"]["content"] == "가", "이름이 사람 줄과 다르다"
    assert p["담당자"] == {"select": {"name": "자동"}}
    assert p["DB 반영"] == {"checkbox": False}, "자동 줄이 공개로 만들어졌다"
    비고 = p["비고"]["rich_text"][0]["text"]["content"]
    assert 비고.startswith(write.짝머리 + 사람), 비고
    assert p["상태"] == {"select": {"name": "offline"}}


def test_새로_만든_자동_줄이_짝으로_읽힌다():
    """다음 판에 같은 사람 줄의 자동 줄을 또 만들면 안 된다."""
    가짜 = _가짜노션([_쪽(사람, "가", 상태="online")])
    m = _명부(가짜)
    m.반영(m.사람줄(m.줄들())[0], _본것("offline"), apply=True)
    비고 = 가짜.만든것[0]["properties"]["비고"]["rich_text"][0]["text"]["content"]
    다음 = _가짜노션([_쪽(사람, "가", 상태="online"),
                    _쪽(자동, "가", 상태="offline", 담당자="자동", 비고=비고)])
    m = _명부(다음)
    줄들 = m.줄들()
    assert [x.page_id for x in m.사람줄(줄들)] == [사람]
    assert m.자동짝[사람.replace("-", "")].page_id == 자동


def test_자동_줄이_있으면_그_줄만_고친다():
    비고 = write.짝머리 + 사람 + "\n" + write.짝설명
    가짜 = _가짜노션([_쪽(사람, "가", 상태="online"),
                    _쪽(자동, "가", 상태="online", 담당자="자동", 비고=비고)])
    m = _명부(가짜)
    r = m.반영(m.사람줄(m.줄들())[0], _본것("offline"), apply=True)
    assert r.자동줄 == "고침", r
    assert not 가짜.만든것, "자동 줄이 있는데 또 만들었다"
    assert [pid for pid, _ in 가짜.고친것] == [자동], 가짜.고친것
    assert 가짜.고친것[0][1]["상태"] == {"select": {"name": "offline"}}


def test_자동_줄이_같으면_안_고친다():
    비고 = write.짝머리 + 사람
    가짜 = _가짜노션([_쪽(사람, "가", 상태="online"),
                    _쪽(자동, "가", 상태="offline", 담당자="자동", 비고=비고,
                       확인일="2026-09-23")])
    m = _명부(가짜)
    p = _본것("offline")
    p.두드림 = False                   # 확인일만 다른 것도 없게
    r = m.반영(m.사람줄(m.줄들())[0], p, apply=True)
    assert not 가짜.고친것 and not 가짜.만든것, (가짜.고친것, 가짜.만든것)
    assert r.자동줄 == "그대로"


def test_자동_줄은_조사하지_않는다():
    비고 = write.짝머리 + 사람
    가짜 = _가짜노션([_쪽(사람, "가"), _쪽(자동, "가", 담당자="자동", 비고=비고)])
    m = _명부(가짜)
    줄들 = m.줄들()
    자동줄 = [x for x in 줄들 if x.자동][0]
    try:
        m.반영(자동줄, _본것("offline"), apply=True)
    except ValueError:
        pass
    else:
        raise AssertionError("자동 줄을 조사 대상으로 받았다")
    assert not 가짜.고친것 and not 가짜.만든것


def test_조사기가_사람줄만_넘긴다():
    """run.py 가 사람줄() 을 안 거치면 자동 줄의 자동 줄이 생긴다."""
    글 = (ROOT / "hub" / "places" / "run.py").read_text(encoding="utf-8")
    assert "줄들 = m.사람줄(m.줄들())" in 글, "한갈래() 가 자동 줄까지 조사한다"
    assert "명부.사람줄(명부(g).줄들())" in 글, "이음 사전에 자동 줄이 들어간다"


def test_자동_선택지가_없으면_안_만든다():
    가짜 = _가짜노션([_쪽(사람, "가", 상태="online")], 담당자선택지=("최현서",))
    m = _명부(가짜)
    r = m.반영(m.사람줄(m.줄들())[0], _본것("offline"), apply=True)
    assert not 가짜.만든것 and not 가짜.고친것
    assert "선택지" in r.오류, r.오류


def test_미리보기는_안_쓴다():
    가짜 = _가짜노션([_쪽(사람, "가", 상태="online")])
    m = _명부(가짜)
    r = m.반영(m.사람줄(m.줄들())[0], _본것("offline"), apply=False)
    assert r.자동줄 == "새로"
    assert not 가짜.만든것 and not 가짜.고친것


def test_사람이_판정한_상태도_안_덮는다():
    """압수됨 · 인계됨 은 사람 판정이다. 전에도 안 덮었고 지금은 사람 줄 자체를 안 쓴다."""
    가짜 = _가짜노션([_쪽(사람, "가", 상태="online")])
    m = _명부(가짜)
    줄 = m.사람줄(m.줄들())[0]
    줄.현재["상태"] = "압수됨"
    r = m.반영(줄, _본것("online"), apply=True)
    assert r.사람판정
    assert not _사람줄에_썼나(가짜)


def test_목록과_글자를_견준다():
    """다중 선택은 노션에서 「a · b」 로 읽힌다. 글자로만 견주면 늘 다르다."""
    assert write._같나("a · b", ["b", "a"])
    assert not write._같나("a", ["a", "b"])
    assert write._같나("예", True) and write._같나("아니오", False)
    assert write._같나("12.0", 12)
    assert write._같나(" online ", "online")


# ── 규모: 숫자가 같고 날짜만 다르면 안 친다 (2026-09-24 최현서 결정) ──────────
def _규모본것(회원: int = 349000, 게시물: int = 821000) -> Place:
    return Place(갈래="forum", 이름="가", 주소="http://a.example", 상태="online",
                 두드림=True, 확인일="2026-09-23", 회원수=회원, 게시물수=게시물)


def test_규모가_날짜만_다르면_자동_줄을_안_만든다():
    """첫 미리보기의 텔레그램 자동 줄 12개가 전부 이 까닭이었다."""
    가짜 = _가짜노션([_쪽(사람, "가", 규모="회원 349,000 · 게시물 821,000 (2026-09-01 기준)")])
    m = _명부(가짜)
    r = m.반영(m.사람줄(m.줄들())[0], _규모본것(), apply=True)
    assert not 가짜.만든것 and not 가짜.고친것, (가짜.만든것, 가짜.고친것)
    assert "규모" not in r.바뀐칸, r.바뀐칸


def test_규모_숫자가_다르면_자동_줄을_만든다():
    가짜 = _가짜노션([_쪽(사람, "가", 규모="회원 349,000 · 게시물 821,000 (2026-09-01 기준)")])
    m = _명부(가짜)
    r = m.반영(m.사람줄(m.줄들())[0], _규모본것(게시물=822000), apply=True)
    assert r.자동줄 == "새로" and "규모" in r.바뀐칸, r
    assert not _사람줄에_썼나(가짜), "사람 줄에 썼다"
    # 견주는 규칙만 바뀌었다. 자동 줄에는 기계가 본 값을 날짜째 쓴다
    쓴값 = 가짜.만든것[0]["properties"]["규모"]["rich_text"][0]["text"]["content"]
    assert 쓴값.endswith("(2026-09-23 기준)"), 쓴값


def test_자동_줄의_규모가_날짜만_다르면_안_고친다():
    """판마다 날짜만 바뀐 규모로 자동 줄을 고치면 PATCH 가 판마다 나간다."""
    비고 = write.짝머리 + 사람
    가짜 = _가짜노션([
        _쪽(사람, "가", 규모="회원 349,000 · 게시물 821,000 (2026-09-01 기준)", 상태="offline"),
        _쪽(자동, "가", 담당자="자동", 비고=비고, 확인일="2026-09-23",
           규모="회원 349,000 · 게시물 822,000 (2026-09-20 기준)"),
    ])
    m = _명부(가짜)
    p = _규모본것(게시물=822000)
    p.두드림 = False                   # 확인일만 다른 것도 없게
    r = m.반영(m.사람줄(m.줄들())[0], p, apply=True)
    assert not 가짜.고친것 and not 가짜.만든것, (가짜.고친것, 가짜.만든것)
    assert r.자동줄 == "그대로", r


def test_합친값을_견주는_규칙():
    같나 = write._합친값_같나
    # 기계 줄 — 날짜를 떼고 숫자만
    assert 같나("구독자 8,145 (2026-09-01 기준)", "구독자 8,145 (2026-09-23 기준)")
    assert not 같나("구독자 8,145 (2026-09-01 기준)", "구독자 8,146 (2026-09-23 기준)")
    assert not 같나("회원 1 · 게시물 2 (2026-09-01 기준)", "회원 1 · 게시물 3 (2026-09-01 기준)")
    assert 같나("646", "646")
    # 사람 글은 글자 그대로. 사람이 쓴 날짜는 기계 꼴이 아니라 남긴다
    assert 같나("멤버 수 못 셈", "멤버 수 못 셈")
    assert not 같나("멤버 수 못 셈", "멤버 수 모름")
    assert not 같나("구독자 1,440명 (2026.08.04 13:32 GMT+9 기준)",
                  "구독자 1,440명 (2026.08.05 13:32 GMT+9 기준)")
    # 사람 글과 기계 줄이 섞여 있으면 줄마다
    assert 같나("사람 메모\n구독자 10 (2026-09-01 기준)", "사람 메모\n구독자 10 (2026-09-23 기준)")
    assert not 같나("사람 메모\n구독자 10 (2026-09-01 기준)", "딴 메모\n구독자 10 (2026-09-23 기준)")
    # 줄이 새로 붙었으면 다르다 — 사람 글만 있던 칸에 기계 줄이 처음 붙는 경우
    assert not 같나("사람 메모", "사람 메모\n구독자 10 (2026-09-23 기준)")
    # 합치는 칸이 아니면 전과 같다
    assert not write._칸같나("상태", "online (2026-09-01 기준)", "online (2026-09-23 기준)")


def test_가짜를_되돌렸다():
    _명부(_가짜노션([]))
    assert not isinstance(write.Notion, type(lambda: 0)), "가짜 노션이 남았다"


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
