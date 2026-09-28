"""대시보드 「게시처 DB」 탭 — 시험. **노션에 안 붙고 밖에 안 나갑니다.**

    python packages/tests/test_명부집계.py          CI 가 이렇게 돌린다

2026-09-25 최현서 승인(인계 ㉮ 3단계). 게시처 DB 셋은 **건수만** 굽고(반출경계표 7-1), 수집 DB
사건 줄로 게시처마다 한국 관련 사건을 기간별로 센다. 셈은 로컬(reader.py)과 배포(worker.js)
두 벌이라 node 로 같은 값을 내는지 맞춰 본다.

값은 전부 지어낸 것이다. 레포가 공개다.

**실행부를 둔다.** CI 는 이 폴더를 `python 파일` 로 돌린다. 시험은 실행부 위에 둔다.
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

import reader  # noqa: E402

워커 = ROOT / "apps" / "dash" / "deploy" / "worker.js"
레지 = ROOT / "apps" / "dash" / "dbs.json"
화면 = ROOT / "apps" / "dash" / "index.html"
오늘 = "2026-09-25"


def _쪽(**칸):
    """게시처 DB 한 줄. 이름 · 주소 · 담당자도 넣어 둔다 — 셈에서 새면 안 된다."""
    p = {
        "포럼 이름": {"type": "title", "title": [{"plain_text": "지어낸포럼이름"}]},
        "주소": {"type": "url", "url": "https://leak.example.invalid/"},
        "담당자": {"type": "select", "select": {"name": "지어낸담당자"}},
    }
    if "상태" in 칸:
        p["상태"] = 칸["상태"]
    if "확인일" in 칸:
        p["확인일"] = {"type": "date", "date": {"start": 칸["확인일"]} if 칸["확인일"] else None}
    if "단계" in 칸:
        p["조사 단계"] = {"type": "select", "select": {"name": 칸["단계"]} if 칸["단계"] else None}
    if "유출" in 칸:
        p["한국 관련 유출"] = {"type": "rich_text", "rich_text": [{"plain_text": 칸["유출"]}] if 칸["유출"] else []}
    if "반영" in 칸:
        p["DB 반영"] = {"type": "checkbox", "checkbox": 칸["반영"]}
    return {"id": "page", "properties": p}


def _고름(이름):
    return {"type": "select", "select": {"name": 이름} if 이름 else None}


쪽들 = [
    _쪽(상태=_고름("online"), 확인일="2026-09-18", 단계="확인만 함", 유출="지어낸유출글 2건", 반영=True),   # 7일
    _쪽(상태=_고름("online"), 확인일="2026-09-17", 단계="조사 중", 유출="미기입", 반영=False),           # 8일
    _쪽(상태=_고름("offline"), 확인일="2026-08-26", 단계="확인만 함", 유출="최근 180일 한국 피해 0건 (2026-09-24 기준)", 반영=True),  # 30일
    _쪽(상태=_고름("offline"), 확인일="2026-08-25", 단계="", 유출="  ", 반영=True),                    # 31일
    _쪽(상태=_고름("미확인"), 확인일="2026-10-01", 유출="해당 없음\n최근 180일 한국 피해 3건 (2026-09-24 기준)"),  # 앞날
    _쪽(상태={"type": "status", "status": {"name": "online"}}, 확인일="", 유출="있음"),               # 빈 날
    _쪽(상태=_고름(None), 확인일="2026-13-45"),                                                      # 없는 날
    _쪽(상태={"type": "multi_select", "multi_select": [{"name": "online"}]},
        확인일="2026-09-24T23:30:00+09:00", 유출="후보 0건, 0건"),                                   # 여러 값 · 시각
    _쪽(),                                                                                         # 칸이 아예 없음
]
기대 = {
    "줄수": 9,
    "상태": {"online": 3, "offline": 2, "미확인": 1, "빈칸": 3},
    "조사단계": {"확인만 함": 2, "조사 중": 1, "빈칸": 6},
    "확인일": {"7일 안": 3, "30일 안": 2, "30일 넘음": 1, "빈칸": 3},
    "한국유출": 3,
    "DB반영": 3,
}


def _칸():
    return json.loads(레지.read_text(encoding="utf-8"))["명부"]["칸"]


def _js(뒤: str):
    """worker.js 의 「노션 읽기」 구역을 잘라 node 로 돌린다. node 가 없으면 None."""
    node = shutil.which("node")
    if not node:
        print("  ?? node 가 없어 JS 쪽을 못 봤다. 파이썬 쪽만 봤다")
        return None
    글 = 워커.read_text(encoding="utf-8")
    m = re.search(r"^// ── 노션 읽기 ─+\n(.*?)^/\*\* 한 번에 읽을 판 수", 글, re.S | re.M)
    assert m, "worker.js 에서 노션 읽기 구역을 못 찾았다"
    코드 = "const 레지스트리 = %s;\n%s\n%s\n" % (레지.read_text(encoding="utf-8"), m.group(1), 뒤)
    r = subprocess.run([node, "-e", 코드], capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert r.returncode == 0, "node 가 실패했다: " + r.stderr[:400]
    return json.loads(r.stdout.strip())


# ── 게시처 DB 셈 ────────────────────────────────────────────────────
def test_명부셈이_건수를_바로_센다():
    assert reader.명부셈(쪽들, _칸(), 오늘) == 기대, reader.명부셈(쪽들, _칸(), 오늘)


def test_명부셈에_이름_주소_담당자_유출글이_없다():
    글 = json.dumps(reader.명부셈(쪽들, _칸(), 오늘), ensure_ascii=False)
    for 값 in ("지어낸포럼이름", "leak.example", "지어낸담당자", "지어낸유출글"):
        assert 값 not in 글, 값


def test_배포와_로컬이_같게_센다():
    js = _js("console.log(JSON.stringify(명부셈(%s, 레지스트리.명부.칸, %s)));"
             % (json.dumps(쪽들, ensure_ascii=False), json.dumps(오늘)))
    if js is None:
        return
    assert js == reader.명부셈(쪽들, _칸(), 오늘), (js, reader.명부셈(쪽들, _칸(), 오늘))


def test_한국_관련_유출은_자리표시와_0건_줄을_안_센다():
    """2026-09-25 최현서 「0건 줄은 빼고 셈」."""
    경우 = {
        "": False, "미기입": False, "해당 없음": False, "  ": False,
        "최근 180일 한국 피해 0건 (2026-09-24 기준)": False, "후보 0건, 0건": False,
        "최근 180일 한국 피해 1,204건 (2026-09-24 기준)": True,
        "해당 없음\n한국 피해 3건": True, "있음": True, "사람이 쓴 글": True,
    }
    for 글, 답 in 경우.items():
        assert reader.한국유출있나(글) is 답, 글
    js = _js("console.log(JSON.stringify(%s.map(한국유출있나)));" % json.dumps(list(경우), ensure_ascii=False))
    if js is not None:
        assert js == list(경우.values()), js


# ── 사건 줄에 더한 칸 ───────────────────────────────────────────────
def test_게시처는_도메인째로_두어_클론이_안_합쳐진다():
    """괄호를 떼면 이름이 같은 BreachForums 클론 다섯이 한 줄로 합쳐졌다(2026-09-25 실제 굽기에서 봄).
    반출경계표 3-3: 수집 DB 에서는 도메인을 안 자른다. 대시보드는 잠긴 팀 화면이다."""
    칸들 = {c["낼"]: c for c in reader.DB하나("수집")["칸"]}
    assert not 칸들["게시처"].get("접기"), 칸들["게시처"]
    둘 = [reader.줄({"id": i, "properties": {"게시처": {"type": "select", "select": {"name": 이름}}}},
                   [칸들["게시처"]])["게시처"] for i, 이름 in enumerate(("BreachForums (bf.st)", "BreachForums (breached.su)"))]
    assert len(set(둘)) == 2, 둘


def test_KST날은_UTC_오후를_다음_날로_옮긴다():
    경우 = {"2026-07-31T16:00:00+00:00": "2026-08-01", "2026-07-31T16:00:00.000Z": "2026-08-01",
            "2026-07-31T10:00:00+09:00": "2026-07-31", "2026-07-31T10:00:00": "2026-07-31",
            "2026-07-31": "2026-07-31", "": "", "날짜아님아님아님": "날짜아님아님아님"[:10]}
    for 원, 답 in 경우.items():
        assert reader._KST날(원) == 답, 원
    js = _js("console.log(JSON.stringify(%s.map(_KST날)));" % json.dumps(list(경우), ensure_ascii=False))
    if js is not None:
        assert js == list(경우.values()), js


def test_사건_줄이_게시처_한국_반영_날짜를_안_그리는_칸으로_담는다():
    칸들 = {c["낼"]: c for c in reader.DB하나("수집")["칸"]}
    for 이름 in ("게시처", "한국", "반영", "게시날", "발견날"):
        assert 이름 in 칸들 and 칸들[이름].get("안그림"), 이름
    assert 칸들["게시날"]["접기"] == "KST날" and 칸들["발견날"]["접기"] == "KST날"
    # 배포와 로컬이 같은 줄을 만든다
    쪽 = {"id": "x", "properties": {
        "게시처": {"type": "select", "select": {"name": "BreachForums (bf.st)"}},
        "한국 관련": {"type": "select", "select": {"name": "직접"}},
        "DB 반영": {"type": "checkbox", "checkbox": True},
        "게시 시각": {"type": "date", "date": {"start": "2026-07-31T16:00:00+00:00"}},
        "발견일": {"type": "date", "date": {"start": "2026-08-02"}}}}
    py = reader.줄(쪽, reader.DB하나("수집")["칸"])
    assert (py["게시처"], py["한국"], py["반영"], py["게시날"], py["발견날"], py["게시"]) == \
        ("BreachForums (bf.st)", "직접", True, "2026-08-01", "2026-08-02", "2026-07-31"), py
    js = _js("console.log(JSON.stringify(줄(%s, DB하나('수집').칸)));" % json.dumps(쪽, ensure_ascii=False))
    if js is not None:
        assert js == py, (js, py)


def test_dbs_json_의_접기가_두_벌에_다_있다():
    레 = json.loads(레지.read_text(encoding="utf-8"))
    쓰는것 = {c["접기"] for d in 레["DB"] for c in d["칸"] if c.get("접기")}
    assert 쓰는것 <= set(reader.접개), 쓰는것 - set(reader.접개)
    js = _js("console.log(JSON.stringify(Object.keys(접개)));")
    if js is not None:
        assert 쓰는것 <= set(js), 쓰는것 - set(js)


# ── 레지스트리 · 한도 ───────────────────────────────────────────────
def test_명부_칸이_게시처_DB_셋에_다_있다():
    스키마 = json.loads((ROOT / "packages" / "tests" / "노션스키마.json").read_text(encoding="utf-8"))
    for 노션칸 in _칸().values():
        for 갈래 in ("forum", "ransom", "telegram"):
            assert 노션칸 in 스키마[갈래]["칸"], (갈래, 노션칸)


def test_명부_id_는_서로_다른_노션_id_다():
    ids = [g["id"].replace("-", "") for g in json.loads(레지.read_text(encoding="utf-8"))["명부"]["갈래"]]
    assert len(ids) == 3 and len(set(ids)) == 3, ids
    assert all(re.fullmatch(r"[0-9a-f]{32}", x) for x in ids), ids


def test_worker_의_포럼_명부_id_와_같다():
    글 = 워커.read_text(encoding="utf-8")
    m = re.search(r'const 포럼명부DS = "([0-9a-f-]+)"', 글)
    if not m:
        print("  ?? worker.js 에 포럼명부DS 가 아직 없다(#42 머지 전). 건너뛴다")
        return
    포럼 = [g for g in json.loads(레지.read_text(encoding="utf-8"))["명부"]["갈래"] if g["열쇠"] == "포럼"][0]
    assert m.group(1) == 포럼["id"], (m.group(1), 포럼["id"])


def test_하위_요청이_무료_한도_50_안이다():
    글 = 워커.read_text(encoding="utf-8")
    판 = int(re.search(r"const 판상한 = (\d+);", 글).group(1))
    명 = int(re.search(r"const 명부판상한 = (\d+);", 글).group(1))
    갈래 = len(json.loads(레지.read_text(encoding="utf-8"))["명부"]["갈래"])
    assert 판 + 명 * 갈래 <= 50, (판, 명, 갈래)


def test_worker_에_줄_구분_문자가_글자로_안_들어_있다():
    """U+2028 · U+2029 가 정규식 안에 글자로 들어가면 JS 가 줄 끝으로 읽어 번들이 깨진다.
    2026-09-25 에 편집 도구가 `\\u2028` 을 글자로 풀어 넣은 적이 있다. 이스케이프로 적는다."""
    글 = 워커.read_text(encoding="utf-8")
    assert chr(0x2028) not in 글 and chr(0x2029) not in 글


def test_굽기와_배포가_집계를_따로_잡는다():
    """게시처 DB 셈이 죽어도 사건 화면은 떠야 한다."""
    b = (ROOT / "apps" / "dash" / "build.py").read_text(encoding="utf-8")
    assert 'd["명부"] = 명부(d["구운때"][:10])' in b
    자리 = b[b.index('d["명부"] = 명부('):]
    assert "except Exception" in 자리[:400]
    w = 워커.read_text(encoding="utf-8")
    assert "명부 = await 명부읽기(env.NOTION_TOKEN" in w
    자리 = w[w.index("명부 = await 명부읽기("):]
    assert "catch (e)" in 자리[:300]


def test_화면이_관문과_한국_기준을_지도_행위자와_같게_쓴다():
    글 = 화면.read_text(encoding="utf-8")
    assert 'x.반영 === true && x.검토 !== "미검토" && x.검토 !== "사건 X"' in 글
    assert 'x.국가 === "한국" || x.한국 === "직접" || x.한국 === "공급망"' in 글
    assert 'data-탭="명부"' in 글 and 'id="명부"' in 글
    assert "x.게시날 || x.발견날" in 글


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
