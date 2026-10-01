"""디코 아침 브리핑(`skills/collect/brief.py`) — 시험. **노션에도 디스코드에도 안 붙는다.**

    python packages/tests/test_brief.py          CI 가 이렇게 돌린다

2026-10-01. 지난 하루 수집 DB 에 새로 들어온 사건을 웹후크로 올린다. 보내기 전에 웹후크가 브리핑 채널을
가리키는지 GET 으로 본다(9/22 옛 웹후크는 다른 채널이었다). 조직명 · 제목 · 핸들 · 주소는 문안에 안 싣는다.
레포가 공개라 로그에는 건수와 「맞음 / 틀림」 만 찍는다. 조직명 · 주소는 지어낸 것이다.

**실행부를 둔다.** CI 는 이 폴더를 `python 파일` 로 돌린다.
"""
from __future__ import annotations

import contextlib
import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packages"))

sys.path.insert(0, str(ROOT / "skills"))
from collect import brief  # noqa: E402

지금 = datetime(2026, 10, 2, 9, 0, tzinfo=brief.KST)
가짜주소 = "https://discord.com/api/webhooks/123/secret-token-not-real"


def _글(v):
    return [{"plain_text": v}] if v else []


def _줄(번호, 검토="미검토", 업종="", 국가="", 규모="", 조직="가짜조직주식회사", 제목="가짜 유출 제목",
       핸들="fakehandle", 소스="텔레그램", 게시처="fakegroup", 한국="미확인"):
    return {"properties": {
        "사건 ID": {"type": "unique_id", "unique_id": {"prefix": "LEAK", "number": 번호}},
        "검토 여부": {"type": "select", "select": {"name": 검토}},
        "산업 분야": {"type": "select", "select": {"name": 업종} if 업종 else None},
        "국가": {"type": "select", "select": {"name": 국가} if 국가 else None},
        "주장 규모": {"type": "rich_text", "rich_text": _글(규모)},
        "대상 조직": {"type": "rich_text", "rich_text": _글(조직)},
        "자료 제목": {"type": "title", "title": _글(제목)},
        "게시자 핸들": {"type": "rich_text", "rich_text": _글(핸들)},
        "게시 플랫폼": {"type": "rich_text", "rich_text": _글("victim-example.test")},
        "소스": {"type": "select", "select": {"name": 소스}},
        "게시처": {"type": "select", "select": {"name": 게시처}},
        "한국 관련": {"type": "select", "select": {"name": 한국}},
    }}


def test_문안에_조직명_제목_핸들_주소가_없다():
    줄들 = [_줄(1, 업종="제조", 국가="미국", 규모="120GB"), _줄(2)]
    for 꼴 in (brief.문안, brief.집계문안):
        글, _ = 꼴(줄들, 지금)
        for 안됨 in ("가짜조직주식회사", "가짜 유출 제목", "fakehandle", "victim-example.test"):
            assert 안됨 not in 글, (꼴.__name__, 안됨)
    글, _ = brief.문안(줄들, 지금)
    assert "LEAK-1 · 제조 · 미국 · 120GB" in 글, 글
    assert "LEAK-2 · 업종 — · 국가 — · 규모 —" in 글, 글


def test_사건_X_는_건수에만_넣고_목록에서_뺀다():
    글, 셈 = brief.문안([_줄(1), _줄(2, 검토="사건 X"), _줄(3, 검토="사건 O")], 지금)
    assert "LEAK-2" not in 글 and "LEAK-1" in 글 and "LEAK-3" in 글, 글
    assert 셈["사건 X"] == 1 and "새로 들어온 사건 3건" in 글, (셈, 글)


def test_디스코드_상한_안에서_자르고_외_N건을_붙인다():
    줄들 = [_줄(i, 업종="제조업 " * 3, 국가="미국", 규모="1.2TB 고객 정보 " * 3) for i in range(1, 200)]
    글, 셈 = brief.문안(줄들, 지금)
    assert len(글) <= 2000, len(글)
    남은 = re.search(r"외 (\d+)건", 글)
    assert 남은 and int(남은.group(1)) == 셈["목록"] - 셈["실린 줄"], (남은, 셈)


def test_새_사건이_없으면_그렇게_적는다():
    for 꼴 in (brief.문안, brief.집계문안):
        글, _ = 꼴([], 지금)
        assert "새로 들어온 사건이 없습니다" in 글


def test_집계_꼴은_차_있는_칸으로_센다():
    줄들 = [_줄(344, 게시처="grpA"), _줄(345, 게시처="grpA"), _줄(347, 게시처="grpB", 국가="한국", 한국="직접")]
    글, _ = brief.집계문안(줄들, 지금)
    assert "LEAK-344 ~ LEAK-347 사이 3건(빈 번호 1)" in 글, 글
    assert "게시처  grpA 2 · grpB 1" in 글, 글
    assert "업종 · 국가 · 규모가 찬 줄  1 / 3" in 글, 글


class _응답:
    def __init__(self, 몸=b"", status=200):
        self.몸, self.status = 몸, status

    def read(self):
        return self.몸

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _찍힌것(f, *a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        r = f(*a, **k)
    return r, buf.getvalue()


def test_웹후크_채널이_맞으면_맞음_틀리면_틀림만_찍는다():
    받은 = []

    def 맞는곳(req, timeout=0):
        받은.append(req.get_method())
        return _응답(json.dumps({"channel_id": brief.브리핑채널, "token": "x"}).encode())

    def 다른곳(req, timeout=0):
        return _응답(json.dumps({"channel_id": "999"}).encode())

    r, 찍힘 = _찍힌것(brief.채널확인, 가짜주소, opener=맞는곳)
    assert r is True and 찍힘.strip() == "웹후크 채널 확인: 맞음", 찍힘
    assert 받은 == ["GET"], "확인은 GET 이라 글이 안 올라가야 한다"
    r, 찍힘 = _찍힌것(brief.채널확인, 가짜주소, opener=다른곳)
    assert r is False and 찍힘.strip() == "웹후크 채널 확인: 틀림", 찍힘
    for 안됨 in ("discord.com", "secret-token", brief.브리핑채널, "999"):
        assert 안됨 not in 찍힘


def test_보낼_때_멘션을_끈다():
    받은 = {}

    def 받기(req, timeout=0):
        받은["method"] = req.get_method()
        받은["몸"] = json.loads(req.data.decode("utf-8"))
        return _응답(status=204)

    r, 찍힘 = _찍힌것(brief.보내기, 가짜주소, "@everyone 시험", opener=받기)
    assert r is True and 받은["method"] == "POST"
    assert 받은["몸"]["allowed_mentions"] == {"parse": []}, 받은
    assert "discord.com" not in 찍힘 and "secret-token" not in 찍힘, 찍힘


def test_틀린_채널이면_보내지_않는다():
    부른것 = []
    옛확인, 옛보내기, 옛새줄, 옛훅 = brief.채널확인, brief.보내기, brief.새줄들, brief.웹후크
    brief.채널확인 = lambda 주소, opener=None: False
    brief.보내기 = lambda *a, **k: 부른것.append(1) or True
    brief.새줄들 = lambda n, 지금, 시간=24: [_줄(1)]
    brief.웹후크 = lambda: 가짜주소
    옛노션 = brief.Notion
    brief.Notion = lambda verbose=False: None
    try:
        r, _ = _찍힌것(brief.main, ["--요약만", "--보낸다"])
    finally:
        brief.채널확인, brief.보내기, brief.새줄들, brief.웹후크, brief.Notion = 옛확인, 옛보내기, 옛새줄, 옛훅, 옛노션
    assert r == 1 and 부른것 == [], (r, 부른것)


def test_요약만은_건수만_찍는다():
    옛새줄, 옛노션 = brief.새줄들, brief.Notion
    brief.새줄들 = lambda n, 지금, 시간=24: [_줄(41, 업종="제조", 국가="미국"), _줄(42)]
    brief.Notion = lambda verbose=False: None
    try:
        r, 찍힘 = _찍힌것(brief.main, ["--요약만"])
    finally:
        brief.새줄들, brief.Notion = 옛새줄, 옛노션
    assert r == 0 and 찍힘.startswith("새로 들어온 줄 2"), 찍힘
    for 안됨 in ("LEAK-41", "제조", "미국", "가짜조직주식회사"):
        assert 안됨 not in 찍힘, (안됨, 찍힘)


def test_워크플로는_손으로만_돌고_기본은_안_보낸다():
    글 = (ROOT / ".github" / "workflows" / "brief.yml").read_text(encoding="utf-8")
    assert "schedule:" not in 글, "예약은 최현서가 시각을 정한 뒤에 넣는다"
    assert re.search(r"send:\s*\n(?:.*\n)*?\s*default: false", 글), "보내기는 기본으로 꺼져 있어야 한다"
    assert "DISCORD_WEBHOOK: ${{ secrets.DISCORD_WEBHOOK }}" in 글
    assert 글.count("--요약만") >= 2, "공개 로그에는 건수만"
    assert "echo \"$DISCORD_WEBHOOK" not in 글 and "echo $DISCORD_WEBHOOK" not in 글


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
