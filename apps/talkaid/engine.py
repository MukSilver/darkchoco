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
import sys
import threading
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

# 엔진을 기계번역으로 띄워도 사이드바는 LLM 을 쓴다. 그때 무엇을 올릴지가 이것이다.
기본LLM = "qwen1.7b"

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


def 자료자리(이름: str) -> list[Path]:
    """자료 파일을 찾을 자리를 앞에서부터 낸다.

    **exe 옆이 맨 앞이다.** 얼려서 지으면 자료가 exe 안에 굳는데 용어·상용구·
    바꿔 쓰기는 계속 는다. 규칙 한 줄 고칠 때마다 141MB 를 다시 지어 다시 보낼
    수는 없다. **파일 하나만 exe 옆에 놓으면 그것이 이긴다.** 12KB 면 메일로 간다.

    소스로 돌 때는 앱 폴더 하나뿐이라 예전과 같다.
    """
    자리 = []
    if getattr(sys, "frozen", False):
        자리.append(Path(sys.executable).resolve().parent / 이름)
    자리.append(HERE / 이름)
    return 자리


def 자료찾기(이름: str) -> Path | None:
    """자료자리 를 차례로 보고 처음 있는 것을 낸다. 없으면 None."""
    for p in 자료자리(이름):
        if p.exists():
            return p
    return None


def 자료읽기(p: Path) -> dict:
    """자료 JSON 을 읽는다. **utf-8-sig 로 읽는다.**

    사람이 메모장이나 PowerShell 로 고쳐 저장하면 앞에 BOM(EF BB BF)이 붙는다.
    utf-8 로 읽으면 거기서 `Unexpected UTF-8 BOM` 으로 죽는다. **갱신하라고
    만든 길에 그 함정을 두지 않는다.** utf-8-sig 는 BOM 이 없어도 그냥 읽는다.
    2026-09-13 에 exe 옆에 갱신본을 놓아 보다가 실제로 걸렸다.
    """
    return json.loads(p.read_text(encoding="utf-8-sig"))


def _rules(p: Path | None = None) -> dict:
    후보들 = [p] if p is not None else 자료자리("terms.json")
    for 후보 in 후보들:
        if 후보 is None or not 후보.exists():
            continue
        try:
            return 자료읽기(후보)
        except Exception as e:
            # 갱신본이 깨졌으면 다음 자리로 물러선다. 통째로 죽는 것보다 낫다
            print("[자료] %s 를 못 읽었다 (%s: %s). 다음 자리를 본다."
                  % (후보, type(e).__name__, e))
    return {}


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


# 풀어 쓴 것을 줄여 쓴다. **뜻이 안 바뀌는 것만 넣는다.**
#
# 일부러 뺀 것 넷이 있다.
#   this is   →  this's 라는 꼴이 영어에 없다
#   let us    →  let us know 를 let's know 로 만들면 뜻이 뒤집힌다
#   have/had  →  I have been 은 I've been 이 맞지만 I have two samples 는 아니다.
#                본동사인지 조동사인지 여기서 가릴 수 없으므로 안 건드린다
#   going to  →  뜻은 같아도 격식이 크게 내려간다. 딱딱해야 할 자리까지 풀어진다
줄임꼴 = [
    (r"\b([Ii]) am\b", r"\1'm"),
    (r"\b([Yy]ou|[Ww]e|[Tt]hey) are\b", r"\1're"),
    (r"\b([Ii]t|[Tt]hat|[Tt]here|[Hh]e|[Ss]he|[Ww]hat|[Ww]ho) is\b", r"\1's"),
    (r"\b([Ii]|[Yy]ou|[Ww]e|[Tt]hey|[Hh]e|[Ss]he|[Ii]t) will\b", r"\1'll"),
    (r"\b([Ii]|[Yy]ou|[Ww]e|[Tt]hey|[Hh]e|[Ss]he) would\b", r"\1'd"),
    (r"\b([Dd]o|[Dd]oes|[Dd]id|[Ii]s|[Aa]re|[Ww]as|[Ww]ere|[Hh]ave|[Hh]as"
     r"|[Hh]ad|[Ww]ould|[Cc]ould|[Ss]hould) not\b", r"\1n't"),
    # 첫 글자를 살린다. Cannot 이 문장 첫머리면 can't 가 아니라 Can't 다
    (r"\bCan ?not\b", "Can't"), (r"\bcan ?not\b", "can't"),
    (r"\bWill not\b", "Won't"), (r"\bwill not\b", "won't"),
]

# 채팅 축약. **기본으로 끈다.** 실측이 반반이기 때문이다.
#
#     ur 6 번  ·  your 8 번        방마다 갈린다 — REDX 38% · Ferriea 0%
#
# 번역기는 u 나 wanna 를 절대 안 낸다. 상용구와 번역칸의 말씨가 벌어지는 곳이
# 바로 여기다. 그런데 늘 켜 두면 격식을 차리던 방에서 갑자기 말투가 바뀌므로,
# **상대에 맞춰 사람이 켠다.**
#
# 실측에서 실제로 쓴 것만 넣었다. going to → gonna 는 뺐다 —
# I'm going to Seoul 이 I'm gonna Seoul 이 되어 뜻이 깨진다.
# you're 가 you 보다 먼저 와야 한다. 순서가 뒤집히면 u're 이 되는데
# 그 꼴은 실측 0 건이다. 실제로 쓴 것은 ur 이다 (if ur not a scammer)
채팅축약 = [
    (r"\b[Yy]ou['’]re\b", "ur"),
    (r"\b[Yy]our\b", "ur"), (r"\b[Yy]ou\b", "u"),
    (r"\b([Ww])ant to\b", r"\1anna"), (r"\b[Gg]ot to\b", "gotta"),
    (r"\b[Ll]et me\b", "lemme"), (r"\b[Kk]ind of\b", "kinda"),
    (r"\b[Tt]hanks\b", "thx"),
]


def 채팅말로(text: str) -> tuple[str, list[str]]:
    """you 를 u 로 줄인다. **사람이 켤 때만 부른다.**

    `말씨다듬기` 와 갈라 둔 이유가 있다. 저쪽은 실측이 71 대 0 이라 늘 맞지만,
    이쪽은 6 대 8 이라 **어느 쪽도 늘 맞지 않는다.** 상대에 따라 갈린다.

        ur 6 번 · your 8 번        방마다 — REDX 38% · 애슐리 40% · Ferriea 8%

    **문장 첫 낱말은 안 건드린다.** 이 낱말들은 실측에서 늘 소문자여서
    (lemme · thx · wanna · gotta · kinda · ur 모두 대문자 0 번) 문장 첫머리를
    바꾸면 거기만 소문자가 된다. 슬랭을 쓰는 방은 문장 전체가 소문자인 경우가
    많지만 (애슐리 88% · REDX 59%) 그렇지 않은 방도 있어서 (Triped 는 슬랭 33%
    인데 소문자 7%) 문체 전체를 내릴 근거는 안 된다. 그래서 첫 낱말은 번역기가
    낸 대로 두고 뒤만 줄인다.
    """
    센것 = 0
    # 구분자를 남기고 쪼갠다. 홀수 자리가 구분자다
    조각들 = re.split(r"([.!?]\s+)", text)
    새것 = []
    for i, 조각 in enumerate(조각들):
        if i % 2 == 1:
            새것.append(조각)
            continue
        m = re.match(r"\s*\S+", 조각)
        머리 = m.group(0) if m else ""
        몸 = 조각[len(머리):]
        for pat, 짧게 in 채팅축약:
            몸, n = re.subn(pat, 짧게, 몸)
            센것 += n
        새것.append(머리 + 몸)
    return "".join(새것), (["채팅 축약 (%d 군데)" % 센것] if 센것 else [])


def 말씨다듬기(text: str) -> tuple[str, list[str]]:
    """번역기가 낸 글을 실제 채팅 말씨로 다듬는다. 0 ms 다. 모델을 안 거친다.

    **실측을 따른다** (우리 발화 157개, 2026-09-16).

        마침표로 끝    9.6%    ← 번역기는 늘 찍는다. 뗀다
        물음표로 끝   29.3%    ← 그대로 둔다
        아무것도 없음  59.2%    ← 이것이 보통이다

        줄여 쓴 것     71 번    ← I'm 29 · I'd 7 · I'll 6 · don't 6 · that's 5
        풀어 쓴 것      0 번    ← I am · do not · it is 를 한 번도 안 썼다

    하는 일이 둘이다.

    **하나. 문장 끝의 마침표 하나를 뗀다.** 여러 문장이면 중간 것은 그대로 둔다 —
    거기까지 떼면 문장 경계가 사라져 읽기 어려워진다. 줄임표(…)와 약어의 마침표도
    안 건드린다.

    **두울. 풀어 쓴 것을 줄여 쓴다.** 실측이 71 대 0 이라 망설일 것이 없다.
    **뜻이 안 바뀌는 것만 넣었다.** `I have been` 을 `I've been` 으로 줄이는 것은
    맞지만 `I have two samples` 를 `I've two samples` 로 줄이면 어색해지므로,
    본동사인지 조동사인지 가릴 수 없는 `have` 와 `had` 는 아예 안 건드린다.
    `going to` → `gonna` 도 뺐다. 뜻은 같아도 격식이 크게 내려가서, 딱딱하게
    가야 할 자리까지 풀어져 버린다.

    첫 글자는 **안 건드린다.** 실측이 대문자 69% 라 번역기가 내는 대로가 맞다.
    상대에 따라 소문자로 쓰기도 하는데(애슐리 88%) 그것은 사람이 고를 일이지
    도구가 정할 일이 아니다.

    주어도 **안 건드린다.** `I` 가 50줄이고 `we` 가 3줄뿐이라 `We're looking for`
    같은 것이 실측과 어긋나 보이지만, 한국어 원문이 「저희」였으면 `we` 가 맞다.
    원문을 모르는 자리에서 주어를 갈면 뜻이 틀린다. 그것은 사람이 볼 일이다.
    """
    바꾼것 = []
    s = text.rstrip()
    # 한 글자짜리 약어(U.S.)나 줄임표는 빼고, 낱말 뒤에 온 마침표 하나만
    if re.search(r"(?<![.A-Z])\.\s*$", s) and not s.endswith(".."):
        s = s[:-1].rstrip()
        바꾼것.append("끝 마침표를 뗐다")
    줄인수 = 0
    for pat, 짧게 in 줄임꼴:
        s, n = re.subn(pat, 짧게, s)
        줄인수 += n
    if 줄인수:
        바꾼것.append("줄여 썼다 (%d 군데)" % 줄인수)
    return s, 바꾼것


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
        # llm=None 으로 띄워도 사이드바는 LLM 을 부른다 (run 의 llm=True).
        # 그때 어느 모델을 올릴지는 따로 들고 있어야 한다
        self.llm_model = llm or 기본LLM
        self._loaded: dict = {}
        self._gen = None
        # 창이 뜨자마자 딴 실에서 미리 올린다. 그 사이 사람이 눌러도 같은 모델을
        # 두 벌 올리면 안 된다 — 1.7B 를 두 번 올리면 메모리가 곱절이다.
        # 기계번역과 LLM 을 따로 잠근다. LLM 을 받는 동안 기계번역은 쓸 수 있어야 한다
        self._자물쇠_기계 = threading.Lock()
        self._자물쇠_llm = threading.Lock()

    # ── 로컬 LLM ──────────────────────────────────
    def load_llm(self):
        """처음 부를 때만 올린다. 1.7B 는 2.8초 걸린다."""
        if self._gen is not None:
            return self._gen
        import ctranslate2
        from huggingface_hub import snapshot_download
        from tokenizers import Tokenizer

        with self._자물쇠_llm:
            # 기다리는 동안 딴 실이 올렸을 수 있다. 잠그고 다시 본다
            if self._gen is not None:
                return self._gen
            d = Path(snapshot_download(LLM_MODELS[self.llm_model]))
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

        with self._자물쇠_기계:
            # 기다리는 동안 딴 실이 올렸을 수 있다. 잠그고 다시 본다
            if pair in self._loaded:
                return self._loaded[pair]
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
    def run(self, text: str, pair: str, back: bool = True,
            llm: bool | None = None, 채팅: bool = False) -> Result:
        # llm 을 안 주면 엔진을 띄울 때 정한 대로 간다. True 를 주면 기계번역으로
        # 띄운 엔진에서도 LLM 을 태운다 — 사이드바가 그렇게 부른다
        import time
        t0 = time.perf_counter()
        r = Result(pair=pair)
        r.sentences = split_sentences(text)
        LLM쓴다 = bool(self.llm) if llm is None else llm

        # LLM 은 자리표도 어미 고치기도 안 쓴다. 둘 다 이 경로에서는 오히려 해롭다.
        #   자리표   낱말의 맥락을 지워 문장이 뻣뻣해진다 (사전이 넷 중 넷으로 이겼다)
        #   어미     **LLM 은 반말 의문형을 스스로 알아듣는다.** 고쳐 주면 되레 나빠진 것이 있다
        if LLM쓴다 and pair == "ko-en":
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

        # **보낼 말에만 건다.** 읽을 말(en-ko·zh-ko)은 내가 읽는 것이라
        # 말씨를 다듬을 이유가 없고, 역번역은 뜻을 보는 것이라 더욱 아니다
        if pair == "ko-en":
            r.text, 다듬은것 = 말씨다듬기(r.text)
            r.swapped += 다듬은것
            if 채팅:                       # 사람이 켰을 때만 you 를 u 로 줄인다
                r.text, 줄인것 = 채팅말로(r.text)
                r.swapped += 줄인것

        # 역번역은 **줄인 뒤의 글**을 되돌린다. 실제로 보낼 것이 그것이라
        # u 나 wanna 때문에 뜻이 흔들리면 여기서 보여야 한다
        if back and BACK.get(pair):
            r.back = self.raw(r.text, BACK[pair])

        r.ms = (time.perf_counter() - t0) * 1000
        return r
