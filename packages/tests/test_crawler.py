"""명부 조사기 셋을 가짜 응답으로 확인합니다.

    python packages/tests/test_crawler.py

밖에 요청을 보내지 않습니다. 응답을 가로채 미리 만든 것을 돌려줍니다.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages"))
sys.path.insert(0, str(ROOT))

from dc_console import use_utf8  # noqa: E402

use_utf8()

from hub.places.place import Place, 규모합치기, 기계가_쓴_줄  # noqa: E402
from hub.places.probe import forum, ransom, telegram  # noqa: E402


class _가짜오프너:
    """검사에서는 밖으로 안 나갑니다. _받기 를 갈아 끼우니 쓰이지 않습니다."""

    def open(self, req, timeout=0):
        raise AssertionError("검사가 실제로 밖에 나가려 했습니다")


def _안나가게(mod):
    """조사기의 오프너를 막습니다. Tor 설정에 검사가 흔들리지 않게 합니다."""
    옛 = mod.오프너
    mod.오프너 = lambda 프록시=None, 갈래="": _가짜오프너()
    return 옛


# 이 파일의 검사는 밖에 안 나갑니다. _받기 를 갈아 끼워 응답을 넣습니다.
# 오프너를 막아 두면 Tor 를 켰든 껐든 결과가 같습니다. 검사가 환경에
# 따라 달라지면 검사가 아닙니다.
for _m in (telegram, ransom, forum):
    _m.오프너 = lambda 프록시=None, 갈래="": _가짜오프너()

사람글 = ("멤버 수·게시물 수 못 셈. 하루 새 글 수도 못 셈 — 2026-08-01 접속 시 "
        "첫 화면 최신 글 목록이 '방금 전'·'1분 전'이었습니다")


# ── 규모 칸 ─────────────────────────────────────────────────────────
def test_빈칸이면_그냥_쓴다():
    assert 규모합치기("", "구독자 8,145 (2026-08-28 기준)") == "구독자 8,145 (2026-08-28 기준)"


def test_사람_글을_안_지운다():
    r = 규모합치기(사람글, "구독자 8,145 (2026-08-28 기준)")
    assert 사람글 in r, "사람이 쓴 조사 결과가 사라졌다"
    assert "구독자 8,145" in r


def test_옛_기계_줄만_갈아_끼운다():
    r = 규모합치기("구독자 7,900 (2026-08-20 기준)\n" + 사람글,
                 "구독자 8,145 (2026-08-28 기준)")
    assert "7,900" not in r, "옛 기계 줄이 남았다"
    assert "8,145" in r
    assert 사람글 in r, "사람 글이 사라졌다"
    assert len(r.splitlines()) == 2, r


def test_숫자만_있는_옛_줄을_갈아_끼운다():
    """이수빈 님이 넣은 646 같은 값. 새 줄이 같은 것을 더 자세히 말한다."""
    r = 규모합치기("646", "구독자 647 (2026-08-28 기준)")
    assert r == "구독자 647 (2026-08-28 기준)", r


def test_사람이_문장으로_쓴_것은_숫자가_있어도_남긴다():
    옛 = "구독자 1,440명 (2026.08.04 13:32 GMT+9 기준)"
    r = 규모합치기(옛, "구독자 534 (2026-08-28 기준)")
    assert 옛 in r, "사람이 적은 시각 정보가 사라졌다"


def test_같은_줄은_두_번_안_넣는다():
    줄 = "구독자 8,145 (2026-08-28 기준)"
    assert 규모합치기(줄, 줄) == 줄


def test_사람이_쓴_옛_형식은_기계_줄이_아니다():
    """이것을 기계 줄로 보면 사람이 적은 시각 정보가 사라진다."""
    assert not 기계가_쓴_줄("구독자 1,440명 (2026.08.04 13:32 GMT+9 기준)")
    assert 기계가_쓴_줄("8145"), "숫자만 있는 줄은 갈아 끼운다"
    assert 기계가_쓴_줄(" 2,487 "), "쉼표가 있어도 숫자만이면 갈아 끼운다"
    assert not 기계가_쓴_줄(사람글)
    assert 기계가_쓴_줄("구독자 8,145 (2026-08-28 기준)")
    assert 기계가_쓴_줄("회원 349,000 · 게시물 821,000 (2026-08-28 기준)")


# ── 노션에 넣는 값 ──────────────────────────────────────────────────
def test_노션_칸을_안_늘린다():
    """다크웹 DB 스키마가 RAG 의 근간이라 기존 칸만 써야 한다.

    옛날에는 칸 이름을 손으로 적어 두고 봤는데, 그러면 노션에 정말
    있는지는 아무도 안 본다. 실제 스키마를 찍어 두고 그것과 댄다.
    노션스키마.json 은 2026-08-28 에 API 로 받은 것이다.
    """
    스키마 = json.loads((HERE / "노션스키마.json").read_text(encoding="utf-8"))
    for 갈래 in ("forum", "telegram", "ransom"):
        있는칸 = set(스키마[갈래]["칸"])
        p = Place(갈래=갈래, 이름="x", 상태="online", 두드림=True,
                  구독자수=10, 회원수=20, 게시물수=30, 피해기업수=40,
                  주소="https://x", 어니언="http://y.onion",
                  형식="RaaS", 종류="group", 최근활동="2026-08-28T00:00:00",
                  언어="영어", 들어가는법="열림", 이전주소="https://old",
                  이전이름="별칭", 어떤곳="설명", 가입필요=False,
                  피해대상="제조 3", 한국유출="한국 피해 1건",
                  연락수단="메일", 연결된곳="포럼 DB: X",
                  출처=["ransomware.live"])
        칸 = set(p.노션값())
        assert 칸 <= 있는칸, f"{갈래}: 노션에 없는 칸을 쓴다 — {칸 - 있는칸}"


def test_기계칸이_세_갈래_어딘가에는_있다():
    """기계칸 에 적어 두고 어느 DB 에도 없는 칸이면 영영 안 쓰인다."""
    스키마 = json.loads((HERE / "노션스키마.json").read_text(encoding="utf-8"))
    어딘가 = set().union(*(set(v["칸"]) for v in 스키마.values()))
    from hub.places.place import 기계칸
    없는것 = 기계칸 - 어딘가
    assert not 없는것, f"어느 DB 에도 없는 칸: {없는것}"


def test_보내는_선택지_값이_실제로_있다():
    """선택지에 없는 값을 보내면 노션이 400 을 낸다.

    포럼 DB 「상태」 에는 압수됨 이 없다. 랜섬웨어 DB 에만 있다.
    """
    스키마 = json.loads((HERE / "노션스키마.json").read_text(encoding="utf-8"))
    assert "압수됨" in 스키마["ransom"]["선택지"]["상태"]
    assert "압수됨" not in 스키마["forum"]["선택지"]["상태"]
    assert "압수됨" not in 스키마["telegram"]["선택지"]["상태"]

    # 조사기가 만드는 상태가 그 갈래에서 쓸 수 있는 값인지 본다.
    for 갈래, 값들 in (("forum", {"online", "offline", "미확인"}),
                     ("telegram", {"online", "offline", "미확인"}),
                     ("ransom", {"online", "offline", "미확인", "압수됨"})):
        있는것 = set(스키마[갈래]["선택지"]["상태"])
        assert 값들 <= 있는것, f"{갈래}: 못 쓰는 상태 {값들 - 있는것}"

    # 「조사 단계」 에 확인만 함 이 있어야 한다.
    for 갈래 in ("forum", "telegram", "ransom"):
        assert "확인만 함" in 스키마[갈래]["선택지"]["조사 단계"]


def test_못_봤으면_미확인과_확인일만_남긴다():
    """언제 봤는데 못 봤는지가 그 자체로 정보다. 규모는 안 건드린다."""
    p = Place(갈래="forum", 이름="x", 못본이유="봤는데 수가 없습니다", 두드림=True)
    v = p.노션값("사람이 쓴 조사 결과")
    assert v == {"확인일": p.확인일[:10], "상태": "미확인"}, v
    assert "규모" not in v, "못 봤는데 규모를 건드린다"


def test_주소가_틀려도_미확인은_남긴다():
    """online 이라고 적혀 있는 것이 근거 없는 값이다. 주소와 규모는 안 건드린다."""
    p = Place(갈래="telegram", 이름="x", 주소="https://nulledbb.com/discord",
              못본이유="텔레그램 주소가 아닙니다", 주소이상=True, 두드림=True)
    v = p.노션값("사람 글")
    assert v == {"확인일": p.확인일[:10], "상태": "미확인"}, v
    assert "주소" not in v and "규모" not in v, v


def test_갈래별_칸이_섞이지_않는다():
    t = Place(갈래="telegram", 이름="x", 상태="online", 구독자수=5,
              형식="RaaS", 어니언="http://a.onion")
    assert "형식" not in t.노션값(), "텔레그램에 랜섬 칸이 들어갔다"
    assert "어니언 주소" not in t.노션값(), "텔레그램에 포럼 칸이 들어갔다"


def test_숫자는_따로_돌려준다():
    """노션에는 한 줄만, 숫자는 우리 쪽 시계열로."""
    p = Place(갈래="forum", 이름="x", 상태="online", 회원수=349000, 게시물수=821000)
    assert p.숫자들() == {"회원수": 349000, "게시물수": 821000}
    assert "회원 349,000 · 게시물 821,000" in p.노션값()["규모"]


# ── 조사기 ─────────────────────────────────────────────────────────
def test_미리보기에서는_밖에_안_나간다():
    assert list(telegram.조사(["x"], dry=True)) == []
    assert list(ransom.조사(dry=True)) == []
    assert list(forum.조사([{"주소": "https://x"}], dry=True)) == []


def test_텔레그램_응답을_읽는다():
    본문 = ('<div class="tgme_channel_info_header_title">테스트 채널</div>'
          '<div class="tgme_header_counter"> 8 145 subscribers</div>'
          '<div class="tgme_widget_message">'
          '<time datetime="2026-08-27T10:00:00+00:00"></time></div>')
    옛 = telegram._받기
    telegram._받기 = lambda url, m, op=None: (200, 본문)
    try:
        p = telegram.한곳("@testchan", [0.0])
    finally:
        telegram._받기 = 옛
    assert p.상태 == "online", p.상태
    assert p.구독자수 == 8145, p.구독자수
    assert p.최근활동.startswith("2026-08-27"), p.최근활동
    assert p.봤나(), p.못본이유
    assert p.노션값()["규모"] == f"구독자 8,145 ({p.확인일[:10]} 기준)"


def test_텔레그램_404_는_offline_이고_이유가_남는다():
    옛 = telegram._받기
    telegram._받기 = lambda url, m, op=None: (404, "")
    try:
        p = telegram.한곳("@없는채널", [0.0])
    finally:
        telegram._받기 = 옛
    assert p.상태 == "offline"
    assert p.못본이유, "왜 못 봤는지가 비어 있다"


def test_텔레그램_수를_못_보면_미확인이다():
    """없음이 아니라 미확인이다. 그 둘은 다르다."""
    옛 = telegram._받기
    telegram._받기 = lambda url, m, op=None: (200, "<html>아무것도 없음</html>")
    try:
        p = telegram.한곳("@조용한채널", [0.0])
    finally:
        telegram._받기 = 옛
    assert p.상태 == "미확인", p.상태
    assert "실계정" in p.못본이유, p.못본이유
    v = p.노션값("사람 글")
    assert v.get("상태") == "미확인" and "규모" not in v, v


def test_랜섬_그룹_목록을_읽는다():
    """실제 /groups 응답 꼴입니다. victims·type·lastseen 은 없습니다.

    2026-08-28 에 392개를 받아 칸을 확인했습니다. 예전 검사는 있지도 않은
    칸을 쓰는 가짜를 넣어서, 조사기가 헛돌고 있는 것을 못 잡았습니다.
    """
    그룹 = [
        {"name": "LockBit3", "altname": "Bolt",
         "description": "DLS 를 운영합니다",
         "url": "https://www.ransomware.live/group/lockbit3",
         "locations": [
             {"available": False, "fqdn": "old.onion",
              "slug": "http://old.onion", "title": "404", "type": "DLS"},
             {"available": True, "fqdn": "lb.onion",
              "slug": "http://lb.onion", "title": "LockBit", "type": "DLS"}]},
        {"name": "SomeMarket", "locations": [
            {"available": False, "slug": "http://m.onion", "type": "market"}]},
        {"noname": 1},
    ]
    달 = [
        {"group": "LockBit3", "country": "KR", "activity": "Manufacturing",
         "attackdate": "2026-08-20T01:00:00+00:00"},
        {"group": "LockBit3", "country": "US", "activity": "Manufacturing",
         "attackdate": "2026-08-25T01:00:00+00:00"},
        {"group": "LockBit3", "country": "DE", "activity": "Financial Services",
         "attackdate": "2026-07-01T01:00:00+00:00"},
    ]
    옛, 옛오프너 = ransom._받기, _안나가게(ransom)
    ransom._받기 = lambda url, m, op=None: 그룹 if url.endswith("/groups") else 달
    try:
        out = list(ransom.조사(개월수=1))
    finally:
        ransom._받기, ransom.오프너 = 옛, 옛오프너

    assert len(out) == 2, [p.이름 for p in out]
    a, b = out
    # 미러가 여럿이면 하나라도 살아 있으면 online 입니다.
    assert a.이름 == "LockBit3" and a.상태 == "online"
    assert a.주소 == "http://lb.onion", a.주소       # 살아있는 쪽이 대표
    assert a.이전주소 == "http://old.onion"          # 나머지는 이전 주소로
    assert a.형식 == "DLS" and a.종류 == "group"
    assert a.이전이름 == "Bolt"
    assert a.어떤곳 == "DLS 를 운영합니다"

    # 피해 건수는 /groups 에 없습니다. 월별 목록을 받아 셉니다.
    assert a.피해기업수 == 3, a.피해기업수
    assert a.최근활동 == "2026-08-25", a.최근활동
    assert "Manufacturing 2" in a.피해대상, a.피해대상
    assert "한국 피해 1건" in a.한국유출, a.한국유출

    assert b.상태 == "offline" and b.형식 == "포럼·마켓"

    값 = a.노션값()
    assert "피해 기업 3" in 값["규모"]
    assert 값["출처"] == ["ransomware.live"]


def test_랜섬_한국_피해는_건수만_적는다():
    """SECURITY.md — 기업 이름은 안 적습니다."""
    그룹 = [{"name": "G", "locations": [{"available": True, "slug": "http://g.onion"}]}]
    달 = [{"group": "G", "country": "KR", "victim": "어느회사",
           "domain": "example.co.kr", "activity": "Manufacturing",
           "attackdate": "2026-08-20T01:00:00+00:00"}]
    옛, 옛오프너 = ransom._받기, _안나가게(ransom)
    ransom._받기 = lambda url, m, op=None: 그룹 if url.endswith("/groups") else 달
    try:
        p = next(iter(ransom.조사(개월수=1)))
    finally:
        ransom._받기, ransom.오프너 = 옛, 옛오프너
    글 = str(p.노션값())
    assert "어느회사" not in 글 and "example.co.kr" not in 글, 글
    assert "한국 피해 1건" in p.한국유출


def test_랜섬_한_달을_못_받아도_나머지를_버리지_않는다():
    """못본이유에 넣으면 노션값() 이 알아낸 것을 전부 버립니다."""
    그룹 = [{"name": "G", "altname": "별칭",
            "locations": [{"available": True, "slug": "http://g.onion"}]}]
    옛, 옛오프너 = ransom._받기, _안나가게(ransom)
    def 받기(url, m, op=None):
        if url.endswith("/groups"):
            return 그룹
        raise OSError("한 달치 못 받음")
    ransom._받기 = 받기
    try:
        p = next(iter(ransom.조사(개월수=1)))
    finally:
        ransom._받기, ransom.오프너 = 옛, 옛오프너
    assert p.봤나(), p.못본이유
    assert "못 받음" in p.받은곳, p.받은곳
    assert p.노션값()["이전 이름·별칭"] == "별칭"


def test_랜섬_목록을_못_받으면_이유가_남는다():
    옛, 옛오프너 = ransom._받기, _안나가게(ransom)
    def 터짐(url, m, op=None):
        raise OSError("연결 안 됨")
    ransom._받기 = 터짐
    try:
        out = list(ransom.조사())
    finally:
        ransom._받기 = 옛
    assert len(out) == 1 and out[0].못본이유, out


def test_포럼은_Tor_없이_안_본다():
    """어니언이든 아니든 같습니다. 규칙이 대상마다 다르면 빠뜨립니다."""
    import os

    from hub.places import egress

    참오프너 = egress.오프너
    옛 = forum.오프너
    forum.오프너 = 참오프너
    지운것 = {k: os.environ.pop(k, None)
            for k in ("TOR_SOCKS_PROXY", "DARKCHOCO_ALLOW_DIRECT",
                      "DARKCHOCO_TOR_SKIP")}
    try:
        out = list(forum.조사([{"이름": "X", "주소": "http://abc.onion"},
                              {"이름": "Y", "주소": "https://plain.example/"}]))
    finally:
        forum.오프너 = 옛
        for k, v in 지운것.items():
            if v is not None:
                os.environ[k] = v

    assert len(out) == 2
    for p in out:
        assert "Tor" in p.못본이유, p.못본이유
        # 두드리지도 못했습니다. 사람이 적어 둔 상태를 안 건드립니다.
        assert p.노션값() == {}, p.노션값()


# ── 508줄을 지울 뻔한 것 ────────────────────────────────────────────
def test_두드리지_못했으면_아무것도_안_쓴다():
    """사람이 확인해 둔 online·offline 을 지우면 안 된다.

    랜섬웨어 DB 508줄(online 126 · offline 379 · 압수됨 2 · 인계됨 1)이
    이것 때문에 날아갈 뻔했다. API 는 살아있는지를 locations[].available
    에 담는데 최상위만 보고 있었다.
    """
    p = Place(갈래="ransom", 이름="X", 상태="미확인", 두드림=False)
    assert p.노션값("기존 규모") == {}, p.노션값()


def test_두드렸는데_못_봤으면_미확인을_쓴다():
    """미리보기가 꺼진 채널. online 이라고 적힌 것이 근거 없는 값이다."""
    p = Place(갈래="telegram", 이름="X", 상태="미확인", 두드림=True,
              못본이유="미리보기가 꺼져 있습니다")
    v = p.노션값("사람 글")
    assert v.get("상태") == "미확인", v
    assert "규모" not in v, "못 봤는데 규모를 건드린다"


def test_랜섬_상태를_locations_에서_읽는다():
    """ransomware.live 는 최상위가 아니라 locations 에 담는다."""
    from hub.places.probe.ransom import _상태로
    assert _상태로({"locations": [{"fqdn": "a.onion", "available": True}]}) == ("online", True)
    assert _상태로({"locations": [{"fqdn": "a.onion", "available": False}]}) == ("offline", True)
    assert _상태로({"available": True}) == ("online", True)
    assert _상태로({"victims": 5}) == ("미확인", False), "못 읽었으면 정했다고 하면 안 된다"


def test_랜섬이_상태를_못_읽으면_노션을_안_건드린다():
    """조사기와 Place 를 이어서 확인한다. 이 둘이 어긋나면 508줄이 날아간다."""
    가짜 = [{"name": "G1", "victims": 3},                       # 상태 표시 없음
           {"name": "G2", "locations": [{"available": False}]}]  # 있음
    옛, 옛오프너 = ransom._받기, _안나가게(ransom)
    ransom._받기 = lambda url, m, op=None: 가짜
    try:
        out = {p.이름: p for p in ransom.조사()}
    finally:
        ransom._받기, ransom.오프너 = 옛, 옛오프너
    assert out["G1"].노션값("기존") == {}, "상태를 못 읽었는데 쓰려 한다"
    assert out["G2"].노션값("기존").get("상태") == "offline"


# ── 첫 화면이 포럼이 아닌 경우 ─────────────────────────────────────
def _포럼한판(본문, code=200):
    """opener 를 갈아 끼워 본문만 바꿔 봅니다."""
    class 응답:
        status = code
        url = "https://f.example/"
        def read(self, n): return 본문.encode()
        def __enter__(self): return self
        def __exit__(self, *a): return False
    class 오프너:
        def open(self, req, timeout=0): return 응답()
    옛 = forum.오프너
    forum.오프너 = lambda 프록시=None, 갈래="": 오프너()
    try:
        return forum.한곳("https://f.example/", "F", [0.0])
    finally:
        forum.오프너 = 옛


def test_압수_배너를_살아있는것으로_세지_않는다():
    """포럼 DB 에는 「압수됨」 선택지가 없다. 미확인으로 두고 사람에게 올린다."""
    p = _포럼한판("<html><body>THIS HIDDEN SITE HAS BEEN SEIZED "
                "by the Federal Bureau of Investigation</body></html>")
    assert p.상태 == "미확인", p.상태
    assert "압수" in p.못본이유, p.못본이유
    assert p.살펴볼것, "압수를 봤는데 사람에게 안 알린다"


def test_파킹된_도메인은_포럼이_아니다():
    p = _포럼한판("<html><body>Buy this domain. The owner is offering "
                "it for sale.</body></html>")
    assert p.상태 == "offline" and "광고" in p.못본이유, (p.상태, p.못본이유)


def test_앞단_검사는_죽은것이_아니다():
    p = _포럼한판("<html><body>Just a moment... checking your browser"
                "</body></html>")
    assert p.상태 == "미확인", p.상태
    assert "뒤에 있습니다" in p.못본이유, p.못본이유


def test_포럼_로그인벽과_언어를_읽는다():
    p = _포럼한판('<html lang="ru"><head><title>DB Forum</title>'
                '<meta name="description" content="Базы данных и логи">'
                '</head><body>You must be registered to view this. '
                'Members: 349,000 Posts: 821,000</body></html>')
    assert p.상태 == "online"
    assert p.언어 == "러시아어", p.언어
    assert p.가입필요 is True
    assert p.어떤곳 == "Базы данных и логи", p.어떤곳
    assert p.회원수 == 349000 and p.게시물수 == 821000, (p.회원수, p.게시물수)


def test_라틴문자만_있으면_언어를_적지_않는다():
    """영어인지 터키어인지 문자만 보고는 못 가립니다."""
    p = _포럼한판("<html><body>Leaked databases for sale. Members: 1,200"
                "</body></html>")
    assert p.언어 == "", p.언어
    assert p.가입필요 is None, "막혔다는 말이 없는데 가입 필요로 적었다"


def test_주소가_옮겨가면_원래_주소를_남긴다():
    class 응답:
        status = 200
        url = "https://new.example/"
        def read(self, n): return b"<html><body>Members: 500</body></html>"
        def __enter__(self): return self
        def __exit__(self, *a): return False
    class 오프너:
        def open(self, req, timeout=0): return 응답()
    옛 = forum.오프너
    forum.오프너 = lambda 프록시=None, 갈래="": 오프너()
    try:
        p = forum.한곳("https://old.example/", "F", [0.0])
    finally:
        forum.오프너 = 옛
    assert p.이전주소 == "https://old.example/", p.이전주소
    assert p.주소 == "https://new.example/", p.주소


def test_사람이_쓴_칸은_안_건드린다():
    """빈칸만칸 은 비어 있을 때만 채웁니다."""
    from hub.places.place import 빈칸만칸
    assert "어떤 곳인지" in 빈칸만칸 and "사용 언어" in 빈칸만칸
    assert "상태" not in 빈칸만칸 and "확인일" not in 빈칸만칸


def test_랜섬_피해집계가_켜져_있다():
    """2026-08-30 에 뒤집혔습니다.

    예전에는 0(안 받음)이었습니다. dls_fill 이 같은 칸을 채우는데 꼴이
    달라 373줄에 겹치는 줄이 붙었기 때문입니다.

    이제 dls-observatory 는 대시보드 재료로만 쓰고 노션에 안 씁니다.
    그래도 누가 --apply 를 주면 겹칠 수 있어, 기계가_쓴_줄() 이 dls_fill
    의 꼴도 알아보게 해 두었습니다(아래 검사).
    """
    from hub.places.probe.ransom import 개월
    assert 개월 >= 1, "피해 대상과 한국 관련 유출이 안 채워진다"
    from hub.places.place import 기계가_쓴_줄
    assert 기계가_쓴_줄("피해자 12건 (최근 6개월)"), (
        "dls_fill 의 줄을 못 알아본다. 그러면 겹쳐 쌓인다")

    그룹 = [{"name": "G", "locations": [{"available": True, "slug": "http://g.onion"}]}]
    친것 = []
    옛, 옛오프너 = ransom._받기, _안나가게(ransom)
    def 받기(url, m, op=None):
        친것.append(url)
        return 그룹
    ransom._받기 = 받기
    try:
        p = next(iter(ransom.조사()))
    finally:
        ransom._받기, ransom.오프너 = 옛, 옛오프너
    # /groups 한 번 + 달마다 한 번입니다. 요청 수가 개월과 같이 늘어야
    # 합니다. 안 늘면 피해 목록을 안 받는 것입니다.
    assert len(친것) == 1 + 개월, 친것
    assert 친것[0].endswith("/groups"), 친것[0]
    assert all("/victims/" in u for u in 친것[1:]), 친것[1:]

    값 = p.노션값()
    assert 값["상태"] == "online"
    # 이 가짜 응답에는 피해 목록이 없어서(같은 그룹 목록을 돌려줍니다)
    # 셀 것이 없습니다. 요청을 보냈다는 것까지만 봅니다.


def test_포럼_총계만_잡는다():
    """첫 화면에는 총계 말고도 숫자가 잔뜩 있습니다.

    2026-08-28 bf.st 첫 화면에서 예전 정규식이 「회원 45」를 만들었습니다.
    실제 회원은 367,224 명입니다. 틀린 값이 사람이 조사한 규모 줄을 갈아
    끼우기 때문에 느슨하게 잡으면 안 됩니다.
    """
    본문 = ("<html><body>"
          "182 users active in the past 60 minutes (44 members, 138 guests)"
          "<br>Board Statistics<br>"
          "857 Threads 4584 Posts"                    # 게시판 하나
          "<br>873955 Total Posts 85413 Total Threads 367224 Total Members"
          "<br>honeydutch Newest Member 14,829 Most Online"
          "</body></html>")
    p = _포럼한판(본문)
    assert p.회원수 == 367224, p.회원수
    assert p.게시물수 == 873955, p.게시물수
    assert "회원 367,224" in p.노션값()["규모"]


def test_포럼_접속자수를_회원수로_읽지_않는다():
    """총계가 없으면 빈칸입니다. 지어내지 않습니다."""
    p = _포럼한판("<html><body>Currently 182 members online. "
                "Most online today: 400</body></html>")
    assert p.회원수 is None, p.회원수
    assert p.게시물수 is None, p.게시물수
    assert "규모" not in p.노션값(), p.노션값()


# ── 연결된 곳 · 조사 단계 ──────────────────────────────────────────
def test_이음은_명부에_있는_곳만_적는다():
    """첫 화면에는 광고와 남의 링크가 잔뜩 있습니다.

    처음 보는 주소를 「연결된 곳」에 적으면 관계가 아니라 잡음입니다.
    """
    from hub.places.extract import links

    class 줄:
        def __init__(s, 이름, 주소="", 어니언=""):
            s.이름, s.주소, s.어니언 = 이름, 주소, 어니언

    사전 = links.이름표만들기({
        "forum": [줄("BreachForums", "https://bf.st/"),
                  줄("ZDL", "", "http://oaptxiyisljt2kv3we2we34kuudmqda7f2geffoylzpeo7ourhtz4dad.onion/")],
        "telegram": [줄("DarkForums", "https://t.me/DarkForumsss"),
                     줄("이상한줄", "@projectwwh")],
    })
    본문 = ("""<a href="https://bf.st/board">여기</a>"""
          """<a href="https://t.me/DarkForumsss">채널</a>"""
          """<a href="https://google.com/">구글</a>"""
          """<a href="https://never-seen.example/">처음</a>"""
          "http://oaptxiyisljt2kv3we2we34kuudmqda7f2geffoylzpeo7ourhtz4dad.onion/ 도 있습니다")
    나온것 = links.찾기(본문, 사전, "포럼 DB: 나")

    assert "포럼 DB: BreachForums" in 나온것, 나온것
    assert "텔레그램 DB: DarkForums" in 나온것, 나온것
    assert "포럼 DB: ZDL" in 나온것, 나온것
    assert "google" not in 나온것, "어디에나 있는 곳을 관계로 셌다"
    assert "never-seen" not in 나온것, "명부에 없는 곳을 적었다"


def test_이음은_자기_자신을_안_센다():
    from hub.places.extract import links

    class 줄:
        def __init__(s, 이름, 주소=""):
            s.이름, s.주소, s.어니언 = 이름, 주소, ""

    사전 = links.이름표만들기({"forum": [줄("나", "https://me.example/")]})
    assert links.찾기('<a href="https://me.example/x">나</a>', 사전,
                    "포럼 DB: 나") == ""


def test_호스트가_아닌_것을_걸러낸다():
    """상대 주소와 파일 이름이 urlparse 를 지나면 호스트처럼 보입니다."""
    from hub.places.extract.links import 호스트
    for 값 in ("@projectwwh", ".", "member.php", "style.css", "search.php",
              "logo.png", "", "  ", "localhost"):
        assert 호스트(값) == "", f"{값!r} 를 호스트로 봤다"
    # 짧은 호스트도 지나가야 합니다. t.me 를 떨어뜨리면 텔레그램 이음이
    # 통째로 안 됩니다.
    assert 호스트("https://t.me/x") == "t.me"
    assert 호스트("https://bf.st/") == "bf.st"
    assert 호스트("www.Example.COM") == "example.com"
    assert 호스트("http://abcd.onion/x") == "abcd.onion"


def test_인프라는_이웃으로_안_센다():
    """CDN 은 어느 쪽이나 씁니다. 관계가 아닙니다."""
    from hub.places.extract.links import 처음보는곳
    본문 = ("""<a href="https://cdnjs.cloudflare.com/x.js">js</a>"""
          """<a href="https://fonts.googleapis.com/c">font</a>"""
          """<a href="https://newsite.example/">새 곳</a>"""
          """<a href="member.php">상대 주소</a>""")
    assert 처음보는곳(본문, {}) == ["newsite.example"]


def test_어니언_제목이_다르면_남의_것으로_본다():
    """첫 화면에 남의 어니언이 광고로 걸려 있을 수 있습니다."""
    from hub.places.probe.forum import _닮았나
    assert _닮았나("BreachForums - The premier Databreach forum",
                 "BreachForums | Databreach")
    assert not _닮았나("BreachForums - Databreach discussion",
                     "Nulled - Community")
    assert not _닮았나("Forum", "Forum")          # 흔한 낱말뿐이면 근거 없음


def test_두드려_본_줄에만_확인만함을_넣는다():
    p = _포럼한판("<html><body>367224 Total Members</body></html>")
    assert p.노션값()["조사 단계"] == "확인만 함"

    from hub.places.place import Place, 빈칸만칸
    # 안 두드린 줄은 아무것도 안 씁니다.
    안봄 = Place(갈래="forum", 이름="X", 상태="미확인", 두드림=False)
    assert 안봄.노션값() == {}
    # 사람이 이미 「조사 중」 이라고 써 둔 줄은 안 건드립니다.
    assert "조사 단계" in 빈칸만칸


def test_압수는_거짓_상태로_안_적는다():
    """포럼 DB 「상태」 선택지에 압수됨 이 없습니다. 랜섬웨어 DB 에만 있습니다."""
    p = _포럼한판("<html><body>THIS SITE HAS BEEN SEIZED by the "
                "Federal Bureau of Investigation</body></html>")
    assert p.상태 == "미확인", p.상태
    assert p.살펴볼것 and "압수" in p.살펴볼것, p.살펴볼것


def test_사람이_판정한_상태를_기계가_안_덮는다():
    """압수됨·인계됨 은 「무슨 일이 있었나」 이지 「살아있나」 가 아니다.

    압수된 사이트도 수사기관 배너로 200 을 돌려주니 기계는 online 이라
    한다. 실제 랜섬웨어 DB 에서 「압수됨 → online」 과 「인계됨 → offline」
    이 될 뻔했다.
    """
    from hub.places.place import 사람판정_상태

    for 옛 in 사람판정_상태:
        for 새 in ("online", "offline"):
            p = Place(갈래="ransom", 이름="X", 상태=새, 두드림=True,
                      주소="http://a.onion")
            값 = p.노션값({"상태": 옛})
            assert "상태" not in 값, f"{옛} 를 {새} 로 덮으려 한다"
            # 확인일은 씁니다. 언제 봤는지는 남겨야 합니다.
            assert 값["확인일"] == p.확인일[:10]

    # 사람 판정이 아니면 그대로 덮습니다.
    p = Place(갈래="ransom", 이름="X", 상태="online", 두드림=True)
    assert p.노션값({"상태": "offline"})["상태"] == "online"


def test_사람_판정을_덮으려_하면_화면에_올린다():
    """조용히 안 쓰고 끝내면 사람이 그 줄을 다시 볼 계기가 없다."""
    from hub.places.write import 반영결과
    assert "사람판정" in 반영결과.__dataclass_fields__
    글 = (ROOT / "hub" / "places" / "run.py").read_text(encoding="utf-8")
    assert "res.사람판정" in 글, "run.py 가 사람판정을 화면에 안 올린다"


# ── 오늘 만든 바닥 결함 넷 ──────────────────────────────────────────
def test_명부_줄이_어니언을_담는다():
    """이음 사전이 이것을 씁니다. 없으면 어니언 관계를 통째로 못 봅니다.

    포럼 명부에 어니언 주소가 43줄 적혀 있는데, 줄 에 어니언 필드가
    없어서 사전에 하나도 안 들어갔습니다. 그래서 아는 곳의 어니언
    미러가 「명부에 없는 이웃」 으로 잡혔습니다.
    """
    from hub.places.write import 줄
    assert "어니언" in 줄.__dataclass_fields__
    글 = (ROOT / "hub" / "places" / "write.py").read_text(encoding="utf-8")
    assert '어니언=_글자(props.get("어니언 주소"))' in 글,         "줄들() 이 어니언 주소를 안 읽는다"


def test_시계열을_못_쌓아도_조사는_산다():
    """한갈래() 는 예외를 밖으로 안 냅니다. _쌓기 만 밖에 있었습니다."""
    글 = (ROOT / "hub" / "places" / "run.py").read_text(encoding="utf-8")
    시작 = 글.index("if apply and 본것:")
    자리 = 글[시작:글.index("r.초 = time.time()", 시작)]
    assert "try:" in 자리 and "except" in 자리,         "_쌓기 가 try 밖이다. 표가 깨지면 dc.py crawl 이 통째로 죽는다"


def test_이웃의_출처를_여럿_담는다():
    """여러 곳이 같은 호스트를 걸어 두면 그것이 더 중요한 실마리다."""
    글 = (ROOT / "hub" / "places" / "run.py").read_text(encoding="utf-8")
    assert "r.처음본곳.setdefault(h, set()).add(" in 글,         "setdefault 로 하나만 담으면 둘째 출처가 버려진다"


def test_살펴볼것을_덮지_않고_붙인다():
    """압수 안내를 봤는데 어니언 후보도 못 열었으면 둘 다 알려야 한다."""
    from hub.places.place import Place, 덧붙임
    p = Place(갈래="forum", 이름="X")
    덧붙임(p, "압수 안내로 바뀌었습니다")
    덧붙임(p, "어니언 후보를 못 확인했습니다")
    덧붙임(p, "압수 안내로 바뀌었습니다")      # 같은 말은 안 쌓입니다
    assert p.살펴볼것.count("압수") == 1, p.살펴볼것
    assert "어니언" in p.살펴볼것, p.살펴볼것

    글 = (ROOT / "hub" / "places" / "probe" / "forum.py").read_text(encoding="utf-8")
    assert "p.살펴볼것 = " not in 글, "아직 덮어쓰는 곳이 있다"


def test_진행이_보인다():
    """끝나야 결과가 나오면 지금 몇 줄째인지 알 수가 없다.

    포럼 269줄이 Tor 를 거치면 한 시간 넘게 걸린다. 사람이 볼 때도,
    자동으로 돌 때 로그를 볼 때도 진행이 보여야 어디서 멈췄는지 안다.
    """
    글 = (ROOT / "hub" / "places" / "run.py").read_text(encoding="utf-8")
    assert "분쯤 남음" in 글, "남은 시간을 안 알려 준다"
    assert "flush=True" in 글, "버퍼에 갇히면 진행이 안 보인다"
    # 조용히 를 주면 안 찍어야 합니다. 검사가 시끄러우면 안 됩니다.
    import inspect

    from hub.places.run import 여러갈래, 한갈래
    for fn in (한갈래, 여러갈래):
        assert "조용히" in inspect.signature(fn).parameters, fn.__name__


def test_게시판_이름이_유통자리와_개인정보로_간다():
    """포럼이 스스로 붙인 이름이 근거다. 우리 추측이 아니다."""
    본문 = ("<html><body>"
          '<a href="forumdisplay.php?fid=3">Leaks &amp; Databases</a>'
          '<a href="forumdisplay.php?fid=4">Marketplace</a>'
          '<a href="forumdisplay.php?fid=12">Fullz &amp; SSN</a>'
          "367224 Total Members</body></html>")
    p = _포럼한판(본문)
    assert "최초 유출" in p.유통자리 and "되팔이" in p.유통자리, p.유통자리
    assert "Fullz & SSN" in p.개인정보, p.개인정보
    값 = p.노션값()
    assert set(값["유통 자리"]) == {"최초 유출", "되팔이"}, 값["유통 자리"]
    assert 값["개인정보 유출"].startswith("게시판 이름: ")


def test_게시판_증거가_없으면_그_칸을_안_쓴다():
    """「모름」 을 269줄에 뿌리면 그 칸이 아무것도 말하지 못한다."""
    p = _포럼한판("<html><body>"
                '<a href="forumdisplay.php?fid=1">Announcements</a>'
                "367224 Total Members</body></html>")
    값 = p.노션값()
    assert "유통 자리" not in 값, 값
    assert "개인정보 유출" not in 값, 값


def test_유통자리와_개인정보는_사람이_쓴_것을_안_덮는다():
    from hub.places.place import 빈칸만칸
    assert "유통 자리" in 빈칸만칸 and "개인정보 유출" in 빈칸만칸


def test_한_줄이_죽어도_나머지는_돈다():
    """명부에 "nulled.to" 처럼 스킴 없는 주소가 적힌 줄이 있다.

    urllib 이 ValueError 를 내는데 조사기의 except 는 연결 실패만 잡아서
    판 전체가 죽었다. 포럼 269줄이 47분 돌다 한 줄 때문에 통째로
    날아갔다. 결과가 하나도 안 남았다.
    """
    from hub.places.run import _조사

    class 가짜줄:
        def __init__(self, 이름, 주소):
            self.이름, self.주소, self.현재 = 이름, 주소, {}
            self.page_id, self.규모, self.상태, self.어니언 = "p", "", "", ""

    옛 = forum.한곳

    def 터짐(*a, **k):
        raise ValueError("unknown url type: 'nulled.to'")

    forum.한곳 = 터짐
    try:
        out = list(_조사("forum", [가짜줄("A", "a.example"),
                                  가짜줄("B", "b.example")], {"tor": None}))
    finally:
        forum.한곳 = 옛

    assert len(out) == 2, "한 줄이 죽으니 나머지도 안 나온다"
    for _, p in out:
        assert "터졌습니다" in p.못본이유, p.못본이유
        assert p.살펴볼것, "사람에게 안 알린다"
        assert p.노션값() == {}, "터진 줄로 노션을 건드린다"


def test_스킴이_없으면_붙여_준다():
    본문 = "<html><body>367224 Total Members</body></html>"

    class 응답:
        status = 200
        url = "https://nulled.to/"
        def read(self, n): return 본문.encode()
        def __enter__(self): return self
        def __exit__(self, *a): return False

    class 오프너:
        def open(self, req, timeout=0):
            assert req.full_url.startswith("https://"), req.full_url
            return 응답()

    옛 = forum.오프너
    forum.오프너 = lambda 프록시=None, 갈래="": 오프너()
    try:
        p = forum.한곳("nulled.to", "Nulled", [0.0])
    finally:
        forum.오프너 = 옛
    assert p.상태 == "online", p.상태
    assert "https" in p.받은곳, p.받은곳


def test_같은_호스트만_기다린다():
    """포럼 명부 224줄이 전부 다른 호스트다. 그 사이 3초는 아무도 안 돕는다."""
    import time as _t

    from hub.places.probe.forum import _기다리기, 간격

    마지막 = {}
    t0 = _t.time()
    for h in ("a.example", "b.example", "c.example"):
        _기다리기(마지막, h)
    assert _t.time() - t0 < 0.5, "다른 호스트끼리 기다린다"

    t0 = _t.time()
    _기다리기(마지막, "a.example")          # 같은 곳을 또 칩니다
    assert _t.time() - t0 >= 간격 - 0.3, "같은 호스트인데 안 기다린다"


def test_동시에_봐도_줄과_결과가_안_엇갈린다():
    """as_completed 는 끝난 순서로 옵니다. 줄을 잘못 짝지으면 남의 값을 씁니다."""
    from hub.places.run import _조사

    class 가짜줄:
        def __init__(self, 이름):
            self.이름, self.주소, self.현재 = 이름, f"https://{이름}/", {}
            self.page_id, self.규모, self.상태, self.어니언 = 이름, "", "", ""

    줄들 = [가짜줄(f"f{i}") for i in range(12)]
    옛 = forum.한곳

    def 가짜한곳(주소, 이름, 마지막, **kw):
        import time as _t
        # 뒤 줄이 먼저 끝나게 해서 순서를 뒤집습니다.
        _t.sleep(0.05 if 이름.endswith(("0", "1", "2")) else 0.001)
        return Place(갈래="forum", 이름=이름, 주소=주소, 상태="online",
                     두드림=True)

    forum.한곳 = 가짜한곳
    try:
        out = list(_조사("forum", 줄들, {"tor": "http://127.0.0.1:9080"}))
    finally:
        forum.한곳 = 옛

    assert len(out) == len(줄들)
    for 줄, p in out:
        assert 줄.이름 == p.이름, f"줄 {줄.이름} 에 {p.이름} 결과가 붙었다"


def test_Tor_가_없으면_한_줄씩_본다():
    """프록시가 없으면 어차피 안 나갑니다. 스레드를 안 만듭니다.

    예전에는 이 검사가 소스에서 문자열 한 줄을 찾았습니다. 흐름을
    통일하면서 그 줄이 없어졌는데, **동작은 그대로인데 검사만 깨졌습니다.**
    낱말이 아니라 뜻을 봅니다.
    """
    from hub.places import run as R

    본것 = []
    옛열기 = R.갈래표["forum"]["여는법"]

    def 세는열기(r, 상황):
        import threading
        본것.append(threading.current_thread().name)
        return Place(갈래="forum", 이름=r.이름, 못본이유="검사")

    class 줄:
        def __init__(self, i):
            self.page_id, self.이름, self.주소, self.어니언 = f"p{i}", f"F{i}", f"https://e{i}.test/", ""

    R.갈래표["forum"]["여는법"] = 세는열기
    try:
        list(R._조사("forum", [줄(i) for i in range(4)],
                    {"tor": None, "이음사전": {}}))
    finally:
        R.갈래표["forum"]["여는법"] = 옛열기
    assert len(set(본것)) == 1, f"Tor 가 없는데 스레드를 {len(set(본것))}개 썼다"


def test_갈래를_보고_가르지_않는다():
    """흐름 통일의 핵심입니다.

    예전에는 `_조사()` 안이 if telegram / elif forum / elif ransom
    세 덩이였습니다. 수집기를 얹으려면 세 곳에 각각 붙여야 했습니다.
    """
    글 = (ROOT / "hub" / "places" / "run.py").read_text(encoding="utf-8")
    자리 = 글[글.index("def _조사"):글.index("def 이음사전만들기")]
    for 나쁜 in ('갈래 == "telegram"', '갈래 == "forum"', '갈래 == "ransom"'):
        assert 나쁜 not in 자리, f"_조사() 안에서 갈래를 가릅니다: {나쁜}"

    from hub.places.run import 갈래표, 갈래들
    assert set(갈래표) == set(갈래들), (set(갈래표), set(갈래들))
    for 갈래, 설정 in 갈래표.items():
        assert callable(설정["여는법"]), 갈래
        assert "동시" in 설정 and "앞선것" in 설정, 갈래


def test_요약이_얼마나_열렸는지_보여_준다():
    """「본 것 22 · 못 본 것 202」 는 오해를 부른다.

    「살아있는 것은 봤는데 회원 수가 첫 화면에 없다」 도 못 본 것으로
    센다. 실제로 몇 곳이 열렸는지가 안 보인다.
    """
    from hub.places.run import 갈래결과, 표로

    r = 갈래결과(갈래="forum", 본것=22, 못본것=202, 바뀐줄=84)
    r.상태셈 = {"online": 140, "offline": 60, "미확인": 24}
    r.이유셈 = {"살아있는 것은 봤는데 회원·게시물 수는 첫 화면에 없습니다": 118,
              "연결이 안 됩니다": 60}
    글 = 표로([r], apply=False)
    assert "열린 곳 140" in 글, 글
    assert "online 140" in 글, 글
    assert "118줄" in 글, 글


def test_클리어넷이_안_되면_어니언으로_다시_간다():
    """다크웹 포럼은 클리어넷 도메인이 자주 죽고 어니언은 살아 있습니다.

    2026-08-28 실측에서 224줄 중 104줄이 「연결이 안 됩니다」 였고 진짜
    죽은 곳은 3곳뿐이었습니다.
    """
    본것 = []

    class 죽음:
        def open(self, req, timeout=0):
            raise OSError("연결 안 됨")

    class 살음:
        def open(self, req, timeout=0):
            class R:
                status = 200
                url = req.full_url
                def read(self, n):
                    return b"<html><body>367224 Total Members</body></html>"
                def __enter__(self): return self
                def __exit__(self, *a): return False
            return R()

    def 오프너(프록시=None, 갈래=""):
        # 첫 번째(클리어넷)는 죽고 두 번째(어니언)는 삽니다.
        본것.append(1)
        return 죽음() if len(본것) == 1 else 살음()

    옛 = forum.오프너
    forum.오프너 = 오프너
    try:
        p = forum.한곳("https://dead.example/", "X", {},
                     프록시="http://127.0.0.1:9080",
                     어니언="http://" + "c" * 56 + ".onion/")
    finally:
        forum.오프너 = 옛

    assert p.상태 == "online", p.상태
    assert p.회원수 == 367224, p.회원수
    assert "어니언" in p.받은곳, p.받은곳
    assert "클리어넷이 안 됩니다" in (p.살펴볼것 or ""), p.살펴볼것
    # 명부의 클리어넷 주소는 그대로 둡니다.
    assert p.주소 == "https://dead.example/", p.주소


def test_어니언만_있는_줄도_본다():
    """포럼 명부 45줄이 클리어넷 주소가 없는데 37줄에 어니언이 있습니다."""
    글 = (ROOT / "hub" / "places" / "run.py").read_text(encoding="utf-8")
    자리 = 글[글.index("볼것 = ["):글.index("r.건너뜀")]
    assert "어니언" in 자리, "어니언만 있는 줄을 안 봅니다"

    out = list(forum.조사([{"이름": "X", "주소": "", "어니언": "http://" + "e" * 56 + ".onion/"}],
                        dry=True))
    assert out == []          # dry 는 그냥 넘어갑니다


def test_어니언도_안_되면_둘_다_남긴다():
    class 죽음:
        def open(self, req, timeout=0):
            raise OSError("연결 안 됨")

    옛 = forum.오프너
    forum.오프너 = lambda 프록시=None, 갈래="": 죽음()
    try:
        p = forum.한곳("https://a.example/", "X", {},
                     프록시="http://127.0.0.1:9080", 어니언="http://" + "d" * 56 + ".onion/")
    finally:
        forum.오프너 = 옛
    assert p.상태 != "offline", "연결 실패를 죽었다고 적는다"
    assert "어니언도 안 됩니다" in (p.살펴볼것 or ""), p.살펴볼것
    assert p.노션값() == {}, p.노션값()


def test_수치가_없다고_나머지를_안_버린다():
    """첫 화면을 다 읽고도 회원 수 하나가 없어 여섯 칸을 버렸습니다.

    못본이유 가 차면 노션값() 이 확인일과 상태만 남깁니다. 「수치가
    첫 화면에 없다」 는 「못 봤다」 가 아닙니다. online 83줄 중 65줄이
    여기 해당했습니다.
    """
    본문 = ('<html lang="ru"><head><title>X</title>'
          '<meta name="description" content="유출 포럼"></head><body>'
          '<a href="forumdisplay.php?fid=3">Leaks</a>'
          "Currently 182 members online</body></html>")     # 총계가 없습니다
    p = _포럼한판(본문)
    assert p.상태 == "online"
    assert p.회원수 is None and p.게시물수 is None
    assert p.봤나(), "수치가 없다고 못 봤다고 적는다"
    값 = p.노션값()
    for k in ("사용 언어", "어떤 곳인지", "유통 자리", "조사 단계"):
        assert k in 값, f"{k} 를 버린다: {sorted(값)}"
    assert "규모" not in 값, "수치가 없는데 규모를 쓴다"
    assert "첫 화면에 없습니다" in p.받은곳, p.받은곳


def test_못_본_줄에도_들어가는_법은_남긴다():
    """무엇에 막혔는지가 바로 그 칸의 내용입니다."""
    p = _포럼한판("<html><body>Just a moment... checking your browser</body></html>")
    assert not p.봤나()
    값 = p.노션값()
    assert 값.get("들어가는 법"), 값
    assert set(값) <= {"확인일", "상태", "들어가는 법"}, 값

    # 두드리지도 못한 줄에는 안 뿌립니다.
    from hub.places.place import Place
    안봄 = Place(갈래="forum", 이름="X", 상태="미확인", 두드림=False,
                들어가는법="아무거나", 못본이유="연결이 안 됩니다")
    assert 안봄.노션값() == {}, 안봄.노션값()


def test_어니언_주소를_씻는다():
    """명부에 「— 미기입 —」·날짜 꼬리·v2 가 섞여 있습니다."""
    from hub.places.probe.forum import _어니언정리
    v3 = "http://" + "a" * 56 + ".onion/"
    assert _어니언정리(v3) == v3
    assert _어니언정리("a" * 56 + ".onion") == "http://" + "a" * 56 + ".onion"
    assert _어니언정리("a" * 56 + ".onion (2026-07-30 확인)").endswith(".onion")
    for 나쁨 in ("— 미기입 —", "— 없음 —", "", "  ",
                "a" * 16 + ".onion", "https://example.com/"):
        assert _어니언정리(나쁨) == "", 나쁨


def test_주소가_비어도_어니언으로_간다():
    """명부 37줄이 어니언만 있어 지금껏 한 번도 조사된 적이 없습니다."""
    친것 = []

    class 오프너:
        def open(self, req, timeout=0):
            친것.append(req.full_url)
            class R:
                status = 200
                url = req.full_url
                def read(self, n):
                    return b"<html><body>367224 Total Members</body></html>"
                def __enter__(self): return self
                def __exit__(self, *a): return False
            return R()

    옛 = forum.오프너
    forum.오프너 = lambda 프록시=None, 갈래="": 오프너()
    try:
        어니언 = "http://" + "b" * 56 + ".onion/"
        p = forum.한곳("", "X", {}, 프록시="http://127.0.0.1:9080", 어니언=어니언)
    finally:
        forum.오프너 = 옛

    assert len(친것) == 1, 친것          # 빈 주소로 헛요청을 안 보냅니다
    assert 친것[0] == 어니언, 친것
    assert p.상태 == "online" and p.회원수 == 367224
    assert p.어니언 == 어니언 and not p.주소


def test_꼴이_깨진_어니언은_안_두드린다():
    친것 = []

    class 오프너:
        def open(self, req, timeout=0):
            친것.append(req.full_url)
            raise AssertionError("두드리면 안 됩니다")

    옛 = forum.오프너
    forum.오프너 = lambda 프록시=None, 갈래="": 오프너()
    try:
        p = forum.한곳("", "X", {}, 프록시="http://127.0.0.1:9080",
                     어니언="— 미기입 —")
    finally:
        forum.오프너 = 옛
    assert 친것 == [], 친것
    assert p.노션값() == {}, p.노션값()


def test_K_M_접미사를_제대로_읽는다():
    """1.6M 을 16 으로, 24.3K 를 243 으로 읽고 있었습니다.

    점을 그냥 지워서 그랬습니다. 그 값이 사람이 조사한 규모 줄을 갈아
    끼웁니다.
    """
    from hub.places.probe.forum import _숫자
    for 값, 기대, 어림 in [("1.6M", 1_600_000, True),
                        ("24.3K", 24_300, True),
                        ("2M", 2_000_000, True),
                        ("367,224", 367_224, False),
                        ("185 091", 185_091, False),
                        ("45", 45, False)]:
        n, a = _숫자(값)
        assert n == 기대, f"{값} → {n} (기대 {기대})"
        assert a == 어림, f"{값} 의 어림수 표시가 {a}"


def test_수를_중간에서_안_자른다():
    """24.3K 에서 되물러 24 를 잡으면 안 됩니다."""
    본문 = "<html><body>Total members: 24.3K Total posts: 1.6M</body></html>"
    p = _포럼한판(본문)
    assert p.회원수 == 24_300, p.회원수
    assert p.게시물수 == 1_600_000, p.게시물수
    assert p.어림수, "K·M 값인데 어림수 표시가 없다"
    assert "안팎" in p.노션값()["규모"], p.노션값()["규모"]


def test_4xx_에서_무엇이_막는지_적는다():
    """HTTP 403 만으로는 손쓸 방법을 못 정합니다."""
    from hub.places.probe.forum import _막은것
    assert "클라우드플레어" in _막은것("error code: 1020",
                                {"Server": "cloudflare", "CF-RAY": "x"})
    assert "속도 제한" in _막은것("error code: 1015", {"CF-RAY": "x"})
    assert "DDoS-Guard" in _막은것("", {"Server": "ddos-guard"})
    assert "Sucuri" in _막은것("", {"X-Sucuri-ID": "1"})
    assert "원서버" in _막은것("Access Denied", {"Server": "nginx"})
    assert _막은것("", {}), "빈 값을 돌려주면 안 됩니다"


def test_두드린_줄은_확인일만_바뀌어도_쓴다():
    """403·404 로 막힌 줄은 상태가 계속 미확인이라, 오늘 두드렸다는
    사실이 아예 안 남았습니다."""
    글 = (ROOT / "hub" / "places" / "write.py").read_text(encoding="utf-8")
    assert 'set(달라진것) <= {"확인일"} and not p.두드림' in 글,         "두드린 줄인데 확인일을 안 쓴다"


def test_텔레그램도_게시판_부품을_쓴다():
    글 = (ROOT / "hub" / "places" / "probe" / "telegram.py").read_text(
        encoding="utf-8")
    assert "boards" in 글, "텔레그램에 게시판 부품이 안 물려 있다"
    assert "유통자리" in 글 and "개인정보" in 글
    # 글 본문은 안 씁니다. 이름과 소개만 씁니다.
    자리 = 글[글.index("말들 = ["):글.index("말들 = [") + 260]
    assert "p.이름" in 자리 and "p.어떤곳" in 자리, 자리[:200]
    # 채널 이름과 소개만 넣습니다. 받아 온 쪽 전체(body)를 안 넣습니다.
    넣는줄 = [l for l in 자리.splitlines() if l.strip().startswith("말들 = ")][0]
    assert "body" not in 넣는줄, 넣는줄



# ── merge.py ───────────────────────────────────────────────────────────
def _랜섬(**kw):
    from hub.places.place import Place
    kw.setdefault("갈래", "ransom")
    kw.setdefault("이름", "TESTGROUP")
    return Place(**kw)


def test_합치기는_이미_찬_칸을_안_덮는다():
    """조사기마다 아는 것이 다릅니다. 겹치면 바탕이 이깁니다."""
    from hub.places.merge import 합치기
    바탕 = _랜섬(언어="러시아어", 어떤곳="주소를 열어 본 설명")
    위 = _랜섬(언어="영어", 어떤곳="API 가 준 설명", 형식="RaaS")
    r = 합치기(바탕, 위)
    assert r.언어 == "러시아어", "바탕을 덮었다"
    assert r.어떤곳 == "주소를 열어 본 설명", "바탕을 덮었다"
    assert r.형식 == "RaaS", "빈칸을 안 채웠다"


def test_합치기는_상태를_뒤엣것에_넘긴다():
    """랜섬에서 뒤엣것은 /groups 입니다. 살아있나가 그 API 의 본업입니다."""
    from hub.places.merge import 합치기
    바탕 = _랜섬(상태="online", 두드림=True)
    r = 합치기(바탕, _랜섬(상태="offline", 두드림=True))
    assert r.상태 == "offline", "뒤엣것이 두드렸는데 안 넘어갔다"

    # 뒤엣것이 못 두드렸으면 안 넘깁니다
    바탕2 = _랜섬(상태="online", 두드림=True)
    r2 = 합치기(바탕2, _랜섬(상태="미확인", 두드림=False))
    assert r2.상태 == "online", "못 두드린 것이 상태를 덮었다"


def test_합치기는_받은곳을_이어_붙인다():
    """어디서 왔는지를 지우면 나중에 왜 그 값인지 못 찾습니다."""
    from hub.places.merge import 합치기
    r = 합치기(_랜섬(받은곳="주소를 엶"), _랜섬(받은곳="/groups"))
    assert "주소를 엶" in r.받은곳 and "/groups" in r.받은곳, r.받은곳


def test_합치기는_출처를_합집합으로_둔다():
    """multi-select 입니다. 둘 다 실제로 쓴 출처입니다."""
    from hub.places.merge import 합치기
    r = 합치기(_랜섬(출처=["직접 확인"]), _랜섬(출처=["ransomware.live"]))
    assert set(r.출처) == {"직접 확인", "ransomware.live"}, r.출처
    # 같은 것을 두 번 얹어도 안 늘어납니다
    r = 합치기(r, _랜섬(출처=["직접 확인"]))
    assert len(r.출처) == 2, r.출처


def test_합치기는_살펴볼것을_안_지운다():
    """사람이 봐야 하는 줄입니다. 덮으면 조용히 사라집니다."""
    from hub.places.merge import 합치기
    r = 합치기(_랜섬(살펴볼것="압수 안내로 바뀜"), _랜섬(살펴볼것="어니언 미러 찾음"))
    assert "압수 안내로 바뀜" in r.살펴볼것 and "어니언 미러 찾음" in r.살펴볼것, r.살펴볼것


def test_조사기가_셋이어도_인자만_늘어난다():
    """이것이 merge.py 를 뺀 이유입니다.

    dls-observatory 가 붙으면 `run.py` 에 if 를 더하는 게 아니라
    여기에 인자를 하나 더 줍니다.
    """
    from hub.places.merge import 합치기
    연것 = _랜섬(언어="영어", 받은곳="주소를 엶")
    API = _랜섬(형식="RaaS", 상태="online", 두드림=True, 받은곳="/groups")
    DLS = _랜섬(피해대상="제조 3 · 의료 1", 연락수단="tox", 받은곳="dls")
    r = 합치기(연것, API, DLS)
    assert r.언어 == "영어" and r.형식 == "RaaS" and r.피해대상 == "제조 3 · 의료 1"
    assert r.연락수단 == "tox" and r.상태 == "online"


def test_run_에_손으로_박은_합치기가_안_남았다():
    """예전에는 칸 이름을 run.py 안에서 문자열로 나열했습니다."""
    글 = (ROOT / "hub" / "places" / "run.py").read_text(encoding="utf-8")
    assert "합치기(" in 글, "merge.py 를 안 씁니다"
    자리 = 글[글.index("def _조사"):글.index("def 이음사전만들기")]
    assert '"이전이름"' not in 자리 and '"최근활동"' not in 자리, (
        "칸 이름을 run.py 에서 다시 나열하고 있습니다. merge.py 로 가야 합니다")


# ── backoff.py ─────────────────────────────────────────────────────────
class _가짜줄:
    def __init__(self, pid, 이름="X"):
        self.page_id, self.이름 = pid, 이름


def _자취():
    import tempfile
    from hub.places.backoff import 기록
    d = tempfile.mkdtemp()
    return 기록(Path(d) / "b.db")


def test_처음_보는_줄은_안_쉰다():
    from hub.places.backoff import 기록  # noqa: F401
    b = _자취()
    try:
        assert b.쉬는중("forum", "새것", 1_000_000.0) == 0
    finally:
        b.close()


def test_한_번_실패는_다음_판에_바로_다시_본다():
    """한 번 죽은 것으로 쉬면 잠깐 끊긴 곳을 놓칩니다."""
    b = _자취()
    try:
        t = 1_000_000.0
        b.적기("forum", "A", False, t)
        assert b.쉬는중("forum", "A", t + 60) == 0, "한 번 실패로 쉬고 있다"
    finally:
        b.close()


def test_두_번_실패하면_하루_쉰다():
    b = _자취()
    try:
        t = 1_000_000.0
        b.적기("forum", "A", False, t)
        b.적기("forum", "A", False, t + 3600)
        assert b.쉬는중("forum", "A", t + 3600 + 3600) > 0, "두 번 실패인데 안 쉰다"
        assert b.쉬는중("forum", "A", t + 3600 + 86400 + 60) == 0, "하루가 지났는데 아직 쉰다"
    finally:
        b.close()


def test_아무리_죽어도_두_주면_다시_본다():
    """영영 안 보면 부활한 곳을 영영 못 찾습니다."""
    from hub.places.backoff import 최대쉼
    b = _자취()
    try:
        t = 1_000_000.0
        for i in range(20):
            b.적기("forum", "A", False, t + i)
        남음 = b.쉬는중("forum", "A", t + 20)
        assert 남음 <= 최대쉼, f"{남음}일이나 쉰다. 최대 {최대쉼}일이어야 한다"
        assert b.쉬는중("forum", "A", t + 20 + (최대쉼 + 1) * 86400) == 0
    finally:
        b.close()


def test_한_번_되면_연속실패가_0_이_된다():
    b = _자취()
    try:
        t = 1_000_000.0
        for i in range(5):
            b.적기("forum", "A", False, t + i)
        assert b.쉬는중("forum", "A", t + 5) > 0
        b.적기("forum", "A", True, t + 5, 3.2)
        assert b.쉬는중("forum", "A", t + 6) == 0, "살아났는데 아직 쉰다"
    finally:
        b.close()


def test_거를것이_볼것과_쉰것을_가른다():
    b = _자취()
    try:
        t = 1_000_000.0
        for i in range(4):
            b.적기("forum", "죽은것", False, t + i)
        볼것, 쉰것 = b.거를것("forum", [_가짜줄("죽은것"), _가짜줄("산것")], t + 4)
        assert [x.page_id for x in 볼것] == ["산것"], [x.page_id for x in 볼것]
        assert [x.page_id for x in 쉰것] == ["죽은것"]
    finally:
        b.close()


def test_갈래가_다르면_따로_센다():
    b = _자취()
    try:
        t = 1_000_000.0
        for i in range(4):
            b.적기("forum", "A", False, t + i)
        assert b.쉬는중("forum", "A", t + 4) > 0
        assert b.쉬는중("ransom", "A", t + 4) == 0, "갈래를 안 가르고 있다"
    finally:
        b.close()


def test_걸린초가_쌓인다():
    """시간 제한과 동시 수를 짐작이 아니라 재서 정하려는 것입니다."""
    b = _자취()
    try:
        t = 1_000_000.0
        for i, 초 in enumerate([1.5, 4.0, 12.0]):
            b.적기("forum", f"P{i}", True, t, 초)
        assert b.걸린초분포("forum") == [1.5, 4.0, 12.0]
    finally:
        b.close()


def test_쉰_줄은_노션을_안_건드린다():
    """`_조사` 에 안 들어가면 `반영` 도 안 불립니다.

    「오늘 봤는데 죽어 있었다」와 「오늘 안 봤다」는 다릅니다. 쉰 줄의
    확인일이 바뀌면 명부가 거짓말을 합니다.
    """
    글 = (ROOT / "hub" / "places" / "run.py").read_text(encoding="utf-8")
    자리 = 글[글.index("자취 = 두드림기록"):글.index("본것: list[Place] = []")]
    assert "거를것" in 자리 and "r.쉰것" in 자리
    # 쉰것을 본것에 도로 넣는 코드가 없어야 합니다
    assert "볼것 + 쉰것" not in 글 and "볼것.extend(쉰것)" not in 글


def test_쉰_줄_수를_화면에_적는다():
    """조용히 건너뛰면 「다 봤다」로 읽힙니다."""
    from hub.places.run import 갈래결과, 표로
    r = 갈래결과(갈래="forum", 본것=10, 쉰것=120)
    글 = 표로([r], apply=False)
    assert "쉰 줄 120" in 글, 글


def test_dls_fill_이_쓴_줄을_갈아_끼운다():
    """겹쳐 쌓이지 않게 하는 안전망입니다.

    dls_fill 을 노션에 안 쓰기로 했지만, 사람이 실수로 --apply 를 줄 수
    있습니다. 그때 크롤러가 자기 줄을 하나 더 붙이면 같은 뜻이 두 줄이
    됩니다. 373줄에 실제로 그런 일이 있었습니다.

    dls_fill 의 세 꼴은 코드에서 확인한 것입니다.
        피해자 {n}건 (최근 {m}개월)                     규모
        업종 ... / 국가 ... (최근 {m}개월 {n}건)         피해 대상
        있음 - {n}건 (최근 {m}개월)                     한국 관련 유출
    """
    from hub.places.place import 규모합치기, 기계가_쓴_줄
    for 옛줄 in ("피해자 12건 (최근 6개월)",
               "업종 Technology(3) / 국가 US(1) (최근 6개월 5건)",
               "있음 - 2건 (최근 6개월)"):
        assert 기계가_쓴_줄(옛줄), 옛줄
        새 = "피해 기업 40 (2026-08-30 기준)"
        r = 규모합치기(옛줄, 새)
        assert r == 새, f"쌓였다: {r!r}"


def test_사람이_쓴_줄은_그대로_둔다():
    """안전망이 사람 글까지 갈아 끼우면 더 나쁩니다."""
    from hub.places.place import 규모합치기, 기계가_쓴_줄
    사람 = "구독자 1,440명 (2026.08.04 13:32 GMT+9 기준)"
    assert not 기계가_쓴_줄(사람), "사람 글을 기계 줄로 봤다"
    r = 규모합치기(사람, "피해 기업 40 (2026-08-30 기준)")
    assert 사람 in r, r


def test_확인일은_한국_시간이다():
    """크롤러가 도는 칼리 VM 이 미국 동부시(EDT)였습니다.

    한국보다 13시간 뒤라 「2026-08-30 새벽에 봤다」가 노션에
    **2026-08-29 로 적혔습니다.** 오류가 안 나고 날짜만 하루 밀립니다.
    명부를 읽는 사람은 「어제 봤구나」 하고 넘어갑니다.

    실제로 8/30 반영분 82줄이 8/29 로 적혔습니다.
    """
    import os
    from datetime import datetime, timedelta, timezone
    from hub.places.place import 지금, 오늘, KST

    assert KST == timezone(timedelta(hours=9)), KST

    # 기계 시간대를 바꿔도 안 흔들려야 합니다
    옛 = os.environ.get("TZ")
    try:
        for tz in ("America/New_York", "UTC", "Asia/Seoul"):
            os.environ["TZ"] = tz
            try:
                import time as _t
                _t.tzset()                      # 윈도우에는 없습니다
            except AttributeError:
                pass
            assert 지금().endswith("+09:00"), f"{tz} 에서 {지금()}"
            assert 오늘() == datetime.now(KST).date()
    finally:
        os.environ.pop("TZ", None)
        if 옛 is not None:
            os.environ["TZ"] = 옛
        try:
            import time as _t
            _t.tzset()
        except AttributeError:
            pass


def test_달을_세는_쪽도_같은_날을_본다():
    """`ransom.py` 가 date.today() 를 쓰면 기계 시간대를 따릅니다.

    확인일만 고치고 이쪽을 놔두면, 자정 언저리에 **확인일과 집계 기간이
    하루 어긋납니다.**
    """
    글 = (ROOT / "hub" / "places" / "probe" / "ransom.py").read_text(encoding="utf-8")
    assert "date.today()" not in 글, "기계 시간대의 오늘을 씁니다"
    assert "_오늘()" in 글, "한국 기준 오늘을 안 씁니다"

if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_"):
            v(); print(f"  OK  {k}"); n += 1
    print(f"\n{n}개 통과")
