#!/usr/bin/env python3
"""창 시험. **모델을 안 올리고 단축키도 안 잡는다.**

    python tests/test_ui.py

창을 실제로 만들되 `mainloop` 은 안 돌린다. `update()` 로 한 번 그리고 위젯을 본다.
번역은 가짜 엔진으로 갈아 끼운다 — 모델을 올리면 2.8초가 들고 인터넷이 필요하다.

**전역 단축키를 안 잡는다.** 온 시스템이 나눠 쓰는 것이라 시험이 잠깐이라도
채가면 사람이 그때 누른 것이 안 먹는다.

윈도우가 아니거나 화면이 없으면 건너뛴다.
"""
from __future__ import annotations

import pathlib
import queue
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if sys.platform != "win32":
    print("건너뜀 — 윈도우 전용이다 (win.py 가 Win32 API 다)")
    raise SystemExit(0)
import engine as E  # noqa: E402
import ui as U  # noqa: E402
import win as W  # noqa: E402

# **확인용 창을 따로 만들지 않는다.** 만들었다 지우면 sv-ttk 가 테마를 걸 때
# 죽은 창에 event 를 쏴서 Tcl 이 시끄럽다. 진짜 창을 만들어 보고 안 되면 건너뛴다

fails = []


def check(name, got, want):
    if got != want:
        fails.append("%s\n     받음 %r\n     기대 %r" % (name, got, want))


class 가짜엔진:
    """모델을 안 올린다. 넣은 대로 돌려준다.

    `LLM터짐` 을 켜면 llm=True 로 부를 때만 예외를 던진다. 사이드바가
    기계번역으로 물러서는지 보는 데 쓴다.
    """
    def __init__(self, LLM터짐: bool = False):
        self.부른것 = []
        self.LLM터짐 = LLM터짐

    def run(self, text, pair, back=True, llm=None, 채팅=False):
        self.부른것.append((text, pair, back, llm))
        self.채팅으로부른것 = getattr(self, "채팅으로부른것", [])
        self.채팅으로부른것.append(채팅)
        if llm and self.LLM터짐:
            raise RuntimeError("모델을 못 올렸다")
        r = E.Result(pair=pair)
        r.text = "%s(%s)" % ("LLM" if llm else "EN", text)
        r.back = "KO(%s)" % text if back else ""
        r.ms = 12.0
        r.sentences = [text]
        return r


# ── 창이 서나 ────────────────────────────────────
eng = 가짜엔진()
상용구 = {"맞장구": [{"한국어": "알겠습니다.", "영어": "got it"},
                {"한국어": "이해했습니다.", "영어": "makes sense"}],
        "시간 벌기": [{"한국어": "잠시만요.", "영어": "one sec"}]}
try:
    w = U.창(eng, 상용구, 단축키켜기=False)
    w.root.update()
except Exception as e:
    print("건너뜀 — 창을 못 만든다 (%s: %s)" % (type(e).__name__, str(e)[:50]))
    raise SystemExit(0)

check("단축키를 안 잡았다", w.키, None)
for 이름 in ("입력", "결과", "역번역", "알림", "상태", "옆", "속", "준비단추"):
    if not hasattr(w, 이름):
        fails.append("위젯 %s 가 없다" % 이름)

# ── 사이드바 열고 닫기 ───────────────────────────
check("처음엔 닫혀 있다", w.사이드바열림, False)
w.사이드바(); w.root.update()
check("누르면 열린다", w.사이드바열림, True)
if "◂" not in w.준비단추.cget("text"):
    fails.append("열렸는데 단추 글자가 안 바뀌었다: %r" % w.준비단추.cget("text"))
w.사이드바(); w.root.update()
check("다시 누르면 닫힌다", w.사이드바열림, False)

# ── 결과를 받으면 그리나 ─────────────────────────
r = E.Result(pair="ko-en"); r.text = "Are you still taking new affiliates?"
r.back = "아직도 새 제휴자를 받고 있나요?"; r.ms = 1500.0
w._받_결과((r, False)); w.root.update()
check("영어가 결과칸에 들어간다", w.결과.get("1.0", "end").strip(), r.text)
check("역번역이 보인다", w.역번역.cget("text"), r.back)
if "1.5" not in w.상태.cget("text"):
    fails.append("걸린 시간이 안 보인다: %r" % w.상태.cget("text"))

# ── 옮긴 것이 클립보드에 들어가나 ────────────────
# 도구는 클립보드에 놓기만 한다. 붙여넣는 것도 보내는 것도 사람이 한다
표식 = "ZZ클립보드표식ZZ"
W.클립보드_쓰기(표식)
깨끗 = E.Result(pair="ko-en"); 깨끗.text = "Are you still taking new affiliates?"
깨끗.ms = 800.0
w._받_결과((깨끗, False)); w.root.update()
check("클립보드에 들어간다", W.클립보드_읽기(), 깨끗.text)
if "넣었다" not in w.알림.cget("text"):
    fails.append("넣었다는 말이 화면에 안 나온다: %r" % w.알림.cget("text"))
W.클립보드_쓰기(표식)   # 되돌린다

# ── 사이드바 줄 그리기 ───────────────────────────
w._받_준비((1, 3, ("제외하는 국가가 있나요?", "Are there any excluded countries?")))
w._받_준비((2, 3, ("지불 기한은요?", "What about the payment deadline?")))
w.root.update()
check("준비 줄이 쌓인다", len(w.준비줄), 2)
check("진행이 보인다", w.준비상태.cget("text"), "2 / 3")
if not w.속.winfo_children():
    fails.append("사이드바에 줄이 안 그려졌다")

w._준비비우기(); w.root.update()
check("비우면 줄이 없다", len(w.준비줄), 0)
check("비우면 위젯도 없다", len(w.속.winfo_children()), 0)

# ── 상용구 (옛 꼴 — 갈래 → 목록) ─────────────────
# 층 1 이다. **번역을 안 거친다.** 그래서 0 ms 다.
# 이 창의 fixture 는 일부러 옛 꼴이다. exe 옆에 옛 snippets.json 을 놓아도
# 안 깨지는 것이 이 앱의 배포 경로라 그것부터 지킨다
w._상용구넣기(); w.root.update()
check("옛 꼴도 그대로 읽는다", len(w.준비줄), 3)
check("한국어와 영어를 짝으로 담는다", w.준비줄[0], ("알겠습니다.", "got it"))
if "상용구 3" not in w.준비상태.cget("text"):
    fails.append("몇 개인지 안 보인다: %r" % w.준비상태.cget("text"))
check("상용구는 엔진을 안 부른다", eng.부른것, [])
check("상용구를 올렸다고 표시한다", w.준비모드, "상용구")
# 상대를 안 골랐으면 **붉게 알린다.** 틀린 초록불이 빨간불보다 나쁘다
if "미선택" not in w.준비상태.cget("text"):
    fails.append("상대를 안 골랐는데 조용하다: %r" % w.준비상태.cget("text"))
w._준비비우기()
check("비우면 모드도 풀린다", w.준비모드, "")

없는것 = U.창(가짜엔진(), {}, 단축키켜기=False)
없는것.root.update(); 없는것._상용구넣기()
if "없다" not in 없는것.준비상태.cget("text"):
    fails.append("상용구가 없는데 그 말이 안 나온다")
없는것._닫기()

# ── 넣을 줄 고르기 ───────────────────────────────
# 표 머리와 소제목은 보낼 말이 아니다. 걸러야 한다
원본 = "# 제목\n첫 질문인가요?\n| 표 | 머리 |\n---\n둘째 질문인가요?\n\n```\n코드\n```"
줄들 = [s.strip() for s in 원본.splitlines() if s.strip()]
남는것 = [s for s in 줄들 if not s.startswith(("#", "|", "---", "```"))]
check("제목·표·구분선을 뺀다", 남는것, ["첫 질문인가요?", "둘째 질문인가요?", "코드"])

# ── 탈이 나도 창이 안 죽나 ───────────────────────
w.도는중 = True
w._받_탈("RuntimeError: 일부러 낸 탈")
w.root.update()
check("탈이 나면 다시 누를 수 있다", str(w.옮김단추.cget("state")), "normal")
if "못 옮겼다" not in w.알림.cget("text"):
    fails.append("탈이 화면에 안 나온다: %r" % w.알림.cget("text"))

# ── 사이드바는 늘 LLM 이다 ───────────────────────
# 창을 --기계번역 으로 띄웠어도 여기만은 LLM 을 고른다. 대화 전에 미리 옮겨
# 두는 자리라 느려도 되고 품질이 전부다


def 큐비우기(창):
    꺼냄 = []
    while not 창.큐.empty():
        꺼냄.append(창.큐.get_nowait())
    return 꺼냄


큐비우기(w)
w.eng = 가짜엔진()
w._준비일(["첫 줄인가", "둘째 줄인가"])
check("사이드바는 LLM 으로 부른다", [c[3] for c in w.eng.부른것], [True, True])
check("사이드바는 역번역을 안 시킨다", [c[2] for c in w.eng.부른것], [False, False])
check("옮긴 것이 LLM 경로다",
      [값[2][1] for 무엇, 값 in 큐비우기(w) if 무엇 == "준비"],
      ["LLM(첫 줄인가)", "LLM(둘째 줄인가)"])

# ── LLM 을 못 올려도 멈추지 않나 ─────────────────
# 모델이 아직 안 받아졌을 수 있다. 그때 통째로 죽는 대신 기계번역으로 잇되
# **조용히 넘기지 않는다.** 품질이 달라진 줄 모르고 쓰면 그대로 상대에게 나간다
w.eng = 가짜엔진(LLM터짐=True)
w._준비일(["첫 줄인가", "둘째 줄인가"])
check("한 번 터지면 그 줄부터 기계번역이다",
      [c[3] for c in w.eng.부른것], [True, False, False])
꺼냄 = 큐비우기(w)
물러섬 = [값 for 무엇, 값 in 꺼냄 if 무엇 == "물러섬"]
check("물러섰다고 한 번만 알린다", len(물러섬), 1)
check("터진 줄도 버리지 않는다",
      [값[2][1] for 무엇, 값 in 꺼냄 if 무엇 == "준비"],
      ["EN(첫 줄인가)", "EN(둘째 줄인가)"])
if 물러섬 and "기계번역" not in 물러섬[0]:
    fails.append("물러섬 안내에 무엇으로 갔는지가 없다: %r" % 물러섬[0])
if 물러섬:
    w._받_물러섬(물러섬[0])
    w.root.update()
    if "기계번역" not in w.알림.cget("text"):
        fails.append("물러섬이 화면에 안 나온다: %r" % w.알림.cget("text"))

# ── 항상 위를 끌 수 있나 ─────────────────────────
# 텔레그램 위에 겹쳐 두는 것이 원래 쓰임새라 기본은 켜 두되, 가릴 때가 있어 끈다
check("처음엔 켜져 있다", bool(w.항상위.get()), True)
check("창에도 걸려 있다", bool(w.root.attributes("-topmost")), True)
w.항상위.set(False)
w._항상위바꾸기()
w.root.update()
check("끄면 창에서도 내려간다", bool(w.root.attributes("-topmost")), False)
w.항상위.set(True)
w._항상위바꾸기()
w.root.update()
check("다시 켤 수 있다", bool(w.root.attributes("-topmost")), True)

# ── 로그가 창 안에 뜨나 ──────────────────────────
# 콘솔을 안 띄우는 대신 여기로 온다. 접혀 있다가 화살표로 펴진다
check("처음엔 접혀 있다", w.로그열림, False)
check("접힌 동안 화면에 없다", w.로그.winfo_ismapped(), 0)
w.로그보기()
w.root.update()
check("펴면 열린 것으로 안다", w.로그열림, True)
if "▾" not in w.로그단추.cget("text"):
    fails.append("펴도 화살표가 안 바뀐다: %r" % w.로그단추.cget("text"))

w._받_로그("첫 줄이다\n")
w._받_로그("받는 중 10%\r받는 중 90%\r받는 중 100%\n")
w.root.update()
글 = w.로그.get("1.0", "end")
if "첫 줄이다" not in 글:
    fails.append("로그에 안 들어갔다: %r" % 글)
# tqdm 이 \r 로 같은 줄을 덮어쓴다. 그대로 쌓으면 진행률이 수백 줄이 된다
if "10%" in 글:
    fails.append("\\r 로 덮어쓴 것이 지워지지 않았다: %r" % 글)
if "100%" not in 글:
    fails.append("마지막 진행률이 없다: %r" % 글)
check("로그는 사람이 못 고친다", str(w.로그.cget("state")), "disabled")
w.로그보기()
w.root.update()
check("다시 접힌다", w.로그열림, False)

# 로그로 는 큐에만 넣는다. 그리는 것은 UI 실이 한다
큐 = queue.Queue()
U.로그로(큐, None).write("남길 말")
check("로그로 가 큐로 보낸다", 큐.get_nowait(), ("로그", "남길 말"))
check("콘솔이 없어도 안 죽는다", U.로그로(큐, None).write(""), 0)

# ── 창을 띄우면 모델을 미리 올리나 ───────────────
# 첫 번역이 1.7GB 내려받기를 떠안으면 창이 멈춘 것처럼 보인다


class 데움엔진(가짜엔진):
    def __init__(self, 터짐=""):
        super().__init__()
        self.올린것 = []
        self.터짐 = 터짐

    def load(self, pair):
        if self.터짐 == "기계번역":
            raise RuntimeError("일부러 낸 탈")
        self.올린것.append(pair)

    def load_llm(self):
        if self.터짐 == "LLM":
            raise RuntimeError("일부러 낸 탈")
        self.올린것.append("llm")


큐비우기(w)
w.eng = 데움엔진()
w._데우기()
check("기계번역과 LLM 을 다 올린다", w.eng.올린것, ["ko-en", "llm"])
말들 = [값 for 무엇, 값 in 큐비우기(w) if 무엇 == "예열"]
check("끝나면 표시를 지운다", 말들[-1], "")

w.eng = 데움엔진(터짐="LLM")
w._데우기()
말들 = [값 for 무엇, 값 in 큐비우기(w) if 무엇 == "예열"]
if not 말들 or "못 올렸다" not in 말들[-1]:
    fails.append("못 올렸는데 조용하다: %r" % (말들[-1] if 말들 else None))
w._받_예열(말들[-1])
w.root.update()
if "못 올렸다" not in w.예열.cget("text"):
    fails.append("예열 탈이 화면에 안 나온다: %r" % w.예열.cget("text"))

w._닫기()

# ── 페르소나 층과 말주머니 ───────────────────────
# **한 사람이 우리에게서 같은 말을 두 번 듣지 않게 한다.** 그게 안 되면
# 상대가 스크립트로 눈치채고 그 컨택은 되살릴 수 없다
import random  # noqa: E402

import bag as BAG  # noqa: E402

새꼴 = {
    "공통": {
        "맞장구": [{"한국어": "네", "영어": "yeah", "영어들": ["yep", "right"]}],
    },
    "사는 쪽": {
        "값 묻기": [{"한국어": "얼마에 파나요", "영어": "how much for it",
                  "영어들": ["whats ur price"]}],
    },
    "파는 쪽": {
        "물어보기": [{"한국어": "뭘 추천하시나요", "영어": "what would u recommend"}],
    },
}
# **경로를 임시로 준다.** 안 그러면 _닫기 가 사람의 진짜 자루 파일을 덮어쓴다.
# 실제로 한 번 덮어썼다 (2026-09-16)
import tempfile  # noqa: E402
임시자루 = pathlib.Path(tempfile.mkdtemp()) / "talkaid_bag.json"
ㅍ = U.창(가짜엔진(), 새꼴, 단축키켜기=False,
        말주머니=BAG.주머니들(난수=random.Random(7), 경로=임시자루))
ㅍ.root.update()

# 「공통」은 고르는 것이 아니라 늘 나오는 것이다. 목록에 넣으면 기본값이 「공통」이
# 되어 정작 거래 문구가 하나도 안 뜬다
check("페르소나를 고를 수 있다", sorted(ㅍ._페르소나들()), ["사는 쪽", "파는 쪽"])
check("공통은 고르는 것이 아니다", "공통" in ㅍ._페르소나들(), False)
check("기본값이 거래 페르소나다", ㅍ.페르소나.get() in ("사는 쪽", "파는 쪽"), True)
check("처음엔 상대를 안 골랐다", ㅍ.상대.get(), "")

# 공통은 어느 페르소나에서나 나오고, 나머지는 고른 것만 나온다
ㅍ.페르소나.set("사는 쪽")
ㅍ._상용구넣기(); ㅍ.root.update()
한국어들 = [ko for ko, _ in ㅍ.준비줄]
check("공통과 고른 페르소나만 나온다", sorted(한국어들), ["네", "얼마에 파나요"])
if "뭘 추천하시나요" in 한국어들:
    fails.append("안 고른 페르소나가 섞여 나왔다")

ㅍ.페르소나.set("파는 쪽")
ㅍ._상용구넣기(); ㅍ.root.update()
check("페르소나를 바꾸면 목록도 바뀐다",
      sorted(ko for ko, _ in ㅍ.준비줄), ["네", "뭘 추천하시나요"])

# ── 상대를 고르면 자루가 돈다 ────────────────────
ㅍ.상대.set("2")
ㅍ.페르소나.set("사는 쪽")
ㅍ._상용구넣기(); ㅍ.root.update()
if "미선택" in ㅍ.준비상태.cget("text"):
    fails.append("상대를 골랐는데 미선택이라 한다: %r" % ㅍ.준비상태.cget("text"))

후보 = BAG.후보뽑기(새꼴["공통"]["맞장구"][0])
check("후보가 셋", 후보, ["yeah", "yep", "right"])
자리 = ("2", "공통", "맞장구", "네")
한바퀴 = [ㅍ.말주머니.뽑기(*자리, 후보) for _ in range(3)]
check("한 바퀴 안에 안 겹친다", sorted(한바퀴), sorted(후보))

# 상대가 다르면 자루도 다르다
셋자리 = ("3", "공통", "맞장구", "네")
check("다른 상대는 처음부터", len({ㅍ.말주머니.뽑기(*셋자리, 후보) for _ in range(3)}), 3)

# ── 두 번 눌러도 클립보드가 안 바뀐다 ────────────
# 예전에는 두 번 눌러도 같은 글이었다. 돌림이 붙으면서 두 번째가 다른 문장을
# 덮어쓰게 됐다. 붙여넣기는 텔레그램에서 하므로 볼 기회가 없다
표식2 = "ZZ디바운스ZZ"
W.클립보드_쓰기(표식2)
check("처음 누름은 들어간다", ㅍ._줄복사("first"), True)
check("클립보드에 들어갔다", W.클립보드_읽기(), "first")
check("0.8초 안의 같은 글 두 번째는 무시", ㅍ._줄복사("first"), False)
check("다른 글은 바로 들어간다", ㅍ._줄복사("second"), True)
W.클립보드_쓰기(표식2)

# ── 상대를 바꿔도 번역 결과가 안 날아간다 ────────
# 2분 들여 옮겨 둔 질문지가 드롭다운 한 번에 사라지면 대화 중 제일 아픈 사고다
ㅍ._준비비우기()
ㅍ.준비모드 = "번역"
ㅍ._받_준비((1, 1, ("옮겨 둔 질문", "a translated question")))
ㅍ.root.update()
전 = len(ㅍ.준비줄)
ㅍ._상대바뀜()
ㅍ.root.update()
check("번역 결과가 올라가 있으면 안 건드린다", len(ㅍ.준비줄), 전)
check("모드도 그대로", ㅍ.준비모드, "번역")

# ── u · ur 체크박스가 엔진까지 닿나 ──────────────
# 단추만 달고 값을 안 넘기면 눌러도 아무 일이 없는데 화면으로는 켜져 보인다.
# 그 상태가 제일 나쁘다 — 켠 줄 알고 보냈는데 안 켜진 것이다.
#
# 딴 실을 안 띄우고 _일 과 _준비일 을 바로 부른다. 넘긴 값이 엔진에 닿는지만 본다
check("기본은 꺼져 있다", bool(ㅍ.채팅축약.get()), False)

eng2 = 가짜엔진()
ㅍ2 = U.창(eng2, 상용구, 단축키켜기=False,
         말주머니=BAG.주머니들(난수=random.Random(7), 경로=임시자루))
ㅍ2._일("보낼 말", 읽기=False, 채팅=True)
check("번역칸이 채팅 축약을 넘긴다", eng2.채팅으로부른것, [True])

eng2.채팅으로부른것 = []
ㅍ2._준비일(["한 줄"], 채팅=True)
check("사이드바도 넘긴다", eng2.채팅으로부른것, [True])

eng2.채팅으로부른것 = []
ㅍ2._일("보낼 말", 읽기=False)
check("안 켜면 안 넘어간다", eng2.채팅으로부른것, [False])

# 읽을 말에는 안 건다. 내가 읽는 것이라 말씨를 줄일 이유가 없다
eng2.채팅으로부른것 = []
ㅍ2._일("Are you still selling", 읽기=True, 채팅=True)
check("읽을 말에는 안 건다", eng2.채팅으로부른것, [False])
ㅍ2._닫기()

ㅍ._닫기()
check("자루는 준 경로에만 쓴다", 임시자루.exists(), True)
check("진짜 설정 파일을 안 건드렸다",
      (BAG.자루파일.exists() and BAG.자루파일 != 임시자루), BAG.자루파일.exists())

# ── 결과 ─────────────────────────────────────────
if fails:
    print("실패 %d" % len(fails))
    for f in fails:
        print("  - %s" % f)
    sys.exit(1)
print("통과. 시험 17 묶음")
