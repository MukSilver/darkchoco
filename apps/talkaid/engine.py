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

# 되돌리는 짝. 역번역에 쓴다
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
                 endings: list[dict] | None = None):
        self.compute_type = compute_type
        self.threads = threads
        self.terms = terms if terms is not None else load_terms()
        self.swaps = swaps if swaps is not None else []
        self.endings = endings if endings is not None else load_endings()
        self._loaded: dict = {}

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
