#!/usr/bin/env python3
"""이미 받아 둔 원문을 다시 읽는다. **밖에 요청을 걸지 않는다.**

    python -m collect.reparse --db data/darkchoco.db
    python -m collect.reparse --db data/darkchoco.db --chan breachdetect
    python -m collect.reparse --db data/darkchoco.db --chan breachdetect --apply

## 왜 필요한가

파서를 고치면 이미 들어와 있는 줄은 옛 해석 그대로 남는다.
2026-08-27 에 breachdetect 50건이 전부 `기타` 로 들어갔다. 글이 JSON 꼴인데
라벨 정규식으로 읽으려 해서 칸을 하나도 못 잡았다. 파서를 고쳐도 그 50줄은
안 바뀐다. 다시 읽어야 바뀐다.

**다시 받지 않는다.** 원문이 `body` 에 그대로 있어서 요청을 다시 걸 이유가 없다.
같은 채널에 두 번 요청하면 흔적만 늘어난다.

## 무엇이 바뀌고 무엇이 안 바뀌나

| | |
|---|---|
| 바뀌는 것 | 글 종류, 대상, 행위자, 원 출처, venue, 제목처럼 **읽어서 얻은 것** |
| 안 바뀌는 것 | 처음 본 날, 마지막으로 본 날, 사람이 봤다는 표시 |

**관측과 해석을 가른다.** 언제 봤는지는 사실이고, 무엇으로 읽었는지는 해석이다.
해석을 고치는 일이 사실을 덮으면 안 된다.

## 기본은 넣지 않는 것이다

`--apply` 를 줘야 실제로 바꾼다. 그 전에는 무엇이 달라지는지만 보인다.
파서를 고칠 때마다 부르는 도구라서, 잘못 고친 파서로 표를 덮는 일을 막는다.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from collect.sources import tg_post  # noqa: E402
from collect.store import Store  # noqa: E402

VER = "reparse v1"

# 다시 읽을 수 있는 소스. 원문에서 다시 뽑는 법을 아는 것만 넣는다
READERS = {"telegram": tg_post.to_item}

# 다시 읽으면 달라질 수 있는 칸. 보고에 이것만 견준다
WATCH = ("venue", "venue_kind", "actor", "target_org", "target_domain",
         "title", "post_url", "kind", "country", "claimed_size")


def js(v, d):
    """`rows()` 는 원시 행이라 JSON 칸이 글자 그대로 온다."""
    try:
        return json.loads(v) if v else d
    except (ValueError, TypeError):
        return d


def chan_of(row) -> str:
    """어느 채널 글인지. `src_id` 가 `채널/번호` 꼴이다."""
    sid = row["src_id"] or ""
    return sid.split("/")[0] if "/" in sid else ""


def again(row):
    """줄 하나를 다시 읽는다. 못 읽으면 None."""
    fn = READERS.get(row["source"])
    if fn is None or not (row["body"] or "").strip():
        return None
    raw = js(row["raw"], {})
    return fn(chan=chan_of(row), src_id=row["src_id"], text=row["body"],
              links=js(row["clues"], {}).get("링크", []),
              when=row["posted_at"] or "",
              perma=raw.get("집계 채널 글 주소", ""),
              got_by=row["got_by"] or "", body_via=row["body_via"] or "")


def run(db: Path, chan: str, source: str, apply: bool) -> int:
    s = Store(db)
    rows = [r for r in s.rows(source=source) if not chan or chan_of(r) == chan]
    if not rows:
        print("다시 읽을 줄이 없다. --chan 이나 --source 를 확인할 것")
        s.close()
        return 1

    skipped = Counter()
    plans = []
    for r in rows:
        it = again(r)
        if it is None:
            # 본문을 지운 줄은 다시 읽을 재료가 없다. 그것이 정상이다
            skipped["본문이 지워짐" if r["forgotten"] else "다시 읽는 법을 모름"] += 1
            continue
        diff = {k: (r[k] or "", getattr(it, k) or "")
                for k in WATCH if (r[k] or "") != (getattr(it, k) or "")}
        old_raw = js(r["raw"], {})
        old_kind, new_kind = old_raw.get("글 종류", ""), it.raw.get("글 종류", "")
        # **`raw` 도 견준다.** 종류가 그대로여도 안에 든 것이 달라질 수 있다.
        # 글 꼴처럼 새로 적기 시작한 칸은 여기서만 잡힌다
        if diff or old_raw != it.raw:
            plans.append((r["uid"], it, diff, old_kind, new_kind))

    print("%d줄 중 %d줄이 달라진다" % (len(rows), len(plans)))
    for why, n in skipped.most_common():
        print("  건너뜀 · %s %d" % (why, n))

    kinds = Counter("%s → %s" % (o or "(없음)", n)
                    for _, _, _, o, n in plans if o != n)
    if kinds:
        print("\n── 글 종류 ──")
        for k, v in kinds.most_common():
            print("  %-34s %d" % (k, v))

    cols = Counter()
    for _, _, diff, _, _ in plans:
        for k, (o, n) in diff.items():
            cols["%s · %s" % (k, "채워짐" if not o else ("비워짐" if not n else "바뀜"))] += 1
    if cols:
        print("\n── 칸 ──")
        for k, v in cols.most_common():
            print("  %-34s %d" % (k, v))

    if not apply:
        # **값은 안 낸다.** 무엇이 몇 건 달라지는지만 낸다
        print("\n안 넣었다. 실제로 바꾸려면 --apply")
        s.close()
        return 0

    done = merged = 0
    for uid, it, _, _, _ in plans:
        new = s.replace(uid, it)
        done += 1
        if new != uid and not s.seen(uid):
            merged += 1
    s.log_run(rows[0]["last_seen"], "reparse/" + (chan or source or "전부"),
              len(rows), done, VER)
    s.close()
    print("\n%d줄을 갈아 끼웠다 (열쇠가 바뀐 것 %d)" % (done, merged))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="이미 받아 둔 원문을 다시 읽는다. 밖에 요청을 걸지 않는다")
    ap.add_argument("--db", required=True, help="수집 표 경로")
    ap.add_argument("--chan", default="", help="채널 하나만. 안 주면 전부")
    ap.add_argument("--source", default="", help="소스 하나만 (telegram 등)")
    ap.add_argument("--apply", action="store_true",
                    help="실제로 바꾼다. 안 주면 무엇이 달라지는지만 본다")
    a = ap.parse_args()
    return run(Path(a.db), a.chan.strip().lstrip("@"), a.source.strip(), a.apply)


if __name__ == "__main__":
    raise SystemExit(main())
