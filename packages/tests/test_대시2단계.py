"""대시보드 ㉮ 2단계 — 검증 · 사고 · 행위자 DB (2026-09-29 최현서, 인계 H-6) 시험. **노션에 안 붙습니다.**

    python packages/tests/test_대시2단계.py          CI 가 이렇게 돌린다

목적은 자동으로 들어온 내용을 확인하는 것이다. 탭마다 새로 들어온 줄이 먼저(만든 때 최신순)이고
어디서 왔는지 · 관련 LEAK 번호를 같이 낸다. 반출경계표대로 실명은 기입됨/미기입, 연락처는 있음/없음,
서술 칸은 주소를 떼고, 검증의 「수집 줄」 은 page id 대신 LEAK 번호로 낸다.

읽기는 로컬(reader.py)과 배포(worker.js) 두 벌이라 node 로 같은 값을 내는지 맞춰 본다.
**실행부를 둔다.** 값은 전부 지어낸 것이다.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps" / "dash"))
import reader  # noqa: E402

워커 = ROOT / "apps" / "dash" / "deploy" / "worker.js"
레지 = ROOT / "apps" / "dash" / "dbs.json"

# 새면 안 되는 지어낸 값들
실명 = "지어낸실명QZX"
텔레값 = "@지어낸텔레그램QZX"
비고글 = "지어낸비고QZX 2026-09-25 수집 DB 게시자 핸들에서 자동 등록"
수집pid = ["aaaaaaaa-1111-2222-3333-444444444444", "bbbbbbbb-1111-2222-3333-444444444444"]
질문pid = "cccccccc-1111-2222-3333-444444444444"


def _글(v):
    return [{"plain_text": v}] if v else []


def _쪽(pid: str, 만든때: str, **p) -> dict:
    return {"id": pid, "created_time": 만든때, "properties": p}


def _고름(v):
    return {"type": "select", "select": {"name": v} if v else None}


# ── 지어낸 줄들 ──────────────────────────────────────────────────────
수집줄 = [
    {"id": 수집pid[0], "번호": "LEAK-7", "검토": "사건 O", "상태": "게시 중", "핸들": "Cl0pSeller",
     "게시날": "2026-09-02", "발견날": "", "수집일": "2026-09-02"},
    {"id": 수집pid[1], "번호": "LEAK-12", "검토": "미검토", "상태": "", "핸들": "clopseller",
     "게시날": "2026-08-30", "발견날": "", "수집일": "2026-09-01"},
    {"id": "dddd", "번호": "LEAK-20", "검토": "사건 X", "상태": "", "핸들": "다른사람", "게시날": ""},
]
검증쪽 = [
    _쪽("v1", "2026-09-20T01:00:00.000Z",
        **{"사건 ID": {"type": "title", "title": _글("LEAK-7")},
           "수집 줄": {"type": "relation", "relation": [{"id": 수집pid[0]}, {"id": "eeee-밖"}]},
           "진위 판정": _고름("진짜 의심"), "검증 요약": {"type": "rich_text", "rich_text": _글("첫 줄\n둘째 줄")},
           "검증자": _고름(실명), "DB 반영": {"type": "checkbox", "checkbox": True},
           "신선도": _고름(None)}),
    _쪽("v2", "2026-09-28T01:00:00.000Z",
        **{"사건 ID": {"type": "title", "title": _글("LEAK-12")},
           "수집 줄": {"type": "relation", "relation": [{"id": 수집pid[1].replace("-", "")}]},
           "검증자": _고름(None)}),
]
사고쪽 = [
    _쪽("s1", "2026-08-10T00:00:00.000Z",
        **{"사건 ID": {"type": "unique_id", "unique_id": {"prefix": "INC", "number": 3}},
           "조직명": {"type": "title", "title": _글("가상기관")}, "외부 확인": _고름("규제기관 확정"),
           "메모": {"type": "rich_text", "rich_text": _글("관련 LEAK-12 · leak-7 · LEAK-12 다시")},
           "기록자": _고름(실명), "평가에 쓴 질문": {"type": "relation", "relation": [{"id": 질문pid}]}}),
    _쪽("s2", "2026-08-11T00:00:00.000Z",
        **{"사건 ID": {"type": "unique_id", "unique_id": {"prefix": "INC", "number": 4}},
           "외부 확인": _고름("게시글만"), "메모": {"type": "rich_text", "rich_text": _글("")}}),
]
행위자쪽 = [
    _쪽("a1", "2026-09-26T00:00:00.000Z",
        **{"핸들": {"type": "title", "title": _글("CLOPSELLER")},
           "비고": {"type": "rich_text", "rich_text": _글(비고글)},
           "연결된 곳": {"type": "rich_text", "rich_text": _글("가상포럼 (forum.example) · 연락 x@y.example · http://a.onion/x")},
           "텔레그램": {"type": "rich_text", "rich_text": _글(텔레값)},
           "담당자": _고름(실명)}),
    _쪽("a2", "2026-08-20T00:00:00.000Z",
        **{"핸들": {"type": "title", "title": _글("아무도")},
           "비고": {"type": "rich_text", "rich_text": _글("사람이 적은 메모")}}),
]


def _읽기():
    """reader 로 세 DB 를 옮기고 잇는다."""
    이음 = reader.이음표(수집줄)
    줄 = {k: [reader.줄(p, reader.DB하나(k)["칸"], 이음) for p in 쪽]
         for k, 쪽 in (("검증", 검증쪽), ("사고", 사고쪽), ("행위자", 행위자쪽))}
    return reader.둘째단(수집줄, 줄["검증"], 줄["사고"], 줄["행위자"])


# ── 레지스트리 ────────────────────────────────────────────────────────
def test_레지스트리에_세_DB_가_있고_뺄_칸은_없다():
    ids = {d["열쇠"]: d["id"] for d in reader.레지스트리()["DB"]}
    assert ids["검증"] == "0d7b48c3-e744-4800-a591-a70b7c93fd20"
    assert ids["사고"] == "493fff58-16ac-4081-95a2-6820ef884879"
    assert ids["행위자"] == "58571d39-209a-4787-a0f5-2d9b735920be"
    적힌것 = {c["노션"] for k in ("검증", "사고", "행위자") for c in reader.DB하나(k)["칸"]}
    for 안될것 in ("평가에 쓴 질문", "지갑 주소", "순위", "검증 자료", "다른 이름", "출처 링크"):
        assert 안될것 not in 적힌것, 안될것
    # 실명 칸은 반드시 접는다
    for k, 칸이름 in (("검증", "검증자"), ("사고", "기록자"), ("행위자", "담당자"), ("행위자", "텔레그램")):
        c = next(c for c in reader.DB하나(k)["칸"] if c["노션"] == 칸이름)
        assert c.get("접기") == "있없", (k, 칸이름)


def test_배포판_노션_호출이_한도_50_안이다():
    글 = 워커.read_text(encoding="utf-8")
    판 = int(re.search(r"^const 판상한 = (\d+);", 글, re.M).group(1))
    명부판 = int(re.search(r"^const 명부판상한 = (\d+);", 글, re.M).group(1))
    둘 = sum(reader.DB하나(k)["판상한"] for k in ("검증", "사고", "행위자"))
    합 = 판 + 명부판 * len(reader.레지스트리()["명부"]["갈래"]) + 둘
    assert 합 <= 50, 합


# ── 읽기 규칙 ─────────────────────────────────────────────────────────
def test_만든때와_잇기():
    이음 = reader.이음표(수집줄)
    v = reader.줄(검증쪽[0], reader.DB하나("검증")["칸"], 이음)
    assert v["만든때"] == "2026-09-20T01:00:00.000Z"
    assert v["사건"] == ["LEAK-7"] and v["사건밖"] == 1, v
    # 이음이 없으면 예전처럼 개수만
    assert reader.줄(검증쪽[0], reader.DB하나("검증")["칸"])["사건"] == 2
    # 하이픈 없는 id 도 맞는다
    assert reader.줄(검증쪽[1], reader.DB하나("검증")["칸"], 이음)["사건"] == ["LEAK-12"]


def test_접기_셋():
    assert reader._LEAK뽑기("관련 LEAK-12 · leak-7 · LEAK-12 다시 · LEAK3") == ["LEAK-3", "LEAK-7", "LEAK-12"]
    assert reader._LEAK뽑기(None) == []
    assert reader._자동표지(비고글) == "자동 수집"
    assert reader._자동표지("사람이 적은 메모") == "검증 스킬 · 사람"
    뗀것 = reader._주소뗌("가상포럼 (forum.example) · 연락 x@y.example · http://a.onion/x · 게시처bf.st")
    for 샘 in ("forum.example", "x@y", "a.onion", "bf.st", "http"):
        assert 샘 not in 뗀것, (샘, 뗀것)
    assert "가상포럼" in 뗀것


# ── 잇기 · 세우기 · 셈 ────────────────────────────────────────────────
def test_둘째단이_잇고_최신순으로_세운다():
    d = _읽기()
    assert [x["번호"] for x in d["검증"]] == ["LEAK-12", "LEAK-7"]            # 만든 때 최신순
    v7 = d["검증"][1]
    assert (v7["수집검토"], v7["수집상태"]) == ("사건 O", "게시 중")
    assert v7["검증자"] == "기입됨" and d["검증"][0]["검증자"] == "미기입"
    assert v7["요약"] == "첫 줄"
    assert [x["갈래"] for x in d["사고"]] == ["주장 기록", "공식"]
    assert d["사고"][1]["메모LEAK"] == ["LEAK-7", "LEAK-12"]
    a1 = next(x for x in d["행위자"] if x["핸들"] == "CLOPSELLER")
    # 0/o · 대소문자를 견딘다. 가장 이른 게시가 첫 사건이다
    assert (a1["첫사건"], a1["사건수"], a1["들어온길"]) == ("LEAK-12", 2, "자동 수집"), a1
    assert (a1["텔레그램"], a1["담당자"]) == ("기입됨", "기입됨")
    a2 = next(x for x in d["행위자"] if x["핸들"] == "아무도")
    assert (a2["첫사건"], a2["사건수"], a2["들어온길"]) == ("", 0, "검증 스킬 · 사람")
    assert d["셈"] == {"검증": {"줄": 2}, "사고": {"발표": 2, "공식": 1, "주장 기록": 1},
                      "행위자": {"줄": 2, "자동 수집": 1, "검증 스킬 · 사람": 1}}


def test_실명_연락처_page_id_가_안_샌다():
    글 = json.dumps(_읽기(), ensure_ascii=False)
    for 값 in (실명, 텔레값, "지어낸비고", 수집pid[0], 수집pid[1], 질문pid, "forum.example", "a.onion"):
        assert 값 not in 글, 값


# ── 배포와 로컬이 같은가 ──────────────────────────────────────────────
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


def test_배포와_로컬이_같게_잇는다():
    j = lambda v: json.dumps(v, ensure_ascii=False)  # noqa: E731
    js = _js("""
      const 수집줄 = %s;
      const 이음 = 이음표(수집줄);
      const 옮긴것 = {};
      for (const [k, 쪽] of [["검증", %s], ["사고", %s], ["행위자", %s]])
        옮긴것[k] = 쪽.map((p) => 줄(p, DB하나(k).칸, 이음));
      console.log(JSON.stringify(둘째단(수집줄, 옮긴것.검증, 옮긴것.사고, 옮긴것.행위자)));
    """ % (j(수집줄), j(검증쪽), j(사고쪽), j(행위자쪽)))
    if js is None:
        return
    assert js == _읽기(), (js, _읽기())


def test_배포와_로컬이_같게_접는다():
    샘 = ["가상포럼 (forum.example) · 연락 x@y.example · http://a.onion/x · 게시처bf.st · 한글도메인.한국",
          "LEAK-1 leak-22 LEAK-22", "", "줄바꿈\n있음 sub.example.co.kr/경로", "x" * 200]
    js = _js("console.log(JSON.stringify(%s.map((s) => [_주소뗌(s), _LEAK뽑기(s), _자동표지(s)])));"
             % json.dumps(샘, ensure_ascii=False))
    if js is None:
        return
    assert js == [[reader._주소뗌(s), reader._LEAK뽑기(s), reader._자동표지(s)] for s in 샘], js


if __name__ == "__main__":
    시험 = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    실패 = 0
    for 이름, f in 시험:
        try:
            f()
            print("  통과  %s" % 이름)
        except AssertionError as e:  # noqa: PERF203
            실패 += 1
            print("  실패  %s  %s" % (이름, str(e)[:300]))
        except Exception as e:  # noqa: BLE001
            실패 += 1
            print("  오류  %s  %s: %s" % (이름, type(e).__name__, str(e)[:300]))
    print("%d개 중 %d개 실패" % (len(시험), 실패))
    raise SystemExit(1 if 실패 else 0)
