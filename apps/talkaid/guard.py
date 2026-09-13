#!/usr/bin/env python3
"""나가면 안 되는 말을 막는다. 정규식이라 **0 ms** 다.

    from guard import check, Verdict
    v = check("we are from Whitehat School")
    if v.막힘:
        print(v.말)      # 무엇이 걸렸는지. **값은 안 찍는다**

실시간 대화에서 팀 신원이 한 번 나가면 되돌릴 수 없다.
**이 검사가 번역 품질보다 중요할 수 있다.**

    막음    나가면 안 된다. 클립보드에 안 넣는다
    경고    사람이 보고 정한다. 클립보드에는 넣는다

**걸린 값을 그대로 찍지 않는다.** 로그가 곧 반출이다 (dcsite 의 guard.mjs 와 같은 규칙).
무엇이 몇 건 걸렸는지만 낸다.

## 실명 목록은 레포에 안 둔다

목록 자체가 개인정보라서다. 자격 정보와 같은 자리에 둔다.

    ~/.config/darkchoco/talkaid_block      한 줄에 하나. # 로 시작하면 주석

없으면 그 검사를 **「못 봄」** 으로 적는다. 없음과 못 봄은 다르다.
"""
from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

CONF = Path(os.environ.get("DARKCHOCO_CONFIG_DIR", Path.home() / ".config" / "darkchoco"))
BLOCK_FILE = CONF / "talkaid_block"

# 우리가 누구인지 드러내는 말. 이것이 나가면 조사가 끝난다.
# 한국어와 영어 표기를 같이 잡는다 — 번역 뒤에 검사하므로 영어 쪽이 실제로 걸린다
신원 = [
    ("팀·소속", re.compile(
        r"화이트\s*햇|whitehat|white\s+hat\s+school|다크\s*초코|darkchoco|dark\s*choco"
        r"|국민일보|kukmin|케이프랩스|cape\s*labs|닥스훈트|dachshund"
        r"|d4rkn3ttz|다크넷츠", re.I)),
]

# 신분을 밝히는 말. **막지 않고 경고만 한다.**
# 팀 문서상 기자는 신분을 밝히고 접근하므로 이것이 의도한 문안일 수 있다.
# 의도했는지 아닌지는 도구가 판단할 수 없다. 사람에게 보이기만 한다
신분 = [
    ("신분을 밝히는 말", re.compile(
        r"\b(security\s+)?research(er|ers)?\b|\bjournalist\b|\breporter\b|\bstudent\b"
        r"|\bwe\s+are\s+(a\s+)?(team|group)\b|취재|기자|연구원|조사팀", re.I)),
]

# 우리 자리. 나가면 우리 인프라가 드러난다
자리 = [
    ("노션", re.compile(r"notion\.so|notion\.site", re.I)),
    ("우리 저장소", re.compile(r"github\.com/(MukSilver|grute02)", re.I)),
    ("내부 케이스 이름", re.compile(r"\bLEAK-\d+\b")),
    ("개인 폴더 경로", re.compile(r"[A-Za-z]:\\Users\\[^\\\s]+|/(?:home|Users)/[^/\s]+")),
]

# 개인정보 꼴. 상대에게 보낼 글에 이것이 들어갈 이유가 없다
개인정보 = [
    ("이메일", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("전화번호", re.compile(r"\b01[0-9]-?\d{3,4}-?\d{4}\b|\b\+?\d{1,3}[-\s]?\d{3,4}[-\s]?\d{4}\b")),
    ("주민번호 꼴", re.compile(r"\b\d{6}[-\s]?[1-4]\d{6}\b")),
]

# 번역이 안 된 채로 나갈 뻔한 것
한글 = re.compile(r"[가-힣]")


@dataclass
class Verdict:
    막힘: bool = False
    막은것: list[str] = field(default_factory=list)
    경고: list[str] = field(default_factory=list)
    못봄: list[str] = field(default_factory=list)

    @property
    def 말(self) -> str:
        줄 = []
        if self.막은것:
            줄.append("막음 — " + " · ".join(self.막은것))
        if self.경고:
            줄.append("경고 — " + " · ".join(self.경고))
        if self.못봄:
            줄.append("못 봄 — " + " · ".join(self.못봄))
        return "\n".join(줄) or "걸린 것 없음"


def load_block(p: Path | None = None) -> list[str]:
    """실명 목록. 없으면 빈 목록이고 부르는 쪽이 「못 봄」으로 적는다."""
    p = p or BLOCK_FILE
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line)
    return out


def _norm(text: str) -> str:
    """자모가 갈라져 있거나 전각이면 규칙이 다 빗나간다. 검사용 사본만 접는다."""
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"[​-‍﻿‪-‮]", "", text)


def check(text: str, block: list[str] | None = None,
          block_file: Path | None = None) -> Verdict:
    """나가는 글을 본다. **걸린 값은 안 담는다.** 규칙 이름과 건수만 담는다."""
    v = Verdict()
    t = _norm(text)

    for 이름, pat in 신원 + 자리:
        n = len(pat.findall(t))
        if n:
            v.막은것.append("%s %d건" % (이름, n))

    if block is None:
        block = load_block(block_file)
        if not block:
            v.못봄.append("실명 목록 없음 (%s)" % BLOCK_FILE)
    for w in block:
        if w and w.lower() in t.lower():
            v.막은것.append("목록에 있는 말 1건")
            break

    for 이름, pat in 신분 + 개인정보:
        n = len(pat.findall(t))
        if n:
            v.경고.append("%s %d건" % (이름, n))

    n = len(한글.findall(t))
    if n:
        v.경고.append("번역 안 된 한글 %d자" % n)

    v.막힘 = bool(v.막은것)
    return v


def main() -> int:
    import sys
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    v = check(" ".join(sys.argv[1:]))
    print(v.말)
    return 1 if v.막힘 else 0


if __name__ == "__main__":
    raise SystemExit(main())
