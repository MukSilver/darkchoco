#!/usr/bin/env python3
"""텔레그램 쪽 넘기기(`telegram_web.쪽들`) 시험.

    python collect/sources/test_tg_pages.py

**밖에 나가지 않는다.** 가짜 요청 도구가 지어낸 쪽을 돌려준다. 값은 전부 지어낸 것이다.

2026-09-29 최현서 결정(인계 H-2 · E-5): 첫 쪽이 꽉 찼고(15개 이상) 가장 오래된 글이
「지금 − 12시간」 보다 새것이면 `before=` 로 한 쪽 더, 채널당 8쪽까지, 모든 채널.
9/26 에 재 보니 osint_cti 는 첫 쪽 20개가 1.6시간 안이라 6시간마다 읽으면 50개쯤을 놓쳤다.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from collect.sources import telegram_web as T  # noqa: E402

fails = []
지금 = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)


def check(name: str, got, want) -> None:
    if got != want:
        fails.append("%s\n     받음 %r\n     기대 %r" % (name, got, want))


def post(num: int, 몇시간전: float) -> str:
    when = (지금 - timedelta(hours=몇시간전)).isoformat()
    return (
        '<div class="tgme_widget_message js-widget_message" data-post="testchan/%d">'
        '<div class="tgme_widget_message_text js-message_text" dir="auto">시험 글 %d</div>'
        '<a class="tgme_widget_message_date" href="https://t.me/testchan/%d">'
        '<time datetime="%s"></time></a></div>' % (num, num, num, when))


def 쪽(끝번호: int, 개수: int, 가장오래된시간: float, 가장새시간: float) -> bytes:
    """글 번호 끝번호-개수+1 ~ 끝번호. 시간은 오래된 것부터 새것까지 고르게."""
    글 = []
    for i in range(개수):
        num = 끝번호 - 개수 + 1 + i
        t = 가장오래된시간 - (가장오래된시간 - 가장새시간) * (i / max(개수 - 1, 1))
        글.append(post(num, t))
    return ('<div class="tgme_channel_history">%s</div>' % "".join(글)).encode("utf-8")


class 가짜요청:
    """주소별로 정한 응답을 돌려준다. 부른 주소를 적어 둔다."""

    def __init__(self, 응답: dict):
        self.응답, self.부름 = 응답, []

    def get(self, url, accept=""):
        self.부름.append(url)
        v = self.응답.get(url)
        if isinstance(v, Exception):
            raise v
        if v is None:
            return 404, b"", ""
        if isinstance(v, tuple):
            return v
        return 200, v, "text/html"


첫주소 = "https://t.me/s/testchan"


def 넘김(n: int) -> str:
    return "%s?before=%d" % (첫주소, n)


쉰것 = []


def 돌리기(f):
    쉰것.clear()
    return T.쪽들(f, "testchan", 지금=지금, 쉬기=쉰것.append)


# ── 1. 꽉 찼고 12시간 안이면 넘기고, 12시간을 넘긴 쪽에서 멈춘다 ──
f = 가짜요청({첫주소: 쪽(200, 20, 3, 0.1), 넘김(181): 쪽(180, 20, 13, 3.2), 넘김(161): 쪽(160, 20, 20, 13.5)})
글, 왜, 쪽수 = 돌리기(f)
check("두 쪽을 읽는다", 쪽수, 2)
check("부른 주소", f.부름, [첫주소, 넘김(181)])
check("글 40개", len(글), 40)
check("글 번호가 겹치지 않는다", len({d["post"] for d in 글}), 40)
check("사유 없음", 왜, "")
check("넘기는 쪽 앞에서만 더 쉰다", len(쉰것), 1)
check("더 쉬는 시간은 정한 범위", T.넘김더쉬기[0] <= 쉰것[0] <= T.넘김더쉬기[1], True)

# ── 2. 첫 쪽이 안 꽉 차면 안 넘긴다 ──
f = 가짜요청({첫주소: 쪽(50, 10, 2, 0.1)})
글, 왜, 쪽수 = 돌리기(f)
check("한 쪽만", (쪽수, len(글), f.부름), (1, 10, [첫주소]))

# ── 3. 가장 오래된 글이 12시간보다 오래면 첫 쪽에서 멈춘다 ──
f = 가짜요청({첫주소: 쪽(50, 20, 30, 0.1)})
check("한가한 채널은 한 쪽", 돌리기(f)[2], 1)

# ── 4. 채널당 8쪽까지 ──
응답 = {첫주소: 쪽(1000, 20, 1, 0.1)}
for k in range(1, 20):
    끝 = 1000 - 20 * k
    응답[넘김(끝 + 1)] = 쪽(끝, 20, 1 + k * 0.5, 0.2 + k * 0.5)
f = 가짜요청(응답)
글, 왜, 쪽수 = 돌리기(f)
check("상한 8쪽", (쪽수, len(f.부름), len(글)), (8, 8, 160))
check("상한은 8", T.쪽상한, 8)
check("되짚는 시간은 12시간", T.되짚을시간, 12)

# ── 5. 빈 쪽 · 더 앞선 글이 안 나오면 멈춘다 ──
f = 가짜요청({첫주소: 쪽(200, 20, 3, 0.1), 넘김(181): b"<div></div>"})
check("빈 쪽에서 멈춤", 돌리기(f)[2], 2)
f = 가짜요청({첫주소: 쪽(200, 20, 3, 0.1), 넘김(181): 쪽(200, 20, 3, 0.1)})
글, 왜, 쪽수 = 돌리기(f)
check("같은 쪽이 또 오면 멈춘다", (쪽수, len(글), len(f.부름)), (2, 20, 2))

# ── 6. 넘긴 쪽 요청이 실패하면 받은 만큼 쓰고 멈춘다 ──
f = 가짜요청({첫주소: 쪽(200, 20, 3, 0.1), 넘김(181): ConnectionError("끊김")})
글, 왜, 쪽수 = 돌리기(f)
check("첫 쪽 글은 남는다", (len(글), 쪽수), (20, 2))
f = 가짜요청({첫주소: 쪽(200, 20, 3, 0.1), 넘김(181): (429, b"", "")})
check("429 면 멈춘다", (len(돌리기(f)[0]), len(f.부름)), (20, 2))

# ── 7. 첫 쪽이 안 되면 예전과 같이 알린다 ──
f = 가짜요청({첫주소: (403, b"", "")})
check("첫 쪽 HTTP", 돌리기(f), ([], "HTTP 403", 1))
f = 가짜요청({첫주소: ConnectionError("끊김")})
try:
    돌리기(f)
    fails.append("첫 쪽 요청 실패를 삼켰다")
except ConnectionError:
    pass
f = 가짜요청({첫주소: b"<html><div class='tgme_page'></div></html>"})
글, 왜, 쪽수 = 돌리기(f)
check("빈 채널은 까닭과 함께", (글, bool(왜), 쪽수), ([], True, 1))

# ── 결과 ────────────────────────────────────────
if fails:
    print("실패 %d" % len(fails))
    for x in fails:
        print("  - %s" % x)
    sys.exit(1)
print("통과. 시험 7 묶음")
