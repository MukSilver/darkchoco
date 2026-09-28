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


def _cand(island, name, aliases=(), on=True):
    return {"island": island, "rawName": name, "aliases": list(aliases), "on": on, "online": True,
            "order": 0, "links": []}


def test_공식_발표_위치는_명부_이름이나_유출_사이트로만_맞춘다():
    # 유출 사고 DB 「보도된 유출 위치」 (설계서 3.2 「유출 사고 DB를 사건으로 넣는 방법」)
    q, a, f, t = (_cand("RANSOMWARE", "Qilin"), _cand("RANSOMWARE", "Anubis"),
                  _cand("FORUM", "Altenen"), _cand("TELEGRAM", "leakchan"))
    ix = bake.RegistryIndex([q, a, f, t])
    ip = bake.incident_place
    assert ip(ix, "Qilin 유출 사이트(DLS)") is q
    assert ip(ix, "Anubis 다크웹 블로그") is a, "「다크웹」 도 떼고 본다"
    assert ip(ix, "Altenen 포럼 (1차 소스가 venue를 밝힌 사례)") is f, "괄호 안 설명은 떼고 본다"
    assert ip(ix, "텔레그램 t.me/leakchan") is t
    for miss in ["텔레그램", "X (트위터)", "GitHub", "미명시", None, "Qilin, Anubis"]:
        assert ip(ix, miss) is None, f"{miss} 는 짐작하지 않는다"


def test_같은_사고는_조직_이름_전체로만_가른다():
    k = bake.same_org_keys
    assert k({"(주)가나다라"}) & k({"가나다라 주식회사"}), "법인 꼬리를 떼고 같다"
    assert k({"x (ganada.co.kr)"}) & k({"https://www.ganada.co.kr/notice"}), "도메인 이름이 같다"
    assert not (k({"한국abc대학교"}) & k({"abc 코리아"})), "조각이 겹친다고 같은 사고가 아니다"
    assert "INC-241" in bake.SAME_AS_COLLECT, "정본이 사람 눈으로 짝지은 줄"


def test_행위자_정보는_선택지와_모양을_통과한_것만_싣는다():
    c = _cand("ACTOR", "hexb", aliases=["hex_b2", "출처: 포럼 글", "x.y", "hexb", "가나다라샵"])
    c["info"] = {"roles": ["판매자", "미확인", "새 선택지"], "countries": ["미확인", "중국"],
                 "firstSeen": "2026-03-01T00:00:00.000+09:00", "deals": "한국 쇼핑몰 DB\n카드 정보"}
    tok = bake.org_tokens({"가나다라샵"})
    out, dropped = bake.actor_info(c, tok)
    assert out == {"roles": ["판매자"], "countries": ["중국"], "firstSeen": "2026-03-01",
                   "deals": "한국 쇼핑몰 DB · 카드 정보", "otherNames": ["hex_b2"]}, out
    assert dropped == 4, dropped  # 메모 · 점 낀 것 · 자기 이름 · 조직명
    c["info"]["deals"] = "가나다라샵 회원 DB"
    assert "deals" not in bake.actor_info(c, tok)[0], "조직 이름이 든 글은 안 싣는다"
    c["info"]["deals"] = "문의 010-1234-5678"
    assert "deals" not in bake.actor_info(c, tok)[0], "전화 모양은 안 싣는다"


def test_새_칸도_반출_검사가_모양까지_본다():
    base = {"territories": [{"id": "a1", "name": "hexb", "islandId": "ACTOR", "web": "dark"},
                            {"id": "f1", "name": "F", "islandId": "FORUM", "web": "dark"}],
            "events": [{"id": "INC-1", "territoryId": "f1", "postedAt": "2026-01-01", "verdict": "confirmed",
                        "size": "unknown", "repost": False, "excluded": False, "kind": "official",
                        "occurredAt": "2025-12-30", "leakItems": ["이름"], "confirm": "언론 보도",
                        "sourceKind": "보안업체"}],
            "relations": [], "links": []}
    assert bake.check(base) == []
    bad = json_copy(base)
    bad["events"][0]["leakItems"] = ["고객 명단"]
    bad["events"][0]["kind"] = "sale"
    assert len(bake.check(bad)) == 2, bake.check(bad)
    bad = json_copy(base)
    bad["territories"][1]["actor"] = {"roles": ["판매자"]}
    bad["territories"][0]["actor"] = {"deals": "x" * 81, "otherNames": ["a b"], "memo": "?"}
    assert len(bake.check(bad)) == 4, bake.check(bad)


def test_랜섬_유출은_파일_공개가_확인돼야_데이터_게시다():
    ek = bake.event_kind
    assert ek("랜섬웨어 유출", False, False) == "claim", "정본 — 공개가 확인 안 되면 피해 주장"
    assert ek("랜섬웨어 유출", False, False, True) == "data_post"
    assert ek("랜섬웨어 유출", True, False, True) == "claim", "카운트다운 중이면 공개 전"
    assert ek("DB 판매", False, True) == "repost", "재게시가 앞선다"
    assert ek("사기 의심", False, False) is None, "사기 의심은 칩이 없다"


def test_위험도는_악용_가능성과_유출_항목으로_가른다():
    rl = bake.risk_level
    assert rl("가능", []) == "high"
    assert rl("조건부", ["주민번호"]) == "high", "높음 줄을 먼저 본다"
    assert rl(None, ["카드금융"]) == "high"
    assert rl("조건부", ["이메일"]) == "medium"
    assert rl("불가", None) == "low" and rl(None, []) == "low"


def test_손_고침_표는_관문_앞에서_영토_날짜_칩을_정한다():
    import tempfile
    q, f = _cand("RANSOMWARE", "Qilin"), _cand("FORUM", "Altenen")
    ix = bake.RegistryIndex([q, f])
    ov = bake.override_of
    assert ov(None, ix) == {"drop": False}
    assert ov({"drop": True}, ix)["drop"] is True
    got = ov({"kind": "sale", "postedAt": "2026-02-02", "territory": ["FORUM", "Altenen"]}, ix)
    assert got == {"drop": False, "postedAt": "2026-02-02", "kind": "sale", "cand": f}, got
    got = ov({"kind": "없는 칩", "postedAt": "어제", "territory": ["FORUM", "없는 곳"]}, ix)
    assert got == {"drop": False}, "표 밖 값은 버린다"
    assert "kind" not in ov({"kind": "official"}, ix), "수집 DB 줄은 공식 발표가 될 수 없다 (G-8)"
    old = bake.OVERRIDES_FILE
    with tempfile.TemporaryDirectory() as d:
        bake.OVERRIDES_FILE = Path(d) / "overrides.json"
        assert bake.load_overrides(lambda m: None) == {}, "파일이 없으면 빈 표"
        bake.OVERRIDES_FILE.write_text('{"events": {"LEAK-1": {"drop": true}}}', encoding="utf-8")
        assert bake.load_overrides(lambda m: None) == {"LEAK-1": {"drop": True}}
    bake.OVERRIDES_FILE = old


def test_연결된_사건은_목록_안_사건끼리만():
    base = {"territories": [{"id": "f1", "name": "F", "islandId": "FORUM", "web": "dark"}],
            "events": [{"id": "LEAK-1", "territoryId": "f1", "postedAt": "2026-01-01", "verdict": "high",
                        "size": "unknown", "repost": False, "excluded": False, "risk": "low", "linked": ["LEAK-2"]},
                       {"id": "LEAK-2", "territoryId": "f1", "postedAt": "2026-01-02", "verdict": "high",
                        "size": "unknown", "repost": False, "excluded": False, "risk": "high", "scam": True}],
            "relations": [], "links": []}
    assert bake.check(base) == []
    base["events"][0]["linked"] = ["LEAK-9", "LEAK-1"]
    base["events"][1]["risk"] = "위험"
    assert len(bake.check(base)) == 2, bake.check(base)


def test_텔레그램_채널은_게시_플랫폼_원문_URL_핸들_순서로_찾는다():
    # 설계서 3.3 「텔레그램 재유포 사건의 채널 정하는 방법」, 2026-09-28 G-7
    a, b, c = _cand("TELEGRAM", "chanA"), _cand("TELEGRAM", "chanB"), _cand("TELEGRAM", "chanC")
    f = _cand("FORUM", "Darkforums")
    ix = bake.RegistryIndex([a, b, c, f])
    read = lambda v: v  # noqa: E731 — 시험 줄은 노션 prop 대신 값 그대로다

    def row(plat=None, url=None, handle=None):
        return {"게시 플랫폼": plat, "원문 URL": url, "게시자 핸들": handle}

    ch = bake.tg_channel
    assert ch(ix, read, row("https://t.me/chanA", "https://t.me/chanB/12", "chanC")) is a, \
        "게시 플랫폼이 먼저 — 지금 붙은 사건은 그대로"
    assert ch(ix, read, row("darkforums.st", "https://t.me/s/chanB/12", "chanC")) is b
    assert ch(ix, read, row("darkforums.st", "https://darkforums.st/Thread-x", "chanC")) is c
    assert ch(ix, read, row(None, "https://t.me/unknownchan/3", "chanC")) is c, \
        "텔레그램 DB 에 없는 채널이면 다음 단서"
    assert ch(ix, read, row("darkforums.st", "https://kit.me/chanB", "Darkforums")) is None, \
        "t.me 로 끝나는 다른 도메인 · 포럼 이름 핸들은 짐작하지 않는다"


def test_원문_URL_은_t_me_채널_이름만_돌려준다():
    read = lambda v: v  # noqa: E731
    tme = bake.col_tme
    assert tme(read, {"원문 URL": "https://t.me/leakchan/77"}, "원문 URL") == "leakchan"
    for url in ["https://darkforums.st/Thread-x", "https://www.ganada.co.kr/", "https://t.me/+AbCdEf",
                "https://t.me/c/1234567/8", "https://kit.me/leakchan", None]:
        assert tme(read, {"원문 URL": url}, "원문 URL") is None, url
    for reader in (lambda: bake.col(read, {}, "원문 URL"), lambda: bake.col_match(read, {}, "원문 URL"),
                   lambda: bake.col_tme(read, {}, "게시 플랫폼")):
        try:
            reader()
        except SystemExit:
            continue
        raise AssertionError("원문 URL 은 col_tme() 로만 읽는다")


def test_공식_발표는_외부_확인이_조직_규제기관_언론인_사고만():
    # 2026-09-28 최현서 G-8. 가르는 것은 「외부 확인」 이지 「출처」 가 아니다
    ur = bake.unofficial_reason
    for ok in ["조직 공식 발표", "규제기관 확정", "언론 보도"]:
        assert ur(ok) is None, ok
    assert ur("게시글만") == ur("연구자 발견") == "외부 확인이 게시글만 · 연구자 발견"
    assert ur(None) == ur("새 선택지") == "외부 확인이 비었거나 선택지 밖", "빈칸은 짐작하지 않는다"
    base = {"territories": [{"id": "f1", "name": "F", "islandId": "FORUM", "web": "dark"}],
            "events": [{"id": "INC-1", "territoryId": "f1", "postedAt": "2026-01-01", "verdict": "confirmed",
                        "size": "unknown", "repost": False, "excluded": False, "kind": "official",
                        "confirm": "규제기관 확정", "sourceKind": "언론 보도"}],
            "relations": [], "links": []}
    assert bake.check(base) == []
    for bad_confirm in ["게시글만", "연구자 발견", None]:
        bad = json_copy(base)
        if bad_confirm:
            bad["events"][0]["confirm"] = bad_confirm
        else:
            del bad["events"][0]["confirm"]
        assert len(bake.check(bad)) == 1, (bad_confirm, bake.check(bad))


def test_공식_발표_여부는_특정된_짝만_붙이고_일수는_한국_날짜로_센다():
    # 2026-09-28 최현서 G-9. 묶음 사고(INC-242 · 243)는 추론이라 표에 없다
    assert bake.SAME_AS_COLLECT["INC-241"] == ["LEAK-170", "LEAK-183"]
    assert "INC-242" not in bake.SAME_AS_COLLECT and "INC-243" not in bake.SAME_AS_COLLECT
    n = bake.incident_note
    assert n("INC-1", "언론 보도", "2026-01-05", "2026-01-04") == \
        {"id": "INC-1", "confirm": "언론 보도", "announcedAt": "2026-01-05", "gapDays": -1}
    # 시각이 붙은 값만 한국 날짜로 옮긴다 — 07-03 20:00 UTC 는 한국 07-04 새벽이다
    assert n("INC-1", "언론 보도", "2026-07-07", "2026-07-03T20:00:00.000Z")["gapDays"] == -3
    assert n("INC-1", "언론 보도", "2026-07-07T23:30:00.000+00:00", "2026-07-08")["gapDays"] == 0
    assert n("INC-1", "언론 보도", None, "2026-01-04") == {"id": "INC-1", "confirm": "언론 보도"}, \
        "공표 시점이 비면 공표일도 일수도 없다"
    assert "gapDays" not in n("INC-1", "언론 보도", "2026-01-05", None), "게시일을 대신 넣은 사건은 일수를 안 둔다"


def test_공식_발표_여부도_반출_검사가_모양과_짝을_본다():
    inc = {"id": "INC-241", "confirm": "언론 보도", "announcedAt": "2026-01-05"}
    base = {"territories": [{"id": "f1", "name": "F", "islandId": "FORUM", "web": "dark"}],
            "events": [{"id": "LEAK-170", "territoryId": "f1", "postedAt": "2026-01-04", "verdict": "high",
                        "size": "unknown", "repost": False, "excluded": False, "kind": "sale",
                        "incident": {**inc, "gapDays": -1}},
                       {"id": "LEAK-183", "territoryId": "f1", "postedAt": "2026-01-14", "verdict": "high",
                        "size": "unknown", "repost": False, "excluded": False,
                        "incident": {**inc, "gapDays": 9}}],
            "relations": [], "links": []}
    assert bake.check(base) == [], "같은 사고가 두 게시에 붙으면 일수만 다르다"
    breaks = [
        lambda d: d["events"][0]["incident"].update(memo="?"),
        lambda d: d["events"][0]["incident"].update(id="INC-x"),
        lambda d: d["events"][0]["incident"].update(confirm="게시글만"),
        lambda d: d["events"][0]["incident"].update(announcedAt="2026-01-05T00:00"),
        lambda d: d["events"][0]["incident"].update(gapDays=True),
        lambda d: d["events"][0]["incident"].pop("announcedAt"),        # 일수만 남는다 (+ 공표일 불일치)
        lambda d: d["events"][0].update(kind="official", confirm="언론 보도"),
        lambda d: d["events"][1]["incident"].update(confirm="규제기관 확정"),  # 같은 사고인데 값이 다르다
        # 게시에 붙은 사고가 따로 된 사건으로도 있다 — 한 사고를 두 번 센다
        lambda d: d["events"].append({"id": "INC-241", "territoryId": "f1", "postedAt": "2026-01-05",
                                      "verdict": "confirmed", "size": "unknown", "repost": False,
                                      "excluded": False, "kind": "official", "confirm": "언론 보도"}),
    ]
    for i, br in enumerate(breaks):
        bad = json_copy(base)
        br(bad)
        assert bake.check(bad), f"{i}번 깨뜨림을 못 잡았다"


def json_copy(x):
    import json
    return json.loads(json.dumps(x))


if __name__ == "__main__":
    tests = [(k, v) for k, v in dict(globals()).items() if k.startswith("test_") and callable(v)]
    for name, fn in tests:
        fn()
        print("ok", name)
    print(f"bake_test: {len(tests)}개 통과")
