"""어댑터를 찾습니다.

hub/events/sources/ 안의 파일을 읽어 목록을 만듭니다. 파일 하나가 어댑터 하나입니다.
새 출처를 붙이려면 그 폴더에 파일 하나를 놓으면 됩니다. 등록표를 따로
고칠 일이 없습니다.

무거운 것을 안 부르는 것이 중요합니다. 목록을 보는 것만으로 telethon 이나
playwright 가 딸려 오면, 랜섬만 쓸 사람이 그것을 받아야 합니다. 그래서
모듈을 실제로 부르는 것은 돌릴 때뿐입니다.
"""

from __future__ import annotations

import importlib
import importlib.util
import re
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
출처들 = HERE / "sources"

# 하나() 가 빠져 있었습니다. run.한판 이 registry.하나 를 부르는데 __all__ 에
# 없어서, 지금은 모듈 경로로 불러 돌지만 import * 로 바꾸면 그때 터집니다.
__all__ = ["Entry", "목록", "하나", "불러오기"]


@dataclass
class Entry:
    """어댑터 하나에 대해, 모듈을 안 부르고도 아는 것."""

    name: str
    module: str
    path: Path
    summary: str = ""
    owner: str = ""
    every: int = 0        # 몇 분마다 도는가. 0 이면 부를 때만
    runs_in: str = "host"


# 모듈을 안 부르고 머리글에서 읽습니다. 정규식이라 무거운 import 가 안 됩니다.
_칸 = re.compile(r'^(NAME|SUMMARY|OWNER|EVERY|RUNS_IN)\s*=\s*(.+)$', re.M)


def _머리글(p: Path) -> dict:
    out = {}
    본문 = p.read_text(encoding="utf-8", errors="replace")
    # 파일 앞쪽만 봅니다. 뒤에 같은 이름이 또 나와도 앞이 정답입니다.
    for m in _칸.finditer(본문[:4000]):
        키, 값 = m.group(1), m.group(2).strip()
        # 뒤에 붙은 주석을 뗍니다. EVERY = 60  # 분  같은 꼴입니다.
        if "#" in 값 and 값[:1] not in "\"'":
            값 = 값.split("#")[0].strip()
        if 값[:1] in "\"'":
            값 = 값.strip("\"'")
        out[키] = 값
    return out


def 목록() -> list[Entry]:
    """어댑터 전부. 이름 순입니다."""
    out = []
    if not 출처들.is_dir():
        return out
    for p in sorted(출처들.glob("*.py")):
        if p.name.startswith("_"):
            continue
        h = _머리글(p)
        이름 = h.get("NAME") or p.stem.replace("_", "-")
        try:
            every = int(h.get("EVERY", "0"))
        except ValueError:
            every = 0
        out.append(Entry(
            name=이름,
            module=f"hub.events.sources.{p.stem}",
            path=p,
            summary=h.get("SUMMARY", ""),
            owner=h.get("OWNER", ""),
            every=every,
            runs_in=h.get("RUNS_IN", "host"),
        ))
    return out


def 하나(name: str) -> Entry | None:
    for e in 목록():
        if e.name == name:
            return e
    return None


def 불러오기(e: Entry):
    """이때 처음으로 모듈을 부릅니다. 무거운 것은 여기서 딸려 옵니다."""
    return importlib.import_module(e.module)
