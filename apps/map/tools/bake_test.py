"""tools/bake.py 의 순수 도우미 시험. 노션을 부르지 않는다.

    python tools/bake_test.py

`npm test` 가 부른다. pytest 가 아니라 파일을 그대로 돌린다 — 맨 아래 실행부가
시험 함수를 모두 부른다. 실패하면 첫 실패에서 멈추고 0 이 아닌 값으로 끝난다.

머지 전 검토(2026-09-25)에서 고친 것들이 되돌아가지 않게 지킨다.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
_spec = importlib.util.spec_from_file_location("bake", Path(__file__).with_name("bake.py"))
bake = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bake)


def test_랜섬_규모_월평균은_여섯_달_건수로_돌려_읽는다():
    # 본진 PR #45 뒤 두 꼴이 섞인다 (인계 지도_랜섬규모단위.md)
    old = bake.registry_size("RANSOMWARE", "피해 기업 60 (2026-09-24 기준)")
    new = bake.registry_size("RANSOMWARE", "피해 월평균 10.0건 (최근 180일) (2026-09-25 기준)")
    assert old == {"raw": 60.0} and new == {"raw": 60.0}, (old, new)
    assert bake.registry_size("RANSOMWARE", "피해 월평균 0.5건 (최근 180일) (2026-09-25 기준)") == {"raw": 3.0}
    assert bake.registry_size("RANSOMWARE", "피해 월평균 1,234.5건 (최근 180일)") == {"raw": 7407.0}
    assert bake.registry_size("RANSOMWARE", "피해 월평균 2건 (최근 90일)") == {"raw": 6.0}, "기간이 달라도 일수로 돌린다"
    assert bake.registry_size("RANSOMWARE", "피해 월평균 0.0건 (최근 180일)") == {}, "0 은 규모 없음"
    # 둘째 줄의 사람 메모는 안 읽는다
    two = "피해 월평균 5.0건 (최근 180일) (2026-09-25 기준)\n사람 메모 — 2026-05 부터 늘어남"
    assert bake.registry_size("RANSOMWARE", two) == {"raw": 30.0}
    # 다른 섬은 그대로 첫 숫자다
    assert bake.registry_size("TELEGRAM", "구독자 12,300명") == {"raw": 12300.0}


def test_주장_규모는_레코드_수를_먼저_가장_큰_것으로_읽는다():
    cs = bake.claim_size
    assert cs("5천만 건") == (5000.0, "만")
    assert cs("1억 2천만") == (1.2, "억")
    assert cs("20 000 000 rows") == (2000.0, "만")
    assert cs("1.2M records") == (120.0, "만")
    assert cs("관리자 3명 포함 120만 건") == (120.0, "만"), "여럿이면 가장 큰 것"
    assert cs("파일 5개, 12GB") == (12.0, "GB"), "개는 레코드 수가 아니다"
    assert cs("255GB 유출") == (255.0, "GB")
    assert cs("2026년 자료") is None and cs(None) is None


def test_연결된_곳은_괄호_안에서_자르지_않는다():
    sl = bake.split_links
    assert sl("앞선곳:A (원본, 2022~2023), 텔레그램:X") == ["앞선곳:A (원본, 2022~2023)", "텔레그램:X"]
    assert sl("포럼 DB: A · 텔레그램 DB: X · 랜섬웨어 DB: Y") == ["포럼 DB: A", "텔레그램 DB: X", "랜섬웨어 DB: Y"]
    assert sl("앞선곳:A (원본\n텔레그램:B") == ["앞선곳:A (원본", "텔레그램:B"], "안 닫힌 괄호가 다음 줄을 삼키지 않는다"
    assert sl(None) == []


def test_조직명_대조는_꾸민_이름과_도메인을_잡고_가해_URL_은_남긴다():
    tok = bake.org_tokens({"Acme Co., Ltd.", "X (acme.co.kr)", "Alpha / Beta", "www.ganada.co.kr",
                           "https://shop.lamaba.com", "가나", "SK"})
    hit = bake.mentions_org
    for item in ["포럼: F Acme DB", "acme.co.kr 재게시", "Beta 유출", "ganada 회원", "lamaba 판매", "가나 회원", "SK 텔레콤"]:
        assert hit(item, tok), item
    for item in ["포럼: XForum https://xforum.onion 이전", "SKY forum", "Darkforums 제휴", "Ltd 공지"]:
        assert not hit(item, tok), item


def test_핸들_다듬기는_반출_검사에_걸릴_모양을_뺀다():
    ch = bake.clean_handle
    assert ch("@abc") == "abc"
    for bad in ["a.bcd", "x@y", "010-1234-5678", "user_010_1234_5678", "joe(at)x", "미기입", None]:
        assert ch(bad) is None, bad


def test_클론_원문은_다른_클론에_안_붙는다():
    own = {"rawName": "X", "links": ["BreachForums (breached.su) 후속", "BreachForums (bf.st) 제휴"], "aliases": []}
    other = {"rawName": "BreachForums (bf.st)", "aliases": ["BreachForums"]}
    note, _ = bake.relation_note(own, other, set(), frozenset({"breachforums"}))
    assert note == "BreachForums (bf.st) 제휴", note


def test_값_훑기는_끊어_적은_전화와_주민번호를_잡는다():
    bad: list[str] = []
    bake.scan_strings({"a": "010-1234-5678", "b": "900101-1234567", "c": "name [at] host.io",
                       "postedAt": "2026-05-14T06:58:00.000+09:00"}, "m", bad)
    # a · b · c 세 칸이 다 걸리고, 게시 시각은 건너뛴다 (c 는 도메인 모양으로도 걸린다)
    assert {x.split(":")[0] for x in bad} == {"m.a", "m.b", "m.c"}, bad


if __name__ == "__main__":
    tests = [(k, v) for k, v in dict(globals()).items() if k.startswith("test_") and callable(v)]
    for name, fn in tests:
        fn()
        print("ok", name)
    print(f"bake_test: {len(tests)}개 통과")
