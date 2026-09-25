"""랜섬 그룹 × 달 피해 건수 쌓기 — 시험. **밖에 안 나가고 노션에 안 붙습니다.**

    python packages/tests/test_월별피해.py          CI 가 이렇게 돌린다

2026-09-25 최현서 승인 (인계 B). 명부 조사기가 판마다 받은 달별 피해 목록을 세고 버리던
것을 노션 「랜섬 그룹 월별 피해」 DB 에 그룹 · 연월 단위로 쌓는다. **피해 조직 이름은 안
남긴다.** 공개 로그에는 그룹 이름도 안 찍는다.

**실행부를 둔다.** CI 는 이 폴더를 `python 파일` 로 돌린다.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packages"))

from hub.places import monthly  # noqa: E402
from hub.places.probe import ransom  # noqa: E402

# 값은 지어낸 것이다. 피해 조직 이름이 절대 노션 속성으로 가면 안 된다
목록 = [
    {"group": "GroupA", "victim": "지어낸피해회사", "domain": "victim.example.kr", "country": "KR",
     "activity": "Manufacturing", "attackdate": "2026-09-02T00:00:00+00:00"},
    {"group": "GroupA", "victim": "Other Victim", "country": "US", "activity": "Healthcare"},
    {"group": "GroupA", "victim": "Third", "country": "US", "activity": "Not Found"},
    {"group": "GroupB", "victim": "B victim", "country": "DE", "activity": "Retail"},
    {"group": "", "victim": "그룹 없음"},
    "꼴이 다른 것",
]


class _가짜노션:
    def __init__(self, 줄들=()):
        self.줄들 = list(줄들)
        self.만든것, self.고친것 = [], []

    def query_all(self, ds):
        assert ds == monthly.월별DS
        return list(self.줄들)

    def request(self, method, path, body=None):
        assert (method, path) == ("POST", "/pages"), (method, path)
        self.만든것.append(body)
        return {"id": "새줄%d" % len(self.만든것)}

    def update_page(self, pid, props):
        self.고친것.append((pid, props))


def _노션줄(pid, 그룹, 연월, 건수, 한국, 업종, 마감, 관계=None):
    """노션이 돌려주는 꼴로 만든 월별 DB 줄."""
    return {"id": pid, "properties": {
        "그룹 이름": {"type": "rich_text", "rich_text": [{"plain_text": 그룹}]},
        "연월": {"type": "date", "date": {"start": 연월 + "-01"}},
        "피해 건수": {"type": "number", "number": 건수},
        "한국 건수": {"type": "number", "number": 한국},
        "업종별 건수": {"type": "rich_text", "rich_text": [{"plain_text": 업종}] if 업종 else []},
        "달 마감": {"type": "checkbox", "checkbox": 마감},
        "그룹": {"type": "relation", "relation": [{"id": x} for x in (관계 or [])]},
    }}


class _명부줄:
    def __init__(self, 이름, page_id):
        self.이름, self.page_id = 이름, page_id


오늘 = date(2026, 9, 25)


# ── 세기 ───────────────────────────────────────────────────────────
def test_한_달_목록을_그룹별로_센다():
    d = ransom.달별세기(목록)
    assert set(d) == {"GroupA", "GroupB"}, d
    assert d["GroupA"]["건수"] == 3 and d["GroupA"]["한국"] == 1
    assert dict(d["GroupA"]["업종"]) == {"Manufacturing": 1, "Healthcare": 1}, "Not Found 를 업종으로 셌다"
    assert ransom.달별세기("꼴이 다름") == {}


def test_노션_속성에_피해_조직_이름이_없다():
    d = ransom.달별세기(목록)
    p = monthly.속성("GroupA", "2026-09", d["GroupA"], "", False, "2026-09-25T10:00:00+09:00")
    글 = json.dumps(p, ensure_ascii=False)
    for 이름 in ("지어낸피해회사", "Other Victim", "victim.example.kr"):
        assert 이름 not in 글, 이름
    assert p["이름"]["title"][0]["text"]["content"] == "GroupA · 2026-09"
    assert p["연월"] == {"date": {"start": "2026-09-01"}}
    assert p["피해 건수"] == {"number": 3} and p["한국 건수"] == {"number": 1}


# ── 쓰기 ───────────────────────────────────────────────────────────
def test_없으면_새로_같으면_그대로_다르면_고친다():
    달별 = {"2026-09": ransom.달별세기(목록)}
    그룹쪽 = {"groupa": "aaaa-1111"}
    # GroupA 는 같은 값이 이미 있다 (받은 때만 다르다). GroupB 는 없다
    있는 = _노션줄("있던줄", "GroupA", "2026-09", 3, 1, "Manufacturing 1 · Healthcare 1", False, ["aaaa1111"])
    가짜 = _가짜노션([있는])
    셈 = monthly.월별표(가짜).반영(달별, 그룹쪽, 오늘=오늘, apply=True)
    assert (셈["새로"], 셈["고침"], 셈["그대로"]) == (1, 0, 1), 셈
    assert len(가짜.만든것) == 1 and not 가짜.고친것
    새 = 가짜.만든것[0]
    assert 새["parent"] == {"type": "data_source_id", "data_source_id": monthly.월별DS}
    assert "그룹" not in 새["properties"], "명부에 없는 그룹인데 관계를 걸었다"

    # 건수가 바뀌면 그 줄만 고친다
    바뀐 = _노션줄("있던줄", "GroupA", "2026-09", 2, 1, "Manufacturing 1 · Healthcare 1", False, ["aaaa1111"])
    가짜 = _가짜노션([바뀐])
    셈 = monthly.월별표(가짜).반영({"2026-09": {"GroupA": 달별["2026-09"]["GroupA"]}}, 그룹쪽,
                                  오늘=오늘, apply=True)
    assert 셈["고침"] == 1 and 가짜.고친것[0][0] == "있던줄", 셈


def test_지난_달은_마감이고_이번_달은_아니다():
    가짜 = _가짜노션()
    monthly.월별표(가짜).반영({"2026-08": {"G": {"건수": 1, "한국": 0, "업종": {}}},
                               "2026-09": {"G": {"건수": 1, "한국": 0, "업종": {}}}},
                              {}, 오늘=오늘, apply=True)
    마감 = {b["properties"]["연월"]["date"]["start"]: b["properties"]["달 마감"]["checkbox"] for b in 가짜.만든것}
    assert 마감 == {"2026-08-01": True, "2026-09-01": False}, 마감


def test_미리보기는_안_쓴다():
    가짜 = _가짜노션()
    셈 = monthly.월별표(가짜).반영({"2026-09": ransom.달별세기(목록)}, {}, 오늘=오늘, apply=False)
    assert 셈["새로"] == 2 and not 가짜.만든것 and not 가짜.고친것


def test_판마다는_이번_달과_지난달만_쓴다():
    달별 = {m: {"G": {"건수": 1, "한국": 0, "업종": {}}} for m in
          ("2026-09", "2026-08", "2026-07", "2026-03")}
    assert set(monthly.이번과지난(달별, 오늘)) == {"2026-09", "2026-08"}
    # 1월이면 지난달은 작년 12월이다
    assert set(monthly.이번과지난({"2026-01": {}, "2025-12": {}, "2025-11": {}}, date(2026, 1, 5))) \
        == {"2026-01", "2025-12"}


def test_명부_그룹과_관계로_잇는다():
    쪽 = monthly.그룹쪽표([_명부줄("GroupA", "p-a"), _명부줄("groupa", "p-dup"), _명부줄("", "p-x")])
    assert 쪽 == {"groupa": "p-a"}, 쪽
    가짜 = _가짜노션()
    monthly.월별표(가짜).반영({"2026-09": {"GroupA": {"건수": 1, "한국": 0, "업종": {}}}}, 쪽,
                            오늘=오늘, apply=True)
    assert 가짜.만든것[0]["properties"]["그룹"] == {"relation": [{"id": "p-a"}]}


def test_요약에_그룹_이름이_없다():
    import collections
    s = monthly.요약(collections.Counter({"새로": 3, "고침": 1, "그대로": 40}), "이번 달 · 지난달")
    assert s.strip() == "월별 피해 (이번 달 · 지난달) — 새로 3 · 고침 1 · 그대로 40", s


# ── 조사기 · 조사 한 판 · 워크플로 ─────────────────────────────────
def test_조사기가_받은_달만_남기고_못_받은_달은_뺀다():
    그룹 = [{"name": "GroupA", "locations": [{"available": True, "slug": "http://a.onion"}]}]
    불린수 = [0]

    def 받기(url, m, op=None):
        if url.endswith("/groups"):
            return 그룹
        불린수[0] += 1
        if 불린수[0] == 2:
            raise OSError("한 달 못 받음")
        return 목록

    class _막음:
        def open(self, *a, **k):
            raise AssertionError("밖으로 나가려 했다")

    옛받기, 옛오프너, 옛오늘 = ransom._받기, ransom.오프너, ransom._오늘
    ransom._받기, ransom.오프너 = 받기, (lambda 프록시=None, 갈래="": _막음())
    ransom._오늘 = lambda: 오늘
    try:
        list(ransom.조사(개월수=3))
    finally:
        ransom._받기, ransom.오프너, ransom._오늘 = 옛받기, 옛오프너, 옛오늘
    assert set(ransom.마지막달별) == {"2026-09", "2026-07"}, ransom.마지막달별.keys()
    assert ransom.마지막달별["2026-09"]["GroupA"]["건수"] == 3


def test_명부_조사_한_판이_월별을_부른다():
    글 = (ROOT / "hub" / "places" / "run.py").read_text(encoding="utf-8")
    assert "monthly.판마다(m.n, ransom.마지막달별, 줄들" in 글
    assert "if 갈래 == \"ransom\" and ransom.마지막달별:" in 글


def test_소급_워크플로는_손으로만_기본은_미리보기다():
    글 = (ROOT / ".github" / "workflows" / "ransom-months.yml").read_text(encoding="utf-8")
    assert "schedule:" not in 글, "소급이 예약으로 돈다"
    assert re.search(r"write_to_notion:\n(?:.*\n)*?\s+default: false", 글), "기본이 쓰기다"
    assert "python -m hub.places.monthly --소급 \"$N\" --apply" in 글
    assert "ExcludeExitNodes {kr}" in 글 and "egress.출구확인" in 글, "Tor 관문이 빠졌다"
    assert "group: places" in 글, "명부 조사와 동시에 집계처를 두드린다"
    for 이름 in re.findall(r"^      (\w[\w-]*):\s*$", 글.split("inputs:", 1)[1].split("concurrency:", 1)[0], re.M):
        assert 이름.isascii(), "입력 이름이 한글이면 워크플로가 거부된다: " + 이름


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
