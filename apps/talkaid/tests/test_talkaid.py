#!/usr/bin/env python3
"""들어가는 자리 시험. **모델을 안 올리고 창도 안 띄운다.**

    python tests/test_talkaid.py

여기서 보는 것은 하나다 — **바꿔 쓰기 규칙이 조용히 빠지지 않는가.**

`en_style.json` 은 스킬 쪽이 정본이고 이 앱에는 사본을 두지 않는다. 그래서
앱 폴더만 떼어 오거나 exe 에 안 실으면 규칙 스물다섯 짝이 통째로 빠지는데,
죽지도 경고하지도 않아서 쓰는 사람이 모른다. 2026-09-13 에 실제로 지어 둔
exe 가 그 상태였다. 그 일이 되풀이되지 않게 여기서 묶어 둔다.

윈도우가 아니어도 돈다. 창과 클립보드를 안 건드린다.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

여기 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(여기))
import talkaid as T  # noqa: E402

fails = []


def check(name, got, want):
    if got != want:
        fails.append("%s\n     받음 %r\n     기대 %r" % (name, got, want))


# ── 규칙 읽기 ────────────────────────────────────
swaps, 상용구, 알림 = T.규칙()
check("셋을 낸다", (type(swaps), type(상용구), type(알림)), (list, dict, str))

# 레포 안에서 돌리고 있으니 정본이 잡혀야 한다
if not swaps:
    fails.append("레포 안인데 바꿔 쓰기가 비었다. 정본을 못 찾았다:\n     %s" % 알림)
if "en_style.json" not in 알림:
    fails.append("어느 파일을 읽었는지 안 적었다: %r" % 알림)
if not 상용구:
    fails.append("snippets.json 을 못 읽었다")

# ── 못 찾으면 반드시 알린다 ──────────────────────
# 이것이 이 파일의 존재 이유다. 조용히 빠지면 쓰는 사람이 모른다
원래 = T.HERE
try:
    T.HERE = Path(tempfile.mkdtemp()) / "없는앱" / "자리"
    빈swaps, _, 빈알림 = T.규칙()
    check("못 찾으면 규칙이 빈다", 빈swaps, [])
    if "못 찾았다" not in 빈알림:
        fails.append("못 찾았는데 조용하다: %r" % 빈알림)
    if "찾아본 자리" not in 빈알림:
        fails.append("어디를 찾았는지 안 알려 준다: %r" % 빈알림)
finally:
    T.HERE = 원래

# ── exe 에도 실리나 ──────────────────────────────
# spec 이 정본을 읽어 넣어야 한다. 안 넣으면 exe 로 받은 사람만 규칙이 빠진다
spec = (여기 / "talkaid.spec").read_text(encoding="utf-8")
for 이름 in ("terms.json", "snippets.json", "en_style.json"):
    if 이름 not in spec:
        fails.append("talkaid.spec 이 %s 를 안 싣는다. "
                     "exe 로 받은 사람만 그것이 빠진 채 돈다" % 이름)

# 정본은 스킬 쪽 하나다. 앱 폴더에 사본을 두면 갱신이 두 번이 되고 갈린다
if (여기 / "en_style.json").exists():
    fails.append("apps/talkaid/en_style.json 이 생겼다. **사본을 두지 않는다** — "
                 "정본은 skills/skills/darkweb-verify-ko/tools 다")

# ── 로그 자리 ────────────────────────────────────
# TEMP 는 안 된다. 이 PC 에서 TEMP 가 C:\Users\Public\... 이었고 거기는 남도 읽는다
if "Public" in str(T.로그파일):
    fails.append("로그가 공용 폴더로 간다: %s" % T.로그파일)
check("로그는 설정 자리에 둔다", T.로그파일.parent.name, "darkchoco")

# ── 상용구 말씨 ──────────────────────────────────
# 2026-09-16 에 여기서 두 번 틀렸다. 전체 비율만 재고 낱말을 안 봐서, 상용구
# 134개를 소문자로 갈았다가 다시 대문자로 갈았고 그때마다 없던 오류가 생겼다.
# 실측을 낱말 단위로 다시 내어 여기 못 박는다. 근거는 우리 발화 157개다.
#
#   축약에서 아포스트로피를 뺀 적이 0 건이다
#     I'm 29 · I'd 7 · I'll 6 · don't 6 · that's 5 · it's 4 · can't 3 ·
#     you're 3 · what's 1 · let's 1 · there's 1 · didn't 1
#     그리고 im · id · ill · dont · thats · its · cant · youre 는 모두 0
#   u 와 ur 은 소문자 19 · 대문자 0. 문장 첫머리도 소문자다 (u go first)
#   Korea 와 Korean 은 대문자 6 · 소문자 0
#   슬랭 축약은 u · ur · wanna · gonna · kinda · lemme · thx · gotta 만 썼다
#
# 0 번인 것을 둘로 가른다. **슬랭 축약이 0 번이면 막고, 평범한 영어가 0 번이면
# 막지 않는다.** yep 이나 fair enough 가 157개에 없는 것은 이상한 일이 아니지만,
# 어느 슬랭 축약을 쓰느냐는 사람마다 갈리는 지문이라 안 쓰던 것을 넣으면 티가 난다.
import re  # noqa: E402

#
# **아포스트로피와 슬랭은 대소문자를 무시하고 잡는다.** Ill 이나 Nvm 처럼 첫 글자만
# 대문자인 꼴이 실제로 나왔는데, 소문자 패턴만 두면 그것을 놓친다.
# 반대로 U 와 korean 은 대소문자 자체가 잣대이므로 플래그를 안 건다.
말씨금지 = [
    (r"\b(im|ive|id|ill|dont|cant|didnt|wont|thats|whats|lets|theres|youre)\b",
     re.I, "축약에서 아포스트로피를 뺐다. 실측 0 건이다"),
    (r"\b(np|nvm|rn|atm|tmr|gimme|ppl|plz|thnx)\b",
     re.I, "한 번도 안 쓴 슬랭 축약이다. 풀어 쓴다"),
    # 슬랭 축약은 문장 첫머리에서도 소문자였다 — 실측에 「thx」 와
    # 「lemme talk to my boss」 가 그대로 있다. 대문자로 쓴 적이 한 번도 없다
    (r"\b(U|Ur|Thx|Lemme|Wanna|Gotta|Kinda|Gonna)\b", 0,
     "이 축약은 늘 소문자다. 대문자는 실측 0 건이다"),
    (r"\b(korea|korean)\b", 0, "Korea 와 Korean 은 늘 대문자다"),
    ("—", 0, "em dash 는 실측 0 건이다"),
    (r"[\U0001F300-\U0001FAFF☀-➿]", 0, "이모지는 실측 0 건이다"),
]
후보수 = 0
for 페르소나, 갈래들 in 상용구.items():
    for 갈래, 목록 in 갈래들.items():
        for 항목 in 목록:
            for 글 in [항목.get("영어", "")] + list(항목.get("영어들", [])):
                후보수 += 1
                for pat, 플래그, 왜 in 말씨금지:
                    m = re.search(pat, 글, 플래그)
                    if m:
                        fails.append("상용구 말씨 — %s / %s / %s\n"
                                     "     %r 안의 %r\n     %s"
                                     % (페르소나, 갈래, 항목.get("한국어", ""),
                                        글, m.group(0), 왜))
if 후보수 < 100:
    fails.append("상용구 후보가 %d 개뿐이다. 통째로 안 읽힌 것 같다" % 후보수)

# ── requirements.txt 를 pip 가 읽을 수 있나 ───────
#
# pip 의 auto_decode 는 BOM → PEP263 coding 선언 → locale 순으로 본다.
# 앞의 둘이 없으면 한국어 윈도우에서 cp949 로 떨어져 한글 주석에서 죽는다.
# setup.bat 의 chcp 65001 은 콘솔 출력 코드페이지만 바꾸므로 이것을 못 막았다.
# 2026-09-23 에 실제로 팀원 설치가 이것으로 멈추는 것을 확인했다.
req = (여기 / "requirements.txt").read_bytes()
BOM들 = (b"\xef\xbb\xbf", b"\xff\xfe", b"\xfe\xff")
coding선언 = re.compile(rb"coding[:=]\s*([-\w.]+)")
읽히나 = req.startswith(BOM들) or any(
    line[:1] == b"#" and coding선언.search(line) for line in req.split(b"\n")[:2]
)
if not 읽히나:
    fails.append("requirements.txt 에 BOM 도 coding 선언도 없다.\n"
                 "     pip 가 cp949 로 읽어 한글 주석에서 죽는다.\n"
                 "     첫 줄에 # -*- coding: utf-8 -*- 을 둔다")
# 선언이 있어도 실제로 UTF-8 로 풀려야 한다
try:
    req.decode("utf-8")
except UnicodeDecodeError as e:
    fails.append("requirements.txt 가 UTF-8 이 아니다: %s" % e)

# ── 결과 ─────────────────────────────────────────
if fails:
    print("실패 %d" % len(fails))
    for f in fails:
        print("  - %s" % f)
    sys.exit(1)
print("통과. 시험 6 묶음 (상용구 후보 %d 개의 말씨를 봤다)" % 후보수)
