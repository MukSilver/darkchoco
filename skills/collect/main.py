#!/usr/bin/env python3
"""수집 한 바퀴. 채널을 읽어 표에 넣고, 알림을 보내고, 검증 큐로 넘긴다.

    python -m collect.main --db data/darkchoco.db
    python -m collect.main --db data/darkchoco.db --notify --go
    python -m collect.main --db data/darkchoco.db --queue <공유폴더>
    python -m collect.main --db data/darkchoco.db --dry

## 한 바퀴가 하는 일

    1  채널마다 t.me/s/<채널> 을 읽는다        간격 2.5~5초. 병렬 없음
    2  글을 수집 표에 넣는다                  거르지 않는다. 종류만 표시한다
    3  (--notify) 유출 관련만 디스코드로       나머지는 표에 남는다
    4  (--queue) 유출 관련만 케이스 큐로       나머지는 표에 남는다

**거른다는 말은 버린다는 뜻이 아니다.** 표에는 다 들어 있다.
보내는 것과 케이스로 올리는 것만 추린다.

## 채널 목록

    ~/.config/darkchoco/telegram_channels

한 줄에 하나씩 적는다. `#` 로 시작하는 줄은 건너뛴다.
**프젝 폴더와 레포 밖에 둔다.** 무엇을 보고 있는지가 드러나는 목록이다.

## 미리보기가 꺼진 채널

`t.me/s/` 로 안 보이는 채널이 있다. 2026-08-27 실측으로 `breachdetect` 가 그렇다.
그런 채널은 여기서 **왜 못 봤는지 적고 넘어간다.** 실계정 경로(`telegram_api.py`)가 맡는다.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 윈도우 콘솔(cp949)에서 한글·기호로 죽는 것을 막습니다.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages"))
from dc_console import use_utf8  # noqa: E402

use_utf8()
from collect.fetch import Fetcher  # noqa: E402
from collect.sources.telegram_web import parse, to_item  # noqa: E402
from collect.store import Store  # noqa: E402

VER = "collect.main v1"

LIST_PLACES = [
    Path(os.environ["DARKCHOCO_CHANNELS"]) if os.environ.get("DARKCHOCO_CHANNELS") else None,
    Path.home() / ".config" / "darkchoco" / "telegram_channels",
]

# 검증 큐를 채우는 도구. 스킬 쪽에 있다
FEED = (Path(__file__).resolve().parent.parent
        / "skills" / "darkweb-verify-ko" / "tools" / "feed_parse.py")


def channels(given: str) -> list[str]:
    if given:
        return [c.strip().lstrip("@") for c in given.split(",") if c.strip()]
    for p in LIST_PLACES:
        if p and p.exists():
            out = []
            for ln in p.read_text(encoding="utf-8").splitlines():
                ln = ln.strip()
                if ln and not ln.startswith("#"):
                    out.append(ln.lstrip("@").replace("https://t.me/", ""))
            return out
    raise SystemExit(
        "볼 채널이 없다. --channels 로 주거나 아래에 한 줄씩 적을 것\n"
        "  ~/.config/darkchoco/telegram_channels\n"
        "**프젝 폴더와 레포 밖에 둔다.** 무엇을 보고 있는지가 드러난다.")


def one(f: Fetcher, s: Store, chan: str, today: str, dry: bool) -> dict:
    """채널 하나. 못 본 것도 왜인지 적어 돌려준다."""
    r = {"채널": chan, "글": 0, "새 것": 0, "종류": {}, "막힌 것": ""}
    try:
        code, body, _ = f.get("https://t.me/s/" + chan, accept="text/html")
    except Exception as e:
        r["막힌 것"] = "요청 실패: %s" % e
        return r
    if code != 200:
        r["막힌 것"] = "HTTP %s" % code
        return r

    posts, why = parse(body.decode("utf-8", errors="replace"), chan)
    if not posts:
        r["막힌 것"] = why
        return r

    r["글"] = len(posts)
    for d in posts:
        r["종류"][d["kind"]] = r["종류"].get(d["kind"], 0) + 1
        if not dry and s.put(to_item(d, chan, today), today):
            r["새 것"] += 1
    if not dry:
        s.log_run(today, "telegram/" + chan, len(posts), r["새 것"], VER)
    return r


def ransom(db: str, feeds: str) -> None:
    """랜섬웨어 유출 사이트 집계를 읽는다. 유출 사이트에 직접 붙지 않는다."""
    for feed in [x.strip() for x in feeds.split(",") if x.strip()]:
        print("\n  ── ransomware.live / %s ──" % feed)
        sys.stdout.flush()
        subprocess.run([sys.executable, "-m", "collect.sources.ransomlive",
                        feed, "--db", db],
                       cwd=str(Path(__file__).resolve().parent.parent))


def main() -> int:
    ap = argparse.ArgumentParser(description="수집 한 바퀴")
    ap.add_argument("--db", required=True, help="수집 표 경로")
    ap.add_argument("--channels", default="", help="쉼표로 나눈 채널. 안 주면 목록 파일")
    ap.add_argument("--ransom", default="kr",
                    help="랜섬 집계. kr · recent · 쉼표로 둘 다. 끄려면 빈칸")
    ap.add_argument("--no-telegram", action="store_true", help="텔레그램을 건너뛴다")
    ap.add_argument("--dry", action="store_true", help="받기만 하고 표에 안 넣는다")
    ap.add_argument("--notify", action="store_true", help="디스코드로 보낸다")
    ap.add_argument("--go", action="store_true", help="알림을 실제로 보낸다")
    ap.add_argument("--queue", help="검증 큐 폴더. 주면 케이스를 만든다")
    a = ap.parse_args()

    today = date.today().isoformat()
    print("한 바퀴 · %s" % today)

    if not a.no_telegram:
        chans = channels(a.channels)
        f = Fetcher()
        s = Store(Path(a.db))
        print("\n  ── 텔레그램 채널 %d개 ──" % len(chans))
        stuck = []
        for c in chans:
            r = one(f, s, c, today, a.dry)
            if r["막힌 것"]:
                stuck.append(r)
                print("  %-18s 못 봄 — %s" % (c, r["막힌 것"]))
            else:
                kinds = " · ".join("%s %d" % (k, v)
                                   for k, v in sorted(r["종류"].items(), key=lambda x: -x[1]))
                print("  %-18s 글 %2d · 새 것 %2d   %s" % (c, r["글"], r["새 것"], kinds))
        s.close()
        print()
        print(f.report())
        if stuck:
            print("\n  못 본 채널 %d개. **비어서가 아니다.**" % len(stuck))
            print("  미리보기가 꺼진 채널은 실계정 경로가 맡는다")

    if a.ransom and not a.dry:
        ransom(a.db, a.ransom)

    if a.notify:
        print("\n── 알림 ──")
        cmd = [sys.executable, "-m", "collect.notify", "--db", a.db]
        if a.go:
            cmd.append("--go")
        sys.stdout.flush()      # 안 하면 자식 출력이 먼저 나온다
        subprocess.run(cmd, cwd=str(Path(__file__).resolve().parent.parent))

    if a.queue:
        print("\n── 검증 큐 ──")
        if not FEED.exists():
            print("  feed_parse.py 를 못 찾았다: %s" % FEED)
        else:
            sys.stdout.flush()
            subprocess.run([sys.executable, str(FEED), a.db, "--out", a.queue])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
