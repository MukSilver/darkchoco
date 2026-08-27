#!/usr/bin/env python3
"""텔레그램 실계정으로 채널을 읽는다. 공개 미리보기로 안 보이는 채널용.

    python -m collect.sources.telegram_api --check
    python -m collect.sources.telegram_api breachdetect --db data/darkchoco.db
    python -m collect.sources.telegram_api breachdetect --limit 50

## 언제 이 길을 쓰나

    가. 공개 미리보기 (`telegram_web.py`)   계정 없음 · 흔적 없음   ← 기본
    나. 실계정 세션 (이 파일)               비공개 채널까지        ← 가로 안 될 때만

**가부터 쓴다.** 2026-08-27 실측으로 `osint_cti` 는 가로 되고 `breachdetect` 는 안 된다.

## 이 길이 남기는 흔적

가와 다르다. 여기서는 **그 계정이 그 채널을 읽은 것이 남는다.**

| | 가 | 나 |
|---|---|---|
| 계정 | 없다 | 전화번호로 만든 실계정 |
| 남는 것 | 없다 | 계정이 채널에 들어간 것, 읽은 것 |
| 볼 수 있는 것 | 공개 미리보기가 켜진 채널 | 그 계정이 들어간 모든 채널 |

**읽기만 한다.** 이 파일에 글을 쓰거나 채널에 드는 코드를 넣지 않는다.
채널에 드는 것은 사람이 앱에서 한다. 코드가 대신 들지 않는다.

## 사람이 먼저 할 것

1. `my.telegram.org` 에서 `api_id` 와 `api_hash` 를 받는다
2. 아래에 두 줄로 넣는다. **프젝 폴더와 레포 밖이다**

       ~/.config/darkchoco/telegram_api
       첫 줄  api_id
       둘째 줄 api_hash

3. `pip install telethon`
4. 처음 한 번은 전화번호와 인증 코드를 넣어야 한다. `--check` 로 한다

**세션 파일은 VM 안에만 둔다.** 그 계정이 어느 채널에 들어가 있는지가 세션에 남는다.
기본 자리는 `~/.config/darkchoco/tg_session` 이다.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from collect.sources import tg_post  # noqa: E402
from collect.store import Store  # noqa: E402

VER = "telegram_api v1"

KEY_PLACES = [
    Path(os.environ["DARKCHOCO_TG_API"]) if os.environ.get("DARKCHOCO_TG_API") else None,
    Path("/run/secrets/telegram_api"),
    Path.home() / ".config" / "darkchoco" / "telegram_api",
]
SESSION = Path(os.environ.get(
    "DARKCHOCO_TG_SESSION",
    str(Path.home() / ".config" / "darkchoco" / "tg_session")))

GAP = 2.5          # 호출 사이 텀. 가와 같은 하한을 지킨다
MAX = 100          # 한 번에 이보다 많이 안 받는다


def keys() -> tuple[int, str]:
    for p in KEY_PLACES:
        if p and p.exists():
            lines = [l.strip() for l in p.read_text(encoding="utf-8").splitlines()
                     if l.strip() and not l.startswith("#")]
            if len(lines) < 2:
                raise SystemExit("%s 에 두 줄이 있어야 한다. 첫 줄 api_id, 둘째 줄 api_hash" % p)
            try:
                return int(lines[0]), lines[1]
            except ValueError:
                raise SystemExit("%s 의 첫 줄이 숫자가 아니다. api_id 여야 한다" % p)
    raise SystemExit(
        "api_id 와 api_hash 를 못 찾았다.\n"
        "  1. my.telegram.org 에서 받는다\n"
        "  2. ~/.config/darkchoco/telegram_api 에 두 줄로 넣는다\n"
        "     첫 줄 api_id · 둘째 줄 api_hash\n"
        "**프젝 폴더와 레포 안에 두지 마라.**")


def client():
    try:
        # **`telethon.sync` 여야 한다.** 그냥 `telethon` 에서 가져오면
        # 메서드가 코루틴 그대로라 `get_me()` 가 안 기다려지고 경고만 뜬다.
        # 코루틴 객체는 참이라 `is None` 검사를 그냥 통과한다. 2026-08-27
        from telethon.sync import TelegramClient
    except ImportError:
        raise SystemExit(
            "telethon 이 없다.  pip install telethon\n"
            "**VM 안에서 깐다.** 세션 파일이 호스트에 남으면 안 된다.")
    api_id, api_hash = keys()
    SESSION.parent.mkdir(parents=True, exist_ok=True)
    return TelegramClient(str(SESSION), api_id, api_hash)


def links_of(msg) -> list:
    """글에 붙은 링크. telethon 이 개체로 준다."""
    out = []
    try:
        for _, val in (msg.get_entities_text() or []):
            s = str(val)
            if s.startswith("http"):
                out.append(s)
    except Exception:
        pass
    return out


def to_item(msg, chan: str):
    """공통 자리(`tg_post`)로 넘긴다. 공개 미리보기 길과 같은 것을 내야 한다."""
    mid = getattr(msg, "id", "")
    return tg_post.to_item(
        chan=chan, src_id="%s/%s" % (chan, mid),
        text=(getattr(msg, "message", "") or "").strip(),
        links=links_of(msg),
        when=(msg.date.isoformat() if getattr(msg, "date", None) else ""),
        perma="https://t.me/%s/%s" % (chan, mid),
        got_by=VER, body_via="telethon")


def run(chan: str, db: Path | None, limit: int) -> int:
    import time
    c = client()
    today = date.today().isoformat()
    with c:
        me = c.get_me()
        if me is None:
            print("로그인이 안 됐다. --check 로 먼저 한 번 로그인할 것")
            return 1
        try:
            msgs = list(c.iter_messages(chan, limit=min(limit, MAX)))
        except Exception as e:
            print("%s  못 읽었다: %s" % (chan, e))
            print("  그 계정이 이 채널에 들어가 있어야 한다. **코드가 대신 들지 않는다.**")
            return 1
        time.sleep(GAP)

    print("채널  %s · 글 %d개" % (chan, len(msgs)))
    if not msgs:
        print("글 0개. 채널이 비었거나 그 계정이 못 보는 채널이다")
        return 1

    items = [to_item(m, chan) for m in msgs if (getattr(m, "message", "") or "").strip()]
    kinds: dict = {}
    shapes: dict = {}
    for it in items:
        kinds[it.raw["글 종류"]] = kinds.get(it.raw["글 종류"], 0) + 1
        shapes[it.raw["글 꼴"]] = shapes.get(it.raw["글 꼴"], 0) + 1
    print("글 꼴  %s" % " · ".join("%s %d" % kv for kv in sorted(shapes.items())))
    for k, v in sorted(kinds.items(), key=lambda x: -x[1]):
        print("    %-18s %2d  %s"
              % (k, v, "우리 대상" if any(i.raw["우리 대상"] and i.raw["글 종류"] == k
                                     for i in items) else ""))
    hard = [i for i in items if i.raw.get("못 읽은 것")]
    if hard:
        print("\n못 읽은 글 %d개. 버리지 않고 raw 에 사유를 적었다" % len(hard))

    if not db:
        print("\n--db 를 주면 넣는다")
        return 0
    s = Store(db)
    fresh = sum(1 for it in items if s.put(it, today))
    s.log_run(today, "telegram_api/" + chan, len(items), fresh, VER)
    s.close()
    print("\n%d개 중 처음 보는 것 %d개" % (len(items), fresh))
    return 0


def check() -> int:
    """준비가 됐는지만 본다. 처음이면 여기서 로그인한다."""
    print("api 키   ", end="")
    try:
        # **값을 한 조각도 내지 않는다.** 있는지와 자릿수만 낸다.
        # 앞자리만 찍어도 로그와 화면 캡처에 남는다. 2026-08-27 에 고쳤다
        api_id, api_hash = keys()
        print("있다 (api_id %d자리 · api_hash %d자)" % (len(str(api_id)), len(api_hash)))
    except SystemExit as e:
        print("없다\n%s" % e)
        return 1
    print("telethon ", end="")
    try:
        import telethon  # noqa: F401
        print("있다")
    except ImportError:
        print("없다.  pip install telethon")
        return 1
    print("세션     %s" % ("있다  " + str(SESSION) if SESSION.with_suffix(".session").exists()
                          else "없다. 아래에서 전화번호와 코드를 넣는다"))
    c = client()
    with c:
        me = c.get_me()
        if me is None:
            print("로그인 실패")
            return 1
        print("로그인   됐다")
        n = 0
        for d in c.iter_dialogs(limit=200):
            if getattr(d, "is_channel", False):
                n += 1
        print("들어가 있는 채널  %d개" % n)
    print("\n**세션 파일은 VM 안에만 둔다.** 어느 채널에 들어가 있는지가 거기 남는다.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="텔레그램 실계정으로 채널을 읽는다")
    ap.add_argument("channel", nargs="?", help="채널 이름. t.me/ 뒤의 것")
    ap.add_argument("--db", help="수집 표 경로")
    ap.add_argument("--limit", type=int, default=50, help="몇 개까지. 상한 %d" % MAX)
    ap.add_argument("--check", action="store_true", help="준비가 됐는지만 본다")
    a = ap.parse_args()
    if a.check:
        return check()
    if not a.channel:
        ap.error("채널 이름이 필요하다. 준비만 보려면 --check")
    return run(a.channel.strip().lstrip("@"), Path(a.db) if a.db else None, a.limit)


if __name__ == "__main__":
    raise SystemExit(main())
