#!/usr/bin/env python3
"""kit_out 시험.

    python tools/test_kit_out.py

킷 없이 돈다. 킷이 내는 꼴을 그대로 본떠 넣는다.
표본 값은 전부 지어낸 것이다. 실제 유출물에서 가져오지 않았다.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import feed_parse as F  # noqa: E402
import kit_out as K  # noqa: E402

fails = []


def check(name: str, got, want) -> None:
    if got != want:
        fails.append("%s\n     받음 %r\n     기대 %r" % (name, got, want))


# 킷의 `이 글 본문` 출력 형태 그대로. 값은 지어낸 것이다
KIT = """# [SELLING] Example Corp Database 500K

- URL : http://abcdef1234.onion/Thread-Example-Corp-500K
- 도구 : forum_kit v2.2
- 확인 : 2026-08-26 14:02
- 추출 방식 : mybb-post

## 본문

```
We have all customer data of Example Corp. 500,000 rows.
Price: 1200 USD. Contact telegram only.

Sample:
1001,hong@example.com,010-0000-0001,19900101
1002,kim@example.com,010-0000-0002,19910202
1003,lee@example.com,010-0000-0003,19920303
short
Proof screenshots attached.
```

## 추출된 단서

- 텔레그램 : t.me/examplehandle
- 파일 호스팅 : gofile.io/d/aaaa · mega.nz/file/bbbb
- 금액 : 1200 USD

## 페이지 내 링크 (앞 40 · 계정·세션 링크 2개 제외)

- 이 글 → /Thread-Example-Corp-500K
"""


def new_case(tmp: Path, name: str, 원출처: str) -> Path:
    c = tmp / name
    c.mkdir()
    st = {"칸": dict.fromkeys(F.ORDER, "못 봄(시험)"), "끝낸 단계": ["①"],
          "들어온 곳": "시험", "샘플 있음": False}
    st["칸"]["대상 조직"] = "Example Corp"
    st["칸"]["원 출처"] = 원출처
    (c / "상태.json").write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
    return c


tmp = Path(tempfile.mkdtemp(prefix="kitout_"))

# ── 1. 킷 출력을 읽는다 ─────────────────────────
got = K.parse(KIT)
check("제목", got["제목"], "[SELLING] Example Corp Database 500K")
check("URL", got["URL"], "http://abcdef1234.onion/Thread-Example-Corp-500K")
check("도구", got["도구"], "forum_kit v2.2")
check("블록", got["블록"], 1)
check("단서 셋", sorted(got["단서"]), ["금액", "텔레그램", "파일 호스팅"])
check("파일 호스팅 둘", len(got["단서"]["파일 호스팅"]), 2)

# ── 2. 샘플 줄만 고른다 ─────────────────────────
check("샘플 셋", len(got["샘플 줄"]), 3)
for ln in got["샘플 줄"]:
    if not ln.strip().startswith("100"):
        fails.append("샘플이 아닌 줄이 섞였다: %r" % ln)

# 오탐 시험. 이 줄들은 샘플이 아니다
for ln, why in [
    ("short", "여덟 자 미만"),
    ("Proof screenshots attached.", "구분자가 없다"),
    ("Price: 1200 USD", "토막이 셋이 안 된다"),
    ("a:b:c", "여덟 자 미만"),
    ("name:phone:email:date", "긴 숫자도 @ 도 없다"),
]:
    if K.is_sample(ln):
        fails.append("샘플로 잘못 봤다 (%s): %r" % (why, ln))

# 진짜 샘플 꼴은 잡아야 한다
for ln in ["1001,a@b.com,010-0000-0001,19900101",
           "user1|pass|3f2a9c8b7d6e5f4a|active",
           "id:1001;email:x@y.z;phone:01000000001"]:
    if not K.is_sample(ln):
        fails.append("샘플을 놓쳤다: %r" % ln)

# ── 3. 빈 칸만 채우고 있는 값은 안 덮는다 ───────
c1 = new_case(tmp, "빈칸", "못 봄(post_url 비어 있음)")
st1 = json.loads((c1 / "상태.json").read_text(encoding="utf-8"))
filled, clash = K.seat(st1, got)
check("원 출처를 채웠다", st1["칸"]["원 출처"], got["URL"])
check("충돌 없음", clash, [])
if not any("원 출처" in x for x in filled):
    fails.append("채운 목록에 원 출처가 없다: %r" % filled)

c2 = new_case(tmp, "이미있음", "http://abcdef1234.onion/Thread-Example-Corp-500K")
st2 = json.loads((c2 / "상태.json").read_text(encoding="utf-8"))
filled2, clash2 = K.seat(st2, got)
check("같으면 충돌 아님", clash2, [])
check("안 덮음", filled2, [])

c3 = new_case(tmp, "다름", "http://other9999.onion/Thread-Other")
st3 = json.loads((c3 / "상태.json").read_text(encoding="utf-8"))
filled3, clash3 = K.seat(st3, got)
if not clash3:
    fails.append("값이 다른데 충돌로 안 적었다")
check("다르면 안 덮는다", st3["칸"]["원 출처"], "http://other9999.onion/Thread-Other")

# ── 4. 파일을 쓴다 ──────────────────────────────
import io  # noqa: E402
old, sys.stdout = sys.stdout, io.StringIO()
sys.argv = ["kit_out.py", str(c1), "-"]
sys.stdin = io.StringIO(KIT)
rc = K.main()
sys.stdout = old
check("정상 종료", rc, 0)
check("②본문.md 그대로", (c1 / "②본문.md").read_text(encoding="utf-8"), KIT)
sample_txt = (c1 / "②샘플.txt").read_text(encoding="utf-8")
check("샘플 파일 세 줄", len(sample_txt.strip().splitlines()), 3)

st = json.loads((c1 / "상태.json").read_text(encoding="utf-8"))
check("샘플 있음", st["샘플 있음"], True)
if "②" not in st["끝낸 단계"]:
    fails.append("② 가 끝낸 단계에 없다")
check("킷 기록", st["기타"]["킷"]["샘플 줄"], 3)
check("다음", st["다음"][:1], "③")

# ── 5. 본문 절이 없으면 멈춘다 ──────────────────
sys.argv = ["kit_out.py", str(c2), "-"]
sys.stdin = io.StringIO("# 제목만 있고 본문이 없다\n\n- URL : http://x.onion/\n")
old, sys.stdout = sys.stdout, io.StringIO()
try:
    K.main()
    sys.stdout = old
    fails.append("본문이 없는데 안 멈췄다")
except SystemExit:
    sys.stdout = old

# ── 6. 샘플이 없어도 본문은 저장한다 ────────────
NOSAMPLE = KIT.replace("1001,hong@example.com,010-0000-0001,19900101\n", "") \
              .replace("1002,kim@example.com,010-0000-0002,19910202\n", "") \
              .replace("1003,lee@example.com,010-0000-0003,19920303\n", "")
c4 = new_case(tmp, "샘플없음", "못 봄(시험)")
sys.argv = ["kit_out.py", str(c4), "-"]
sys.stdin = io.StringIO(NOSAMPLE)
old, sys.stdout = sys.stdout, io.StringIO()
K.main()
sys.stdout = old
check("본문은 저장", (c4 / "②본문.md").exists(), True)
check("샘플 파일은 안 만든다", (c4 / "②샘플.txt").exists(), False)
st4 = json.loads((c4 / "상태.json").read_text(encoding="utf-8"))
check("샘플 없음", st4["샘플 있음"], False)
if "못 봄" not in st4["다음"]:
    fails.append("샘플이 없는데 못 봄 안내가 없다: %r" % st4["다음"])

# ── 7. 스레드 꼴도 읽는다 ───────────────────────
# 2026-09-08 에 킷의 「이 글 본문」이 `### 원문 / ### 답글 N` 꼴로 바뀌었다.
# 그때부터 `## 본문` 이 안 나오는데 여기는 그것만 보고 있었다.
# **킷이 글을 제대로 읽은 경우가 오히려 빈손으로 떨어졌다** (2026-09-22 확인).
THREAD = """# [SELLING] Example Corp Database 500K

- URL : http://abcdef1234.onion/Thread-Example-Corp-500K
- 도구 : forum_kit v2.7
- 엔진 : mybb
- 확인 : 2026-09-22 03:10
- 답글 쪽 : 2쪽까지 받음

### 원문  seller01  2026-08-26 14:02

```
We have all customer data of Example Corp. 500,000 rows.
1001,hong@example.com,010-0000-0001,19900101
```

### 답글 1  buyer02  2026-08-26 15:30

```
Proof please.
1002,kim@example.com,010-0000-0002,19910202
```

### 답글 2  seller01  2026-08-26 16:00

```
1003,lee@example.com,010-0000-0003,19920303
```

## 추출된 단서

- 텔레그램 : t.me/examplehandle
- 금액 : 1200 USD

## 못 받은 쪽 (1)

- 3쪽 · 403
"""

t = K.parse(THREAD)
check("스레드 블록 셋", t["블록"], 3)
check("스레드 제목", t["제목"], "[SELLING] Example Corp Database 500K")
check("스레드 URL", t["URL"], "http://abcdef1234.onion/Thread-Example-Corp-500K")
check("스레드 샘플 셋", len(t["샘플 줄"]), 3)
check("스레드 단서 둘", sorted(t["단서"]), ["금액", "텔레그램"])

# 단서와 못 받은 쪽 절이 본문으로 새어 들어오면 안 된다
for b in K.bodies(THREAD):
    if "t.me/" in b or "403" in b:
        fails.append("본문 밖 절이 섞였다: %r" % b[:60])

# 이어 받기 판은 「글 N」 으로 적힌다
글N = THREAD.replace("### 원문  seller01", "### 글 1  seller01") \
            .replace("### 답글 1  buyer02", "### 글 2  buyer02") \
            .replace("### 답글 2  seller01", "### 글 3  seller01")
check("글 N 꼴도 읽는다", K.parse(글N)["블록"], 3)

# 블록 꼴은 그대로 돌아야 한다 (예비 경로)
check("블록 꼴 그대로", K.parse(KIT)["블록"], 1)

# 스레드 꼴로도 파일이 써진다
c5 = new_case(tmp, "스레드", "못 봄(시험)")
sys.argv = ["kit_out.py", str(c5), "-"]
sys.stdin = io.StringIO(THREAD)
old, sys.stdout = sys.stdout, io.StringIO()
K.main()
sys.stdout = old
check("스레드도 본문 저장", (c5 / "②본문.md").exists(), True)
check("스레드 샘플 세 줄",
      len((c5 / "②샘플.txt").read_text(encoding="utf-8").strip().splitlines()), 3)

# ── 결과 ────────────────────────────────────────
if fails:
    print("실패 %d" % len(fails))
    for f in fails:
        print("  - %s" % f)
    sys.exit(1)
print("통과. 시험 7 묶음")
