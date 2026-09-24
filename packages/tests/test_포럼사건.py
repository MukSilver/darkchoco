"""포럼 사건 받기 — 시험. **노션에 안 붙습니다.**

    python packages/tests/test_포럼사건.py          CI 가 이렇게 돌린다
    python -m pytest packages/tests/test_포럼사건.py

2026-09-23 최현서 결정. 수집 여섯 칸 중 마지막 칸이다. 포럼 킷이 낸 「칸 값」 을 대시보드가
받아, 사람이 미리 보고 누를 때 수집 DB 에 새 줄로 올린다. 원문은 킷이 PC 에만 떨군다.

**같은 일을 하는 곳이 셋이다.** 셋이 같은 줄을 만들어야 한다.

    옛 길      skills/collect/kit_in.py → dc_store.Item.uid() → push.py
    로컬       apps/dash/api.py        포럼UID() · 포럼줄속성()
    배포       apps/dash/deploy/worker.js  포럼UID재료() · 해시16() · 포럼줄속성()

UID 가 어긋나면 두 길로 올린 같은 글이 두 줄이 된다. 그래서 같은 입력을 셋에 먹여 본다.

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
sys.path.insert(0, str(ROOT / "skills"))

import api  # noqa: E402
from collect import kit_in  # noqa: E402

워커 = ROOT / "apps" / "dash" / "deploy" / "worker.js"
킷 = ROOT / "skills" / "bookmarklets" / "forum_kit.js"
화면 = ROOT / "apps" / "dash" / "index.html"

# 값은 전부 지어낸 것이다. 실제 포럼 · 조직 · 사람이 아니다.
긴제목 = "🔥 [DB] 지어낸회사 고객 데이터 " + "가나다라마바사 " * 20
줄1 = {"제목": 긴제목, "URL": "https://forum.example.test/showthread.php?tid=123",
       "게시자": "Seller", "날짜": "09-20-2026, 10:15 AM", "게시판": "Databases", "본문": "받음",
       "한국 신호": {"도메인": ["shop.example.co.kr", "evil.example.com"], "한글": True, "korea": True},
       # 킷이 안 보내는 키. 누가 끼워 보내도 노션까지 가면 안 된다
       "body": "leak@example.test 010-0000-0000", "본문 전체": "지어낸 본문"}
줄2 = {"제목": "Locked thread", "URL": "https://forum.example.test/threads/locked-title.4567/",
       "게시자": "", "날짜": "", "게시판": "Leaks", "본문": "403", "한국 신호": {}}
줄3 = {"제목": "Listed only\u0007 title", "URL": "https://forum.example.test/Thread-listed-only",
       "게시자": "Guy", "날짜": "2026-09-01", "게시판": "Leaks", "본문": "안 봄",
       "한국 신호": {"도메인": [], "한글": False, "korea": False}}


def _짐(*줄들):
    return {"종류": "darkchoco-forum-rows", "판": 1, "킷": "forum kit v2.8", "줄": list(줄들)}


def _킷출력() -> str:
    """kit_in.py 가 읽는 옛 원문 꼴. 같은 글 셋을 담는다."""
    x1, x2 = api.포럼줄검사(_짐(줄1))[0], api.포럼줄검사(_짐(줄2))[0]
    return (
        "# forum.example.test 수집\n\nforum kit v2.8\n출처 목록 : https://forum.example.test/Forum-x\n"
        "확인 : 2026-09-23 · 2026-09-23T00:00:00Z\n대상 3건 (수집 3건) · 마스킹 OFF(원문)\n"
        "\n---\n\n## %s\n\n- URL : %s\n- 엔진 : mybb\n- 확인 : 2026-09-23\n"
        "\n### 원문  Seller  09-20-2026, 10:15 AM\n\n```\n지어낸 본문\n```\n"
        "\n---\n\n## %s\n\n- URL : %s\n- 상태 : 403 접근 권한 없음 (등급 제한 또는 삭제·이동)\n"
        "- 확인 : 2026-09-23\n"
        "\n---- TSV (게시판 · 제목 · 작성자 · 답글 · 조회 · 날짜 · URL) ----\n"
        "Leaks\tListed only  title\tGuy\t1\t2\t2026-09-01\t%s\n"
        % (x1["제목"], x1["URL"], x2["제목"], x2["URL"], 줄3["URL"]))


# ── 거르기 ─────────────────────────────────────────────────────────
def test_킷이_낸_것이_아니면_안_받는다():
    for 나쁨 in ({}, {"종류": "다른것", "판": 1, "줄": [줄1]},
               {"종류": "darkchoco-forum-rows", "판": 2, "줄": [줄1]},
               _짐(), _짐(*([줄3] * 21))):
        try:
            api.포럼줄검사(나쁨)
        except ValueError:
            continue
        raise AssertionError("받으면 안 되는 것을 받았다: %r" % str(나쁨)[:80])


def test_http_주소만_받는다():
    for 주소 in ("javascript:alert(1)", "file:///etc/passwd", "forum.example.test/x", ""):
        try:
            api.포럼줄검사(_짐(dict(줄3, URL=주소)))
        except ValueError:
            continue
        raise AssertionError("받으면 안 되는 주소: %r" % 주소)


def test_kr_도메인만_남기고_제어문자를_지운다():
    x1, _, x3 = api.포럼줄검사(_짐(줄1, 줄2, 줄3))
    assert x1["신호"]["도메인"] == ["shop.example.co.kr"], x1["신호"]
    assert "\u0007" not in x3["제목"], x3["제목"]


def test_본문과_모르는_키는_노션에_안_간다():
    x = api.포럼줄검사(_짐(줄1))[0]
    p = json.dumps(api.포럼줄속성(x, "u", "2026-09-23"), ensure_ascii=False)
    for 값 in ("leak@example.test", "010-0000-0000", "지어낸 본문"):
        assert 값 not in p, "노션 속성에 %r 이 들어갔다" % 값


def test_새_줄은_미검토고_공개를_안_켠다():
    p = api.포럼줄속성(api.포럼줄검사(_짐(줄1))[0], "u", "2026-09-23")
    assert p["검토 여부"] == {"select": {"name": "미검토"}}
    assert "DB 반영" not in p, "새 줄이 공개로 들어간다"
    assert p["소스"] == {"select": {"name": "포럼"}}
    assert p["한국 관련"] == {"select": {"name": "미확인"}}
    근거 = p["한국 관련 근거"]["rich_text"][0]["text"]["content"]
    assert "shop.example.co.kr" in 근거 and "한글" in 근거 and "korea" in 근거, 근거
    # 포럼 날짜 꼴은 노션 날짜가 아니다. ISO 일 때만 보낸다 (push.py 의 _날 과 같다)
    assert "게시 시각" not in p
    p3 = api.포럼줄속성(api.포럼줄검사(_짐(줄3))[0], "u", "2026-09-23")
    assert p3["게시 시각"] == {"date": {"start": "2026-09-01"}}


# ── 옛 길과 UID 가 같은가 ──────────────────────────────────────────
def test_UID_가_옛_길과_같다():
    """kit_in.py 가 원문 파일에서 만든 Item.uid() 와 로컬이 만든 UID 가 같다."""
    items, _ = kit_in.read(_킷출력())
    옛 = {it.post_url: it.uid() for it in items}
    for 줄 in (줄1, 줄2, 줄3):
        x = api.포럼줄검사(_짐(줄))[0]
        assert x["URL"] in 옛, "옛 길이 이 글을 못 읽었다: %s" % x["URL"]
        assert api.포럼UID(x) == 옛[x["URL"]], "UID 가 옛 길과 다르다: %s" % x["URL"]


# ── 배포(worker.js)와 로컬이 같은가 ────────────────────────────────
def _js_부분():
    """worker.js 에서 포럼 사건의 순수 함수 묶음을 떼어 온다. 손으로 베끼면 파일과 어긋난다."""
    글 = 워커.read_text(encoding="utf-8")
    m = re.search(r"^// ── 포럼 사건 받기 ─+\n(.*?)^async function 포럼사건받기", 글, re.S | re.M)
    assert m, "worker.js 에서 포럼 사건 함수 묶음을 못 찾았다"
    return m.group(1)


def test_배포와_로컬이_같은_줄을_만든다():
    node = shutil.which("node")
    if not node:
        # CI 러너(ubuntu-latest)에는 node 가 있다. 여기서 빠지는 것은 로컬뿐이다
        print("  ?? node 가 없어 JS 쪽을 못 봤다. 파이썬 쪽만 봤다")
        return
    짐 = _짐(줄1, 줄2, 줄3)
    코드 = ("const crypto = globalThis.crypto || require('crypto').webcrypto;\n" + _js_부분()
          + "\n(async () => { const 검 = 포럼줄검사(%s); const 밖 = [];\n"
            "  for (const x of 검.줄) { const uid = await 해시16(포럼UID재료(x));\n"
            "    밖.push({ uid, p: 포럼줄속성(x, uid, '2026-09-23') }); }\n"
            "  console.log(JSON.stringify(밖)); })();\n" % json.dumps(짐, ensure_ascii=False))
    r = subprocess.run([node, "-e", 코드], capture_output=True, text=True,
                       encoding="utf-8", timeout=30)
    assert r.returncode == 0, "node 가 실패했다: " + r.stderr[:400]
    js = json.loads(r.stdout.strip())
    py = []
    for x in api.포럼줄검사(짐):
        uid = api.포럼UID(x)
        py.append({"uid": uid, "p": api.포럼줄속성(x, uid, "2026-09-23")})
    assert len(js) == len(py) == 3
    for j, p in zip(js, py):
        assert j["uid"] == p["uid"], "UID 가 다르다 — JS %s · 파이썬 %s" % (j["uid"], p["uid"])
        assert j["p"] == p["p"], "속성이 다르다\n JS %s\n PY %s" % (
            json.dumps(j["p"], ensure_ascii=False)[:400], json.dumps(p["p"], ensure_ascii=False)[:400])


def test_JS_도_나쁜_것을_거른다():
    node = shutil.which("node")
    if not node:
        print("  ?? node 가 없어 JS 쪽을 못 봤다")
        return
    나쁜것 = [{}, _짐(), _짐(*([줄3] * 21)), _짐(dict(줄3, URL="javascript:alert(1)"))]
    코드 = (_js_부분() + "\nconsole.log(JSON.stringify(%s.map(d => !!포럼줄검사(d).오류)));\n"
          % json.dumps(나쁜것, ensure_ascii=False))
    r = subprocess.run([node, "-e", 코드], capture_output=True, text=True,
                       encoding="utf-8", timeout=30)
    assert r.returncode == 0, "node 가 실패했다: " + r.stderr[:400]
    assert json.loads(r.stdout.strip()) == [True] * 4, r.stdout


def test_한번에_보내는_수가_셋이_같다():
    """화면이 나눠 보내는 수와 서버가 받는 상한이 다르면 뒤쪽 묶음이 통째로 400 이다."""
    w = int(re.search(r"^const 포럼줄상한 = (\d+);", 워커.read_text(encoding="utf-8"), re.M).group(1))
    h = int(re.search(r"const 포럼한번 = (\d+);", 화면.read_text(encoding="utf-8")).group(1))
    assert w == h == api.포럼줄상한, (w, h, api.포럼줄상한)


def test_로컬_자리가_잘못된_것을_400_으로_돌려준다():
    코드, 답 = api.처리("/api/forum-rows", b"{not json")
    assert 코드 == 400, (코드, 답)
    코드, 답 = api.처리("/api/forum-rows", json.dumps(_짐()).encode("utf-8"))
    assert 코드 == 400 and "줄" in 답["오류"], (코드, 답)


# ── 킷 ─────────────────────────────────────────────────────────────
def test_킷에_대시보드_주소가_없다():
    """레포가 공개다. 주소는 설치 페이지에서 각자 넣는다."""
    for f in [킷] + sorted((ROOT / "skills" / "bookmarklets").glob("*.bookmarklet.txt")) + \
             [ROOT / "skills" / "bookmarklets" / "설치.html"]:
        글 = f.read_text(encoding="utf-8")
        assert not re.search(r"https://[a-z0-9-]+\.[a-z0-9-]+\.workers\.dev", 글), \
            "%s 에 대시보드 주소가 적혀 있다" % f.name
    assert "'@@DASH@@'" in 킷.read_text(encoding="utf-8"), "킷에 자리표시자가 없다"


def test_킷의_칸_값에_본문이_안_들어간다():
    """ROWS 에 넣는 키가 정해진 것뿐인가. text(본문)는 신호를 보는 데만 쓴다."""
    글 = 킷.read_text(encoding="utf-8")
    m = re.search(r"ROWS\.push\(\{(.*?)\}\);", 글, re.S)
    assert m, "킷에서 ROWS.push 를 못 찾았다"
    키 = {k.strip() for k in re.findall(r"(?:^|[,{])\s*'?([가-힣A-Za-z ]+?)'?\s*:", m.group(1))}
    assert 키 <= {"제목", "URL", "게시자", "날짜", "게시판", "한국 신호", "도메인", "한글", "korea"}, 키
    # `본문` 은 줄임 꼴(본문,)로 들어간다. 받음 · 안 봄 · 403 표시다
    assert re.search(r"[,{]\s*본문\s*,", m.group(1)), "본문 표시 칸이 없다"
    # 본문 칸은 「받음 · 안 봄 · 403」 표시다. 글자가 아니다
    for 자리 in re.findall(r"칸줄\((.*?)\);", 글, re.S):
        assert 자리.rstrip().endswith(("'받음')", "'안 봄')", "'403')", "'받음'", "'안 봄'", "'403'")) \
            or "'받음' : '안 봄'" in 자리, 자리[-60:]


def test_킷_노션_직접_안_쓴다():
    글 = 킷.read_text(encoding="utf-8")
    assert "api.notion.com" not in 글 and "/api/forum-rows" not in 글, "킷이 서버나 노션을 직접 부른다"


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
