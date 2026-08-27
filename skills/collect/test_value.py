#!/usr/bin/env python3
"""값 계약 시험.

    python collect/test_value.py

절반이 오탐 시험이다. **`없음` 과 `못 봄` 을 가르는 것**이 이 모듈의 핵심이라
그 둘이 섞이지 않는지를 특히 본다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from collect.value import Rec, V, 값, 못봄, 미확인, 안봄, 없음, 추정  # noqa: E402

fails = []


def check(name: str, got, want) -> None:
    if got != want:
        fails.append("%s\n     받음 %r\n     기대 %r" % (name, got, want))


def throws(name: str, fn) -> None:
    try:
        fn()
        fails.append("%s: 막았어야 하는데 통과했다" % name)
    except ValueError:
        pass


# ── 1. 넷을 만든다 ──────────────────────────────
a = V.봤다("가상출판", src="krleak.db", day="2026-08-27")
b = V.없다(src="수집 DB 직접 조회", day="2026-08-27")
c = V.막혔다("Cloudflare 챌린지", src="bf.st", day="2026-08-27")
d = V.안봤다()
check("값", a.state, 값)
check("없음", b.state, 없음)
check("못 봄", c.state, 못봄)
check("안 봄", d.state, 안봄)

# ── 2. 없음만 부재의 근거다 ─────────────────────
# 이것이 이 모듈이 있는 이유다. 검색으로 못 찾은 것을 없음으로 적으면 안 된다
check("값은 근거 아님", a.부재의근거인가(), False)
check("**없음만 근거**", b.부재의근거인가(), True)
check("못 봄은 근거 아님", c.부재의근거인가(), False)
check("안 봄은 근거 아님", d.부재의근거인가(), False)

# ── 3. 못 봄에는 사유가 있어야 한다 ─────────────
throws("사유 없는 못 봄", lambda: V(못봄))
throws("사유 없는 못 봄 2", lambda: V(못봄, why=""))
V(못봄, why="토큰 없음")          # 사유가 있으면 된다

# ── 4. 값 상태인데 값이 비면 막는다 ─────────────
throws("빈 값", lambda: V(값, v=""))
throws("None 값", lambda: V(값, v=None))
throws("모르는 상태", lambda: V("확인됨"))
throws("모르는 확신도", lambda: V(값, v="x", sure="아마도"))

# ── 5. 확신도는 상태와 다른 축이다 ──────────────
e = V.봤다("한국", src="국가 코드에서 미루어", sure=추정)
check("추정도 값이다", e.state, 값)
check("확신도만 다르다", e.sure, 추정)
check("추정은 부재 근거 아님", e.부재의근거인가(), False)
if "추정" not in e.글자():
    fails.append("추정 표시가 글자에 안 나온다: %r" % e.글자())

# ── 6. 사람이 읽는 한 줄 ────────────────────────
check("값 글자", a.글자(), "가상출판 (krleak.db · 2026-08-27)")
check("없음 글자", b.글자(), "없음 (수집 DB 직접 조회 · 2026-08-27)")
check("못 봄 글자", c.글자(), "못 봄(Cloudflare 챌린지) · 2026-08-27")
check("안 봄 글자", d.글자(), "안 봄")

# ── 7. 안 봄은 키를 아예 안 만든다 ──────────────
check("안 봄은 짐이 없다", d.짐(), None)
if a.짐() is None:
    fails.append("값인데 짐이 없다")

r = Rec(표본기준="상위 50건 기준. 전체 아님", 수집방식="api", 도구="ransom.py v1")
r.넣기("대상 조직", a)
r.넣기("공식 도메인", b)
r.넣기("원 출처", c)
r.넣기("주장 규모", d)
짐 = r.짐()
check("안 본 칸은 빠진다", "주장 규모" in 짐["칸"], False)
check("나머지 셋은 있다", len(짐["칸"]), 3)
check("표본 기준이 머리에", 짐["표본기준"], "상위 50건 기준. 전체 아님")

# ── 8. 왕복 ─────────────────────────────────────
for x in (a, b, c, d, e):
    back = V.풀기(x.짐())
    check("왕복 %s" % x.state, (back.state, back.v, back.why, back.sure),
          (x.state, x.v, x.why, x.sure))

j = json.loads(r.json())
check("json 왕복", j["칸"]["대상 조직"]["v"], "가상출판")

# ── 9. 못 본 칸을 셀 수 있다 ────────────────────
check("못 본 칸", r.못본칸(), ["원 출처"])

# ── 10. 글자 출력에 순서를 줄 수 있다 ───────────
줄 = r.글자(["대상 조직", "공식 도메인", "원 출처", "주장 규모"])
check("네 줄 + 머리", len(줄.splitlines()), 5)
if "안 봄" not in 줄:
    fails.append("안 본 칸이 화면에는 나와야 한다. 저장만 빠진다")
if "상위 50건 기준" not in 줄:
    fails.append("표본 기준이 머리에 안 나온다")

# ── 결과 ────────────────────────────────────────
if fails:
    print("실패 %d" % len(fails))
    for f in fails:
        print("  - %s" % f)
    sys.exit(1)
print("통과. 시험 10 묶음")
