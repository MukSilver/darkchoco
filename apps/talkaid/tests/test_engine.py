#!/usr/bin/env python3
"""engine 의 순수 함수 시험. **모델을 안 올린다.**

    python tests/test_engine.py

모델을 올리면 400 ms 가 들고 인터넷이 필요하다. 파이프라인에서 품질을 실제로
고치는 것은 문장 나누기와 자리표인데 **둘 다 모델 없이 시험할 수 있다.**
번역 자체는 사람이 눈으로 본다.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import engine as E  # noqa: E402

fails = []


def check(name, got, want):
    if got != want:
        fails.append("%s\n     받음 %r\n     기대 %r" % (name, got, want))


# ── 언어 판별 ────────────────────────────────────
check("한국어", E.detect_lang("지금도 신규 제휴자를 받나요?"), "ko")
check("영어", E.detect_lang("Are you still taking on new affiliates?"), "en")
check("중국어", E.detect_lang("这个数据库是从哪里来的？"), "zh")
check("한자가 섞인 한국어는 한국어", E.detect_lang("한국 기업 三星 유출"), "ko")
check("빈 글은 한국어로 둔다", E.detect_lang(""), "ko")

# ── 문장 나누기 — 품질에 가장 크게 걸린다 ──────────
check("두 문장을 나눈다",
      E.split_sentences("확인하고 싶습니다. 백만 개가 맞나요?"),
      ["확인하고 싶습니다.", "백만 개가 맞나요?"])
check("물음표도 끊는다",
      E.split_sentences("맞나요? 아닌가요?"), ["맞나요?", "아닌가요?"])
check("중국어 문장부호도 끊는다",
      E.split_sentences("这是什么？我不知道。"), ["这是什么？", "我不知道。"])
check("줄바꿈으로도 끊는다",
      E.split_sentences("첫 줄\n둘째 줄"), ["첫 줄", "둘째 줄"])
check("한 문장은 그대로", E.split_sentences("하나뿐이다"), ["하나뿐이다"])
check("빈 글은 빈 목록", E.split_sentences("   "), [])
# 소수점이나 줄임표에서 잘못 끊기면 뜻이 무너진다
check("문장부호 뒤에 공백이 없으면 안 끊는다",
      E.split_sentences("파일 1.5GB 짜리"), ["파일 1.5GB 짜리"])

# ── 자리표 ───────────────────────────────────────
용어 = [{"한국어": "어피실리에이트", "영어": "affiliates"},
       {"한국어": "피해사", "영어": "victim organization"},
       {"한국어": "피해", "영어": "damage"}]

t, m = E.protect("신규 어피실리에이트를 받나요?", 용어)
check("용어가 자리표로 빠진다", "어피실리에이트" in t, False)
check("자리표가 들어간다", "XQ" in t, True)
check("짝이 하나", len(m), 1)
check("되돌리면 영어가 들어간다", E.restore(t, m).count("affiliates"), 1)

# 긴 것이 먼저 바뀌어야 한다. 「피해」가 먼저 먹으면 「피해사」가 「damage사」가 된다
t2, m2 = E.protect("게시가 내려간 피해사가 있나요?", 용어)
check("긴 용어가 먼저 바뀐다", "victim organization" in E.restore(t2, m2), True)
check("짧은 용어가 긴 것을 안 먹는다", "damage사" in E.restore(t2, m2), False)

# 모델이 자리표를 그대로 두지 않고 흔든다. 아래는 전부 실제로 본 것이다
check("띄어 쓴 자리표도 되돌린다",
      E.restore("about XQ 1 today", {"XQ1": "affiliates"}), "about affiliates today")
# 이걸 놓쳐서 「What's xQ1.」 이 나갔다 (2026-09-13)
check("소문자로 바뀌어도 되돌린다",
      E.restore("What's xQ1.", {"XQ1": "revenue split"}), "What's revenue split.")
check("둘 다 흔들려도 되돌린다",
      E.restore("about xq 1 today", {"XQ1": "affiliates"}), "about affiliates today")
# XQ1 이 XQ10 안을 먹으면 엉뚱한 자리가 바뀐다
check("두 자리 자리표를 안 먹는다",
      E.restore("XQ10 and XQ1", {"XQ1": "A", "XQ10": "B"}), "B and A")
check("안 나온 자리표는 그냥 둔다",
      E.restore("nothing here", {"XQ1": "A"}), "nothing here")

t3, m3 = E.protect("아무 용어도 없는 문장", 용어)
check("걸릴 것이 없으면 그대로", t3, "아무 용어도 없는 문장")
check("걸릴 것이 없으면 짝도 없다", m3, {})

# ── 반말 의문 어미 ───────────────────────────────
# 모델이 「~있나」를 의문문으로 못 읽는다. 「I don't know if…」 라는 엉뚱한 진술이 된다
어미 = [{"반말": "있나", "존대": "있나요"},
       {"반말": "하나", "존대": "하나요"},
       {"반말": "인가", "존대": "인가요"},
       {"반말": "운영하나", "존대": "운영하나요"}]

check("반말 의문형을 고친다",
      E.fix_question("업종이 있나", 어미), ("업종이 있나요?", "있나 → 있나요?"))
check("긴 어미가 먼저 맞는다",
      E.fix_question("누가 운영하나", 어미)[0], "누가 운영하나요?")
# 물음표를 찍었으면 사람이 의도한 것이다. 안 건드린다
check("물음표가 있으면 안 건드린다",
      E.fix_question("업종이 있나요?", 어미), ("업종이 있나요?", None))
check("마침표가 있으면 안 건드린다",
      E.fix_question("업종이 있다.", 어미), ("업종이 있다.", None))
check("걸리는 어미가 없으면 그대로",
      E.fix_question("그냥 문장", 어미), ("그냥 문장", None))
check("빈 글은 그대로", E.fix_question("", 어미), ("", None))
check("어미 목록이 비면 아무것도 안 한다",
      E.fix_question("업종이 있나", []), ("업종이 있나", None))
# 「하나」는 숫자와 겹친다. 고쳐 버리지만 **무엇을 고쳤는지 반드시 낸다**
_, 고침 = E.fix_question("필요한 건 하나", 어미)
if not 고침:
    fails.append("「하나」 오탐을 고쳤으면서 무엇을 고쳤는지 안 냈다")

실어미 = E.load_endings()
if not 실어미:
    fails.append("terms.json 에 「의문 어미」 가 없다")
for e in 실어미:
    if not e.get("반말") or not e.get("존대"):
        fails.append("의문 어미에 빈 칸이 있다: %r" % e)
        break
for 말 in ("있나", "하나", "인가", "쓰나"):
    if not any(x["반말"] == 말 for x in 실어미):
        fails.append("실측에서 깨진 어미 「%s」 가 목록에 없다" % 말)

# ── 바꿔 쓰기 ────────────────────────────────────
짝 = [{"딱딱": "Could you please explain in detail", "구어": "can you walk me through"},
     {"딱딱": "In order to", "구어": "to"},
     {"딱딱": "As you may already know", "구어": "(뺀다)"}]

out, 바꾼 = E.apply_swaps("Could you please explain in detail?", 짝)
check("번역투가 바뀐다", out, "can you walk me through?")
check("무엇을 바꿨는지 낸다", len(바꾼), 1)

out2, _ = E.apply_swaps("in order to check", 짝)
check("대소문자를 가리지 않는다", out2, "to check")

out3, 바꾼3 = E.apply_swaps("As you may already know, it works.", 짝)
check("(뺀다) 표시는 치환하지 않는다", out3, "As you may already know, it works.")
check("치환 안 했으면 목록에도 없다", 바꾼3, [])

out4, 바꾼4 = E.apply_swaps("nothing to change here", [])
check("규칙이 없으면 그대로", out4, "nothing to change here")

# ── 실제 용어 파일 ───────────────────────────────
실용어 = E.load_terms()
if not 실용어:
    fails.append("terms.json 을 못 읽었다")
for t in 실용어:
    if not t.get("한국어") or not t.get("영어"):
        fails.append("빈 칸이 있는 용어: %r" % t)
        break
# 실측에서 실제로 깨진 셋이 들어 있어야 한다
for 말 in ("어피실리에이트", "피해사", "업종"):
    if not any(x["한국어"] == 말 for x in 실용어):
        fails.append("실측에서 깨진 「%s」 가 용어집에 없다" % 말)

# ── 짝과 사슬 ────────────────────────────────────
for pair in E.MODELS:
    if pair not in E.BACK:
        fails.append("%s 의 역번역 짝이 없다" % pair)
for pair, (a, b) in E.CHAINS.items():
    if a not in E.MODELS or b not in E.MODELS:
        fails.append("사슬 %s 가 없는 모델을 가리킨다" % pair)

# ── run 의 llm 인자가 경로를 가르나 ──────────────
# 모델을 안 올린다. 두 경로를 가짜로 바꿔 놓고 어느 쪽으로 갔는지만 본다


class 길본다(E.Engine):
    def __init__(self, llm):
        super().__init__(terms=[], swaps=[], endings=[], llm=llm)
        self.간길 = []

    def _llm_one(self, text):
        self.간길.append("llm")
        return "LLM"

    def raw(self, text, pair):
        self.간길.append("mt")
        return "MT"


꺼둠 = 길본다(llm=None)
꺼둠.run("규칙이 있나", "ko-en", back=False)
check("기계번역으로 띄우면 기계번역이다", 꺼둠.간길, ["mt"])

꺼둠.간길 = []
꺼둠.run("규칙이 있나", "ko-en", back=False, llm=True)
check("llm=True 면 기계번역 엔진도 LLM 을 탄다", 꺼둠.간길, ["llm"])

켜둠 = 길본다(llm="qwen1.7b")
켜둠.run("규칙이 있나", "ko-en", back=False)
check("LLM 으로 띄우면 LLM 이다", 켜둠.간길, ["llm"])

켜둠.간길 = []
켜둠.run("규칙이 있나", "ko-en", back=False, llm=False)
check("llm=False 면 LLM 엔진도 기계번역으로 간다", 켜둠.간길, ["mt"])

# 기계번역으로 띄워도 어느 모델을 올릴지는 알고 있어야 한다. 모르면 사이드바가 죽는다
check("llm 없이 띄워도 올릴 모델을 안다", E.Engine(llm=None).llm_model, E.기본LLM)
check("llm 을 주면 그것을 올린다", E.Engine(llm="qwen1.7b").llm_model, "qwen1.7b")
if E.기본LLM not in E.LLM_MODELS:
    fails.append("기본LLM %r 이 LLM_MODELS 에 없다" % E.기본LLM)

# ── 같은 모델을 두 번 올리지 않나 ────────────────
# 창이 뜨면 딴 실이 미리 올린다. 그 사이 사람이 눌러도 1.7B 가 두 벌 올라가면 안 된다
이미 = E.Engine()
이미._gen = ("올려둔", "것")
check("LLM 을 이미 올렸으면 그대로 쓴다", 이미.load_llm(), ("올려둔", "것"))
이미._loaded["ko-en"] = ("올려둔", "것", "셋")
check("기계번역도 그대로 쓴다", 이미.load("ko-en"), ("올려둔", "것", "셋"))
for 이름 in ("_자물쇠_기계", "_자물쇠_llm"):
    if not hasattr(이미, 이름):
        fails.append("%s 가 없다. 딴 실이 같이 올리면 두 벌이 뜬다" % 이름)

# ── 결과 ─────────────────────────────────────────
if fails:
    print("실패 %d" % len(fails))
    for f in fails:
        print("  - %s" % f)
    sys.exit(1)
print("통과. 시험 10 묶음")
