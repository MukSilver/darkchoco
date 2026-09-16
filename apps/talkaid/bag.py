#!/usr/bin/env python3
"""말주머니. **같은 사람이 우리에게서 같은 말을 두 번 듣지 않게 한다.**

    from bag import 주머니들
    ㅁ = 주머니들.읽기()
    ㅁ.지금("2", "사는 쪽", "값 묻기", "얼마에 파나요", 후보)   화면에 보일 것
    ㅁ.뽑기("2", "사는 쪽", "값 묻기", "얼마에 파나요", 후보)   [복사] 를 눌렀다

## 왜 random.choice 가 아닌가

넷 중에 무작위로 고르면 **네 번에 한 번은 직전과 같은 것**이 나온다. 그것이 바로
상대가 스크립트로 눈치채는 자리다. 섞어서 끝까지 쓰면 한 바퀴 안에는 절대 안 겹친다.
같은 줄 수로 더 강한 쪽을 쓴다.

**이음매도 막는다.** 주머니가 비어 다시 섞을 때 새 첫 장이 직전 마지막과 같으면
한 칸 민다. 안 그러면 경계에서 두 번 연달아 같은 말이 나간다.

## 왜 상대마다 따로인가

문제는 「우리가 같은 말을 자주 쓰는 것」이 아니라 **「한 사람이 우리에게서 같은 말을
두 번 듣는 것」** 이다. 404muse 에게 다 쓴 말이 REDX 에게는 새것이다.

## 파일에 무엇을 적나

`~/.config/darkchoco/talkaid_bag.json` 에 **번호만** 적는다.

    적는 것    별칭 · 후보 개수 · 남은 번호 · 직전 번호
    안 적는 것  **영어 문장 · 상대 핸들 · 대화 내용 · 시각**

문장을 적으면 그 파일이 곧 발화 기록이 되고, 핸들을 적으면 접촉 명부가 된다.
번호만 적으면 파일만 봐서는 무엇을 언제 보냈는지 알 수 없다.

후보 목록이 바뀌면 번호가 어긋난다. 개수를 같이 적어 두고 다르면 그 주머니를 버린다.
"""
from __future__ import annotations

import json
import os
import random
from pathlib import Path

CONF = Path(os.environ.get("DARKCHOCO_CONFIG_DIR",
                           Path.home() / ".config" / "darkchoco"))
자루파일 = CONF / "talkaid_bag.json"

기본별칭 = ["1", "2", "3", "4", "5"]


def 열쇠(상대: str, 페르소나: str, 갈래: str, 한국어: str) -> str:
    """주머니 하나를 가리키는 이름. `|` 는 별칭에 못 쓰게 막는다."""
    return "|".join(x.replace("|", "/") for x in (상대, 페르소나, 갈래, 한국어))


class 주머니들:
    def __init__(self, 별칭: list[str] | None = None,
                 자루: dict | None = None, 난수=None, 경로: Path | None = None):
        self.별칭 = list(별칭) if 별칭 else list(기본별칭)
        self.자루: dict = 자루 or {}
        # 시험에서 씨앗을 고정하려고 밖에서 넣을 수 있게 한다
        self.난수 = 난수 or random.Random()
        # **자기 경로를 들고 있는다.** 안 그러면 시험이 사람의 진짜 설정 파일을
        # 덮어쓴다. 실제로 한 번 덮어썼다 (2026-09-16)
        self.경로 = 경로 or 자루파일

    # ── 뽑기 ──────────────────────────────────────
    def _칸(self, k: str, n: int) -> dict:
        """그 주머니를 꺼낸다. 없거나 후보 개수가 달라졌으면 새로 섞는다."""
        칸 = self.자루.get(k)
        if 칸 is None or 칸.get("n") != n or not isinstance(칸.get("남은"), list):
            칸 = {"n": n, "남은": self._섞기(n, None), "직전": None}
            self.자루[k] = 칸
        if not 칸["남은"]:
            칸["남은"] = self._섞기(n, 칸.get("직전"))
        return 칸

    def _섞기(self, n: int, 직전) -> list[int]:
        """0..n-1 을 섞는다. **첫 장이 직전과 같으면 한 칸 민다.**"""
        차례 = list(range(n))
        self.난수.shuffle(차례)
        if len(차례) > 1 and 직전 is not None and 차례[0] == 직전:
            차례[0], 차례[1] = 차례[1], 차례[0]
        return 차례

    def 지금(self, 상대, 페르소나, 갈래, 한국어, 후보: list[str]) -> str:
        """장전된 것. 화면에 보이는 것이고 [복사] 를 누르면 이것이 나간다."""
        if not 후보:
            return ""
        칸 = self._칸(열쇠(상대, 페르소나, 갈래, 한국어), len(후보))
        return 후보[칸["남은"][0]]

    def 뽑기(self, 상대, 페르소나, 갈래, 한국어, 후보: list[str]) -> str:
        """장전된 것을 내고 다음을 건다. 낸 것을 돌려준다."""
        if not 후보:
            return ""
        k = 열쇠(상대, 페르소나, 갈래, 한국어)
        칸 = self._칸(k, len(후보))
        i = 칸["남은"].pop(0)
        칸["직전"] = i
        if not 칸["남은"]:
            칸["남은"] = self._섞기(len(후보), i)
        return 후보[i]

    def 넘기기(self, 상대, 페르소나, 갈래, 한국어, 후보: list[str]) -> str:
        """안 닳게 다음으로 돌린다. 되돌려 넣으므로 한 바퀴가 줄지 않는다."""
        if len(후보) < 2:
            return self.지금(상대, 페르소나, 갈래, 한국어, 후보)
        칸 = self._칸(열쇠(상대, 페르소나, 갈래, 한국어), len(후보))
        칸["남은"].append(칸["남은"].pop(0))
        return 후보[칸["남은"][0]]

    # ── 저장 ──────────────────────────────────────
    def 담기(self) -> dict:
        return {"별칭": self.별칭, "자루": self.자루}

    def 쓰기(self, p: Path | None = None) -> bool:
        """임시 파일에 쓰고 바꿔치기한다. 쓰다 죽어도 옛것이 남는다."""
        p = p or self.경로
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            임시 = p.with_suffix(".tmp")
            임시.write_text(json.dumps(self.담기(), ensure_ascii=False),
                          encoding="utf-8")
            임시.replace(p)
            return True
        except Exception as e:
            print("[자루] 못 썼다 (%s: %s)" % (type(e).__name__, e))
            return False

    @classmethod
    def 읽기(cls, p: Path | None = None, 난수=None) -> "주머니들":
        """깨졌으면 빈 것으로 시작한다. **도구가 안 뜨는 일은 없다.**"""
        p = p or 자루파일
        if not p.exists():
            return cls(난수=난수, 경로=p)
        try:
            d = json.loads(p.read_text(encoding="utf-8-sig"))
            별칭 = d.get("별칭")
            자루 = d.get("자루")
            return cls(별칭 if isinstance(별칭, list) else None,
                       자루 if isinstance(자루, dict) else None, 난수, p)
        except Exception as e:
            print("[자루] 못 읽었다 (%s: %s). 빈 것으로 시작한다." % (type(e).__name__, e))
            return cls(난수=난수, 경로=p)


def 후보뽑기(항목: dict) -> list[str]:
    """한 항목의 실제 후보. **`영어` 는 스칼라로 두고 `영어들` 을 덧붙인다.**

    같은 글을 두 군데 적는 규약을 만들지 않으려는 것이다. `영어들` 이 없으면
    후보가 하나이고 그 줄은 오늘과 한 픽셀도 다르지 않게 돈다.

    `섞기` 를 `"고정"` 으로 두면 변형을 적어 뒀어도 첫 것만 낸다.
    """
    첫 = (항목.get("영어") or "").strip()
    if 항목.get("섞기") == "고정":
        return [첫] if 첫 else []
    더 = 항목.get("영어들") or []
    if not isinstance(더, list):
        더 = []
    본 = set()
    out = []
    for s in [첫] + [str(x).strip() for x in 더]:
        if s and s not in 본:
            본.add(s)
            out.append(s)
    return out
