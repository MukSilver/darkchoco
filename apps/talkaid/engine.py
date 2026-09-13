#!/usr/bin/env python3
"""한국어와 외국어를 서로 옮긴다. **밖으로 요청을 보내지 않는다.**

    from engine import Engine, split_sentences, detect_lang
    eng = Engine()
    r = eng.run("지금도 신규 어피실리에이트를 받고 있나요?", "ko-en")
    print(r.text)      # 보낼 영어
    print(r.back)      # 역번역. 뜻이 살았는지 사람이 본다

번역은 CTranslate2 로 이 PC 안에서만 돈다. 팀 규칙이
「번역은 조사 환경 안에서. 외부 서버로 안 나가게」 라서 번역 API 를 부르지 않는다.

## 왜 이 순서인가 (2026-09-13 실측)

기계번역만으로는 스무 문장 중 넷의 뜻이 틀렸다. 무엇이 고치는지 재서 순서를 정했다.

    1  문장 나누기    **효과가 가장 크다.** 두 문장을 합쳐 넣으면 뜻이 뭉개지고
                     의문문이 사라지는데, 나눠 넣으면 둘 다 정확해진다
    2  용어 자리표     「어피실리에이트」는 efisilite 로 깨진다. affiliate 로 미리 바꿔도
                     affliate 가 된다. **XQ1 같은 자리표는 온전히 통과한다**
    3  번역          문장당 50~90 ms
    4  자리표 되돌리기
    5  바꿔 쓰기      번역투를 걷는다. 규칙이라 0 ms
    6  역번역         **뜻이 틀린 것을 사람이 알아보게 한다.** 50~90 ms 가 더 든다

**역번역이 이 도구의 핵심이다.** 「게시가 내려간 피해사가 있나요?」가
「Is there any damage she's doing?」 로 나가는 것을 사람이 못 알아본다.
역번역이 「그녀가 하고 있는 일 중에 피해가 있나요?」 라고 되돌려 주면 즉시 안다.

기계번역은 초안이다. **보낼지는 사람이 정한다.**
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent

# 윈도우에서 개발자 모드가 꺼져 있으면 huggingface_hub 가 심볼릭 링크를 못 만들어
# WinError 1314 로 죽는다. 링크 대신 복사하게 한다 (2026-09-13 실제로 겪었다).
# 모델을 받기 전에 정해져 있어야 하므로 import 자리에서 건다
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS", "1")

# 실측으로 고른 것들이다. 자세한 것은 docs/재기_20260913.md
MODELS = {
    "ko-en": "gaudi/opus-mt-ko-en-ctranslate2",
    "en-ko": "eskara1398/opus-mt-tc-big-en-ko-ct2",
    "zh-en": "gaudi/opus-mt-zh-en-ctranslate2",
}

# 로컬 LLM. **기계번역보다 낫다** — 문장 구조와 빠뜨림에서 이긴다 (2026-09-13 실측).
# 대신 느리다. 문장당 1.5~2.0초. 3초 예산 안이라 대화에 쓸 수 있다.
#
#   4B 는 안 쓴다     받는 데 80분이고 CPU 에서 4초를 넘길 것으로 잡힌다
#   0.6B 도 안 쓴다   빠르지만 못 쓴다. 「백만」을 100으로 읽고 문장이 안 되는 것이 나온다
LLM_MODELS = {
    "qwen1.7b": "jncraton/Qwen3-1.7B-ct2-int8",
}

# 되돌리는 짝. 역번역에 쓴다.
# **역번역은 LLM 을 안 쓴다.** 90ms 짜리 기계번역이면 된다 — 뜻이 흘렀는지
# 사람에게 보이는 것이 일이지 잘 쓰는 것이 일이 아니다
BACK = {"ko-en": "en-ko", "zh-en": "en-ko", "en-ko": "ko-en"}

# 중국어에서 한국어로 곧장 가는 OPUS-MT 모델이 없다. 영어를 거친다
CHAINS = {"zh-ko": ("zh-en", "en-ko")}

# 자리표. XQ1 은 번역을 온전히 통과하는 것을 실측으로 확인했다 (2026-09-13).
# ZZ1ZZ 는 ZZ1Z 로 한 글자가 떨어진다. 바꾸기 전에 반드시 다시 재 볼 것
PH = "XQ%d"
PH_RE = re.compile(r"XQ(\d+)")

# 문장 끝. 갈래를 둘로 둔다.
#   전각 부호(。！？…)  뒤에 공백이 없어도 끊는다. 중국어는 문장 사이를 안 띄운다
#   반각 부호(.!?)     **공백을 반드시 요구한다.** 안 그러면 「1.5GB」 가 잘린다
END = re.compile(r"(?<=[。！？…])\s*|(?<=[.!?])\s+|\n+")

HANGUL = re.compile(r"[가-힣ᄀ-ᇿ㄰-㆏]")
HANZI = re.compile(r"[一-鿿㐀-䶿]")
LATIN = re.compile(r"[A-Za-z]")


def detect_lang(text: str) -> str:
    """ko · zh · en 중 하나. 섞여 있으면 많은 쪽이다."""
    h, z, l = len(HANGUL.findall(text)), len(HANZI.findall(text)), len(LATIN.findall(text))
    if h and h >= z:
        return "ko"
    if z:
        return "zh"
    return "en" if l else "ko"


def split_sentences(text: str) -> list[str]:
    """문장으로 나눈다. **이것이 품질에 가장 크게 걸린다.**

    두 문장을 합쳐 넣으면 모델이 뜻을 뭉개고 의문문을 평서문으로 바꾼다.
    """
    out = [s.strip() for s in END.split(text) if s and s.strip()]
    return out or ([text.strip()] if text.strip() else [])


def _rules(p: Path | None = None) -> dict:
    p = p or HERE / "terms.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def load_terms(p: Path | None = None) -> list[dict]:
    return _rules(p).get("용어", [])


def load_endings(p: Path | None = None) -> list[dict]:
    return _rules(p).get("의문 어미", [])


# 문장 끝의 마침표·물음표. 이것이 있으면 어미를 안 건드린다
END_MARK = re.compile(r"[.!?。！？…]\s*$")


def fix_question(text: str, endings: list[dict]) -> tuple[str, str | None]:
    """반말 의문형을 존댓말 의문형으로 바꾼다. 0 ms 다.

    **모델이 「~있나」를 의문문으로 못 읽는다.** 「I don't know if there's a rule…」
    이라는 엉뚱한 진술이 되거나 평서문이 된다. 어미 하나만 바꾸면 그 실패가 사라진다.
    2026-09-13 실측에서 다섯 중 다섯이 고쳐졌다.

        협상과 유출 사이트는 누가 운영하나      →  Negotiate and leak site.
        협상과 유출 사이트는 누가 운영하나요?   →  Who runs negotiations and leak site.

    **문장부호가 있으면 안 건드린다.** 물음표든 마침표든 사람이 찍었으면 그 뜻대로 둔다.
    「하나」는 숫자와 겹치므로 바꾼 것을 화면에 보여 사람이 오탐을 알아보게 한다.
    """
    t = text.rstrip()
    if not t or END_MARK.search(t):
        return text, None
    for e in sorted(endings, key=lambda x: -len(x.get("반말", ""))):
        반말, 존대 = e.get("반말"), e.get("존대")
        if not 반말 or not 존대 or not t.endswith(반말):
            continue
        새것 = t[: -len(반말)] + 존대 + "?"
        return 새것, "%s → %s?" % (반말, 존대)
    return text, None


def protect(text: str, terms: list[dict]) -> tuple[str, dict[str, str]]:
    """용어를 자리표로 뺀다. 긴 것부터 바꿔야 짧은 것이 먼저 먹지 않는다."""
    mapping: dict[str, str] = {}
    n = 0
    for t in sorted(terms, key=lambda x: -len(x.get("한국어", ""))):
        ko, en = t.get("한국어"), t.get("영어")
        if not ko or not en or ko not in text:
            continue
        n += 1
        key = PH % n
        text = text.replace(ko, key)
        mapping[key] = en
    return text, mapping


def restore(text: str, mapping: dict[str, str]) -> str:
    """자리표를 되돌린다.

    모델이 자리표를 그대로 두지 않고 흔든다. 실제로 본 것들이다 (2026-09-13).

        XQ1  →  xQ1      대소문자를 바꾼다. **이걸 놓쳐서 What's xQ1. 이 나갔다**
        XQ1  →  XQ 1     사이를 띄운다

    `XQ1` 이 `XQ10` 안을 먹지 않게 뒤에 숫자가 오면 안 잡는다.
    """
    for key, val in mapping.items():
        num = key[2:]
        text = re.sub(r"[Xx]\s*[Qq]\s*" + re.escape(num) + r"(?!\d)", val, text)
    return text


def apply_swaps(text: str, swaps: list[dict]) -> tuple[str, list[str]]:
    """번역투를 걷는다. 0 ms 다. 무엇을 바꿨는지도 같이 낸다."""
    바꾼것 = []
    for s in swaps:
        딱딱, 구어 = s.get("딱딱"), s.get("구어")
        if not 딱딱 or not 구어 or 구어.startswith("("):
            continue
        pat = re.compile(re.escape(딱딱), re.I)
        if pat.search(text):
            text = pat.sub(구어, text)
            바꾼것.append("%s → %s" % (딱딱, 구어))
    return text, 바꾼것


@dataclass
class Result:
    text: str = ""                       # 옮긴 것
    back: str = ""                       # 역번역. 뜻 확인용
    sentences: list[str] = field(default_factory=list)
    swapped: list[str] = field(default_factory=list)
    terms: dict[str, str] = field(default_factory=dict)
    endings: list[str] = field(default_factory=list)   # 고친 반말 의문 어미
    ms: float = 0.0
    pair: str = ""


class Engine:
    """모델을 물고 있는다. **단축키마다 새로 올리면 안 된다** — 올리는 데 0.4~1.1초다."""

    def __init__(self, compute_type: str = "int8", threads: int = 8,
                 terms: list[dict] | None = None, swaps: list[dict] | None = None,
                 endings: list[dict] | None = None, llm: str | None = None):
        self.compute_type = compute_type
        self.threads = threads
        self.terms = terms if terms is not None else load_terms()
        self.swaps = swaps if swaps is not None else []
        self.endings = endings if endings is not None else load_endings()
        self.llm = llm            # None 이면 기계번역만. LLM_MODELS 의 열쇠를 주면 그것으로
        self._loaded: dict = {}
        self._gen = None

    # ── 로컬 LLM ──────────────────────────────────
    def load_llm(self):
        """처음 부를 때만 올린다. 1.7B 는 2.8초 걸린다."""
        if self._gen is not None:
            return self._gen
        import ctranslate2
        from huggingface_hub import snapshot_download
        from tokenizers import Tokenizer

        d = Path(snapshot_download(LLM_MODELS[self.llm]))
        self._gen = (
            ctranslate2.Generator(str(d), device="cpu",
                                  compute_type=self.compute_type,
                                  intra_threads=self.threads),
            Tokenizer.from_file(str(d / "tokenizer.json")),
        )
        return self._gen

    def llm_prompt(self, text: str) -> str:
        """걸린 용어만 사전으로 붙인다.

        **자리표보다 낫다** (2026-09-13 실측, 넷 중 넷). 자리표는 그 낱말의 맥락을
        지워 문장이 뻣뻣해지는데, 사전은 뜻을 알려 주므로 유창함이 안 죽는다.

            자리표   double extortion besides any other pressure tactics is used?
            사전     Double extortion aside, are there any other pressure tactics being used?

        걸린 것만 넣는다. 용어집 스물여덟을 다 넣으면 프롬프트가 길어져 느려진다.
        """
        # 이 지시문은 판정 세트로 세 판을 돌려 다듬은 것이다. 한 줄씩 이유가 있다.
        #
        #   translator, not an assistant      LLM 이 질문을 **대답해 버린다.** 여섯 건 났다.
        #                                     「몇 가지 물어봐도 될까요?」 에 "Sure, I can answer
        #                                     that. What do you want to know?" 라고 답했다
        #   Keep the sentence type            앞 판에서 「대답하지 마라」만 넣었더니 평서문까지
        #                                     질문으로 바꿨다. 「사려는 게 아닙니다」 가
        #                                     "Is it not something you want to do?" 가 됐다
        #   Keep the speaker                  같은 이유로 주어가 뒤집혔다. 나와 상대가 바뀐다
        #   Do not think out loud             빈 <think></think> 를 넣어도 짧은 입력에서 샌다.
        #                                     434자짜리 「Okay, let's see. The user said…」 가 나왔다
        지시 = ("You are a translator, not an assistant.\n"
              "The Korean below is a message the user is about to SEND to someone else.\n"
              "**Never answer it. Never reply to it. Never continue the conversation.**\n"
              "Keep the sentence type: a question stays a question, "
              "a statement stays a statement.\n"
              "Keep the speaker: the user is 'I'. Do not swap 'I' and 'you'.\n"
              "Translate it into natural, spoken English for a live chat.\n"
              "Keep the meaning exactly. Do not add or remove anything.\n"
              "Plain conversational English. No slang, no formal letter style.\n"
              "Do not explain. Do not think out loud.\n"
              "Output exactly one line: the English translation. Nothing else.")
        걸린것 = [(t["한국어"], t["영어"]) for t in self.terms
                if t.get("한국어") and t.get("영어") and t["한국어"] in text]
        if 걸린것:
            지시 += "\nUse these exact terms:\n" + "\n".join(
                "  %s = %s" % (k, v) for k, v in 걸린것)
        # Qwen3 는 생각 모드가 기본이라 토큰을 전부 <think> 에 쓴다.
        # 빈 <think></think> 를 미리 넣는 것이 공식 틀의 enable_thinking=False 다
        return ("<|im_start|>system\n%s<|im_end|>\n"
                "<|im_start|>user\n%s<|im_end|>\n"
                "<|im_start|>assistant\n<think>\n\n</think>\n\n" % (지시, text))

    def _llm_one(self, text: str) -> str:
        gen, tok = self.load_llm()
        ids = tok.encode(self.llm_prompt(text), add_special_tokens=False).tokens
        # **정지 토큰을 반드시 준다.** 안 주면 max_length 까지 끝까지 만들어
        # 문장당 5.9초가 된다 (2026-09-13 에 실제로 그랬다)
        out = gen.generate_batch([ids], max_length=256, sampling_temperature=0.2,
                                 include_prompt_in_result=False,
                                 end_token="<|im_end|>")
        return tok.decode(out[0].sequences_ids[0], skip_special_tokens=True).strip()

    # ── 모델 ──────────────────────────────────────
    def load(self, pair: str):
        """처음 부를 때만 올린다."""
        if pair in self._loaded:
            return self._loaded[pair]
        import ctranslate2
        import sentencepiece as spm
        from huggingface_hub import snapshot_download

        d = Path(snapshot_download(MODELS[pair]))
        tr = ctranslate2.Translator(str(d), device="cpu",
                                    compute_type=self.compute_type,
                                    intra_threads=self.threads)
        self._loaded[pair] = (
            tr,
            spm.SentencePieceProcessor(model_file=str(d / "source.spm")),
            spm.SentencePieceProcessor(model_file=str(d / "target.spm")),
        )
        return self._loaded[pair]

    def _one(self, text: str, pair: str) -> str:
        tr, ss, st = self.load(pair)
        src = ss.encode(text, out_type=str) + ["</s>"]
        out = tr.translate_batch([src], beam_size=4, max_decoding_length=384)
        return st.decode(out[0].hypotheses[0])

    def raw(self, text: str, pair: str) -> str:
        """문장을 나눠 넣고 다시 붙인다. 자리표와 바꿔 쓰기는 안 건드린다."""
        if pair in CHAINS:
            a, b = CHAINS[pair]
            return self.raw(self.raw(text, a), b)
        return " ".join(self._one(s, pair) for s in split_sentences(text))

    # ── 본체 ──────────────────────────────────────
    def run(self, text: str, pair: str, back: bool = True) -> Result:
        import time
        t0 = time.perf_counter()
        r = Result(pair=pair)
        r.sentences = split_sentences(text)

        # LLM 은 자리표도 어미 고치기도 안 쓴다. 둘 다 이 경로에서는 오히려 해롭다.
        #   자리표   낱말의 맥락을 지워 문장이 뻣뻣해진다 (사전이 넷 중 넷으로 이겼다)
        #   어미     **LLM 은 반말 의문형을 스스로 알아듣는다.** 고쳐 주면 되레 나빠진 것이 있다
        if self.llm and pair == "ko-en":
            r.text = " ".join(self._llm_one(s) for s in r.sentences)
        else:
            조각 = []
            for s in r.sentences:
                # 어미를 먼저 고친다. 자리표보다 앞이다 — 자리표가 끝에 오면 어미를 못 본다
                if self.endings and pair.startswith("ko-"):
                    s, 고침 = fix_question(s, self.endings)
                    if 고침:
                        r.endings.append(고침)
                보호, 짝 = protect(s, self.terms)
                r.terms.update(짝)
                조각.append(restore(self.raw(보호, pair), 짝))
            r.text = " ".join(조각)

        if self.swaps:
            r.text, r.swapped = apply_swaps(r.text, self.swaps)

        if back and BACK.get(pair):
            r.back = self.raw(r.text, BACK[pair])

        r.ms = (time.perf_counter() - t0) * 1000
        return r
