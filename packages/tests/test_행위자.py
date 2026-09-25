"""행위자 DB 자동 등록 — 시험. **밖에 안 나가고 노션에 안 붙습니다.**

    python packages/tests/test_행위자.py          CI 가 이렇게 돌린다

2026-09-25 최현서 결정 D-3. 수집이 한 판 돌 때마다 수집 DB 전체를 훑어 행위자 DB · 명부 셋
어디에도 없는 판매 · 공개 핸들을 행위자 DB 에 올린다. 규칙은 `hub/events/actor.py`.

**피해 조직 이름은 행위자 줄에 안 들어간다.** 한국 관련 유출은 「YYYY-MM 한국 N건」 뿐이다.
값은 전부 지어낸 것이다. 레포가 공개다.

**실행부를 둔다.** CI 는 이 폴더를 `python 파일` 로 돌린다.
"""
from __future__ import annotations

import collections
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packages"))

from hub.events import actor  # noqa: E402


def _글칸(종류, 값):
    return {"type": 종류, 종류: [{"plain_text": 값}] if 값 else []}


def _고른칸(값):
    return {"type": "select", "select": {"name": 값} if 값 else None}


def 수집줄(핸들, 성격, *, 곳="", 소스="포럼", 시각="", 국가="", 한국="", 대상="지어낸피해회사"):
    return {"id": "s-" + 핸들, "properties": {
        "게시자 핸들": _글칸("rich_text", 핸들),
        "게시 성격": _고른칸(성격),
        "게시처": _고른칸(곳),
        "소스": _고른칸(소스),
        "게시 시각": {"type": "date", "date": {"start": 시각} if 시각 else None},
        "발견일": {"type": "date", "date": None},
        "국가": _고른칸(국가),
        "한국 관련": _고른칸(한국),
        "대상 조직": _글칸("rich_text", 대상),
    }}


def 행위자줄(핸들, 다른=""):
    return {"id": "a-" + 핸들, "properties": {
        "핸들": _글칸("title", 핸들), "다른 이름": _글칸("rich_text", 다른)}}


def 명부줄(제목칸, 이름, 별칭=""):
    return {"id": "m-" + 이름, "properties": {
        제목칸: _글칸("title", 이름), "이전 이름·별칭": _글칸("rich_text", 별칭)}}


class _가짜노션:
    def __init__(self, 수집, 행위자=(), 랜섬=(), 포럼=(), 텔레=()):
        명부 = dict(zip((db for db, _ in actor.명부), (랜섬, 포럼, 텔레)))
        self.표 = {actor.수집DS: list(수집), actor.행위자DS: list(행위자),
                  **{db + "-ds": list(줄) for db, 줄 in 명부.items()}}
        self.만든것 = []

    def data_sources(self, db):
        return [{"id": db + "-ds"}]

    def query_all(self, ds):
        return list(self.표[ds])

    def request(self, method, path, body=None):
        assert (method, path) == ("POST", "/pages"), (method, path)
        assert body["parent"] == {"type": "data_source_id", "data_source_id": actor.행위자DS}
        self.만든것.append(body["properties"])
        return {"id": "새줄"}


오늘 = date(2026, 9, 25)


def _핸들(p):
    return p["핸들"]["title"][0]["text"]["content"]


# ── 무엇을 올리나 ───────────────────────────────────────────────────
def test_없는_판매_핸들만_올린다():
    가짜 = _가짜노션([
        수집줄("SellerA", "DB 판매"),
        수집줄("FreeB", "DB 무료 공개"),
        수집줄("GroupC", "랜섬웨어 유출", 소스="텔레그램"),      # 그룹이다. 행위자가 아니다
        수집줄("OldD", "DB 판매"),                              # 이미 행위자 DB 에 있다
        수집줄("", "DB 판매"),                                  # 핸들이 비었다
    ], 행위자=[행위자줄("OldD")])
    셈 = actor.훑기(가짜, apply=True, 오늘=오늘)
    assert sorted(_핸들(p) for p in 가짜.만든것) == ["FreeB", "SellerA"], 가짜.만든것
    assert (셈["새로"], 셈["만듦"], 셈["이미 있음"], 셈["판매·공개 글 없음"]) == (2, 2, 1, 1), 셈


def test_다른_이름과_명부_별칭과_0o_를_견딘다():
    가짜 = _가짜노션([
        수집줄("Max_98", "DB 판매"),      # 행위자 DB 다른 이름 「max98」
        수집줄("Cl0p", "DB 판매"),        # 랜섬 명부 「Clop」
        수집줄("ForumGuy", "DB 판매"),    # 포럼 명부 별칭
        수집줄("chanx", "DB 판매"),       # 텔레 명부 이름
    ], 행위자=[행위자줄("Someone", "max98 (breached.st) · Max (Signal)")],
        랜섬=[명부줄("그룹 이름", "Clop")],
        포럼=[명부줄("포럼 이름", "SomeForum", "forum guy")],
        텔레=[명부줄("채널 이름", "ChanX")])
    셈 = actor.훑기(가짜, apply=True, 오늘=오늘)
    assert not 가짜.만든것 and 셈["이미 있음"] == 4, 셈


def test_같은_열쇠의_핸들은_한_줄이고_많이_쓴_표기를_쓴다():
    가짜 = _가짜노션([수집줄("dbhooligan", "DB 판매"), 수집줄("DBHooligan", "DB 판매"),
                    수집줄("DBHooligan", "DB 판매")])
    actor.훑기(가짜, apply=True, 오늘=오늘)
    assert [_핸들(p) for p in 가짜.만든것] == ["DBHooligan"], 가짜.만든것


# ── 줄 모양 ─────────────────────────────────────────────────────────
def test_줄은_9_3_모양이고_피해_조직_이름이_없다():
    줄들 = [수집줄("SellerA", "DB 판매", 곳="SomeForum", 시각="2026-08-16T10:00:00+09:00",
                  국가="한국", 대상="지어낸피해회사"),
           수집줄("SellerA", "DB 무료 공개", 곳="OtherForum", 소스="텔레그램",
                  시각="2026-07-04T00:00:00+00:00", 한국="직접", 대상="또다른피해회사"),
           수집줄("SellerA", "DB 판매", 곳="SomeForum", 국가="미국", 대상="외국회사")]
    p = actor.속성("SellerA", 줄들, "2026-09-25")
    글 = json.dumps(p, ensure_ascii=False)
    for 이름 in ("지어낸피해회사", "또다른피해회사", "외국회사"):
        assert 이름 not in 글, 이름
    assert p["연결된 곳"]["rich_text"][0]["text"]["content"] == "OtherForum · SomeForum"
    assert p["처음 본 날"] == {"date": {"start": "2026-07-04"}}
    assert [x["name"] for x in p["출처"]["multi_select"]] == ["텔레그램", "포럼"]
    assert p["역할"] == {"multi_select": [{"name": "판매자"}]}
    assert p["한국 관련 유출"]["rich_text"][0]["text"]["content"] == "2026-07 한국 1건 · 2026-08 한국 1건"
    assert p["조사 단계"] == {"select": {"name": "시작 전"}}
    assert p["DB 반영"] == {"checkbox": True}
    비고 = p["비고"]["rich_text"][0]["text"]["content"]
    assert 비고 == "2026-09-25 수집 DB 게시자 핸들에서 자동 등록", 비고
    assert actor.표지 in 비고, "⑨-3 이 알아볼 표지가 없다"
    for 칸 in ("다른 이름", "국가", "지갑 주소", "텔레그램"):
        assert 칸 not in p, "근거 없는 칸을 채웠다: " + 칸


def test_무료_공개만이면_역할은_미확인이고_날짜가_없으면_비운다():
    p = actor.속성("FreeB", [수집줄("FreeB", "DB 무료 공개")], "2026-09-25")
    assert p["역할"] == {"multi_select": [{"name": "미확인"}]}
    assert "처음 본 날" not in p and "한국 관련 유출" not in p and "연결된 곳" not in p


def test_소급_줄도_같은_표지를_단다():
    # 9/25 소급 도구가 단 비고. ⑨-3 이 이 줄도 빈 칸만 채워야 한다
    assert actor.표지 in "2026-09-25 수집 DB 게시자 핸들에서 소급 등록 (AI)"


# ── 쓰기 ────────────────────────────────────────────────────────────
def test_미리보기는_안_쓴다():
    가짜 = _가짜노션([수집줄("SellerA", "DB 판매")])
    셈 = actor.훑기(가짜, apply=False, 오늘=오늘)
    assert 셈["새로"] == 1 and not 가짜.만든것
    assert "미리보기" in actor.요약(셈, False)


def test_한_판에_너무_많으면_안_쓴다():
    가짜 = _가짜노션([수집줄("S%d" % i, "DB 판매") for i in range(actor.상한 + 1)])
    셈 = actor.훑기(가짜, apply=True, 오늘=오늘)
    assert not 가짜.만든것 and 셈["상한 넘어 안 씀"] == actor.상한 + 1, 셈
    assert "안 씁니다" in actor.요약(셈, True)


def test_요약에_핸들이_없다():
    가짜 = _가짜노션([수집줄("SecretSeller", "DB 판매")])
    셈 = actor.훑기(가짜, apply=True, 오늘=오늘)
    s = actor.요약(셈, True)
    assert "SecretSeller" not in s, s
    assert "만듦 1" in s, s


def test_한_줄이_죽어도_나머지를_올린다():
    가짜 = _가짜노션([수집줄("A1", "DB 판매"), 수집줄("B2", "DB 판매")])
    원래 = 가짜.request

    def 한번죽음(method, path, body=None):
        if _핸들(body["properties"]) == "A1":
            raise RuntimeError("노션 500")
        return 원래(method, path, body)

    가짜.request = 한번죽음
    셈 = actor.훑기(가짜, apply=True, 오늘=오늘)
    assert (셈["만듦"], 셈["못 만듦"]) == (1, 1), 셈


# ── push.py 에 붙은 자리 ────────────────────────────────────────────
def test_push_가_판마다_훑고_죽어도_수집은_그대로다():
    from hub.events import push

    글 = (ROOT / "hub" / "events" / "push.py").read_text(encoding="utf-8")
    # 올릴 줄이 없는 판 · 미리보기 · 쓴 뒤, 세 자리 모두에서 부른다
    assert 글.count("행위자훑기(n, ") == 3, "행위자 훑기를 빠뜨린 길이 있다"

    class _죽는노션:
        def data_sources(self, db):
            raise RuntimeError("노션이 죽었다")

    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        push.행위자훑기(_죽는노션(), True)          # 예외가 밖으로 안 나온다
    assert "못 채웠습니다" in buf.getvalue()


def test_열쇠가_소급_도구와_같다():
    # 9/25 소급(D-2)과 인계가 쓴 열쇠. 한글은 남기고 0 은 o
    assert actor.키("Cl0p Team!") == "clopteam"
    assert actor.키("다크 초코_0") == "다크초코o"
    assert collections.Counter(actor.조각("a / b · c, d (e)")) == collections.Counter("abcde")


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
