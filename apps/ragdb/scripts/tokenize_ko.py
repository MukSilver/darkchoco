# -*- coding: utf-8 -*-
"""한국어 낱말 쪼개기 — F-06 색인 · F-12 검색 · F-17 질문 키가 함께 쓴다.

세 자리가 **같은 함수**를 써야 한다. 하나만 바꾸면 색인과 질의가 어긋나 아무것도 안 걸린다.

F-06 처리 2 — 「kiwipiepy로 낱말을 쪼개 bm25s 색인을 만든다. 영문 고유명사는 쪼개지 않는다」
"""
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from kiwipiepy import Kiwi

# 남길 품사. 조사(J*) · 어미(E*) · 문장부호(S* 일부)는 뺀다.
#   NNG 일반명사 · NNP 고유명사 · NNB 의존명사 · NR 수사
#   VV 동사 · VA 형용사 · MAG 부사 · XR 어근
#   SL 외국어 · SN 숫자 · SH 한자
KEEP = {"NNG", "NNP", "NNB", "NR", "VV", "VA", "MAG", "XR", "SL", "SN", "SH"}

# 도메인 이름·주소는 통째로 남긴다. 쪼개면 breached.st와 breached.su가 같아진다
DOMAIN = re.compile(r"[a-z0-9][a-z0-9\-]*(?:\.[a-z0-9\-]+)+", re.I)

_kiwi = None


def kiwi():
    global _kiwi
    if _kiwi is None:
        _kiwi = Kiwi()
    return _kiwi


def tokens(text):
    """글자를 낱말 목록으로. 색인과 질의가 같은 결과를 내야 한다."""
    if not text:
        return []

    out = []
    # ① 도메인을 먼저 떼어 통째로 넣는다
    rest = []
    last = 0
    for m in DOMAIN.finditer(text):
        rest.append(text[last:m.start()])
        out.append(m.group(0).lower())
        last = m.end()
    rest.append(text[last:])

    # ② 나머지를 형태소로 쪼개고 내용어만 남긴다
    for seg in rest:
        if not seg.strip():
            continue
        for t in kiwi().tokenize(seg):
            if t.tag not in KEEP:
                continue
            f = t.form.strip().lower()
            if len(f) < 1:
                continue
            # 한 글자 의존명사·부사는 뜻이 옅어 뺀다.
            # 한 글자 동사·형용사는 남긴다 — 「살(다)」 「있(다)」 「없(다)」가 상태를 묻는 핵심이다
            if len(f) == 1 and t.tag in ("NNB", "MAG"):
                continue
            out.append(f)
    return out


def question_key(text):
    """F-17 · F-16의 질문 키 — 낱말을 사전순으로 정렬해 이어붙인 것.

    조사와 어미가 떨어져 나가므로 「브리치드 살아있어?」와 「브리치드는 지금 살아있나요?」가
    같은 키가 된다. 두 기능이 같은 방식을 써야 사전 답변이 걸린다.
    """
    # 부사는 키에서 뺀다 — 「아직 살아있어?」와 「지금 살아있나요?」가 같은 키가 되어야
    # 사전 답변이 걸린다. 색인 쪽 tokens()는 부사를 남긴다
    from kiwipiepy import Kiwi  # noqa
    keep = set()
    for f in tokens(text):
        keep.add(f)
    drop = set()
    for t in kiwi().tokenize(text):
        if t.tag == "MAG":
            drop.add(t.form.strip().lower())
    return " ".join(sorted(keep - drop))


if __name__ == "__main__":
    samples = [
        "브리치드 아직 살아있어?",
        "브리치드는 지금 살아있나요?",
        "BreachForums 회원 수가 몇이야",
        "breached.st 와 breached.su 는 다른 곳인가",
        "한국 개인정보가 올라온 포럼을 알려줘",
    ]
    print("낱말 쪼개기\n")
    for s in samples:
        print("  %-32s" % s)
        print("      %s" % " · ".join(tokens(s)))
    print("\n질문 키 — 앞의 둘이 같아야 한다\n")
    for s in samples[:2]:
        print("  %-32s -> %s" % (s, question_key(s)))
