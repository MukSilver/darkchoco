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

import queue
import threading
import tkinter as tk
from tkinter import filedialog, ttk

import engine as E
import guard as G
import win as W

글꼴 = "Malgun Gothic"      # 윈도우 한국어 UI 글꼴
좁게, 넓게 = 560, 980


class 창:
    def __init__(self, eng: E.Engine, 상용구: dict | None = None,
                 단축키켜기: bool = True):
        # 시험에서는 끈다. 전역 단축키는 온 시스템이 나눠 쓰는 것이라
        # 시험이 잠깐이라도 채가면 사람이 쓰던 것이 그 사이에 안 먹는다
        self.eng = eng
        self.상용구 = 상용구 or {}
        self.큐: queue.Queue = queue.Queue()
        self.도는중 = False
        self.사이드바열림 = False
        self.준비줄: list[tuple[str, str]] = []

        self.dpi = W.dpi_켜기()
        self.root = tk.Tk()
        self.root.title("talkaid — 밖으로 아무것도 안 보낸다")
        self.root.geometry("%dx420" % 좁게)
        self.root.minsize(480, 360)
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

        self.관문 = ttk.Label(바깥, text="", wraplength=좁게 - 40, justify="left")
        self.관문.grid(row=7, column=0, sticky="ew")

        self._사이드바짜기()

    def _사이드바짜기(self) -> None:
        self.옆 = ttk.Frame(self.root, padding=(0, 10, 10, 10), width=400)
        머리 = ttk.Frame(self.옆)
        머리.pack(fill="x")
        ttk.Label(머리, text="미리 옮겨 두는 자리").pack(side="left")
        self.준비상태 = ttk.Label(머리, text="", foreground="#666")
        self.준비상태.pack(side="right")

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
            self.관문.configure(
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
        self.root.after(50, self._큐꺼내기)

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
        r, v, 읽기 = 값
        self.도는중 = False
        self.옮김단추.configure(state="normal")
        self.결과.delete("1.0", "end")
        self.결과.insert("1.0", r.text)
        self.역번역.configure(text=r.back or "(역번역 없음)")
        self.상태.configure(text="%.1f초" % (r.ms / 1000))

        if v is None:
            self.관문.configure(text="", foreground="#444")
            W.클립보드_쓰기(r.text)
            return
        if v.막힘:
            self.관문.configure(text="클립보드에 안 넣었다 — " + v.말.replace("\n", " / "),
                              foreground="#a33")
            return
        self.관문.configure(text=(v.말.replace("\n", " / ") if (v.경고 or v.못봄)
                                else "클립보드에 넣었다"),
                          foreground="#b8860b" if v.경고 else "#2a7")
        W.클립보드_쓰기(r.text)

    def _받_탈(self, e) -> None:
        self.도는중 = False
        self.옮김단추.configure(state="normal")
        self.관문.configure(text="못 옮겼다 — %s" % e, foreground="#a33")

    def _받_준비(self, 값) -> None:
        했다, 다, 짝 = 값
        self.준비상태.configure(text="%d / %d" % (했다, 다))
        if 짝:
            self.준비줄.append(짝)
            self._준비그리기(len(self.준비줄), 짝)

    # ── 옮기기 ───────────────────────────────────
    def 옮기기(self, 읽기: bool = False) -> None:
        글 = self.입력.get("1.0", "end").strip()
        if not 글 or self.도는중:
            return
        self.도는중 = True
        self.옮김단추.configure(state="disabled")
        self.상태.configure(text="옮기는 중…")
        self.관문.configure(text="")
        threading.Thread(target=self._일, args=(글, 읽기), daemon=True).start()

    def _일(self, 글: str, 읽기: bool) -> None:
        try:
            if 읽기:
                말 = E.detect_lang(글)
                pair = {"zh": "zh-ko", "en": "en-ko"}.get(말, "ko-en")
                r = self.eng.run(글, pair, back=False)
                self.큐.put(("결과", (r, None, True)))
            else:
                r = self.eng.run(글, "ko-en", back=True)
                self.큐.put(("결과", (r, G.check(r.text), False)))
        except Exception as e:
            self.큐.put(("탈", "%s: %s" % (type(e).__name__, e)))

    def _지우기(self) -> None:
        self.입력.delete("1.0", "end")
        self.결과.delete("1.0", "end")
        self.역번역.configure(text="")
        self.관문.configure(text="")
        self.상태.configure(text="")

    # ── 사이드바 ─────────────────────────────────
    def 사이드바(self) -> None:
        if self.사이드바열림:
            self.옆.pack_forget()
            self.root.geometry("%dx%d" % (좁게, self.root.winfo_height()))
            self.준비단추.configure(text="준비해 둔 것 ▸")
        else:
            self.옆.pack(side="right", fill="both")
            self.root.geometry("%dx%d" % (넓게, self.root.winfo_height()))
            self.준비단추.configure(text="◂ 접기")
        self.사이드바열림 = not self.사이드바열림

    def _파일열기(self) -> None:
        p = filedialog.askopenfilename(
            title="한국어 문안 파일", filetypes=[("텍스트", "*.txt *.md"), ("전부", "*.*")])
        if p:
            with open(p, encoding="utf-8", errors="replace") as f:
                self._준비시작(f.read())

    def _붙여넣기(self) -> None:
        self._준비시작(W.클립보드_읽기())

    def _상용구넣기(self) -> None:
        """상용구는 **번역을 안 거친다.** 그래서 0 ms 다.

        맞장구·되묻기·시간 벌기·마무리는 종류가 적어 미리 손으로 써 둘 수 있다.
        대화의 상당 부분이 이것으로 덮인다. 통역사가 실제로 하는 일이 그렇다.
        """
        if not self.상용구:
            self.준비상태.configure(text="snippets.json 이 없다")
            return
        if not self.사이드바열림:
            self.사이드바()
        self._준비비우기()
        for 갈래, 목록 in self.상용구.items():
            for s in 목록:
                ko, en = s.get("한국어", ""), s.get("영어", "")
                if not en:
                    continue
                self.준비줄.append((ko, en))
                self._준비그리기(len(self.준비줄), (ko, en))
        self.준비상태.configure(text="상용구 %d" % len(self.준비줄))

    def _준비비우기(self) -> None:
        self.준비줄.clear()
        for w in self.속.winfo_children():
            w.destroy()
        self.준비상태.configure(text="")

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
        threading.Thread(target=self._준비일, args=(줄들,), daemon=True).start()

    def _준비일(self, 줄들: list[str]) -> None:
        for i, s in enumerate(줄들, 1):
            try:
                r = self.eng.run(s, "ko-en", back=False)
                self.큐.put(("준비", (i, len(줄들), (s, r.text))))
            except Exception as e:
                self.큐.put(("준비", (i, len(줄들), (s, "**못 옮겼다** %s" % e))))

    def _준비그리기(self, n: int, 짝: tuple[str, str]) -> None:
        ko, en = 짝
        칸 = ttk.Frame(self.속, padding=(0, 4, 0, 6))
        칸.pack(fill="x", anchor="w")
        ttk.Label(칸, text="%d.  %s" % (n, ko), wraplength=340,
                  justify="left", foreground="#777", font=(글꼴, 9)).pack(anchor="w")
        ttk.Label(칸, text=en, wraplength=340, justify="left",
                  font=(글꼴, 10)).pack(anchor="w")
        ttk.Button(칸, text="복사", width=6,
                   command=lambda t=en: self._줄복사(t)).pack(anchor="e", pady=(2, 0))
        ttk.Separator(self.속, orient="horizontal").pack(fill="x")

    def _줄복사(self, t: str) -> None:
        v = G.check(t)
        if v.막힘:
            self.관문.configure(text="그 줄은 클립보드에 안 넣었다 — "
                                  + v.말.replace("\n", " / "), foreground="#a33")
            return
        W.클립보드_쓰기(t)
        self.관문.configure(text="클립보드에 넣었다", foreground="#2a7")

    # ── 돌리기 ───────────────────────────────────
    def _닫기(self) -> None:
        if self.키:
            self.키.끄기()
        self.root.destroy()

    def 돌린다(self) -> None:
        self.root.mainloop()
