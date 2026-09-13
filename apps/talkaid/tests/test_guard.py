#!/usr/bin/env python3
"""guard 시험.

    python tests/test_guard.py

**표본에 진짜 이름과 진짜 주소를 쓰지 않는다.** 2026-09-06 에 팀 레포의 시험 표본에
실명과 실제 텔레그램 주소가 남아 있던 것을 발견해 익명화한 적이 있다. 같은 일을
여기서 반복하지 않는다. 아래는 전부 지어낸 값이다.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import guard as G  # noqa: E402

fails = []


def 막힌다(name, text):
    v = G.check(text, block=[])
    if not v.막힘:
        fails.append("%s — 막았어야 한다: %r" % (name, text))


def 안막힌다(name, text):
    v = G.check(text, block=[])
    if v.막힘:
        fails.append("%s — 막으면 안 된다: %r  (%s)" % (name, text, v.말))


def 경고한다(name, text, 조각):
    v = G.check(text, block=[])
    if not any(조각 in w for w in v.경고):
        fails.append("%s — 「%s」 경고가 없다. 나온 것: %r" % (name, 조각, v.경고))


# ── 팀 신원은 막는다 ─────────────────────────────
막힌다("팀 이름 한글", "저희는 다크초코 팀입니다")
막힌다("팀 이름 영문", "we are from darkchoco")
막힌다("학교 한글", "화이트햇 스쿨에서 조사 중입니다")
막힌다("학교 영문", "This is Whitehat School")
막힌다("띄어쓴 학교", "white hat school project")
막힌다("협업 언론", "국민일보와 함께 보고 있습니다")
막힌다("협업사", "cape labs 와 협업 중")
막힌다("공개 계정", "reported by d4rkn3ttz")
막힌다("대소문자 섞임", "WE ARE DarkChoco")

# ── 우리 자리도 막는다 ───────────────────────────
막힌다("노션 주소", "see https://www.notion.so/abc123")
막힌다("우리 저장소", "github.com/MukSilver/darkchoco")
막힌다("내부 케이스 이름", "this matches LEAK-27 in our records")
막힌다("윈도우 개인 경로", r"the file is at C:\Users\someone\Desktop\a.txt")
막힌다("유닉스 개인 경로", "saved to /home/someone/data.csv")

# ── 신분을 밝히는 말은 경고만 한다 ────────────────
# 팀 문서상 기자는 신분을 밝히고 접근한다. 막으면 의도한 문안이 막힌다
안막힌다("기자라고 밝히는 것은 막지 않는다", "I am a journalist working on a story")
경고한다("기자는 경고로 뜬다", "I am a journalist working on a story", "신분")
경고한다("연구자도 경고", "I am a security researcher", "신분")

# ── 개인정보는 경고 ──────────────────────────────
경고한다("이메일", "reach me at nobody@example.invalid", "이메일")
경고한다("전화번호", "call 010-0000-0000", "전화")
경고한다("주민번호 꼴", "the field looks like 900101-1000000", "주민번호")
안막힌다("개인정보는 막지는 않는다", "reach me at nobody@example.invalid")

# ── 번역이 안 된 한글 ────────────────────────────
경고한다("한글이 남았다", "Are you still 받고 있나요?", "한글")
v = G.check("Are you still taking new affiliates?", block=[])
if any("한글" in w for w in v.경고):
    fails.append("영어만 있는데 한글 경고가 떴다")

# ── 깨끗한 글은 아무것도 안 걸린다 ────────────────
for s in ["Are you still taking on new affiliates?",
          "Where's the line between operators and affiliates?",
          "Can you walk me through how the split works?",
          "one sec, let me check that"]:
    v = G.check(s, block=[])
    if v.막힘 or v.경고:
        fails.append("깨끗한 글에 오탐: %r → %s" % (s, v.말))

# ── 실명 목록 ────────────────────────────────────
v = G.check("hello", block=["ZZTESTNAME"])
if v.막힘 or v.못봄:
    fails.append("목록에 없는 말인데 걸렸다: %s" % v.말)
v = G.check("hello ZZTESTNAME there", block=["ZZTESTNAME"])
if not v.막힘:
    fails.append("목록에 있는 말을 못 막았다")

with tempfile.TemporaryDirectory() as td:
    없는파일 = Path(td) / "없다"
    v = G.check("hello", block_file=없는파일)
    if not v.못봄:
        fails.append("목록 파일이 없으면 「못 봄」으로 적어야 한다")
    있는파일 = Path(td) / "있다"
    있는파일.write_text("# 주석은 무시한다\nZZFAKE\n\n  ZZSPACED  \n", encoding="utf-8")
    목록 = G.load_block(있는파일)
    if 목록 != ["ZZFAKE", "ZZSPACED"]:
        fails.append("목록 읽기가 틀렸다: %r" % 목록)

# ── 값이 새지 않는다 ─────────────────────────────
# 걸린 값을 그대로 적으면 로그가 곧 반출이다
v = G.check("we are darkchoco and my mail is nobody@example.invalid", block=["ZZSECRET"])
말 = v.말
for 새면안됨 in ["darkchoco", "nobody@example.invalid", "ZZSECRET"]:
    if 새면안됨 in 말:
        fails.append("걸린 값이 출력에 그대로 나왔다: %r" % 새면안됨)

# ── 우회 시도 ────────────────────────────────────
# 제로폭 문자 한 글자면 모든 규칙이 빗나간다
막힌다("제로폭이 끼어 있어도", "dark\u200bchoco team")
막힌다("전각으로 써도", "ｄａｒｋｃｈｏｃｏ")

# ── BOM 이 붙어도 첫 줄이 걸리나 ─────────────────
# **여기가 특히 중요하다.** 실명 목록은 사람이 손으로 만드는 파일이고 메모장으로
# 저장하면 BOM 이 붙는다. utf-8 로 읽으면 첫 줄이 "﻿홍길동" 이 되어
# **그 이름만 조용히 안 걸린다.** 막아야 할 것이 새는 자리다
with tempfile.TemporaryDirectory() as td:
    bom목록 = Path(td) / "talkaid_block"
    bom목록.write_text("﻿ZZFIRST\nZZSECOND\n", encoding="utf-8")
    if bom목록.read_bytes()[:3] != b"\xef\xbb\xbf":
        fails.append("시험이 BOM 을 못 만들었다. 이 시험이 무의미하다")
    읽은것 = G.load_block(bom목록)
    if 읽은것 != ["ZZFIRST", "ZZSECOND"]:
        fails.append("BOM 이 붙은 목록을 잘못 읽었다: %r" % 읽은것)
    if 읽은것 and 읽은것[0].startswith("﻿"):
        fails.append("첫 이름에 BOM 이 묻었다. **그 이름만 조용히 안 걸린다**")
    # 실제로 막히는지까지 본다. 목록만 맞고 안 막히면 뜻이 없다
    v = G.check("contact ZZFIRST now", block=읽은것)
    if not v.막힘:
        fails.append("BOM 이 붙었던 첫 이름이 안 막힌다")

# ── 결과 ─────────────────────────────────────────
if fails:
    print("실패 %d" % len(fails))
    for f in fails:
        print("  - %s" % f)
    sys.exit(1)
print("통과. 시험 8 묶음")
