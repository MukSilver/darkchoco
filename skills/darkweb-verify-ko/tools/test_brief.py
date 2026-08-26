#!/usr/bin/env python3
"""brief 시험.

    python tools/test_brief.py

큐를 임시로 만들어 다섯 묶음이 제대로 갈리는지 본다.
**추리지 않고 나눈다**가 규칙이라 넣은 건수와 낸 건수가 같아야 한다.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import brief as B  # noqa: E402
import feed_parse as F  # noqa: E402

fails = []


def check(name: str, got, want) -> None:
    if got != want:
        fails.append("%s\n     받음 %r\n     기대 %r" % (name, got, want))


tmp = Path(tempfile.mkdtemp(prefix="brief_"))


def case(name: str, **kw) -> Path:
    d = tmp / name
    d.mkdir()
    st = {"칸": dict.fromkeys(F.ORDER, "못 봄(시험)"), "끝낸 단계": ["①"],
          "들어온 곳": "시험", "샘플 있음": False}
    st["칸"].update(kw.pop("칸", {}))
    st.update(kw)
    (d / "상태.json").write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
    return d


# 다섯 묶음이 하나씩 나오게 만든다
case("a_막힘", **{"막힌 것": ["압축이 안 풀렸다"],
                "칸": {"대상 조직": "가나회사", "탐지 시각": "2026-08-20T00:00:00"}})
case("b_아는건", **{"도구 분류": {"재게시": 2},
                 "칸": {"대상 조직": "다라회사", "탐지 시각": "2026-08-21T00:00:00"}})
case("c_열어야", **{"칸": {"대상 조직": "마바회사", "탐지 시각": "2026-08-22T00:00:00"}})
d = case("d_돌릴수", **{"칸": {"대상 조직": "사아회사", "탐지 시각": "2026-08-23T00:00:00"}})
(d / "②본문.md").write_text("본문", encoding="utf-8")
e = case("e_끝남", **{"끝낸 단계": ["①", "②", "③기계", "⑥"],
                    "칸": {"대상 조직": "자차회사", "탐지 시각": "2026-08-24T00:00:00"}})
(e / "②본문.md").write_text("본문", encoding="utf-8")

rows = B.load(tmp, None)
check("다섯 건", len(rows), 5)

buckets = {name: B.bucket(st, tmp / name) for name, st in rows}
check("막힘", buckets["a_막힘"], "막힌 것")
check("아는 건", buckets["b_아는건"], "이미 아는 건")
check("열어야", buckets["c_열어야"], "열어야 할 것")
check("돌릴 수", buckets["d_돌릴수"], "돌릴 수 있는 것")
check("끝남", buckets["e_끝남"], "끝난 것")

# 막힘이 다른 무엇보다 먼저다. 끝났어도 막혔으면 막힌 것으로 간다
check("막힘이 우선",
      B.bucket({"막힌 것": ["x"], "끝낸 단계": ["⑥"]}, tmp / "e_끝남"), "막힌 것")

text = B.render(rows, tmp, None)

# ── 추리지 않는다. 다섯이 다 나와야 한다 ────────
for org in ("가나회사", "다라회사", "마바회사", "사아회사", "자차회사"):
    if org not in text:
        fails.append("브리핑에서 %s 가 빠졌다" % org)
check("건수 표기", "건수 5" in text, True)

# ── 묶음마다 무엇을 하는지 적는다 ───────────────
for k in B.ORDER_B:
    if k not in text:
        fails.append("묶음 %s 가 없다" % k)
    if B.WHY[k] not in text:
        fails.append("묶음 %s 의 할 일이 없다" % k)

# ── 확정이 아니라는 표기 ────────────────────────
for must in ("도구가 낸 분류는 확정이 아니다", "② 와 ⑧ 은 끝까지 사람이 한다"):
    if must not in text:
        fails.append("브리핑에 %r 가 없다" % must)

# ── 막힌 이유를 그대로 보인다 ───────────────────
if "압축이 안 풀렸다" not in text:
    fails.append("막힌 이유가 안 나온다")

# ── since 로 자른다 ─────────────────────────────
check("22일 이후 셋", len(B.load(tmp, "2026-08-22")), 3)
check("25일 이후 없다", len(B.load(tmp, "2026-08-25")), 0)

# ── 상태.json 이 깨져도 안 죽는다 ───────────────
bad = tmp / "f_깨짐"
bad.mkdir()
(bad / "상태.json").write_text("{깨진 JSON", encoding="utf-8")
rows2 = B.load(tmp, None)
check("깨진 것도 센다", len(rows2), 6)
if B.bucket(dict(rows2[-1][1]), bad) != "막힌 것":
    fails.append("깨진 상태를 막힌 것으로 안 넣었다")

# ── 결과 ────────────────────────────────────────
if fails:
    print("실패 %d" % len(fails))
    for f in fails:
        print("  - %s" % f)
    sys.exit(1)
print("통과. 시험 7 묶음")
