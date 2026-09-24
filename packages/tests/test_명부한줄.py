"""명부가 한 곳에 한 줄로 쓰이고 사람 값을 안 지우는가 — 시험. **노션에 안 붙습니다.**

    python packages/tests/test_명부한줄.py          CI 가 이렇게 돌린다
    python -m pytest packages/tests/test_명부한줄.py

2026-09-24 최현서 결정이다. 사람 줄 옆에 기계 줄을 따로 두는 방식을 접고
칸 갈래로 사람 값을 지킨다.

    빈칸만칸       사람이 쓴 칸은 안 건드린다
    합치는칸       사람 글은 두고 기계 줄만 갈아 끼운다. 숫자가 같고 날짜만 다르면 안 쓴다
    이어붙이는칸   지우지 않고 새 주소를 맨 뒤에 붙인다   (어니언 주소 · 이전 주소)
    주소           사이트가 스스로 옮겼을 때(리다이렉트)만 바꾼다

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
옛어니언 = "a" * 56 + ".onion"
새어니언 = "b" * 56 + ".onion"

스키마 = {"포럼 이름": "title", "주소": "url", "상태": "select", "확인일": "date",
        "담당자": "select", "비고": "rich_text", "DB 반영": "checkbox",
        "어니언 주소": "rich_text", "이전 주소": "rich_text", "규모": "rich_text",
        "사용 언어": "rich_text"}


def _글(v: str) -> list:
    return [{"plain_text": v}] if v else []


def _쪽(*, 주소: str = "http://a.example", 상태: str = "online", 확인일: str = "2026-09-20",
       어니언: str = "", 이전주소: str = "", 규모: str = "", 언어: str = "") -> dict:
    return {"id": 사람, "properties": {
        "포럼 이름": {"type": "title", "title": _글("가")},
        "주소": {"type": "url", "url": 주소 or None},
        "상태": {"type": "select", "select": {"name": 상태} if 상태 else None},
        "확인일": {"type": "date", "date": {"start": 확인일}},
        "담당자": {"type": "select", "select": {"name": "최현서"}},
        "비고": {"type": "rich_text", "rich_text": _글("사람 메모")},
        "DB 반영": {"type": "checkbox", "checkbox": True},
        "어니언 주소": {"type": "rich_text", "rich_text": _글(어니언)},
        "이전 주소": {"type": "rich_text", "rich_text": _글(이전주소)},
        "규모": {"type": "rich_text", "rich_text": _글(규모)},
        "사용 언어": {"type": "rich_text", "rich_text": _글(언어)},
    }}


class _가짜노션:
    def __init__(self, 쪽들: list):
        self.쪽들 = 쪽들
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
                "상태": {"type": "select", "select": {
                    "options": [{"name": x} for x in ("online", "offline", "미확인", "압수됨")]}},
            }}
        if method == "POST" and path == "/pages":
            self.만든것.append(body)
            return {"id": "new"}
        raise AssertionError(f"모르는 요청 {method} {path}")


def _명부(가짜: _가짜노션):
    """가짜 노션을 물린 명부. **가짜를 꼭 되돌린다.**"""
    옛 = write.Notion
    write.Notion = lambda verbose=False: 가짜
    try:
        m = write.명부("forum")
    finally:
        write.Notion = 옛
    return m


def _본것(**kw) -> Place:
    기본 = dict(갈래="forum", 이름="가", 주소="http://a.example", 상태="online",
              두드림=True, 확인일="2026-09-23")
    기본.update(kw)
    return Place(**기본)


def _돌려(쪽: dict, p: Place, *, apply: bool = True):
    가짜 = _가짜노션([쪽])
    m = _명부(가짜)
    r = m.반영(m.줄들()[0], p, apply=apply)
    쓴것 = 가짜.고친것[0][1] if 가짜.고친것 else {}
    return r, 가짜, 쓴것


def _글자값(속성: dict) -> str:
    """보낸 rich_text · url 속성에서 글자를 꺼낸다."""
    if "url" in 속성:
        return 속성["url"] or ""
    return "".join(x["text"]["content"] for x in 속성.get("rich_text", []))


# ── 한 곳 한 줄 ────────────────────────────────────────────────────
def test_새_줄을_만들지_않고_그_줄만_고친다():
    r, 가짜, 쓴것 = _돌려(_쪽(상태="online"), _본것(상태="offline"))
    assert not 가짜.만든것, "명부에 새 줄을 만들었다"
    assert [pid for pid, _ in 가짜.고친것] == [사람], 가짜.고친것
    assert 쓴것["상태"] == {"select": {"name": "offline"}}


def test_사람_판정_상태는_안_덮는다():
    r, 가짜, 쓴것 = _돌려(_쪽(상태="압수됨"), _본것(상태="online"))
    assert "상태" not in 쓴것, 쓴것
    assert r.사람판정


# ── 주소 ───────────────────────────────────────────────────────────
def test_표기만_다른_같은_주소는_아무것도_안_쓴다():
    """http · 끝의 / · 대소문자만 다르면 같은 주소다. 이전 주소에도 안 붙인다."""
    r, 가짜, 쓴것 = _돌려(_쪽(주소="http://a.example"), _본것(주소="https://A.example/"))
    assert "주소" not in 쓴것 and "이전 주소" not in 쓴것, 쓴것
    assert "주소" in r.사람글


def test_기계가_본_주소가_다르면_주소는_두고_이전_주소에_붙인다():
    """랜섬 집계 API 가 고른 대표 주소가 사람 주소와 다른 경우다. 버리지 않는다."""
    쪽 = _쪽(주소="http://a.example", 이전주소="http://z.example")
    r, 가짜, 쓴것 = _돌려(쪽, _본것(주소="http://b.example"))
    assert "주소" not in 쓴것, 쓴것
    assert _글자값(쓴것["이전 주소"]) == "http://z.example\nhttp://b.example", 쓴것


def test_사이트가_옮겼으면_주소를_바꾸고_옛_주소를_이어_붙인다():
    쪽 = _쪽(주소="http://a.example", 이전주소="http://z.example")
    r, 가짜, 쓴것 = _돌려(쪽, _본것(주소="http://b.example", 이전주소="http://a.example"))
    assert 쓴것["주소"] == {"url": "http://b.example"}, 쓴것
    assert _글자값(쓴것["이전 주소"]) == "http://z.example\nhttp://a.example", 쓴것


def test_다른_미러는_주소를_안_바꾼다():
    """이전주소 가 명부의 주소와 다르면 옮겨 간 것이 아니다. 둘 다 이전 주소에 남는다."""
    쪽 = _쪽(주소="http://a.example")
    r, 가짜, 쓴것 = _돌려(쪽, _본것(주소="http://b.example", 이전주소="http://m.example"))
    assert "주소" not in 쓴것, 쓴것
    assert _글자값(쓴것["이전 주소"]) == "http://m.example\nhttp://b.example", 쓴것


def test_주소가_비었으면_채운다():
    r, 가짜, 쓴것 = _돌려(_쪽(주소=""), _본것(주소="http://b.example"))
    assert 쓴것["주소"] == {"url": "http://b.example"}, 쓴것


# ── 이어 붙이기 ────────────────────────────────────────────────────
def test_어니언은_맨_뒤에_이어_붙인다():
    기존 = 옛어니언 + " (2026-07-30 확인)"
    r, 가짜, 쓴것 = _돌려(_쪽(어니언=기존), _본것(어니언="http://" + 새어니언))
    값 = _글자값(쓴것["어니언 주소"])
    assert 값 == 기존 + "\nhttp://" + 새어니언, 값
    assert 값.split()[0] == 옛어니언, "조사기가 두드릴 첫 주소가 바뀌었다"


def test_이미_있는_어니언이면_안_쓴다():
    """꼴(http:// · 끝의 /)만 달라도 같은 주소다."""
    r, 가짜, 쓴것 = _돌려(_쪽(어니언=옛어니언 + " (2026-07-30 확인)"),
                      _본것(어니언="http://" + 옛어니언 + "/"))
    assert "어니언 주소" not in 쓴것, 쓴것


def test_자리표시자_어니언은_새것으로_바꾼다():
    """「— 미기입 —」 뒤에 붙이면 조사기가 첫 조각 「—」 을 두드린다."""
    r, 가짜, 쓴것 = _돌려(_쪽(어니언="— 미기입 —"), _본것(어니언="http://" + 새어니언))
    assert _글자값(쓴것["어니언 주소"]) == "http://" + 새어니언, 쓴것


def test_이어_붙이기_규칙():
    붙 = write._이어붙이기
    assert 붙("", "x.example") == "x.example"
    assert 붙("x.example", "") == "x.example"
    assert 붙("x.example", "http://X.example/") == "x.example"
    assert 붙("x.example", "y.example") == "x.example\ny.example"
    assert 붙("x.example\ny.example", "y.example") == "x.example\ny.example"
    assert 붙("— 없음 —", "y.example") == "y.example"


def test_미러_줄은_주소마다_본다():
    """랜섬 조사기는 미러 여럿을 「a · b · c」 한 줄로 넘긴다. 첫 주소만 보면 안 된다.

    2026-09-24 첫 쓰기에서 첫 주소가 새것인 줄이 이미 있던 미러까지 통째로 붙어
    랜섬 9줄에 같은 주소가 두 번 들어갔다.
    """
    붙 = write._이어붙이기
    있던 = "http://a.onion · http://b.onion"
    assert 붙(있던, "http://c.onion · http://a.onion · http://b.onion") == 있던 + "\nhttp://c.onion"
    assert 붙("http://a.onion", "http://a.onion · http://d.onion") == "http://a.onion\nhttp://d.onion"
    assert 붙(있던, "http://b.onion · http://a.onion") == 있던
    assert 붙("(http://a.onion)", "http://a.onion/") == "(http://a.onion)"
    assert 붙("x.example (2026.08.04 확인)", "y.example") == "x.example (2026.08.04 확인)\ny.example"


def test_미러가_섞여_와도_없던_것만_이전_주소에_붙인다():
    쪽 = _쪽(주소="http://a.example", 이전주소="http://z.example")
    r, 가짜, 쓴것 = _돌려(쪽, _본것(이전주소="http://m.example · http://z.example"))
    assert _글자값(쓴것["이전 주소"]) == "http://z.example\nhttp://m.example", 쓴것


# ── 규모: 숫자가 같고 날짜만 다르면 안 쓴다 ─────────────────────────
def _규모본것(게시물: int = 821000) -> Place:
    return _본것(회원수=349000, 게시물수=게시물)


def test_규모가_날짜만_다르면_안_쓴다():
    r, 가짜, 쓴것 = _돌려(_쪽(규모="회원 349,000 · 게시물 821,000 (2026-09-01 기준)"),
                      _규모본것())
    assert "규모" not in 쓴것, 쓴것


def test_규모_숫자가_다르면_기계_줄만_바꾸고_사람_글은_둔다():
    기존 = "사람이 적은 설명\n회원 349,000 · 게시물 821,000 (2026-09-01 기준)"
    r, 가짜, 쓴것 = _돌려(_쪽(규모=기존), _규모본것(게시물=822000))
    값 = _글자값(쓴것["규모"])
    assert 값 == "사람이 적은 설명\n회원 349,000 · 게시물 822,000 (2026-09-23 기준)", 값


def test_합친값을_견주는_규칙():
    같나 = write._합친값_같나
    assert 같나("구독자 8,145 (2026-09-01 기준)", "구독자 8,145 (2026-09-23 기준)")
    assert not 같나("구독자 8,145 (2026-09-01 기준)", "구독자 8,146 (2026-09-23 기준)")
    assert 같나("멤버 수 못 셈", "멤버 수 못 셈")
    assert not 같나("구독자 1,440명 (2026.08.04 13:32 GMT+9 기준)",
                  "구독자 1,440명 (2026.08.05 13:32 GMT+9 기준)")
    assert not 같나("사람 메모", "사람 메모\n구독자 10 (2026-09-23 기준)")
    assert not write._칸같나("상태", "online (2026-09-01 기준)", "online (2026-09-23 기준)")


# ── 빈칸만칸 · 견주기 ──────────────────────────────────────────────
def test_사람이_쓴_빈칸만칸은_안_쓴다():
    r, 가짜, 쓴것 = _돌려(_쪽(언어="한국어"), _본것(언어="English"))
    assert "사용 언어" not in 쓴것, 쓴것
    assert "사용 언어" in r.사람글


def test_목록과_글자를_견준다():
    """다중 선택은 노션에서 「a · b」 로 읽힌다. 글자로만 견주면 늘 다르다."""
    assert write._같나("a · b", ["b", "a"])
    assert not write._같나("a", ["a", "b"])
    assert write._같나("예", True) and write._같나("아니오", False)
    assert write._같나("12.0", 12)


def test_미리보기는_안_쓴다():
    r, 가짜, 쓴것 = _돌려(_쪽(상태="online"), _본것(상태="offline"), apply=False)
    assert "상태" in r.바뀐칸
    assert not 가짜.고친것 and not 가짜.만든것


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
