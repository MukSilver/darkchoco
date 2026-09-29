"""수집 DB 「게시처」 를 정하는 규칙 — 시험. **노션에 안 붙습니다.**

    python packages/tests/test_게시처.py          CI 가 이렇게 돌린다

2026-09-25 최현서 결정. 게시처는 9/22 에 한 번 채운 뒤로 아무도 안 써서 새 줄이 비었다.
이제 수집(push.py)과 대시보드 포럼 사건(api.py · worker.js)이 줄을 만들 때 같이 쓴다.
규칙은 `hub/events/publisher.py` 한 곳에 있고, worker.js 에 포럼 쪽이 JS 로 한 벌 더 있다.

**실행부를 둔다.** CI 는 이 폴더를 `python 파일` 로 돌린다.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packages"))
sys.path.insert(0, str(ROOT / "apps" / "dash"))

import api  # noqa: E402
from hub.events import publisher as pub  # noqa: E402
from hub.events import push  # noqa: E402

워커 = ROOT / "apps" / "dash" / "deploy" / "worker.js"


def _글(v: str) -> dict:
    return {"type": "rich_text", "rich_text": [{"plain_text": v}] if v else []}


def _쪽(이름: str, 제목칸: str, *, 주소: str = "", 이전: str = "", 어니언: str = "",
       별칭: str = "", 담당자: str = "") -> dict:
    """명부 한 줄. 값은 지어낸 것이다."""
    return {"properties": {
        제목칸: {"type": "title", "title": [{"plain_text": 이름}]},
        "주소": {"type": "url", "url": 주소 or None},
        "이전 주소": _글(이전), "어니언 주소": _글(어니언), "이전 이름·별칭": _글(별칭),
        "담당자": {"type": "select", "select": {"name": 담당자} if 담당자 else None},
    }}


랜섬 = [_쪽("Cl0p", "그룹 이름", 별칭="CLOP / CL0P^_- LEAKS"),
        _쪽("LockBit", "그룹 이름", 주소="http://lockbitexampleaaaa.onion"),
        _쪽("qilin", "그룹 이름")]
포럼 = [_쪽("BreachForums (bf.st)", "포럼 이름", 주소="https://bf.st/"),
        _쪽("PwnForums", "포럼 이름", 주소="https://pwnforums.example/",
            어니언="pwnexampleonionaaaa.onion"),
        # 채널 주소가 적힌 포럼 줄. t.me 가 열쇠가 되면 CTI 채널 줄이 여기 붙는다
        _쪽("어떤포럼", "포럼 이름", 주소="https://t.me/some_forum_channel"),
        # 자동 줄은 찾기 표에 안 넣는다
        _쪽("가짜자동", "포럼 이름", 주소="https://auto.example/", 담당자="자동")]
텔레 = [_쪽("osint_cti 채널", "채널 이름", 주소="https://t.me/osint_cti")]


def _표():
    return pub.명부표([("랜섬", "그룹 이름", 랜섬), ("포럼", "포럼 이름", 포럼), ("텔레", "채널 이름", 텔레)])


# ── 소스마다 무엇으로 맞추나 ───────────────────────────────────────
def test_X_는_게시처를_안_채운다():
    """X 는 집계 계정 글이라 게시처를 비운다 (DEV 9/26 X 절 · 인계 H-8, 2026-09-29).

    주소가 명부에 있는 포럼이어도, 핸들이 명부 그룹이어도 안 채운다. 전에는 랜섬 갈래로 떨어져
    주소 → 표기 → 핸들로 채우고, 못 맞추면 핸들에 「명부 없음」 까지 켰다."""
    표 = _표()
    for 표기, 핸들 in (("https://bf.st/Thread-x", "Clop"), ("x.com/어느계정", "Qilin"), ("", "")):
        assert pub.고르기(표, "X", 표기, 핸들)[0] == "", (표기, 핸들)
        assert pub.속성(표, [], "X", 표기, 핸들) == {}, (표기, 핸들)
    줄 = {"source": "x", "venue": "bf.st", "actor": "Clop"}
    assert push.게시처칸(_표(), [], 줄) == {}


def test_텔레그램은_핸들로만_맞춘다():
    표 = _표()
    assert pub.고르기(표, "텔레그램", "t.me/osint_cti", "Clop")[:1] == ("Cl0p",)
    # 게시 플랫폼이 채널 주소여도 그것으로 안 맞춘다. 핸들이 곧 그룹이다
    assert pub.고르기(표, "텔레그램", "t.me/osint_cti", "")[0] == ""
    assert pub.고르기(표, "텔레그램", "https://bf.st/x", "Qilin")[0] == "qilin"


def test_t_me_는_주소_열쇠가_아니다():
    """9/22 도구의 함정. t.me 가 열쇠면 CTI 채널 줄 32개가 한 곳에 붙는다."""
    표 = _표()
    assert "t.me" not in 표.주소
    assert pub.고르기(표, "포럼", "t.me/osint_cti", "")[0] == ""


def test_핸들은_별칭과_꼬리_뗌까지만_정확히_맞춘다():
    표 = _표()
    assert pub.고르기(표, "텔레그램", "", "CL0P^_- LEAKS")[0] == "Cl0p"      # 별칭
    assert pub.고르기(표, "텔레그램", "", "LockBit3")[:2] == ("LockBit", "핸들(꼬리 뗌)")
    # 낱말이 박혀 있는 것으로는 안 맞춘다
    assert pub.고르기(표, "텔레그램", "", "clop affiliate")[0] == "clop affiliate"


def test_명부에_없는_핸들은_그대로_쓰고_명부_없음을_켠다():
    이름, 어떻게, 있나 = pub.고르기(_표(), "텔레그램", "", "Zawoo")
    assert (이름, 있나) == ("Zawoo", False), (이름, 어떻게)
    p = pub.속성(_표(), [], "텔레그램", "", "Zawoo")
    assert p == {"게시처": {"select": {"name": "Zawoo"}}, "명부 없음": {"checkbox": True}}


def test_포럼은_주소와_표기_이름으로만_맞춘다():
    표 = _표()
    assert pub.고르기(표, "포럼", "bf.st", "글쓴이")[0] == "BreachForums (bf.st)"
    assert pub.고르기(표, "포럼", "pwnexampleonionaaaa.onion", "")[0] == "PwnForums"   # 어니언 주소
    assert pub.고르기(표, "포럼", "PwnForums", "")[0] == "PwnForums"                   # 표기 이름
    # 못 맞추면 비운다. 글쓴이 핸들을 게시처로 쓰지 않는다
    assert pub.고르기(표, "포럼", "unknown.example", "글쓴이")[0] == ""
    assert pub.고르기(표, "포럼", "auto.example", "")[0] == "", "자동 줄이 찾기 표에 들어갔다"


def test_랜섬은_주소_다음_핸들이다():
    표 = _표()
    assert pub.고르기(표, "랜섬웨어", "lockbitexampleaaaa.onion", "")[0] == "LockBit"
    assert pub.고르기(표, "랜섬웨어", "ransomware.live", "clop")[0] == "Cl0p"


def test_이미_있는_선택지를_먼저_쓴다():
    """`Emperador` 와 `emperador` 가 선택지 둘로 갈리지 않게 한다 (2026-09-25 실제로 걸렸다)."""
    assert pub.선택지맞춤("Emperador", ["emperador", "Cl0p"]) == "emperador"
    assert pub.선택지맞춤("Cl0p", ["clop"]) == "clop"
    assert pub.선택지맞춤("Newgroup", ["emperador"]) == "Newgroup"
    p = pub.속성(_표(), ["emperador"], "텔레그램", "", "Emperador")
    assert p["게시처"] == {"select": {"name": "emperador"}}


# ── 수집(push.py) ──────────────────────────────────────────────────
def test_수집이_줄을_만들_때_게시처를_같이_쓴다():
    줄 = {"source": "telegram", "venue": "t.me/osint_cti", "actor": "Clop"}
    assert push.게시처칸(_표(), [], 줄) == {"게시처": {"select": {"name": "Cl0p"}}}
    # 명부를 못 읽었으면 칸을 비운다. 줄은 그대로 올린다
    assert push.게시처칸(None, [], 줄) == {}


def test_수집이_수집DB_상수를_안_건드렸다():
    """push.py 의 수집DB 기본값은 최현서 자리다. 9/29 부터 NOTION_COLLECT_DB 로 바꿀 수 있고 기본값은 한 곳에만 있다."""
    글 = (ROOT / "hub" / "events" / "push.py").read_text(encoding="utf-8")
    assert 글.count('_수집DB_기본 = "5160ce53-7ce2-4271-879e-06f3ad9957cf"') == 1
    assert 글.count("5160ce53-7ce2-4271-879e-06f3ad9957cf") == 1


# ── 대시보드 포럼 사건 — 로컬과 배포가 같은가 ────────────────────────
def test_포럼_사건은_명부_없음을_안_켠다():
    표 = pub.명부표([("포럼", "포럼 이름", 포럼)])
    assert api.포럼게시처칸("bf.st", 표, []) == {"게시처": {"select": {"name": "BreachForums (bf.st)"}}}
    assert api.포럼게시처칸("unknown.example", 표, []) == {}
    assert api.포럼게시처칸("bf.st", None, []) == {}


def _js_부분():
    글 = 워커.read_text(encoding="utf-8")
    m = re.search(r"^// ── 포럼 사건 받기 ─+\n(.*?)^async function 포럼사건받기", 글, re.S | re.M)
    assert m, "worker.js 에서 포럼 사건 함수 묶음을 못 찾았다"
    return m.group(1)


def test_배포와_로컬이_같은_게시처를_낸다():
    node = shutil.which("node")
    if not node:
        print("  ?? node 가 없어 JS 쪽을 못 봤다. 파이썬 쪽만 봤다")
        return
    물음 = ["bf.st", "www.bf.st", "pwnexampleonionaaaa.onion", "PwnForums", "BREACHFORUMS (BF.ST)",
          "unknown.example", "t.me", "auto.example", ""]
    선택지 = ["breachforums (bf.st)", "Cl0p"]
    코드 = (_js_부분() + "\nconst 표 = 포럼명부표(%s);\nconsole.log(JSON.stringify(%s.map(q => 포럼게시처칸(q, 표, %s))));\n"
          % (json.dumps(포럼, ensure_ascii=False), json.dumps(물음, ensure_ascii=False),
             json.dumps(선택지, ensure_ascii=False)))
    r = subprocess.run([node, "-e", 코드], capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert r.returncode == 0, "node 가 실패했다: " + r.stderr[:400]
    js = json.loads(r.stdout.strip())
    표 = pub.명부표([("포럼", "포럼 이름", 포럼)])
    py = [api.포럼게시처칸(q, 표, 선택지) for q in 물음]
    for q, j, p in zip(물음, js, py):
        assert j == p, "%r — JS %r · 파이썬 %r" % (q, j, p)
    assert py[0] == {"게시처": {"select": {"name": "breachforums (bf.st)"}}}, py[0]


# ── 2026-09-25 머지 전 검토로 고친 것 ────────────────────────────────
def test_쉼표가_든_이름은_쉼표_없이_간다():
    """노션 선택지 이름에는 쉼표가 못 들어가 줄 만들기 전체가 거부됐다."""
    p = pub.속성(_표(), [], "텔레그램", "", "GroupA, GroupB")
    assert p["게시처"] == {"select": {"name": "GroupA · GroupB"}}, p
    표 = pub.명부표([("포럼", "포럼 이름", [_쪽("콤마, 포럼", "포럼 이름", 주소="https://comma.example/")])])
    assert api.포럼게시처칸("comma.example", 표, []) == {"게시처": {"select": {"name": "콤마 · 포럼"}}}


def test_짧은_열쇠는_통째로만_맞춘다():
    """민키가 한글 · 키릴을 지워 한글 이름끼리 아무 선택지에나 붙었다."""
    assert pub.선택지맞춤("Хакер", ["다른포럼", "Cl0p"]) == "Хакер"
    assert pub.선택지맞춤("새포럼", ["옛포럼"]) == "새포럼"
    assert pub.선택지맞춤("포럼 A", ["게시판 A"]) == "포럼 A"
    assert pub.선택지맞춤("XSS", ["xss"]) == "xss"            # 짧아도 대소문자만 다르면 같다
    assert pub.선택지맞춤("옛포럼", ["옛포럼 "]) == "옛포럼 "


def test_자리표시_핸들은_게시처로_안_쓴다():
    for h in ("Unknown", "N/A", "-", "없음"):
        assert pub.고르기(_표(), "텔레그램", "", h)[0] == "", h
        assert pub.속성(_표(), [], "텔레그램", "", h) == {}, h


def test_한글에_붙은_주소와_대괄호_점도_주소로_읽는다():
    assert pub.호스트들("examplefor.st로 이전") == ["examplefor.st"]
    assert pub.호스트들("abcexample[.]onion (2026-07-30 확인)") == ["abcexample.onion"]


# 검토에서 나온 경우를 담은 명부. 위의 포럼 목록은 그대로 둔다
포럼더 = 포럼 + [_쪽("ForumA", "포럼 이름", 이전="examplefor.st로 이전"),
                _쪽("DotForum", "포럼 이름", 주소="https://dotforum[.]example/"),
                _쪽("콤마, 포럼", "포럼 이름", 주소="https://comma.example/"),
                _쪽("새포럼", "포럼 이름", 주소="https://kf.example/")]


def test_배포와_로컬이_검토에서_나온_경우도_같게_낸다():
    node = shutil.which("node")
    if not node:
        print("  ?? node 가 없어 JS 쪽을 못 봤다. 파이썬 쪽만 봤다")
        return
    물음 = ["examplefor.st", "dotforum.example", "comma.example", "kf.example", "bf.st"]
    선택지 = ["옛포럼", "breachforums (bf.st)", "Cl0p"]
    짝 = [["Хакер", ["다른포럼", "Cl0p"]], ["-", ["다른포럼"]], ["새포럼", ["옛포럼"]],
          ["XSS", ["xss"]], ["포럼 A", ["게시판 A"]], ["Emperador", ["emperador"]]]
    코드 = (_js_부분()
          + "\nconst 표 = 포럼명부표(%s);\n" % json.dumps(포럼더, ensure_ascii=False)
          + "console.log(JSON.stringify([%s.map(q => 포럼게시처칸(q, 표, %s)), "
            "%s.map(([a, b]) => 선택지맞춤(a, b))]));\n"
          % (json.dumps(물음, ensure_ascii=False), json.dumps(선택지, ensure_ascii=False),
             json.dumps(짝, ensure_ascii=False)))
    r = subprocess.run([node, "-e", 코드], capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert r.returncode == 0, "node 가 실패했다: " + r.stderr[:400]
    js칸, js맞춤 = json.loads(r.stdout.strip())
    표 = pub.명부표([("포럼", "포럼 이름", 포럼더)])
    py칸 = [api.포럼게시처칸(q, 표, 선택지) for q in 물음]
    for q, j, p in zip(물음, js칸, py칸):
        assert j == p, "%r — JS %r · 파이썬 %r" % (q, j, p)
    assert py칸[:4] == [{"게시처": {"select": {"name": n}}} for n in ("ForumA", "DotForum", "콤마 · 포럼", "새포럼")], py칸
    py맞춤 = [pub.선택지맞춤(a, b) for a, b in 짝]
    assert js맞춤 == py맞춤, (js맞춤, py맞춤)


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
