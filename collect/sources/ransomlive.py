#!/usr/bin/env python3
"""`ransomware.live` 공개 API 를 읽어 수집 표로 바꾼다.

    python -m collect.sources.ransomlive kr
    python -m collect.sources.ransomlive kr --db data/darkchoco.db
    python -m collect.sources.ransomlive recent --db data/darkchoco.db
    python -m collect.sources.ransomlive kr --dry

클리어넷 공개 API 다. **로그인이 없고 유출 사이트에 직접 붙지 않는다.**
유출 사이트 onion 주소는 값으로만 받아 적고, 그 주소를 두드리지 않는다.

## 두 엔드포인트의 칸 이름이 다르다

2026-08-27 실측이다. 짐작으로 쓰면 조용히 깨진다.

| 우리 칸 | `countryvictims/KR` | `recentvictims` |
|---|---|---|
| 대상 조직 | `post_title` | `victim` |
| 도메인 | `website` | `domain` |
| 행위자 | `group_name` | `group` |
| 원 출처 | `post_url` | **`claim_url`** |
| 게시 시각 | `published` | `discovered` |

**`recentvictims` 의 `url` 은 원 출처가 아니다.** `ransomware.live/id/...` 라는
그 사이트 자기 페이지다. 그것을 원 출처로 세면 요약 사이트를 독립 출처로 세게 된다.
원 출처는 `claim_url` 이고, `url` 은 재게시 자리로 간다.

## `description` 은 게시글 본문이 아니다

실측한 값이 이렇다.

    "Air Liquide has operated in South Korea for several decades and supplies…"

랜섬웨어 조직이 쓴 글이 아니라 **회사 소개**다. 2026-08-26 에 팀원 도구를 읽다
같은 칸을 게시글 본문으로 잘못 알았다. 여기서는 `body_kind` 에 회사 소개라고 적는다.

## 팀원 도구가 안 읽는 칸을 읽는다

`data_size` 와 `ransom` 이 API 에 있는데 Kr-Leak-alarm 의 어댑터가 안 읽는다.
그래서 `주장 규모` 가 늘 못 봄이었다. 여기서는 읽는다.
KR 115줄 기준으로 `data_size` 는 9줄에만 차 있다. 적지만 없는 것보다 낫다.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from collect.fetch import Fetcher  # noqa: E402
from collect.store import Item, Store  # noqa: E402

VER = "ransomlive v1"
BASE = "https://api.ransomware.live/v2"

# 엔드포인트마다 칸 이름이 다르다. 여기만 고치면 새 엔드포인트가 붙는다
FEEDS = {
    "kr": {
        "url": BASE + "/countryvictims/KR",
        "설명": "한국 관련 피해자",
        "org": "post_title", "domain": "website", "actor": "group_name",
        "origin": "post_url", "posted": "published", "seen": "discovered",
        "mirror": "", "sector": "activity",
    },
    "recent": {
        "url": BASE + "/recentvictims",
        "설명": "최근 피해자 (나라 안 가림)",
        "org": "victim", "domain": "domain", "actor": "group",
        # `url` 은 ransomware.live 자기 페이지다. 원 출처가 아니다
        "origin": "claim_url", "posted": "attackdate", "seen": "discovered",
        "mirror": "url", "sector": "activity",
    },
}


def g(row: dict, key: str) -> str:
    v = row.get(key)
    return "" if v is None else str(v).strip()


def to_item(row: dict, f: dict, feed: str) -> Item:
    org = g(row, f["org"])
    dom = g(row, f["domain"])
    origin = g(row, f["origin"])
    mirror = g(row, f["mirror"]) if f["mirror"] else ""
    desc = g(row, "description")
    # 유출 사이트 주소를 값으로 받아 적을 뿐 두드리지 않는다
    venue = origin.split("/")[2] if origin.startswith("http") else "ransomware.live"

    extra = {}
    for k in ("press", "infostealer", "screenshot", "claim_url", "url",
              "attackdate", "post_title", "victim"):
        v = row.get(k)
        if v not in (None, "", [], {}):
            extra[k] = v

    return Item(
        source="ransom",
        # 그 사이트의 고유 열쇠가 없다. 원 출처와 행위자와 대상으로 가른다
        src_id="%s|%s" % (g(row, f["actor"]), org),
        venue=venue,
        venue_kind="dls" if origin else "그밖",
        actor=g(row, f["actor"]),
        target_org=org,
        target_domain=dom,
        title=org,
        # **회사 소개다.** 랜섬웨어 조직이 쓴 글이 아니다
        body=desc,
        body_kind="회사 소개" if desc else "없음",
        body_via="api",
        posted_at=g(row, f["posted"]),
        post_url=origin,
        # 우리가 알게 된 곳이지 원 출처가 아니다
        via=["ransomware.live"],
        claimed_size=g(row, "data_size"),      # 팀원 어댑터가 안 읽는 칸
        price=g(row, "ransom"),                # 위와 같다
        kind="랜섬웨어 유출",
        country=g(row, "country"),
        raw=dict(extra, **{"산업 분야": g(row, f["sector"]),
                           "엔드포인트": feed,
                           "재게시 자리": mirror}),
        got_by=VER,
    )


def run(feed: str, db: Path | None, dry: bool, limit: int) -> int:
    f = FEEDS[feed]
    fe = Fetcher(dry=dry)
    try:
        code, body, _ = fe.get(f["url"])
    except Exception as e:
        print("못 받았다: %s" % e)
        return 1
    if dry:
        print("dry run\n%s" % fe.report())
        return 0
    if code != 200 or not body:
        print("HTTP %s" % code)
        return 1
    try:
        rows = json.loads(body)
    except ValueError as e:
        print("JSON 이 아니다: %s" % e)
        return 1
    if not isinstance(rows, list):
        rows = rows.get("victims") or rows.get("data") or []
    if not rows:
        print("줄 0개. 비어서인지 꼴이 바뀌어서인지 확인할 것")
        return 1

    rows = rows[:limit] if limit else rows
    print("%s  %s" % (feed, f["설명"]))
    print("줄 %d개" % len(rows))

    # 어느 칸이 실제로 차 있는지 늘 낸다. 조용히 빈 채로 넘어가지 않게
    for our, key in (("대상 조직", f["org"]), ("도메인", f["domain"]),
                     ("행위자", f["actor"]), ("원 출처", f["origin"]),
                     ("주장 규모", "data_size"), ("몸값", "ransom")):
        n = sum(1 for r in rows if g(r, key))
        print("    %-10s %3d/%d  (%s)" % (our, n, len(rows), key))

    if not db:
        print("\n--db 를 주면 넣는다")
        return 0
    s = Store(db)
    today = date.today().isoformat()
    items = [to_item(r, f, feed) for r in rows]
    fresh = sum(1 for it in items if s.put(it, today))
    s.log_run(today, "ransomlive/" + feed, len(items), fresh, VER)
    s.close()
    print("\n%d개 중 처음 보는 것 %d개" % (len(items), fresh))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="ransomware.live 공개 API 를 수집 표로")
    ap.add_argument("feed", choices=sorted(FEEDS), help=" · ".join(
        "%s=%s" % (k, v["설명"]) for k, v in FEEDS.items()))
    ap.add_argument("--db")
    ap.add_argument("--limit", type=int, default=0, help="0 이면 전부")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    return run(a.feed, Path(a.db) if a.db else None, a.dry, a.limit)


if __name__ == "__main__":
    raise SystemExit(main())
