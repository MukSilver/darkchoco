"""X(트위터) CTI 계정 글을 Jina Reader 로 읽습니다.

원래 도구는 skills/collect/sources/x_jina.py 입니다. 읽는 규칙 · 판정 · 로그 방침이 거기
들어 있습니다. 여기서는 그것을 부르기만 합니다. 텔레그램 미리보기(tg_preview.py)와 같은 짝입니다.

2026-09-26 최현서 결정. 조사 보고서는 `프젝/02_리서치/X수집_조사_20260926.md` 입니다.
키 없는 Jina 는 x.com 이 익명 사용자 전체에 1시간씩 막혀 못 씁니다. **최현서가 받은 키로,
좁은 계정 목록만** 읽습니다. 둘 다 저장소 밖 파일에 둡니다 — 무엇을 보는지가 드러납니다.

    ~/.config/darkchoco/jina_key      키 한 줄
    ~/.config/darkchoco/x_accounts    계정 한 줄에 하나

키나 목록이 없으면 안 돕니다(Skip). Jina 가 막거나 잔액이 없으면 **오류로 올립니다** —
그래야 스케줄러가 물러났다가 다시 봅니다.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterator

NAME = "x-cti"
SUMMARY = "X CTI 계정 글을 Jina Reader 로 읽습니다 (키 · 계정 목록은 저장소 밖)"
OWNER = "최현서"
EVERY = 360         # 분. 여섯 시간
RUNS_IN = "host"

ROOT = Path(__file__).resolve().parents[3]   # hub/events/sources/ 에서 세 칸
sys.path.insert(0, str(ROOT / "skills"))

from hub.events.contract import Ctx, Item, Needs, Skip  # noqa: E402

NEEDS = Needs(packages=["requests"])


def collect(ctx: Ctx) -> Iterator[Item]:
    # 무거운 것은 여기서 부릅니다. 목록만 볼 때는 requests 가 필요 없습니다.
    from collect.sources import x_jina

    목록 = x_jina.계정들()
    if not 목록:
        raise Skip("볼 X 계정이 없습니다. 아래에 한 줄씩 적으십시오.\n"
                   "      ~/.config/darkchoco/x_accounts\n"
                   "      (저장소 밖에 둡니다. 무엇을 보는지가 드러납니다)")
    키 = x_jina.키읽기()
    if not 키 and not ctx.dry:
        raise Skip("Jina 키가 없습니다. 최현서가 jina.ai 에서 받아 아래에 둡니다.\n"
                   "      ~/.config/darkchoco/jina_key")

    셈: dict = {}
    yield from x_jina.모으기(목록, 키, dry=ctx.dry, 셈=셈)
    # 로그에는 건수와 오류 이름만 나갑니다(x_jina.요약)
    print("    " + x_jina.요약(셈), file=sys.stderr)
    if 셈.get("잔액 부족으로 멈춤"):
        raise RuntimeError("Jina 잔액이 없습니다. 충전할지 최현서가 정합니다")
    if 셈.get("오류") and not 셈.get("쪽") and not ctx.dry:
        raise RuntimeError("Jina 가 한 쪽도 못 읽었습니다: "
                           + " · ".join("%s %d" % kv for kv in sorted(셈["오류"].items())))
