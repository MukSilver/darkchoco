"""명부 조사기 셋을 가짜 응답으로 확인합니다.

    python packages/tests/test_crawler.py

밖에 요청을 보내지 않습니다. 응답을 가로채 미리 만든 것을 돌려줍니다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages"))
sys.path.insert(0, str(ROOT))

from dc_console import use_utf8  # noqa: E402

use_utf8()

from hub.crawler.place import Place, 규모합치기, 기계가_쓴_줄  # noqa: E402
from hub.crawler.probe import forum, ransom, telegram  # noqa: E402

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


def test_같은_줄은_두_번_안_넣는다():
    줄 = "구독자 8,145 (2026-08-28 기준)"
    assert 규모합치기(줄, 줄) == 줄


def test_사람이_쓴_옛_형식은_기계_줄이_아니다():
    """이것을 기계 줄로 보면 사람이 적은 시각 정보가 사라진다."""
    assert not 기계가_쓴_줄("구독자 1,440명 (2026.08.04 13:32 GMT+9 기준)")
    assert not 기계가_쓴_줄("8145")
    assert not 기계가_쓴_줄(사람글)
    assert 기계가_쓴_줄("구독자 8,145 (2026-08-28 기준)")
    assert 기계가_쓴_줄("회원 349,000 · 게시물 821,000 (2026-08-28 기준)")


# ── 노션에 넣는 값 ──────────────────────────────────────────────────
def test_노션_칸을_안_늘린다():
    """다크웹 DB 스키마가 RAG 의 근간이라 기존 칸만 써야 한다."""
    기존칸 = {"상태", "규모", "확인일", "주소", "어니언 주소", "형식", "종류", "최근 활동"}
    for 갈래 in ("forum", "telegram", "ransom"):
        p = Place(갈래=갈래, 이름="x", 상태="online", 구독자수=10,
                  회원수=20, 게시물수=30, 피해기업수=40,
                  주소="https://x", 어니언="http://y.onion",
                  형식="RaaS", 종류="group", 최근활동="2026-08-28T00:00:00")
        칸 = set(p.노션값())
        assert 칸 <= 기존칸, f"{갈래}: 없는 칸을 쓴다 — {칸 - 기존칸}"


def test_못_봤으면_상태를_안_건드린다():
    """틀린 값을 남기느니 옛 값을 두는 편이 낫다."""
    p = Place(갈래="forum", 이름="x", 못본이유="Tor 가 없습니다")
    assert p.노션값() == {}, p.노션값()


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
    telegram._받기 = lambda url, m: (200, 본문)
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
    telegram._받기 = lambda url, m: (404, "")
    try:
        p = telegram.한곳("@없는채널", [0.0])
    finally:
        telegram._받기 = 옛
    assert p.상태 == "offline"
    assert p.못본이유, "왜 못 봤는지가 비어 있다"


def test_텔레그램_수를_못_보면_미확인이다():
    """없음이 아니라 미확인이다. 그 둘은 다르다."""
    옛 = telegram._받기
    telegram._받기 = lambda url, m: (200, "<html>아무것도 없음</html>")
    try:
        p = telegram.한곳("@조용한채널", [0.0])
    finally:
        telegram._받기 = 옛
    assert p.상태 == "미확인", p.상태
    assert "실계정" in p.못본이유, p.못본이유
    assert p.노션값() == {}, "못 봤는데 노션에 쓰려 한다"


def test_랜섬_그룹_목록을_읽는다():
    가짜 = [
        {"name": "LockBit3", "victims": 412, "type": "ransomware",
         "locations": [{"fqdn": "http://lb.onion"}],
         "available": True, "lastseen": "2026-08-27T12:00:00"},
        {"name": "SomeMarket", "type": "market", "available": False},
        {"noname": 1},
    ]
    옛 = ransom._받기
    ransom._받기 = lambda url, m: 가짜
    try:
        out = list(ransom.조사())
    finally:
        ransom._받기 = 옛
    assert len(out) == 2, [p.이름 for p in out]
    a, b = out
    assert a.이름 == "LockBit3" and a.상태 == "online"
    assert a.피해기업수 == 412 and a.형식 == "RaaS"
    assert a.주소 == "http://lb.onion"
    assert b.상태 == "offline" and b.형식 == "포럼·마켓"
    assert "피해 기업 412" in a.노션값()["규모"]


def test_랜섬_목록을_못_받으면_이유가_남는다():
    옛 = ransom._받기
    def 터짐(url, m):
        raise OSError("연결 안 됨")
    ransom._받기 = 터짐
    try:
        out = list(ransom.조사())
    finally:
        ransom._받기 = 옛
    assert len(out) == 1 and out[0].못본이유, out


def test_포럼_어니언은_Tor_없이_안_본다():
    out = list(forum.조사([{"이름": "X", "주소": "http://abc.onion"}]))
    assert len(out) == 1
    assert "Tor" in out[0].못본이유, out[0].못본이유
    assert out[0].노션값() == {}


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_"):
            v(); print(f"  OK  {k}"); n += 1
    print(f"\n{n}개 통과")
