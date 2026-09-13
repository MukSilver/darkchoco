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

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if sys.platform != "win32":
    print("건너뜀 — 윈도우 전용이다 (win.py 가 Win32 API 다)")
    raise SystemExit(0)
import engine as E  # noqa: E402
import guard as G  # noqa: E402
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

    def run(self, text, pair, back=True, llm=None):
        self.부른것.append((text, pair, back, llm))
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
for 이름 in ("입력", "결과", "역번역", "관문", "상태", "옆", "속", "준비단추"):
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
w._받_결과((r, G.check(r.text), False)); w.root.update()
check("영어가 결과칸에 들어간다", w.결과.get("1.0", "end").strip(), r.text)
check("역번역이 보인다", w.역번역.cget("text"), r.back)
if "1.5" not in w.상태.cget("text"):
    fails.append("걸린 시간이 안 보인다: %r" % w.상태.cget("text"))

# ── 막히면 클립보드를 안 건드리나 ────────────────
# **이것이 이 화면에서 가장 중요한 시험이다.** 팀 이름이 나가면 되돌릴 수 없다
표식 = "ZZ클립보드표식ZZ"
W.클립보드_쓰기(표식)
막힐것 = E.Result(pair="ko-en")
막힐것.text = "we are from darkchoco at Whitehat School"
막힐것.back = "우리는 …"; 막힐것.ms = 900.0
v = G.check(막힐것.text)
check("이 글은 막혀야 한다", v.막힘, True)
w._받_결과((막힐것, v, False)); w.root.update()
check("**막히면 클립보드가 안 바뀐다**", W.클립보드_읽기(), 표식)
if "안 넣었다" not in w.관문.cget("text"):
    fails.append("막혔는데 그 말이 화면에 안 나온다: %r" % w.관문.cget("text"))

# 깨끗한 것은 들어가야 한다
깨끗 = E.Result(pair="ko-en"); 깨끗.text = "Are you still taking new affiliates?"
깨끗.ms = 800.0
w._받_결과((깨끗, G.check(깨끗.text), False)); w.root.update()
check("안 막히면 클립보드에 들어간다", W.클립보드_읽기(), 깨끗.text)
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

# ── 상용구 ───────────────────────────────────────
# 층 1 이다. **번역을 안 거친다.** 그래서 0 ms 다
w._상용구넣기(); w.root.update()
check("상용구가 다 들어간다", len(w.준비줄), 3)
check("한국어와 영어를 짝으로 담는다", w.준비줄[0], ("알겠습니다.", "got it"))
check("몇 개인지 보인다", w.준비상태.cget("text"), "상용구 3")
check("상용구는 엔진을 안 부른다", eng.부른것, [])
w._준비비우기()

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
if "못 옮겼다" not in w.관문.cget("text"):
    fails.append("탈이 화면에 안 나온다: %r" % w.관문.cget("text"))

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
    if "기계번역" not in w.관문.cget("text"):
        fails.append("물러섬이 화면에 안 나온다: %r" % w.관문.cget("text"))

w._닫기()

# ── 결과 ─────────────────────────────────────────
if fails:
    print("실패 %d" % len(fails))
    for f in fails:
        print("  - %s" % f)
    sys.exit(1)
print("통과. 시험 9 묶음")
