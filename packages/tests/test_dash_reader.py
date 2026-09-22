"""대시보드가 노션 속성을 값으로 옮기는 자리 시험. **노션에 안 붙습니다.**

    python -m pytest packages/tests/test_dash_reader.py

2026-09-22 에 칸 목록을 `apps/dash/dbs.json` 한 장으로 뺐습니다. 전에는 같은
목록이 `build.py` 와 `deploy/worker.js` 두 곳에 글자로 박혀 있어서, 한쪽을
고치고 다른 쪽을 잊으면 로컬과 배포가 다른 화면이 됐습니다.

**여기서 지키는 것은 셋입니다.**

    종류마다 무엇을 내나        relation 과 people 이 특히 중요합니다
    접기가 실명을 실제로 접나
    레지스트리가 코드와 안 어긋나나
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packages"))
sys.path.insert(0, str(ROOT / "apps" / "dash"))

import reader  # noqa: E402


def _속성(종류, 값):
    return {"type": 종류, 종류: 값}


# ── 종류마다 무엇을 내나 ────────────────────────────────

def test_글자_종류():
    assert reader.값(_속성("title", [{"plain_text": " 어떤 회사 "}])) == "어떤 회사"
    assert reader.값(_속성("rich_text", [{"plain_text": "a"}, {"plain_text": "b"}])) == "ab"
    assert reader.값(_속성("select", {"name": "랜섬웨어"})) == "랜섬웨어"
    assert reader.값(_속성("status", {"name": "검증 완료"})) == "검증 완료"
    assert reader.값(_속성("url", "http://example.invalid")) == "http://example.invalid"


def test_목록과_숫자와_날짜():
    v = _속성("multi_select", [{"name": "이름"}, {"name": "전화"}])
    assert reader.값(v) == ["이름", "전화"]
    assert reader.값(_속성("date", {"start": "2026-09-22T10:00:00+09:00"})).startswith("2026-09-22")
    assert reader.값(_속성("checkbox", True)) is True
    assert reader.값(_속성("number", 12)) == 12


def test_사건_번호():
    assert reader.값(_속성("unique_id", {"prefix": "LEAK", "number": 197})) == "LEAK-197"
    # 번호가 없으면 빈칸이다. 「LEAK-None」 을 만들지 않는다
    assert reader.값(_속성("unique_id", {"prefix": "LEAK", "number": None})) == ""


def test_relation_은_개수만_낸다():
    """**page id 를 그대로 내면 레지스트리 밖 DB 의 줄을 짚는 열쇠가 나갑니다.**

    검증 DB 의 「수집 줄」 이 여기 걸립니다.
    """
    v = _속성("relation", [{"id": "aaaa-1111"}, {"id": "bbbb-2222"}])
    assert reader.값(v) == 2
    난것 = str(reader.값(v))
    assert "aaaa" not in 난것 and "bbbb" not in 난것


def test_people_은_찼는지만_낸다():
    """**실명이 들어가는 자리입니다.**"""
    v = _속성("people", [{"id": "u1", "name": "어떤사람"}])
    assert reader.값(v) == "기입됨"
    assert "어떤사람" not in str(reader.값(v))
    assert reader.값(_속성("people", [])) == "미기입"
    assert reader.값(_속성("created_by", {"id": "u1", "name": "어떤사람"})) == "기입됨"


def test_한_겹_벗겨서_본다():
    assert reader.값({"type": "formula", "formula": {"type": "string", "string": "ㄱ"}}) == "ㄱ"
    assert reader.값({"type": "rollup", "rollup": {"type": "number", "number": 3}}) == 3
    안 = {"type": "rollup", "rollup": {"type": "array",
                                      "array": [_속성("select", {"name": "ㄴ"})]}}
    assert reader.값(안) == ["ㄴ"]


def test_모르는_종류를_지어내지_않는다():
    assert reader.값({"type": "언젠가생길것", "언젠가생길것": {"뭔가": 1}}) == ""
    assert reader.값(None) == ""
    assert reader.값({}) == ""


# ── 접기 ────────────────────────────────────────────────

def test_사람자동_접기():
    """선택지 아홉 중 일곱이 팀원 실명이다. **이름이 안 나가야 한다.**"""
    assert reader.접개["사람자동"]("자동") == "자동"
    assert reader.접개["사람자동"]("어떤팀원") == "사람"
    assert reader.접개["사람자동"]("미기입") == "미기입"
    assert reader.접개["사람자동"]("") == "미기입"
    assert "어떤팀원" not in reader.접개["사람자동"]("어떤팀원")


def test_있없_접기():
    assert reader.접개["있없"]("어떤검증자") == "기입됨"
    assert reader.접개["있없"]("미기입") == "미기입"
    assert reader.접개["있없"]("") == "미기입"


def test_첫줄_접기():
    assert reader.접개["첫줄"]("첫 줄\n둘째 줄") == "첫 줄"
    assert len(reader.접개["첫줄"]("가" * 500)) == 120


# ── 레지스트리 ──────────────────────────────────────────

def test_줄_은_레지스트리가_적은_대로_옮긴다():
    페이지 = {"id": "p-1", "properties": {
        "자료 제목": _속성("title", [{"plain_text": "어떤 회사"}]),
        "수집자": _속성("select", {"name": "어떤팀원"}),
        "게시 시각": _속성("date", {"start": "2026-09-22T10:00:00+09:00"}),
        "안 적은 칸": _속성("rich_text", [{"plain_text": "나가면 안 되는 값"}]),
    }}
    칸들 = [
        {"노션": "자료 제목", "낼": "제목"},
        {"노션": "수집자", "낼": "수집자", "접기": "사람자동"},
        {"노션": "게시 시각", "낼": "게시", "날짜만": True},
    ]
    got = reader.줄(페이지, 칸들)
    assert got == {"id": "p-1", "제목": "어떤 회사", "수집자": "사람", "게시": "2026-09-22"}
    # **레지스트리에 안 적은 칸은 아예 안 나간다**
    assert "나가면 안 되는 값" not in str(got)


def test_모르는_접기_갈래는_조용히_지나가지_않는다():
    import pytest
    with pytest.raises(ValueError):
        reader.줄({"id": "x", "properties": {}}, [{"노션": "ㄱ", "낼": "ㄱ", "접기": "없는것"}])


def test_안그림_칸은_열에서_빠진다():
    칸들 = [{"노션": "ㄱ", "낼": "ㄱ"}, {"노션": "소스", "낼": "소스", "안그림": True}]
    assert reader.열이름들(칸들) == ["ㄱ"]


def test_레지스트리의_수집_id_가_push_와_같다():
    """**어긋나면 대시보드가 엉뚱한 DB 를 봅니다.**

    `push.py` 의 상수는 세 트랙이 같이 쓰는 자리라 옮기지 않기로 했습니다
    (DEV.md 0-0). 그래서 같은 값이 두 곳에 있고, 여기서 맞춰 봅니다.
    """
    from hub.events.push import 수집DB
    assert reader.DB하나("수집")["id"] == 수집DB


def test_레지스트리에_없는_DB_를_물으면_있는것을_알려준다():
    import pytest
    with pytest.raises(KeyError) as e:
        reader.DB하나("없는DB")
    assert "수집" in str(e.value)


def test_수집_레지스트리가_열세_칸을_적었다():
    """2026-09-22 에 최현서가 고른 열셋이다. 늘리려면 반출 경계를 먼저 본다."""
    칸들 = reader.DB하나("수집")["칸"]
    assert [c["낼"] for c in 칸들] == [
        "번호", "제목", "검토", "상태", "대상", "업종", "국가", "항목",
        "자리", "핸들", "게시", "수집일", "수집자", "소스"]
    # 소스는 거르개만 쓴다. 열로는 안 그린다
    assert reader.열이름들(칸들)[-1] == "수집자"


def test_뺀_칸이_레지스트리에_안_들어와_있다():
    """**「한국 관련 근거」 는 사람이 쓴 27줄 중 여덟에 이메일이 값째로 있었다.**"""
    적힌것 = {c["노션"] for c in reader.DB하나("수집")["칸"]}
    for 안될것 in ("한국 관련 근거", "원문 URL", "관측자", "본문"):
        assert 안될것 not in 적힌것
