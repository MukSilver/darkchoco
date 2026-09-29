"""텔레그램 공개 미리보기를 읽습니다.

원래 도구는 skills/collect/sources/telegram_web.py 입니다. 최현서 님이
만든 것이고, 읽는 규칙과 방어가 거기 들어 있습니다. 여기서는 그것을
부르기만 합니다.

`t.me/s/<채널>` 은 로그인 없이 보이는 자리입니다. 계정을 안 쓰므로 그
계정이 무엇을 봤는지가 남지 않습니다. 그래서 이것을 먼저 씁니다.
미리보기가 꺼진 채널만 실계정으로 갑니다.

볼 채널은 저장소 밖 파일에 둡니다. 무엇을 보고 있는지가 드러나기
때문입니다.

    ~/.config/darkchoco/telegram_channels     한 줄에 하나
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterator

NAME = "tg-preview"
SUMMARY = "텔레그램 공개 미리보기를 읽습니다"
OWNER = "최현서"
EVERY = 60          # 분
RUNS_IN = "host"

ROOT = Path(__file__).resolve().parents[3]   # hub/events/sources/ 에서 세 칸
sys.path.insert(0, str(ROOT / "skills"))

from hub.events.contract import Ctx, Item, Needs, Skip  # noqa: E402

NEEDS = Needs(packages=["requests"])


def _채널들(ctx: Ctx) -> list[str]:
    """볼 채널 목록. 환경변수가 가리키는 파일이 먼저입니다."""
    자리 = []
    env = (ctx.env.get("DARKCHOCO_CHANNELS") or "").strip()
    if env:
        자리.append(Path(env))
    자리.append(Path.home() / ".config" / "darkchoco" / "telegram_channels")

    for p in 자리:
        try:
            if p.is_file():
                줄 = [l.strip() for l in p.read_text(encoding="utf-8").splitlines()]
                return [l for l in 줄 if l and not l.startswith("#")]
        except OSError:
            continue

    raise Skip(
        "볼 채널 목록이 없습니다. 아래에 한 줄씩 적으십시오.\n"
        "      ~/.config/darkchoco/telegram_channels\n"
        "      (저장소 밖에 둡니다. 무엇을 보는지가 드러납니다)")


def collect(ctx: Ctx) -> Iterator[Item]:
    # 무거운 것은 여기서 부릅니다. 목록만 볼 때는 requests 가 필요 없습니다.
    from collect.fetch import Fetcher
    from collect.sources.telegram_web import to_item, 쪽들

    채널 = _채널들(ctx)
    f = Fetcher(dry=ctx.dry)

    for chan in 채널:
        # 첫 쪽이 꽉 찼고 12시간 안이면 거슬러 더 읽습니다(채널당 8쪽). Actions 쪽과 같은 함수입니다 (2026-09-29)
        try:
            posts, why, _ = 쪽들(f, chan)
        except Exception as e:  # noqa: BLE001  한 채널이 막혀도 다음으로 갑니다
            print(f"    {chan}: 요청 실패 — {e}", file=sys.stderr)
            continue
        if not posts:
            print(f"    {chan}: {why}", file=sys.stderr)
            continue

        for d in posts:
            yield to_item(d, chan, ctx.today)
