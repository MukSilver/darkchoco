"""디코 아침 브리핑(`skills/collect/brief.py`) — 시험. **노션에도 디스코드에도 안 붙는다.**

    python packages/tests/test_brief.py          CI 가 이렇게 돌린다

2026-10-01 · 꼴 10/02(최현서). 지난 하루 수집 DB 에 새로 들어온 사건을 「LEAK-번호 · 조직명 · 행위자 · 한국 여부」 로
브리핑 채널에 한 번 올린다. 브리핑 채널은 팀원만 봐서 조직명을 싣지만, **공개 Actions 로그에는 건수와
「맞음 / 틀림」 만** 찍는다. 보내기가 실패해도 보낸 내용이 안 찍힌다. 개인 이름으로 보이는 대상은 가린다.
보내기 전에 웹후크가 브리핑 채널을 가리키는지 GET 으로 본다(9/22 옛 웹후크는 다른 채널이었다).

조직명 · 사람 이름 · 핸들 · 주소는 모두 지어낸 것이다.
**실행부를 둔다.** CI 는 이 폴더를 `python 파일` 로 돌린다.
"""
from __future__ import annotations

import contextlib
import io
import json
import re
import sys
import urllib.error
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


def _줄(번호, 조직="가짜조직주식회사", 핸들="FakeGroup", 게시처="fakegroup", 한국="직접", 검토="미검토",
       제목="가짜 유출 제목", 근거="", 국가=""):
    return {"properties": {
        "사건 ID": {"type": "unique_id", "unique_id": {"prefix": "LEAK", "number": 번호}},
        "검토 여부": {"type": "select", "select": {"name": 검토}},
        "대상 조직": {"type": "rich_text", "rich_text": _글(조직)},
        "게시자 핸들": {"type": "rich_text", "rich_text": _글(핸들)},
        "게시처": {"type": "select", "select": {"name": 게시처} if 게시처 else None},
        "한국 관련": {"type": "select", "select": {"name": 한국}},
        "자료 제목": {"type": "title", "title": _글(제목)},
        "게시 플랫폼": {"type": "rich_text", "rich_text": _글("t.me/fakechannel")},
        "한국 관련 근거": {"type": "rich_text", "rich_text": _글(근거)},
        "국가": {"type": "select", "select": {"name": 국가} if 국가 else None},
    }}


# ── 1. 꼴 — LEAK-번호 · 조직명 · 행위자 · 한국 여부 ─────────────
def test_한_줄_꼴():
    글, 셈 = brief.문안([_줄(1, 조직="Acme Holdings", 한국="직접"), _줄(2, 조직="Beta Clinic", 한국="간접")], 지금)
    assert "· LEAK-1 · Acme Holdings · FakeGroup · 한국 직접" in 글, 글
    assert "· LEAK-2 · Beta Clinic · FakeGroup · 한국 간접" in 글, 글
    assert "지난 24시간 새로 들어온 2건 중 한국 관련 2건" in 글 and 셈["실린 줄"] == 2, (글, 셈)
    assert "목록에서 뺀 것" not in 글, "뺀 것이 없으면 그 줄도 없다"


def test_한국은_직접_간접만_싣는다():
    for 값, 기대 in (("직접", "한국 직접"), ("간접", "한국 간접")):
        assert 기대 in brief.한줄(_줄(1, 한국=값))[0]
    for 값 in ("미확인", "", "아님"):
        assert "한국" not in brief.한줄(_줄(1, 조직="Acme Holdings", 한국=값))[0]


def test_검토_상태_제목_전한_채널은_안_싣는다():
    글, _ = brief.문안([_줄(1)], 지금)
    for 안됨 in ("미검토", "가짜 유출 제목", "t.me", "fakechannel"):
        assert 안됨 not in 글, 안됨


def test_사건_X_는_목록에서_빼고_머리에_건수만():
    글, 셈 = brief.문안([_줄(1), _줄(2, 검토="사건 X", 조직="Xco Holdings"), _줄(3)], 지금)
    assert "LEAK-2" not in 글 and "Xco Holdings" not in 글, 글
    assert "새로 들어온 3건 중 한국 관련 2건" in 글 and "목록에서 뺀 것: 한국과 무관(사건 X) 1건" in 글, 글
    assert 셈["사건 X"] == 1, 셈


# ── 2. 행위자 ────────────────────────────────────────────────
def test_행위자는_핸들_없으면_게시처():
    assert "· qilin" in brief.한줄(_줄(1, 핸들="", 게시처="qilin"))[0]
    for 자리 in ("-", "unknown", "없음"):
        assert "· qilin" in brief.한줄(_줄(1, 핸들=자리, 게시처="qilin"))[0], 자리
    assert "행위자 모름" in brief.한줄(_줄(1, 핸들="", 게시처=""))[0]


def test_텔레그램_주소_꼴은_행위자로_안_싣는다():
    줄, _ = brief.한줄(_줄(1, 핸들="https://t.me/relaychannel", 게시처="qilin"))
    assert "relaychannel" not in 줄 and "· qilin" in 줄, 줄


# ── 3. 개인 이름은 가린다 ────────────────────────────────────
def test_개인_이름으로_보이면_가린다():
    for 이름 in ("John Smith", "Maria J. Lopez", "Dr. Alan Brown", "someone@example.test", "홍길동"):
        줄, 가림 = brief.한줄(_줄(1, 조직=이름))
        assert 가림 and brief.가림말 in 줄 and 이름 not in 줄, (이름, 줄)


def test_조직으로_보이면_안_가린다():
    for 이름 in ("Acme Holdings", "Beta Clinic", "Den Hartog Industries", "Becker Logistik", "Vera Science",
                 "example-corp.test", "가짜병원", "가짜전자 주식회사", "Island", "SMCARE"):
        assert brief.개인이름같나(이름) is False, 이름


def test_이미_가린_값은_그대로_두고_서식을_무력화한다():
    줄, 가림 = brief.한줄(_줄(1, 조직="M****n"))
    assert not 가림 and "M\\*\\*\\*\\*n" in 줄, 줄


def test_가린_줄을_센다():
    _, 셈 = brief.문안([_줄(1, 조직="John Smith"), _줄(2, 조직="Acme Holdings")], 지금)
    assert 셈["가린 줄"] == 1, 셈


# ── 4. 2000자 ────────────────────────────────────────────────
def test_디스코드_상한_안에서_자르고_그_밖_N건():
    줄들 = [_줄(i, 조직="Very Long Organisation Holdings International " * 2) for i in range(1, 200)]
    글, 셈 = brief.문안(줄들, 지금)
    assert len(글) <= 2000, len(글)
    남은 = re.search(r"그 밖 (\d+)건은 대시보드에서", 글)
    assert 남은 and int(남은.group(1)) == 셈["목록"] - 셈["실린 줄"], (남은, 셈)


def test_새_사건이_없으면_그렇게_적는다():
    글, _ = brief.문안([], 지금)
    assert "새로 들어온 0건 중 한국 관련 0건" in 글 and "한국 관련으로 보이는 새 사건이 없습니다" in 글, 글


# ── 4-0. 목록에는 확실한 한국 건만 (10/02 최현서) ─────────────
def test_갈래():
    assert brief.갈래(_줄(1, 한국="직접")) == "목록"
    assert brief.갈래(_줄(1, 한국="간접")) == "목록"
    assert brief.갈래(_줄(1, 한국="미확인", 검토="사건 O")) == "목록", "사람이 사건 O 로 정한 줄은 싣는다"
    assert brief.갈래(_줄(1, 한국="직접", 검토="사건 X")) == "무관", "사건 X 가 먼저다"
    assert brief.갈래(_줄(1, 한국="미확인")) == "신호 없음"
    assert brief.갈래(_줄(1, 한국="미확인", 근거="한국 도메인(.kr) — 본문")) == "미확인"
    assert brief.갈래(_줄(1, 한국="미확인", 국가="일본")) == "미확인", "국가가 적혔으면 「국가 미상」 이 아니다"


def test_확실한_한국_건만_싣고_나머지는_건수만():
    줄들 = [_줄(1, 조직="Acme Holdings", 한국="직접"),
           _줄(2, 조직="Unknownland Steel", 한국="미확인"),
           _줄(3, 조직="Unknownland Foods", 한국="미확인"),
           _줄(4, 조직="Weak Signal Corp", 한국="미확인", 근거="본문에 korea 한 번"),
           _줄(5, 조직="Xco Holdings", 한국="미확인", 검토="사건 X")]
    글, 셈 = brief.문안(줄들, 지금, "https://fake-dash.example.test")
    assert "LEAK-1 · Acme Holdings" in 글, 글
    for 안됨 in ("LEAK-2", "LEAK-3", "LEAK-4", "LEAK-5", "Unknownland", "Weak Signal", "Xco"):
        assert 안됨 not in 글, (안됨, 글)
    assert "새로 들어온 5건 중 한국 관련 1건" in 글, 글
    assert ("목록에서 뺀 것: 국가 미상 · 한국 신호 없음 2건 · 한국 여부 미확인 1건 · 한국과 무관(사건 X) 1건"
            in 글), 글
    assert 글.endswith("자세한 내용: <https://fake-dash.example.test>"), "링크가 맨 끝이다"
    assert (셈["신호 없음"], 셈["미확인"], 셈["사건 X"], 셈["목록"]) == (2, 1, 1, 1), 셈


def test_목록이_비어도_뺀_건수와_링크는_적는다():
    글, _ = brief.문안([_줄(1, 한국="미확인"), _줄(2, 한국="미확인")], 지금, "https://fake-dash.example.test")
    assert "한국 관련으로 보이는 새 사건이 없습니다" in 글, 글
    assert "국가 미상 · 한국 신호 없음 2건" in 글 and 글.endswith("<https://fake-dash.example.test>"), 글


# ── 4-1. 끝에 대시보드 링크 (10/02) ──────────────────────────
가짜대시 = "https://fake-dash.example.test"


def test_끝에_자세한_내용_링크를_붙인다():
    글, _ = brief.문안([_줄(1)], 지금, 가짜대시)
    assert 글.endswith(f"\n자세한 내용: <{가짜대시}>"), 글
    글, _ = brief.문안([], 지금, 가짜대시)
    assert 글.endswith(f"자세한 내용: <{가짜대시}>"), "새 사건이 없어도 링크는 붙는다"
    글, _ = brief.문안([_줄(1)], 지금)
    assert "자세한 내용" not in 글, "링크가 없으면 줄째 뺀다"


def test_링크를_붙여도_상한_안이고_링크가_잘리지_않는다():
    줄들 = [_줄(i, 조직="Very Long Organisation Holdings International " * 2) for i in range(1, 200)]
    글, 셈 = brief.문안(줄들, 지금, 가짜대시)
    assert len(글) <= brief.상한 and 글.endswith(f"<{가짜대시}>"), len(글)
    남은 = re.search(r"그 밖 (\d+)건은 대시보드에서", 글)
    assert 남은 and int(남은.group(1)) == 셈["목록"] - 셈["실린 줄"], (남은, 셈)


def test_대시보드_링크는_https_꼴만_받는다():
    옛 = brief.os.environ.get("DASH_URL")
    try:
        for 값, 기대 in ((가짜대시, 가짜대시), ("  " + 가짜대시 + "\n", 가짜대시), ("", ""),
                         ("http://fake-dash.example.test", ""), ("https://a b", ""), ("https://x>y", "")):
            brief.os.environ["DASH_URL"] = 값
            assert brief.대시보드링크() == 기대, 값
    finally:
        if 옛 is None:
            brief.os.environ.pop("DASH_URL", None)
        else:
            brief.os.environ["DASH_URL"] = 옛


# ── 5. 로그에는 건수와 맞음 / 틀림만 ─────────────────────────
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


def test_요약만은_건수만_찍는다():
    옛새줄, 옛노션 = brief.새줄들, brief.Notion
    brief.새줄들 = lambda n, 지금, 시간=24, 시작=None: [_줄(41, 조직="Acme Holdings", 한국="직접"), _줄(42, 조직="John Smith")]
    brief.Notion = lambda verbose=False: None
    try:
        r, 찍힘 = _찍힌것(brief.main, ["--요약만"])
    finally:
        brief.새줄들, brief.Notion = 옛새줄, 옛노션
    assert r == 0 and 찍힘.startswith("새 줄 2"), 찍힘
    for 안됨 in ("LEAK-41", "Acme", "John", "FakeGroup", "직접"):
        assert 안됨 not in 찍힘, (안됨, 찍힘)


def test_요약만은_대시보드_주소를_안_찍고_있음만_찍는다():
    옛새줄, 옛노션, 옛링크 = brief.새줄들, brief.Notion, brief.대시보드링크
    brief.새줄들 = lambda n, 지금, 시간=24, 시작=None: [_줄(41)]
    brief.Notion = lambda verbose=False: None
    brief.대시보드링크 = lambda: 가짜대시
    try:
        r, 찍힘 = _찍힌것(brief.main, ["--요약만"])
    finally:
        brief.새줄들, brief.Notion, brief.대시보드링크 = 옛새줄, 옛노션, 옛링크
    assert r == 0 and "링크 있음" in 찍힘, 찍힘
    assert "fake-dash" not in 찍힘 and "https" not in 찍힘, 찍힘


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

    r, 찍힘 = _찍힌것(brief.보내기, 가짜주소, "@everyone Acme Holdings", opener=받기)
    assert r is True and 받은["method"] == "POST"
    assert 받은["몸"]["allowed_mentions"] == {"parse": []}, 받은
    assert "Acme" not in 찍힘 and "discord.com" not in 찍힘, 찍힘


def test_보내기가_실패해도_보낸_내용이_안_찍힌다():
    글 = "· LEAK-1 · Acme Holdings · FakeGroup"

    def http_실패(req, timeout=0):
        raise urllib.error.HTTPError(가짜주소, 400, "Bad Request " + 글, {}, io.BytesIO(글.encode()))

    def 다른_실패(req, timeout=0):
        raise ValueError("payload was: " + req.data.decode("utf-8"))

    for 실패 in (http_실패, 다른_실패):
        r, 찍힘 = _찍힌것(brief.보내기, 가짜주소, 글, opener=실패)
        assert r is False, 실패
        for 안됨 in ("Acme", "LEAK-1", "FakeGroup", "discord.com", "secret-token"):
            assert 안됨 not in 찍힘, (실패.__name__, 찍힘)


def test_틀린_채널이면_보내지_않는다():
    부른것 = []
    옛 = (brief.채널확인, brief.보내기, brief.새줄들, brief.웹후크, brief.Notion)
    brief.채널확인 = lambda 주소, opener=None: False
    brief.보내기 = lambda *a, **k: 부른것.append(1) or True
    brief.새줄들 = lambda n, 지금, 시간=24, 시작=None: [_줄(1)]
    brief.웹후크 = lambda: 가짜주소
    brief.Notion = lambda verbose=False: None
    try:
        r, _ = _찍힌것(brief.main, ["--요약만", "--보낸다"])
    finally:
        brief.채널확인, brief.보내기, brief.새줄들, brief.웹후크, brief.Notion = 옛
    assert r == 1 and 부른것 == [], (r, 부른것)


def test_워크플로는_수집_검증_뒤에_불리고_손으로는_기본이_안_보낸다():
    글 = (ROOT / ".github" / "workflows" / "brief.yml").read_text(encoding="utf-8")
    # 10/03 최현서 「디코는 자동 수집 주기에 맞춰 매번」 · 「검증 이후로」. 수집 또는 판정이 send=true 로 부른다
    assert "workflow_run:" not in 글 and "- cron:" not in 글, "스스로 깨지 않는다. 수집 · 판정이 부른다"
    assert "run-name: ${{ inputs.send && '브리핑 보냄' || '브리핑 시험' }}" in 글
    assert "SEND: ${{ inputs.send && 'yes' || 'no' }}" in 글
    assert 'select(.displayTitle == "브리핑 보냄" or .event == "schedule")' in 글, "범위는 마지막으로 보낸 판부터. 손 시험 판은 안 센다"
    assert "CANDIDATES: ${{ inputs.candidates }}" in 글 and '--후보 "$CANDIDATES"' in 글, "후보 번호는 env 로만 넘긴다"
    assert "${{ inputs.candidates }}\"" not in 글 and "python skills/collect/brief.py --후보 ${{" not in 글
    수집 = (ROOT / ".github" / "workflows" / "collect.yml").read_text(encoding="utf-8")
    assert "if: steps.fire.outputs.fired != 'yes'" in 수집 and "gh workflow run brief.yml" in 수집, "판정을 못 부른 판은 수집이 브리핑을 부른다"
    assert re.search(r"send:\s*\n(?:.*\n)*?\s*default: false", 글), "손으로 돌릴 때 보내기는 기본으로 꺼져 있어야 한다"
    assert "DISCORD_WEBHOOK: ${{ secrets.DISCORD_WEBHOOK }}" in 글
    assert "DASH_URL: ${{ secrets.DASH_URL }}" in 글, "대시보드 주소는 비밀값으로만 넘긴다"
    assert "workers.dev" not in 글
    부르기 = re.findall(r"(?m)^\s+python skills/collect/brief\.py[^\n]*", 글)
    assert 부르기 and all("--요약만" in x for x in 부르기), 부르기
    assert "echo \"$DISCORD_WEBHOOK" not in 글 and "echo $DISCORD_WEBHOOK" not in 글


def test_시작시각은_48시간_안의_지난_시각만_받는다():
    지금 = datetime(2026, 10, 3, 20, 0, tzinfo=brief.KST)
    assert brief.시작시각("2026-10-03T05:00:00Z", 지금) is not None
    assert brief.시작시각("", 지금) is None
    assert brief.시작시각("꼴이 틀림", 지금) is None
    assert brief.시작시각("2026-09-30T00:00:00Z", 지금) is None, "48시간보다 오래면 지난 24시간으로"
    assert brief.시작시각("2026-10-04T00:00:00Z", 지금) is None, "미래는 안 받는다"
    assert brief.시작시각("2026-10-03T05:00:00", 지금) is None, "시간대가 없으면 안 받는다"


def test_후보_번호는_LEAK_꼴만_열개까지():
    assert brief.후보번호("LEAK-451,LEAK-460") == [451, 460]
    assert brief.후보번호("") == []
    assert brief.후보번호("LEAK-1, LEAK-1, x; rm -rf / LEAK-2") == [1, 2]
    assert len(brief.후보번호(",".join(f"LEAK-{i}" for i in range(30)))) == brief.후보상한


def test_AI_후보는_따로_싣고_목록과_겹치면_뺀다():
    지금 = datetime(2026, 10, 3, 20, 0, tzinfo=brief.KST)
    목록줄 = _줄(41, 조직="Acme Holdings", 한국="직접")
    후보줄 = _줄(42, 조직="Beta Corp")
    글, 셈 = brief.문안([목록줄], 지금, "", "10/03 14:00 뒤", [후보줄, 목록줄])
    assert "AI 판정 한국 후보(사람 확정 전)" in 글 and "LEAK-42" in 글, 글
    assert 글.count("LEAK-41") == 1, "목록에 이미 있는 줄은 후보에 다시 싣지 않는다"
    assert 셈["AI 후보"] == 1
    글0, 셈0 = brief.문안([], 지금, "", "10/03 14:00 뒤", [후보줄])
    assert "LEAK-42" in 글0 and 셈0["AI 후보"] == 1, "새 줄이 없어도 후보는 싣는다"


def test_머리에_범위를_적는다():
    지금 = datetime(2026, 10, 3, 20, 0, tzinfo=brief.KST)
    글, _ = brief.문안([], 지금, "", "10/03 14:00 뒤")
    assert "수집 브리핑" in 글 and "10/03 14:00 뒤 새로 들어온 0건" in 글, 글


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
