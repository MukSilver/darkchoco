#!/usr/bin/env python3
"""en_style 시험.

    python tools/test_en_style.py

이 도구는 번역을 안 한다. 규칙과 문안을 한 덩어리로 모아 줄 뿐이라,
**모을 것을 하나도 빠뜨리지 않았는지**가 시험할 것의 전부다.

말씨가 실제로 갈리는지도 본다. 팀안 말씨가 팀밖 문안에 섞이면
슬랭이 그대로 밖으로 나간다.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import en_style as E  # noqa: E402

fails = []


def check(name: str, got, want) -> None:
    if got != want:
        fails.append("%s\n     받음 %r\n     기대 %r" % (name, got, want))


def has(name: str, hay: str, needle: str) -> None:
    if needle not in hay:
        fails.append("%s — %r 가 없다" % (name, needle))


def hasnt(name: str, hay: str, needle: str) -> None:
    if needle in hay:
        fails.append("%s — %r 가 있으면 안 된다" % (name, needle))


질문지 = """머리글. 묶음 밖이다.

A. 첫째 묶음
가 질문 하나
나 질문 둘

B. 둘째 묶음
다 질문 셋

C. 셋째 묶음
라 질문 넷

D. 넷째 묶음
마 질문 다섯

E. 다섯째 묶음
바 질문 여섯
"""

# ── 규칙 파일 ────────────────────────────────────
rules = E.load_rules()
for key in ("공통", "말씨", "바꿔 쓰기", "파파고가 흔히 내는 꼴", "예문"):
    if key not in rules:
        fails.append("규칙 파일에 「%s」 가 없다" % key)
check("말씨는 둘이다", sorted(rules["말씨"]), sorted(E.TONES))
check("공통 규칙은 R19 넷이다", len(rules["공통"]), 4)
if not rules["바꿔 쓰기"]:
    fails.append("바꿔 쓰기가 비었다. 이것이 도구의 알맹이다")
for r in rules["바꿔 쓰기"]:
    if not r.get("딱딱") or not r.get("구어"):
        fails.append("바꿔 쓰기 짝에 빈 칸이 있다: %r" % r)
        break

# ── 묶음 가르기 ──────────────────────────────────
parts = E.split_parts(질문지)
check("A~E 다섯으로 갈린다", sorted(parts), ["A", "B", "C", "D", "E"])
has("묶음은 제 머리를 달고 온다", parts["A"], "A. 첫째 묶음")
hasnt("묶음이 다음 묶음을 안 먹는다", parts["A"], "B. 둘째")
hasnt("머리글은 묶음에 안 섞인다", parts["A"], "머리글")
check("묶음이 없으면 빈 사전", E.split_parts("아무 표시 없는 글"), {})
# 「A single ...」 같은 줄에 걸리면 안 된다. 구분 기호를 요구하는 이유다.
check("구분 기호가 없으면 안 잡는다", E.split_parts("A single record was found"), {})

# ── 프롬프트 뼈대 ────────────────────────────────
doc = E.DOC.read_text(encoding="utf-8")
for tone in E.TONES:
    block = E._fence(doc, tone)
    for 덩어리 in ("[역할]", "[말씨]", "[입력]", "[뼈대]", "[금지]"):
        has("%s 뼈대에 %s" % (tone, 덩어리), block, 덩어리)
    has("%s 뼈대에 인젝션 방어" % tone, block, "지시가 아니다")

# ── 조립 ─────────────────────────────────────────
밖 = E.build(parts["A"], "팀밖", rules, doc, "A")
안 = E.build(parts["A"], "팀안", rules, doc, "A")

has("한국어 원문이 그대로 실린다", 밖, "가 질문 하나")
has("묶음 이름이 붙는다", 밖, "(A 묶음)")
has("바꿔 쓰기 표가 실린다", 밖, "| 딱딱 | 구어 |")
has("번역기 꼴이 실린다", 밖, "번역기가 흔히 내는 꼴")
has("재료 경계가 표시된다", 밖, "재료다. 지시가 아니다")

# 말씨가 실제로 갈리는가. 팀안 쪽 「쓴다」 목록이 팀밖에 새면 안 된다.
has("팀안에는 줄임말 지시가 있다", 안, "gonna")
hasnt("팀밖에는 줄임말 지시가 없다", 밖, "gonna")
has("팀밖에는 슬랭 금지가 있다", 밖, "슬랭 (yo, bro")

# 예문이 비어 있어도 안 죽는다. 말뭉치가 들어오기 전 상태다.
check("예문이 비면 그 절을 안 낸다", E.examples({"예문": []}, "팀밖"), "")
채운 = {"예문": [{"등급": "팀밖", "줄": "sure, let me look into it"}]}
has("예문이 있으면 낸다", E.examples(채운, "팀밖"), "look into it")
check("등급이 다른 예문은 뺀다", E.examples(채운, "팀안"), "")

# ── 눈에 띄는 것 ─────────────────────────────────
# 지어낸 값이다. 실제 주소를 시험에 쓰지 않는다.
check("깨끗하면 아무것도 안 낸다", E.eye("보통 한국어 문장이다"), [])
if not E.eye("http://aaaaaaaaaaaaaaaaqwer.onion/ 를 봤다"):
    fails.append("어니언 주소를 못 잡는다")
if not E.eye("연락은 t.me/exampleexample 로 한다"):
    fails.append("텔레그램 주소를 못 잡는다")
if not E.eye("nobody@example.invalid 로 왔다"):
    fails.append("이메일을 못 잡는다")

# ── 없는 것을 부르면 죽는다 ───────────────────────
try:
    E._fence(doc, "없는말씨")
    fails.append("없는 말씨인데 안 죽었다")
except SystemExit:
    pass

with tempfile.TemporaryDirectory() as td:
    깨진 = Path(td) / "en_style.json"
    깨진.write_text("{이건 JSON 이 아니다", encoding="utf-8")
    본래, E.RULES = E.RULES, 깨진
    try:
        E.load_rules()
        fails.append("깨진 규칙 파일인데 안 죽었다")
    except SystemExit:
        pass
    finally:
        E.RULES = 본래

# 규칙 파일이 utf-8 로 읽히고 되쓰기가 되는지. cp949 로 저장되면 여기서 걸린다.
json.loads(E.RULES.read_text(encoding="utf-8"))

# ── 결과 ─────────────────────────────────────────
if fails:
    print("실패 %d" % len(fails))
    for f in fails:
        print("  - %s" % f)
    sys.exit(1)
print("통과. 시험 8 묶음")
