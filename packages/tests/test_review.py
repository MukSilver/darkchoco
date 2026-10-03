"""매일 미검토 판정(`hub/events/review.py`) — 시험. **노션에 안 붙는다.** 가짜 노션을 쓴다.

    python packages/tests/test_review.py          CI 가 이렇게 돌린다

2026-10-02 최현서 「매일 아침 예약으로 판정하자 · 사건 O 는 직접 돌릴 때만」.
조직명은 모두 지어낸 것이다. **실행부를 둔다.** CI 는 이 폴더를 `python 파일` 로 돌린다.
"""
from __future__ import annotations

import contextlib
import io
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packages"))

from hub.events import review  # noqa: E402


def _글(v):
    return [{"plain_text": v}] if v else []


def _줄(번호, 검토="미검토", 소스="텔레그램", 조직="Fakeland Steel", 한국="미확인", 근거="", 국가="",
       반영=False, 플랫폼="t.me/fakechannel", 핸들="FakeGroup"):
    return {"id": "page-%d" % 번호, "last_edited_time": "2026-10-02T00:00:00.000Z", "properties": {
        "사건 ID": {"type": "unique_id", "unique_id": {"prefix": "LEAK", "number": 번호}},
        "검토 여부": {"type": "select", "select": {"name": 검토}},
        "소스": {"type": "select", "select": {"name": 소스}},
        "대상 조직": {"type": "rich_text", "rich_text": _글(조직)},
        "한국 관련": {"type": "select", "select": {"name": 한국}},
        "한국 관련 근거": {"type": "rich_text", "rich_text": _글(근거)},
        "국가": {"type": "select", "select": {"name": 국가} if 국가 else None},
        "DB 반영": {"type": "checkbox", "checkbox": 반영},
        "게시 플랫폼": {"type": "rich_text", "rich_text": _글(플랫폼)},
        "원문 URL": {"type": "url", "url": "https://t.me/fakechannel/1"},
        "게시자 핸들": {"type": "rich_text", "rich_text": _글(핸들)},
        "게시 시각": {"type": "date", "date": {"start": "2026-10-01T10:00:00.000+00:00"}},
    }}


class 가짜노션:
    def __init__(self, 줄들):
        self.줄 = {p["id"]: p for p in 줄들}
        self.쓴것 = []

    def query_all(self, ds):
        return list(self.줄.values())

    def page(self, pid):
        return json.loads(json.dumps(self.줄[pid]))

    def update_page(self, pid, props):
        self.쓴것.append((pid, props))
        p = self.줄[pid]["properties"]
        p["검토 여부"]["select"] = {"name": props["검토 여부"]["select"]["name"]}
        p["DB 반영"]["checkbox"] = props["DB 반영"]["checkbox"]


@contextlib.contextmanager
def _판(줄들):
    """임시 자리 · 가짜 노션으로 바꿔 끼운다."""
    d = Path(tempfile.mkdtemp(prefix="review_"))
    n = 가짜노션(줄들)
    옛 = (review.노션, review.수집DS)
    review.노션, review.수집DS = (lambda: n), (lambda: "fake-ds")
    try:
        yield d, n
    finally:
        review.노션, review.수집DS = 옛
        shutil.rmtree(d, ignore_errors=True)


def _돌림(*args):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        r = review.main(list(args))
    return r, buf.getvalue()


def _판정(id_, verdict="사건 X", conf="높음", refuted=False):
    return {"id": id_, "verdict": verdict, "confidence": conf, "hq_country": "Fakeland", "kr_presence": "없음",
            "reason": "지어낸 근거", "sources": ["https://fake.example.test/about"],
            "refute": None if refuted is None else {"refuted": refuted, "reason": "", "sources": []}}


# ── 1. 대상 ────────────────────────────────────────────────────
def test_미검토만_고르고_포럼_보류_전에_판정한_줄은_뺀다():
    줄들 = [_줄(1), _줄(2, 검토="사건 X"), _줄(3, 소스="포럼", 조직=""), _줄(4), _줄(5), _줄(6, 검토="사건 O")]
    고른, 셈 = review.고르기(줄들, {"LEAK-4"}, {"LEAK-5"}, 다시=False)
    assert [review.값(p, "사건 ID") for p in 고른] == ["LEAK-1"], 고른
    assert 셈 == {"보류": 1, "포럼": 1, "전에 판정함": 1}, 셈
    고른, _ = review.고르기(줄들, {"LEAK-4"}, {"LEAK-5"}, 다시=True)
    assert sorted(review.값(p, "사건 ID") for p in 고른) == ["LEAK-1", "LEAK-5"], "--다시 면 전에 판정한 줄도 본다"


def test_재료에는_게시_플랫폼_원문_근거를_안_넘긴다():
    r = review.재료(_줄(1, 근거="someone@example.test 가 적은 메모"))
    assert tuple(r) == review.재료칸, r
    본 = json.dumps(r, ensure_ascii=False)
    for 안됨 in ("t.me", "fakechannel", "example.test", "메모"):
        assert 안됨 not in 본, (안됨, 본)


def test_집계처만_한국이라_한_직접_줄을_표시한다():
    assert review.재료(_줄(1, 한국="직접", 근거="집계처 국가만 — 도메인·이름·한글 신호 없음 · 소스 country=KR"))["집계처 한국"]
    assert not review.재료(_줄(1, 한국="직접", 근거="한국 도메인(.kr)"))["집계처 한국"]
    assert not review.재료(_줄(1, 한국="미확인"))["집계처 한국"]


def test_대상은_화면에_조직명을_안_낸다():
    with _판([_줄(1, 조직="Fakeland Steel"), _줄(2, 조직="Pretend Foods")]) as (d, n):
        r, 찍힘 = _돌림("대상", "--자리", str(d), "--날", "20261003")
        assert r == 0 and "오늘 판정 2줄" in 찍힘, 찍힘
        for 안됨 in ("Fakeland", "Pretend"):
            assert 안됨 not in 찍힘, 찍힘
        assert len(json.loads((d / "20261003" / "조사재료.json").read_text(encoding="utf-8"))) == 2
        assert n.쓴것 == [], "대상은 노션에 안 쓴다"


def test_자리가_레포_안이면_멈춘다():
    try:
        review.main(["대상", "--자리", str(ROOT / "hub" / "data" / "x")])
    except SystemExit as e:
        assert "레포 안" in str(e), e
    else:
        raise AssertionError("레포 안 자리를 받았다")


# ── 2. 제안 규칙 ───────────────────────────────────────────────
def test_사건_X_는_반박을_버티고_확신이_충분할_때만():
    assert review.제안(_판정("LEAK-1", conf="높음"), 무인=True) == "사건 X"
    assert review.제안(_판정("LEAK-1", conf="중간"), 무인=True) == "미검토", "예약 판은 높음만"
    assert review.제안(_판정("LEAK-1", conf="중간"), 무인=False) == "사건 X", "사람이 시킨 판은 중간도"
    assert review.제안(_판정("LEAK-1", conf="낮음"), 무인=False) == "미검토"
    assert review.제안(_판정("LEAK-1", refuted=True), 무인=False) == "미검토", "반박된 X"
    assert review.제안(_판정("LEAK-1", refuted=None), 무인=False) == "미검토", "반박을 못 돌린 X"


def test_사건_O_는_제안하지_않는다():
    for 무인 in (True, False):
        assert review.제안(_판정("LEAK-1", verdict="사건 O"), 무인) == "미검토"


def test_결과는_틀린_판정값을_받지_않는다():
    with _판([_줄(1)]) as (d, n):
        _돌림("대상", "--자리", str(d), "--날", "20261003")
        f = d / "판정.json"
        f.write_text(json.dumps({"rows": [_판정("LEAK-1", verdict="O")]}), encoding="utf-8")
        try:
            review.main(["결과", str(f), "--자리", str(d), "--날", "20261003"])
        except SystemExit as e:
            assert "틀린 줄" in str(e), e
        else:
            raise AssertionError("틀린 판정값을 받았다")


# ── 3. 반영 ────────────────────────────────────────────────────
def _끝까지(d, 판정들, *반영인자, 무인=True):
    f = d / "판정.json"
    f.write_text(json.dumps({"rows": 판정들}, ensure_ascii=False), encoding="utf-8")
    _돌림("대상", "--자리", str(d), "--날", "20261003")
    _돌림("결과", str(f), "--자리", str(d), "--날", "20261003", *(["--무인"] if 무인 else []))
    return _돌림("반영", "--자리", str(d), "--날", "20261003", *반영인자)


def test_예약_판은_사건_X_만_쓴다():
    with _판([_줄(1), _줄(2), _줄(3), _줄(4)]) as (d, n):
        r, 찍힘 = _끝까지(d, [_판정("LEAK-1"), _판정("LEAK-2", conf="중간"), _판정("LEAK-3", verdict="사건 O"),
                           _판정("LEAK-4", refuted=True)], "--쓴다")
        assert r == 0, 찍힘
        assert [(pid, p["검토 여부"]["select"]["name"], p["DB 반영"]["checkbox"]) for pid, p in n.쓴것] == \
            [("page-1", "사건 X", False)], n.쓴것
        assert "Fakeland" not in 찍힘


def test_쓰기_직전에_사람이_바꾼_줄은_건너뛴다():
    with _판([_줄(1), _줄(2)]) as (d, n):
        _끝까지(d, [_판정("LEAK-1"), _판정("LEAK-2")])            # 미리보기만
        n.줄["page-2"]["properties"]["검토 여부"]["select"] = {"name": "사건 O"}   # 그 사이 대시보드에서 누름
        n.줄["page-2"]["properties"]["DB 반영"]["checkbox"] = True
        기록 = json.loads((d / "20261003" / "되돌리기.json").read_text(encoding="utf-8"))
        assert len(기록["줄"]) == 2
        with contextlib.redirect_stdout(io.StringIO()):
            review.반영쓰기(type("A", (), {"자리": str(d), "날": "20261003"})(), n)
        assert [pid for pid, _ in n.쓴것] == ["page-1"], n.쓴것


def test_사건_O_는_사람이_적은_줄만_AI_판정이_O_일_때():
    with _판([_줄(1), _줄(2)]) as (d, n):
        r, 찍힘 = _끝까지(d, [_판정("LEAK-1", verdict="사건 O"), _판정("LEAK-2", verdict="확신 낮음", conf="낮음")],
                        "--사건O", "LEAK-1", "--쓴다", 무인=False)
        assert r == 0, 찍힘
        assert [(pid, p["검토 여부"]["select"]["name"], p["DB 반영"]["checkbox"]) for pid, p in n.쓴것] == \
            [("page-1", "사건 O", True)], n.쓴것
    with _판([_줄(1), _줄(2)]) as (d, n):
        r, 찍힘 = _끝까지(d, [_판정("LEAK-1", verdict="사건 O"), _판정("LEAK-2", verdict="확신 낮음", conf="낮음")],
                        "--사건O", "LEAK-2", "--쓴다", 무인=False)
        assert r == 1 and n.쓴것 == [], "AI 판정이 O 가 아닌 줄은 이 길로 O 를 안 쓴다"


def test_예약_판에서는_사건_O_옵션을_못_쓴다():
    try:
        review.main(["반영", "--자리", "x", "--무인", "--사건O", "LEAK-1"])
    except SystemExit as e:
        assert "사람이 시킨 판" in str(e), e
    else:
        raise AssertionError("--무인 과 --사건O 를 같이 받았다")


def test_보류_줄은_판정이_있어도_안_쓴다():
    with _판([_줄(1), _줄(2)]) as (d, n):
        (d / "보류.txt").write_text("LEAK-2  # 조직을 특정 못 함\n", encoding="utf-8")
        f = d / "판정.json"
        f.write_text(json.dumps({"rows": [_판정("LEAK-1"), _판정("LEAK-2")]}), encoding="utf-8")
        _돌림("대상", "--자리", str(d), "--날", "20261003", "--다시")
        대상 = json.loads((d / "20261003" / "대상.json").read_text(encoding="utf-8"))
        assert [x["사건ID"] for x in 대상] == ["LEAK-1"], "보류는 대상에서 빠진다"


def test_적용한_기록은_다시_안_쓰고_되돌리기는_우리가_쓴_값만():
    with _판([_줄(1), _줄(2)]) as (d, n):
        _끝까지(d, [_판정("LEAK-1"), _판정("LEAK-2")], "--쓴다")
        assert len(n.쓴것) == 2
        r, 찍힘 = _돌림("반영", "--자리", str(d), "--날", "20261003", "--쓴다")
        assert r == 1 and "이미 적용한 기록" in 찍힘, 찍힘
        n.줄["page-2"]["properties"]["검토 여부"]["select"] = {"name": "사건 O"}   # 사람이 뒤집음
        n.줄["page-2"]["properties"]["DB 반영"]["checkbox"] = True
        r, 찍힘 = _돌림("반영", "--자리", str(d), "--날", "20261003", "--되돌린다")
        assert "되돌렸습니다 1" in 찍힘, 찍힘
        assert review.값(n.줄["page-1"], "검토 여부") == "미검토"
        assert review.값(n.줄["page-2"], "검토 여부") == "사건 O", "사람이 바꾼 줄은 그대로"


def test_하루에_두_판이_돌면_두_번째_판은_새_폴더를_쓴다():
    # 사람이 시킨 판 뒤에 07:12 예약 판이 같은 날 돌아도 앞 판의 「적용됨」 에 걸려 멈추지 않는다(10/03)
    with _판([_줄(1), _줄(2)]) as (d, n):
        f = d / "판정.json"
        f.write_text(json.dumps({"rows": [_판정("LEAK-1")]}), encoding="utf-8")
        _돌림("대상", "--자리", str(d))
        _돌림("결과", str(f), "--자리", str(d), "--무인")
        r, _ = _돌림("반영", "--자리", str(d), "--쓴다")
        assert r == 0 and len(n.쓴것) == 1
        n.줄["page-3"] = _줄(3)                                   # 그 사이 새 줄이 들어왔다
        f.write_text(json.dumps({"rows": [_판정("LEAK-2"), _판정("LEAK-3")]}), encoding="utf-8")
        r, 찍힘 = _돌림("대상", "--자리", str(d))
        assert "오늘 판정 2줄" in 찍힘, 찍힘                      # LEAK-1 은 전에 판정함
        _돌림("결과", str(f), "--자리", str(d), "--무인")
        r, 찍힘 = _돌림("반영", "--자리", str(d), "--쓴다")
        assert r == 0, 찍힘
        판들 = sorted(p.name for p in d.iterdir() if p.is_dir())
        assert len(판들) == 2 and 판들[1].endswith("-2"), 판들
        assert [pid for pid, _ in n.쓴것] == ["page-1", "page-2", "page-3"], n.쓴것


def test_확정대기는_전에_판정했고_아직_미검토인_줄만():
    줄들 = [_줄(1), _줄(2, 검토="사건 X"), _줄(3)]
    기록 = {"LEAK-1": {"날": "20261003", "판정": "사건 O", "확신": "높음"},
          "LEAK-2": {"날": "20261003", "판정": "사건 X", "확신": "높음"}}
    md = review.확정대기(줄들, 기록, set())
    assert "LEAK-1" in md and "LEAK-2" not in md and "LEAK-3" not in md, md



def test_국가가_한국인_줄은_판정하지_않는다():
    # 10/03 최현서 「국가 한국(korea, KR) 명시는 검증 생략」
    assert review.한국명시("한국") and review.한국명시("KR") and review.한국명시(" Korea ") and review.한국명시("South Korea")
    assert not review.한국명시("") and not review.한국명시("미국") and not review.한국명시("North Korea")


if __name__ == "__main__":
    from dc_console import use_utf8
    use_utf8()
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
