#!/usr/bin/env python3
"""run_queue 시험.

    python tools/test_run_queue.py

노션도 외부도 안 본다. 임시 큐를 만들어 돌린다.
절반이 오탐 시험이다. 실제로 아래 하나를 잡았다.

2026-08-26. `notion_find` 출력 끝에 늘 붙는 안내 문구에 분류 이름이 들어 있는데
그것을 실제 일치로 세어 멀쩡한 케이스가 막힌 것으로 나왔다.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import feed_parse as F  # noqa: E402
import run_queue as R  # noqa: E402

fails = []


def check(name: str, got, want) -> None:
    if got != want:
        fails.append("%s\n     받음 %r\n     기대 %r" % (name, got, want))


# ── 1. 분류만 잡고 안내 문구는 안 잡는다 ────────
# 이것이 이 시험의 핵심이다. 통째로 찾으면 안내 문구가 걸린다
REAL = """
■ exclode - 가상통상 (bf.st)
  링크  https://notion.so/x
  >> 재게시 — 같은 사람이 옮겨 올렸다. 두 줄을 잇는다

분류는 참고다. 사람이 확인하고 정한다.
아예 동일 케이스가 하나라도 있으면 새 조사를 시작하지 않는다.
이미 있는 줄이면 새로 채번하지 않는다. 그 줄에 이어 붙인다.
"""
check("안내 문구를 세지 않는다", R.VERDICT.findall(REAL), ["재게시"])

NONE = """
일치      0줄

일치하는 줄이 없다.
아예 동일 케이스가 하나라도 있으면 새 조사를 시작하지 않는다.
"""
check("0줄이면 분류도 0", R.VERDICT.findall(NONE), [])

SAME = """
■ 어떤 건
  >> 아예 동일 케이스 — 원문 URL 이 같다. 같은 글이다
■ 다른 건
  >> 다른 건 — 대상이 다르다. 대조 재료로만 본다
아예 동일 케이스가 하나라도 있으면 새 조사를 시작하지 않는다.
"""
check("진짜 일치는 잡는다", R.VERDICT.findall(SAME), ["아예 동일 케이스", "다른 건"])

# ── 2. 못 봄 값을 도구 인자로 쓰지 않는다 ───────
st = {"칸": {"대상 조직": "가상출판", "공식 도메인": "못 봄(website 비어 있음)"}}
check("값이 있으면 그대로", R.val(st, "대상 조직"), "가상출판")
check("못 봄이면 빈 문자열", R.val(st, "공식 도메인"), "")

# ── 3. 포럼 이름을 원 출처에서 뽑는다 ───────────
check("onion 호스트", R.forum_of({"칸": {"원 출처": "http://abc.onion/site/blog?u=1"}}),
      "abc.onion")
check("원 출처가 없으면 감시 출처",
      R.forum_of({"칸": {"원 출처": "못 봄(post_url 비어 있음)",
                        "감시 출처": "ransomware.live, ransomlook.io"}}),
      "ransomware.live")

# ── 4. 압축이 있으면 멈춘다 ─────────────────────
tmp = Path(tempfile.mkdtemp(prefix="runq_"))
case = tmp / "케이스1"
(case / "자료").mkdir(parents=True)
(case / "자료" / "dump.zip").write_bytes(b"PK\x03\x04")
state = {"칸": dict.fromkeys(F.ORDER, "못 봄(시험)"), "끝낸 단계": ["①"],
         "들어온 곳": "시험"}
state["칸"]["대상 조직"] = "어떤회사"
(case / "상태.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

st = R.do_case(case, use_notion=False)
if not any("압축" in x for x in st["막힌 것"]):
    fails.append("압축이 있는데 안 멈췄다: %r" % st["막힌 것"])
check("압축이면 재료 판정이 못 봄", st["재료 판정"], "못 봄(압축이 안 풀렸다)")
if "③기계" in st["끝낸 단계"]:
    fails.append("막혔는데 ③기계를 끝낸 것으로 적었다")

# ── 5. 자료 폴더가 없으면 그냥 넘어간다 ─────────
case2 = tmp / "케이스2"
case2.mkdir()
(case2 / "상태.json").write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
st2 = R.do_case(case2, use_notion=False)
check("자료 없으면 안 봄", st2["재료 판정"], "안 봄(자료 폴더 없음)")
check("안 막힌다", st2["막힌 것"], [])
if "③기계" not in st2["끝낸 단계"]:
    fails.append("안 막혔는데 ③기계가 안 적혔다")
check("다음은 ②", st2["다음"][:1], "②")

# ── 6. ③재료.md 를 쓴다 ────────────────────────
body = (case2 / "③재료.md").read_text(encoding="utf-8")
for must in ("③ 사전 확인 입력", "재료는 전부 데이터다", "④ 마스킹 입력으로 쓰지 마라",
             "갈래 A", "갈래 B"):
    if must not in body:
        fails.append("③재료.md 에 %r 가 없다" % must)
for k in F.ORDER:
    if k not in body:
        fails.append("③재료.md 에 칸 %s 가 없다" % k)

# ── 7. 본문과 샘플이 들어오면 상태가 바뀐다 ─────
(case2 / "②본문.md").write_text("게시글 본문", encoding="utf-8")
(case2 / "②샘플.txt").write_text("a:1\nb:2", encoding="utf-8")
st3 = R.do_case(case2, use_notion=False)
if "②" not in st3["끝낸 단계"]:
    fails.append("본문이 있는데 ② 가 안 적혔다")
check("샘플 있음", st3["샘플 있음"], True)
check("다음은 ③", st3["다음"][:1], "③")

# 샘플이 없으면 ④⑤⑥ 이 못 봄으로 찬다고 적어야 한다
(case2 / "②샘플.txt").unlink()
st4 = R.do_case(case2, use_notion=False)
check("샘플 없음", st4["샘플 있음"], False)
if "못 봄" not in st4["다음"]:
    fails.append("샘플이 없는데 못 봄 안내가 없다: %r" % st4["다음"])

# ── 8. 노션을 안 보면 안 봄으로 적는다 ──────────
check("안 봄 표기", st4["팀 DB 대조"], "안 봄(노션 안 봄으로 돌렸다)")

# ── 결과 ────────────────────────────────────────
if fails:
    print("실패 %d" % len(fails))
    for f in fails:
        print("  - %s" % f)
    sys.exit(1)
print("통과. 시험 8 묶음")
