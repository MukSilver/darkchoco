#!/usr/bin/env python3
"""창. tkinter 로 만든다. **표준 라이브러리 + sv-ttk 83KB 가 전부다.**

    from ui import 창
    창(eng).돌린다()

## 왜 창을 띄워 두나

**역번역을 사람이 반드시 봐야 한다.** 기계번역이든 LLM 이든 뜻이 틀리는 것이 남는다.
「게시가 내려간 피해사가 있나요?」가 「Is there victim organization that she went down?」
으로 나가는 것을 사람이 못 알아보는데, 역번역이 「그녀가 쓰러뜨린…」이라고 되돌려 주면
즉시 안다. **그래서 트레이로 숨기지 않는다.**

## 실 (thread) 규칙

**tkinter 는 실 안전하지 않다.** 추론은 딴 실에서 돌리고 결과는 큐에 넣는다.
UI 는 `after()` 로 큐를 꺼내 그린다. 같은 실에서 돌리면 창이 얼어붙는다.
전역 단축키도 딴 실이라 같은 큐를 쓴다.

## 사이드바는 작업판이다

미리 채워 둔 붙박이 목록이 아니다. **사람이 txt 를 넣거나 붙여넣으면 통째로 옮겨
한국어와 영어를 나란히 세워 둔다.** 대화 중에 열고 닫으며 줄을 눌러 복사한다.
번역은 대화 전에 하므로 느려도 된다. 품질이 전부다.
"""
from __future__ import annotations

import io
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, ttk

import bag as BAG
import engine as E
import win as W

글꼴 = "Malgun Gothic"      # 윈도우 한국어 UI 글꼴
좁게, 넓게 = 560, 980
로그높이 = 170              # 로그를 펼 때 창이 이만큼 커진다
로그줄상한 = 500            # 넘으면 위에서 지운다. 안 그러면 하루 켜 두면 쌓인다


class 로그로(io.TextIOBase):
    """`print` 와 남의 라이브러리 출력을 창 안 로그로 보낸다.

    **콘솔을 안 띄우려면 이것이 있어야 한다.** pythonw 로 띄우면 콘솔이 없고
    `sys.stdout` 이 None 이라 어디에도 안 남는다. 모델 받는 진행률도 여기로 온다.

    큐에 넣기만 한다. 그리는 것은 UI 실이 한다 — tkinter 는 실 안전하지 않다.
    """

    def __init__(self, 큐: queue.Queue, 원래=None):
        self.큐 = 큐
        self.원래 = 원래        # 콘솔이 있으면 거기에도 그대로 쓴다

    def write(self, s: str) -> int:
        if s:
            self.큐.put(("로그", s))
            if self.원래 is not None:
                try:
                    self.원래.write(s)
                except Exception:
                    pass        # 콘솔이 사라져도 창은 살아야 한다
        return len(s)

    def flush(self) -> None:
        if self.원래 is not None:
            try:
                self.원래.flush()
            except Exception:
                pass


class 창:
    def __init__(self, eng: E.Engine, 상용구: dict | None = None,
                 단축키켜기: bool = True, 말주머니=None):
        # 시험에서는 끈다. 전역 단축키는 온 시스템이 나눠 쓰는 것이라
        # 시험이 잠깐이라도 채가면 사람이 쓰던 것이 그 사이에 안 먹는다
        self.eng = eng
        self.상용구 = 상용구 or {}
        self.큐: queue.Queue = queue.Queue()
        self.도는중 = False
        self.사이드바열림 = False
        self.로그열림 = False
        self._다음 = None
        self._되돌릴출력 = None
        self.준비줄: list[tuple[str, str]] = []
        # 사이드바에 지금 무엇이 올라가 있나. 상대를 바꿀 때 번역 결과를
        # 날리지 않으려고 본다 — 2분 들여 옮겨 둔 질문지가 드롭다운 한 번에
        # 사라지면 대화 중 제일 아픈 사고다
        self.준비모드 = ""
        self._마지막복사 = [0.0, ""]      # 두 번 누름 막기 (0.8초)
        # 시험에서는 씨앗을 고정한 것을 넣는다
        self.말주머니 = 말주머니 if 말주머니 is not None else BAG.주머니들.읽기()

        self.dpi = W.dpi_켜기()
        self.root = tk.Tk()
        self.root.title("talkaid — 밖으로 아무것도 안 보낸다")
        self.root.geometry("%dx420" % 좁게)
        self.root.minsize(480, 360)
        # 기본은 켜 둔다. 텔레그램 위에 겹쳐 놓고 쓰는 것이 원래 쓰임새다.
        # 다만 가리는 것이 거슬릴 때가 있어 아래 설정 줄에서 끌 수 있다
        self.항상위 = tk.BooleanVar(value=True)
        self.root.attributes("-topmost", True)
        try:
            import sv_ttk
            sv_ttk.set_theme("light")
        except Exception:
            pass
        self.root.option_add("*Font", (글꼴, 10))

        self._짜기()
        self.키 = None
        if 단축키켜기:
            self._단축키()
        self.root.after(50, self._큐꺼내기)
        self.root.protocol("WM_DELETE_WINDOW", self._닫기)

    # ── 화면 짜기 ────────────────────────────────
    def _짜기(self) -> None:
        바깥 = ttk.Frame(self.root, padding=10)
        바깥.pack(fill="both", expand=True)
        바깥.columnconfigure(0, weight=1)
        바깥.rowconfigure(1, weight=1)
        바깥.rowconfigure(4, weight=1)
        self.왼쪽 = 바깥

        머리 = ttk.Frame(바깥)
        머리.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        ttk.Label(머리, text="보낼 말 (한국어)").pack(side="left")
        self.준비단추 = ttk.Button(머리, text="준비해 둔 것 ▸", width=14,
                                command=self.사이드바)
        self.준비단추.pack(side="right")

        self.입력 = tk.Text(바깥, height=4, wrap="word", font=(글꼴, 11),
                          relief="solid", borderwidth=1)
        self.입력.grid(row=1, column=0, sticky="nsew")
        self.입력.bind("<Control-Return>", lambda e: (self.옮기기(), "break")[1])

        줄 = ttk.Frame(바깥)
        줄.grid(row=2, column=0, sticky="ew", pady=6)
        self.옮김단추 = ttk.Button(줄, text="옮기기  (Ctrl+Enter)", command=self.옮기기)
        self.옮김단추.pack(side="left")
        ttk.Button(줄, text="지우기", width=8, command=self._지우기).pack(side="left", padx=4)
        self.상태 = ttk.Label(줄, text="", foreground="#666")
        self.상태.pack(side="right")

        ttk.Label(바깥, text="보낼 영어").grid(row=3, column=0, sticky="w")
        self.결과 = tk.Text(바깥, height=4, wrap="word", font=(글꼴, 11),
                          relief="solid", borderwidth=1, background="#f7f7f7")
        self.결과.grid(row=4, column=0, sticky="nsew", pady=(2, 6))

        ttk.Label(바깥, text="역번역 — 뜻이 살았는지 본다",
                  foreground="#666").grid(row=5, column=0, sticky="w")
        self.역번역 = ttk.Label(바깥, text="", wraplength=좁게 - 40,
                             justify="left", foreground="#444")
        self.역번역.grid(row=6, column=0, sticky="ew", pady=(2, 4))

        # 알림 줄. 클립보드에 넣었다 · 못 옮겼다 · 규칙이 낡았다 같은 것이 여기 뜬다
        self.알림 = ttk.Label(바깥, text="", wraplength=좁게 - 40, justify="left")
        self.알림.grid(row=7, column=0, sticky="ew")

        # ── 설정 줄 ──
        # 왼쪽에 로그 여닫기, 가운데에 모델 데우는 상태, 오른쪽에 항상 위
        설정 = ttk.Frame(바깥)
        설정.grid(row=8, column=0, sticky="ew", pady=(8, 0))
        self.로그단추 = ttk.Button(설정, text="▸ 로그", width=8, command=self.로그보기)
        self.로그단추.pack(side="left")
        self.예열 = ttk.Label(설정, text="", foreground="#666")
        self.예열.pack(side="left", padx=8)
        ttk.Checkbutton(설정, text="항상 위", variable=self.항상위,
                        command=self._항상위바꾸기).pack(side="right")

        # 로그는 접어 둔다. **콘솔을 안 띄우는 대신 여기로 온다.**
        # 모델 받는 진행률과 탈이 다 여기에 쌓인다
        self.로그 = tk.Text(바깥, height=8, wrap="none", font=("Consolas", 9),
                          relief="solid", borderwidth=1, background="#fbfbfb",
                          foreground="#444", state="disabled")
        self.로그.grid(row=9, column=0, sticky="nsew", pady=(4, 0))
        self.로그.grid_remove()

        self._사이드바짜기()

    def _사이드바짜기(self) -> None:
        self.옆 = ttk.Frame(self.root, padding=(0, 10, 10, 10), width=400)
        머리 = ttk.Frame(self.옆)
        머리.pack(fill="x")
        ttk.Label(머리, text="미리 옮겨 두는 자리").pack(side="left")
        self.준비상태 = ttk.Label(머리, text="", foreground="#666")
        self.준비상태.pack(side="right")

        # ── 상대와 페르소나 ──
        # **대화 하나에 한 번만 고른다.** 메시지마다 고르는 것이 아니다.
        # 상대를 가르는 이유는 「한 사람이 우리에게서 같은 말을 두 번 듣는 것」을
        # 막으려는 것이다. 404muse 에게 다 쓴 말이 REDX 에게는 새것이다.
        #
        # **핸들을 적지 않는다.** 창이 늘 위에 떠 있어 캡처마다 따라 들어가고,
        # 팀 규칙이 계정명을 반드시 가리라고 못박았다. 번호와 상대의 짝은
        # 사람이 자기 수첩에 적는다
        고르개 = ttk.Frame(self.옆)
        고르개.pack(fill="x", pady=(4, 0))
        ttk.Label(고르개, text="상대", foreground="#666").pack(side="left")
        self.상대 = tk.StringVar(value="")
        self.상대고르개 = ttk.Combobox(고르개, textvariable=self.상대, width=6,
                                   state="readonly",
                                   values=[""] + list(self.말주머니.별칭))
        self.상대고르개.pack(side="left", padx=(4, 10))
        self.상대고르개.bind("<<ComboboxSelected>>", lambda e: self._상대바뀜())

        ttk.Label(고르개, text="페르소나", foreground="#666").pack(side="left")
        self.페르소나 = tk.StringVar(value=self._페르소나들()[0])
        self.페르소나고르개 = ttk.Combobox(고르개, textvariable=self.페르소나, width=9,
                                     state="readonly", values=self._페르소나들())
        self.페르소나고르개.pack(side="left", padx=4)
        self.페르소나고르개.bind("<<ComboboxSelected>>", lambda e: self._상대바뀜())

        줄 = ttk.Frame(self.옆)
        줄.pack(fill="x", pady=6)
        ttk.Button(줄, text="txt 열기", command=self._파일열기).pack(side="left")
        ttk.Button(줄, text="클립보드에서", command=self._붙여넣기).pack(side="left", padx=4)
        ttk.Button(줄, text="상용구", width=7, command=self._상용구넣기).pack(side="left")
        ttk.Button(줄, text="비우기", width=7, command=self._준비비우기).pack(side="right")

        감 = ttk.Frame(self.옆)
        감.pack(fill="both", expand=True)
        self.판 = tk.Canvas(감, highlightthickness=0, width=380)
        막대 = ttk.Scrollbar(감, orient="vertical", command=self.판.yview)
        self.속 = ttk.Frame(self.판)
        self.속.bind("<Configure>",
                    lambda e: self.판.configure(scrollregion=self.판.bbox("all")))
        self.판.create_window((0, 0), window=self.속, anchor="nw")
        self.판.configure(yscrollcommand=막대.set)
        self.판.pack(side="left", fill="both", expand=True)
        막대.pack(side="right", fill="y")
        self.판.bind_all("<MouseWheel>",
                        lambda e: self.판.yview_scroll(-e.delta // 120, "units")
                        if self.사이드바열림 else None)

    # ── 단축키 ───────────────────────────────────
    def _단축키(self) -> None:
        self.키 = W.단축키({1: ("ctrl+alt", ord("1")),
                        2: ("ctrl+alt", ord("2")),
                        3: ("ctrl+alt", ord("3"))})
        못잡음 = self.키.켜기(lambda hid: self.큐.put(("단축키", hid)))
        if 못잡음:
            self.알림.configure(
                text="단축키 %s 을 못 잡았다. 다른 프로그램이 이미 쓰고 있다."
                     % " · ".join("Ctrl+Alt+%d" % h for h in 못잡음),
                foreground="#a33")

    # ── 큐 ───────────────────────────────────────
    def _큐꺼내기(self) -> None:
        try:
            while True:
                무엇, 값 = self.큐.get_nowait()
                getattr(self, "_받_" + 무엇, lambda v: None)(값)
        except queue.Empty:
            pass
        # **표를 들고 있어야 닫을 때 끊는다.** 안 끊으면 창이 죽은 뒤에도
        # 걸려 있던 것이 한 번 더 돌아 Tcl 이 「invalid command name」 을 낸다
        self._다음 = self.root.after(50, self._큐꺼내기)

    def _받_단축키(self, hid: int) -> None:
        if hid == 1:
            self.입력.delete("1.0", "end")
            self.입력.insert("1.0", W.클립보드_읽기().strip())
            self.옮기기()
        elif hid == 2:
            self.입력.delete("1.0", "end")
            self.입력.insert("1.0", W.클립보드_읽기().strip())
            self.옮기기(읽기=True)
        elif hid == 3:
            self.사이드바()
        self.root.deiconify()
        self.root.lift()

    def _받_결과(self, 값) -> None:
        r, 읽기 = 값
        self.도는중 = False
        self.옮김단추.configure(state="normal")
        self.결과.delete("1.0", "end")
        self.결과.insert("1.0", r.text)
        self.역번역.configure(text=r.back or "(역번역 없음)")
        self.상태.configure(text="%.1f초" % (r.ms / 1000))

        # **반환값을 본다.** 다른 프로그램이 클립보드를 잡고 있으면 실패하는데
        # 여태 그래도 초록 「넣었다」가 떴다
        if W.클립보드_쓰기(r.text):
            self.알림.configure(text="클립보드에 넣었다", foreground="#2a7")
        else:
            self.알림.configure(
                text="**클립보드에 못 넣었다.** 결과칸에서 직접 복사한다",
                foreground="#a33")

    def _받_탈(self, e) -> None:
        self.도는중 = False
        self.옮김단추.configure(state="normal")
        self.알림.configure(text="못 옮겼다 — %s" % e, foreground="#a33")

    def _받_준비(self, 값) -> None:
        했다, 다, 짝 = 값
        self.준비상태.configure(text="%d / %d" % (했다, 다))
        if 짝:
            self.준비줄.append(짝)
            self._준비그리기(len(self.준비줄), 짝)

    def _받_물러섬(self, 말: str) -> None:
        # 사이드바가 LLM 을 못 써서 기계번역으로 내려갔다. 조용히 넘기지 않는다 —
        # 품질이 달라진 것을 모르고 쓰면 그대로 상대에게 나간다
        self.알림.configure(text=말, foreground="#a33")

    # ── 옮기기 ───────────────────────────────────
    def 옮기기(self, 읽기: bool = False) -> None:
        글 = self.입력.get("1.0", "end").strip()
        if not 글 or self.도는중:
            return
        self.도는중 = True
        self.옮김단추.configure(state="disabled")
        self.상태.configure(text="옮기는 중…")
        self.알림.configure(text="")
        threading.Thread(target=self._일, args=(글, 읽기), daemon=True).start()

    def _일(self, 글: str, 읽기: bool) -> None:
        try:
            if 읽기:
                말 = E.detect_lang(글)
                pair = {"zh": "zh-ko", "en": "en-ko"}.get(말, "ko-en")
                r = self.eng.run(글, pair, back=False)
                self.큐.put(("결과", (r, True)))
            else:
                r = self.eng.run(글, "ko-en", back=True)
                self.큐.put(("결과", (r, False)))
        except Exception as e:
            self.큐.put(("탈", "%s: %s" % (type(e).__name__, e)))

    def _지우기(self) -> None:
        self.입력.delete("1.0", "end")
        self.결과.delete("1.0", "end")
        self.역번역.configure(text="")
        self.알림.configure(text="")
        self.상태.configure(text="")

    # ── 설정 줄 ──────────────────────────────────
    def _항상위바꾸기(self) -> None:
        self.root.attributes("-topmost", bool(self.항상위.get()))

    def 로그보기(self) -> None:
        """로그를 접었다 편다. 창 높이를 같이 늘린다."""
        높이 = self.root.winfo_height()
        if self.로그열림:
            self.로그.grid_remove()
            self.root.geometry("%dx%d" % (self.root.winfo_width(),
                                          max(360, 높이 - 로그높이)))
            self.로그단추.configure(text="▸ 로그")
        else:
            self.로그.grid()
            self.root.geometry("%dx%d" % (self.root.winfo_width(), 높이 + 로그높이))
            self.로그단추.configure(text="▾ 로그")
            self.로그.see("end")
        self.로그열림 = not self.로그열림

    def _받_로그(self, s: str) -> None:
        self.로그.configure(state="normal")
        # tqdm 이 \r 로 같은 줄을 덮어쓰며 진행률을 낸다. 그대로 넣으면 모델 하나
        # 받는 데 수백 줄이 쌓인다. **\r 로 갈린 조각은 마지막 것만 남긴다.**
        s = s.replace("\r\n", "\n")     # 이건 그냥 줄바꿈이다. 덮어쓰기가 아니다
        줄들 = s.split("\n")
        for i, 줄 in enumerate(줄들):
            if "\r" in 줄:
                줄 = 줄.rpartition("\r")[2]
                self.로그.delete("end-1c linestart", "end-1c")   # 쓰던 줄을 지운다
            if 줄:
                self.로그.insert("end", 줄)
            if i < len(줄들) - 1:
                self.로그.insert("end", "\n")
        넘침 = int(self.로그.index("end-1c").split(".")[0]) - 로그줄상한
        if 넘침 > 0:
            self.로그.delete("1.0", "%d.0" % (넘침 + 1))
        self.로그.see("end")
        self.로그.configure(state="disabled")

    # ── 모델 데우기 ──────────────────────────────
    def _데우기(self) -> None:
        """창을 띄우자마자 딴 실에서 모델을 올린다.

        **첫 번역이 모델 받기까지 떠안으면 안 된다.** LLM 은 1.7GB 라 처음에는
        내려받기가 붙어 30분을 넘길 수 있다. 그동안 창이 멈춘 것처럼 보이던 것을
        여기서 미리 하고 진행을 화면에 적는다.
        """
        for 이름, 일 in (("기계번역", lambda: self.eng.load("ko-en")),
                       ("LLM", self.eng.load_llm)):
            self.큐.put(("예열", "%s 준비 중…" % 이름))
            try:
                일()
            except Exception as e:
                self.큐.put(("예열", "%s 를 못 올렸다 — 로그를 본다" % 이름))
                print("[예열] %s 실패: %s: %s" % (이름, type(e).__name__, e))
                return
        self.큐.put(("예열", ""))
        print("[예열] 모델을 다 올렸다. 이제 기다림 없이 돈다.")

    def _받_예열(self, 말: str) -> None:
        self.예열.configure(text=말)

    # ── 사이드바 ─────────────────────────────────
    def 사이드바(self) -> None:
        if self.사이드바열림:
            self.옆.pack_forget()
            self.root.geometry("%dx%d" % (좁게, self.root.winfo_height()))
            self.준비단추.configure(text="준비해 둔 것 ▸")
        else:
            # **before= 가 있어야 한다.** pack 은 선언한 차례대로 공간을 나눠 주는데
            # 왼쪽이 expand=True 로 먼저 자리를 잡아 창을 다 먹는다. 그러면 사이드바가
            # 오른쪽 아래로 밀려 단추가 잘린다. 먼저 끼워 제 폭부터 확보한다
            self.옆.pack(side="right", fill="both", before=self.왼쪽)
            self.root.geometry("%dx%d" % (넓게, self.root.winfo_height()))
            self.준비단추.configure(text="◂ 접기")
        self.사이드바열림 = not self.사이드바열림

    def _파일열기(self) -> None:
        p = filedialog.askopenfilename(
            title="한국어 문안 파일", filetypes=[("텍스트", "*.txt *.md"), ("전부", "*.*")])
        if p:
            # utf-8-sig 다. 남이 준 txt 는 BOM 이 붙어 있기 쉽고, 그러면 첫 줄이
            # "﻿질문" 이 되어 그 한 줄만 엉뚱하게 번역된다
            with open(p, encoding="utf-8-sig", errors="replace") as f:
                self._준비시작(f.read())

    def _붙여넣기(self) -> None:
        self._준비시작(W.클립보드_읽기())

    def _페르소나들(self) -> list[str]:
        """고를 수 있는 페르소나.

        **「공통」은 여기 안 넣는다.** 그것은 고르는 것이 아니라 어느 페르소나에서나
        늘 나오는 것이다. 목록에 넣으면 기본값이 「공통」이 되어 정작 거래 문구가
        하나도 안 뜬다. 옛 꼴(갈래→목록)이면 고를 것이 없다.
        """
        갈래들 = [k for k, v in self.상용구.items()
                if isinstance(v, dict) and k != "공통"]
        return 갈래들 or ["(없음)"]

    def _펼치기(self) -> list[tuple[str, str, dict]]:
        """(페르소나, 갈래, 항목) 로 펼친다. **옛 꼴도 읽는다.**

        값이 dict 면 새 꼴(페르소나→갈래→목록)이고 list 면 옛 꼴(갈래→목록)이다.
        exe 옆에 옛 파일을 놓아도 안 깨지게 하려는 것이다.

        「공통」 은 어느 페르소나에서나 나오고, 나머지는 고른 것만 나온다.
        """
        고른것 = self.페르소나.get() if hasattr(self, "페르소나") else ""
        out = []
        for 위, 값 in self.상용구.items():
            if isinstance(값, list):            # 옛 꼴 — 위가 곧 갈래다
                out += [("", 위, x) for x in 값 if isinstance(x, dict)]
                continue
            if not isinstance(값, dict):
                continue
            if 위 != "공통" and 고른것 and 위 != 고른것:
                continue
            for 갈래, 목록 in 값.items():
                if isinstance(목록, list):
                    out += [(위, 갈래, x) for x in 목록 if isinstance(x, dict)]
        return out

    def _상용구넣기(self) -> None:
        """상용구는 **번역을 안 거친다.** 그래서 0 ms 이고 틀릴 수 없다.

        항목에 `영어들` 이 있으면 누를 때마다 다른 변형이 나가고, 한 바퀴 안에는
        안 겹친다. **상대를 안 고르면 자루를 안 돌리고 첫 변형만 낸다** —
        틀린 초록불이 빨간불보다 나쁘다.
        """
        if not self.상용구:
            if not self.사이드바열림:
                self.사이드바()
            self.준비상태.configure(text="snippets.json 이 없다")
            return
        if not self.사이드바열림:
            self.사이드바()
        self._준비비우기()
        self.준비모드 = "상용구"

        상대 = (self.상대.get() or "").strip()
        앞갈래, 버린것 = None, 0
        for 페르소나, 갈래, 항목 in self._펼치기():
            후보 = BAG.후보뽑기(항목)
            ko = (항목.get("한국어") or "").strip()
            if not 후보 or not ko:
                버린것 += 1
                continue
            if 갈래 != 앞갈래:
                self._갈래머리(갈래)
                앞갈래 = 갈래
            보임 = (self.말주머니.지금(상대, 페르소나, 갈래, ko, 후보)
                  if 상대 else 후보[0])
            self.준비줄.append((ko, 보임))
            self._준비그리기(len(self.준비줄), (ko, 보임),
                         후보=후보, 자리=(페르소나, 갈래, ko))

        말 = "상용구 %d" % len(self.준비줄)
        if 버린것:
            말 += " · 이상 %d" % 버린것
        if not 상대:
            말 += " · 상대 미선택"
        self.준비상태.configure(text=말)
        if not 상대:
            self.알림.configure(
                text="상대를 안 골라 자루를 안 돌린다. 같은 말이 또 나갈 수 있다.",
                foreground="#a33")

    def _갈래머리(self, 갈래: str) -> None:
        """갈래 머리글. 스물여덟 줄을 통째로 쌓으면 대화 중에 못 찾는다."""
        ttk.Label(self.속, text="── %s" % 갈래, foreground="#999",
                  font=(글꼴, 9)).pack(anchor="w", pady=(8, 2))

    def _준비비우기(self) -> None:
        self.준비줄.clear()
        for w in self.속.winfo_children():
            w.destroy()
        self.준비상태.configure(text="")
        self.준비모드 = ""

    def _상대바뀜(self) -> None:
        """상대나 페르소나를 바꿨다. **번역 결과가 올라가 있으면 안 건드린다.**"""
        if self.준비모드 != "상용구":
            return
        self._상용구넣기()

    def _준비시작(self, 글: str) -> None:
        줄들 = [s.strip() for s in 글.splitlines() if s.strip()]
        # 표 머리나 소제목은 뺀다. 보낼 말만 남긴다
        줄들 = [s for s in 줄들 if not s.startswith(("#", "|", "---", "```"))]
        if not 줄들:
            self.준비상태.configure(text="넣을 줄이 없다")
            return
        if not self.사이드바열림:
            self.사이드바()
        self._준비비우기()
        self.준비모드 = "번역"
        # 첫 줄이 나오기까지 모델 올리는 시간이 얹힌다. 아무 표시가 없으면 멈춘 줄 안다
        self.준비상태.configure(text="0 / %d  (LLM 을 올린다)" % len(줄들))
        threading.Thread(target=self._준비일, args=(줄들,), daemon=True).start()

    def _준비일(self, 줄들: list[str]) -> None:
        # **사이드바는 늘 LLM 이다.** 대화 전에 미리 옮겨 두는 자리라 느려도 되고,
        # 창을 --기계번역 으로 띄웠어도 여기만은 품질을 고른다
        LLM으로 = True
        for i, s in enumerate(줄들, 1):
            try:
                r = self.eng.run(s, "ko-en", back=False, llm=LLM으로)
                self.큐.put(("준비", (i, len(줄들), (s, r.text))))
                continue
            except Exception as e:
                탈 = e
            # 모델을 못 올렸으면 남은 줄은 기계번역으로 잇는다. 통째로 멈추는 것보다 낫다
            if LLM으로:
                LLM으로 = False
                self.큐.put(("물러섬", "LLM 을 못 썼다 (%s) — 남은 줄은 기계번역이다" % 탈))
                try:
                    r = self.eng.run(s, "ko-en", back=False, llm=False)
                    self.큐.put(("준비", (i, len(줄들), (s, r.text))))
                    continue
                except Exception as e2:
                    탈 = e2
            self.큐.put(("준비", (i, len(줄들), (s, "**못 옮겼다** %s" % 탈))))

    def _준비그리기(self, n: int, 짝: tuple[str, str],
                 후보: list[str] | None = None,
                 자리: tuple[str, str, str] | None = None) -> None:
        """한 줄. 후보가 둘 이상이면 [↻] 와 변형 개수가 붙는다.

        번역 경로는 후보·자리를 안 주므로 옛날과 똑같이 그려진다.
        """
        ko, en = 짝
        칸 = ttk.Frame(self.속, padding=(0, 4, 0, 6))
        칸.pack(fill="x", anchor="w")
        ttk.Label(칸, text="%d.  %s" % (n, ko), wraplength=340,
                  justify="left", foreground="#777", font=(글꼴, 9)).pack(anchor="w")
        # **라벨은 늘 「지금 누르면 나갈 말」이다.** 화면과 클립보드가 어긋나면
        # 안 읽은 문장이 상대에게 간다
        보임 = tk.StringVar(value=en)
        ttk.Label(칸, textvariable=보임, wraplength=340, justify="left",
                  font=(글꼴, 10)).pack(anchor="w")

        아래 = ttk.Frame(칸)
        아래.pack(fill="x", pady=(2, 0))
        여럿 = 후보 and len(후보) > 1 and 자리
        if 여럿:
            ttk.Label(아래, text="변형 %d" % len(후보),
                      foreground="#999", font=(글꼴, 8)).pack(side="left")
            ttk.Button(아래, text="↻", width=3,
                       command=lambda: self._넘기기(보임, 후보, 자리)
                       ).pack(side="right", padx=(4, 0))
        ttk.Button(아래, text="복사", width=6,
                   command=(lambda: self._돌려복사(보임, 후보, 자리)) if 여럿
                   else (lambda t=en: self._줄복사(t))).pack(side="right")
        ttk.Separator(self.속, orient="horizontal").pack(fill="x")

    def _돌려복사(self, 보임, 후보: list[str], 자리) -> None:
        """보이는 것을 넣고 다음을 건다. **한 바퀴 안에는 안 겹친다.**"""
        상대 = (self.상대.get() or "").strip()
        나간것 = 보임.get()
        if not self._줄복사(나간것):
            return                      # 디바운스에 걸렸으면 안 돌린다
        if not 상대:
            return                      # 상대를 안 골랐으면 자루를 안 쓴다
        페르소나, 갈래, ko = 자리
        self.말주머니.뽑기(상대, 페르소나, 갈래, ko, 후보)
        보임.set(self.말주머니.지금(상대, 페르소나, 갈래, ko, 후보))

    def _넘기기(self, 보임, 후보: list[str], 자리) -> None:
        """안 닳게 다음으로. 되돌려 넣으므로 한 바퀴가 안 줄어든다."""
        상대 = (self.상대.get() or "").strip()
        if not 상대:
            # 자루를 안 쓰므로 목록 안에서 그냥 다음으로 민다
            보임.set(후보[(후보.index(보임.get()) + 1) % len(후보)]
                   if 보임.get() in 후보 else 후보[0])
            return
        페르소나, 갈래, ko = 자리
        보임.set(self.말주머니.넘기기(상대, 페르소나, 갈래, ko, 후보))

    def _줄복사(self, t: str) -> bool:
        """클립보드에 넣는다. 넣었으면 True.

        **0.8초 안의 같은 글 두 번째 누름은 무시한다.** 예전에는 두 번 눌러도
        같은 글이었는데 돌림이 붙으면서 두 번째가 다른 문장을 덮어쓰게 됐다.
        붙여넣기는 텔레그램에서 하므로 무엇이 들어갔는지 볼 기회가 없다.
        """
        이제 = time.monotonic()
        앞시각, 앞글 = self._마지막복사
        if 앞글 == t and 이제 - 앞시각 < 0.8:
            return False
        self._마지막복사 = [이제, t]
        # **반환값을 본다.** 다른 프로그램이 클립보드를 잡고 있으면 실패하는데
        # 여태 그래도 초록 「넣었다」가 떴다
        if W.클립보드_쓰기(t):
            self.알림.configure(text='넣었다 — "%s"' % t, foreground="#2a7")
            return True
        self.알림.configure(text="**클립보드에 못 넣었다.** 다른 프로그램이 잡고 있다",
                          foreground="#a33")
        return False

    # ── 돌리기 ───────────────────────────────────
    def _출력가로채기(self) -> None:
        """print 와 남의 라이브러리 출력을 창 안 로그로 돌린다.

        **`돌린다()` 에서만 한다.** 시험은 창을 만들고 `mainloop` 을 안 도니
        시험 출력까지 삼키면 안 된다.
        """
        self._되돌릴출력 = (sys.stdout, sys.stderr)
        sys.stdout = 로그로(self.큐, sys.stdout)
        sys.stderr = 로그로(self.큐, sys.stderr)

    def _출력되돌리기(self) -> None:
        if self._되돌릴출력:
            sys.stdout, sys.stderr = self._되돌릴출력
            self._되돌릴출력 = None

    def _닫기(self) -> None:
        if self.키:
            self.키.끄기()
        if self._다음:
            self.root.after_cancel(self._다음)
            self._다음 = None
        # 자루를 남긴다. 창을 다시 띄워도 한 바퀴가 이어져 안 겹친다.
        # **번호만 적는다** — 영어 문장도 핸들도 시각도 안 적는다
        if self.말주머니.자루:
            self.말주머니.쓰기()
        self._출력되돌리기()
        self.root.destroy()

    def 돌린다(self, 시작말: str = "") -> None:
        self._출력가로채기()
        if 시작말:
            print(시작말)      # 가로챈 뒤라야 창 안 로그에도 남는다
        # 창을 먼저 그리고 데운다. 안 그러면 모델 받는 동안 빈 창이 뜬다
        self.root.after(120, lambda: threading.Thread(
            target=self._데우기, daemon=True).start())
        try:
            self.root.mainloop()
        finally:
            self._출력되돌리기()
