#!/usr/bin/env python3
"""수집한 것을 디스코드로 보낸다.

    python -m collect.notify --db data/darkchoco.db --dry
    python -m collect.notify --db data/darkchoco.db --go
    python -m collect.notify --db data/darkchoco.db --go --all

## 왜 여기에만 쓰기가 있나

`collect/fetch.py` 에는 POST 가 아예 없다. 조사 대상 사이트에 흔적을 안 남기려는 것이다.
디스코드 웹훅은 **우리 채널**이라 그 규칙이 걸리는 자리가 아니다.
그래서 쓰기를 여기 한 곳에만 두고, 다른 어디서도 안 부른다.

## 한 건에 한 메시지로 보낸다

팀원 도구는 알림 한 건에 피해자를 최대 열 건 접어 보낸다.
받는 쪽(`alert_watch.py`)은 메시지 하나를 한 건으로 세므로 열 건이 한 건이 된다.
같은 실수를 안 하려고 한 건에 한 메시지다. 대신 한 번에 보내는 수에 상한을 둔다.

## 자격 정보

웹훅 주소는 `~/.config/darkchoco/discord_webhook` 에 있다. **프젝 폴더 밖이다.**
코드, 로그, 출력, 커밋 어디에도 값을 넣지 않는다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from collect.store import Store  # noqa: E402

VER = "notify v1"
LIMIT = 1900            # 디스코드 한 메시지 상한은 2000자다. 여유를 둔다
GAP = 1.5               # 웹훅은 분당 서른쯤이 상한이다
MAX_PER_RUN = 25        # 한 번에 이보다 많으면 나머지는 다음으로 미룬다
TIMEOUT = 15

# 우리 대상인 것만 보낸다. **표에는 다 들어가 있다.** 보내는 것만 추린다
OURS = ("랜섬웨어 유출", "DB 판매", "DB 무료 공개", "접근 권한 판매", "확인 못 함")

PLACES = [
    Path(os.environ.get("DARKCHOCO_WEBHOOK", "")) if os.environ.get("DARKCHOCO_WEBHOOK") else None,
    Path("/run/secrets/discord_webhook"),
    Path.home() / ".config" / "darkchoco" / "discord_webhook",
]


def hook() -> str:
    for p in PLACES:
        if p and p.exists():
            v = p.read_text(encoding="utf-8").strip()
            if v.startswith("https://"):
                return v
            raise SystemExit("%s 의 값이 https:// 로 시작하지 않는다" % p)
    raise SystemExit(
        "웹훅 주소를 못 찾았다. 아래에 한 줄로 넣을 것\n"
        "  ~/.config/darkchoco/discord_webhook\n"
        "**프젝 폴더 안에 두지 마라.**")


def cut(s: str, n: int) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[:n - 1].rstrip() + "…"


def line(row) -> str:
    """한 건을 한 메시지로. `alert_watch.py` 가 읽을 수 있는 칸 꼴로 적는다."""
    raw = {}
    try:
        raw = json.loads(row["raw"] or "{}")
    except ValueError:
        pass
    L = ["**%s**" % cut(row["target_org"] or row["title"] or "(대상 못 읽음)", 90),
         "Company: %s" % (row["target_org"] or "못 봄"),
         "Actor: %s" % (row["actor"] or "못 봄"),
         "Type: %s" % (row["kind"] or "확인 못 함"),
         "Posted: %s" % (row["posted_at"] or "못 봄"),
         "Seen: %s" % row["first_seen"],
         "Venue: %s" % row["venue"]]
    if row["post_url"]:
        L.append("Original: <%s>" % row["post_url"])   # 미리보기를 막는다
    if row["country"]:
        L.append("Country: %s" % row["country"])
    if raw.get("글 종류"):
        L.append("Kind: %s" % raw["글 종류"])
    body = cut(re.sub(r"\n{3,}", "\n\n", row["body"] or ""), 700)
    if body:
        L += ["", "```", body, "```"]
    L += ["", "_이 줄은 단서다. 확인한 것이 아니다. 원 게시물을 보기 전에 검증을 시작하지 않는다._"]
    return cut("\n".join(L), LIMIT)


def send(url: str, text: str) -> tuple[bool, str]:
    body = json.dumps({"content": text, "allowed_mentions": {"parse": []}}).encode()
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json",
                 "User-Agent": "darkchoco-research/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return 200 <= r.status < 300, str(r.status)
    except urllib.error.HTTPError as e:
        return False, "HTTP %s" % e.code
    except OSError as e:
        return False, str(e)


def pick(s: Store, everything: bool) -> tuple[list, int]:
    rows = s.rows(only_new=True)
    if everything:
        return rows, 0
    keep = [r for r in rows if (r["kind"] or "") in OURS]
    return keep, len(rows) - len(keep)


def main() -> int:
    ap = argparse.ArgumentParser(description="수집한 새 건을 디스코드로 보낸다")
    ap.add_argument("--db", required=True)
    ap.add_argument("--go", action="store_true", help="실제로 보낸다. 기본은 미리보기")
    ap.add_argument("--all", action="store_true",
                    help="우리 대상이 아닌 것도 보낸다. 기본은 대상만")
    ap.add_argument("--max", type=int, default=MAX_PER_RUN)
    a = ap.parse_args()

    s = Store(Path(a.db))
    rows, held = pick(s, a.all)
    print("새 건 %d개%s" % (len(rows), (" · 대상이 아니라 안 보내는 것 %d개" % held) if held else ""))
    if held:
        print("  **버린 것이 아니다.** 표에는 다 들어 있고 보내는 것만 추렸다")
    if not rows:
        s.close()
        return 0

    over = max(0, len(rows) - a.max)
    rows = rows[:a.max]
    if over:
        print("  한 번에 %d개까지만 보낸다. %d개는 다음으로 미룬다" % (a.max, over))

    if not a.go:
        print("\n미리보기. --go 를 붙이면 보낸다\n")
        print("─" * 60)
        print(line(rows[0]))
        print("─" * 60)
        s.close()
        return 0

    url = hook()
    ok = bad = 0
    for i, r in enumerate(rows):
        if i:
            time.sleep(GAP)
        good, why = send(url, line(r))
        if good:
            s.ack(r["uid"])
            ok += 1
        else:
            bad += 1
            print("  못 보냄 %s — %s" % (r["uid"], why))
            if bad >= 3:
                print("  세 번 실패해서 멈춘다")
                break
    s.log_run(date.today().isoformat(), "notify", len(rows), ok, VER)
    s.close()
    print("보냄 %d · 실패 %d" % (ok, bad))
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
