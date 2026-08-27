#!/usr/bin/env python3
"""텔레그램 공개 미리보기(`t.me/s/<채널>`)를 읽어 수집 표로 바꾼다.

    python -m collect.sources.telegram_web osint_cti
    python -m collect.sources.telegram_web osint_cti --db data/darkchoco.db
    python -m collect.sources.telegram_web osint_cti --dry

## 왜 이 길인가

    가. 공개 미리보기   계정이 없다. 로그인이 없다. 흔적이 안 남는다   ← 이 파일
    나. 실계정 세션     비공개 채널까지 본다. 그 계정이 들어간 것이 남는다

**가부터 쓴다.** 가로 안 보이는 채널만 나로 간다.
2026-08-27 실측: `osint_cti` 는 가로 글 20개가 보이고,
`breachdetect` 는 미리보기가 꺼져 있어 설명만 나온다.

## 거르지 않는다. 표시만 붙인다

이 채널은 네 종류를 섞어 보낸다. 실측 20건 기준으로 이랬다.

    CVE 알림          10   우리 대상이 아니다
    랜섬 피해자         5   우리 대상이다
    악성코드 시그니처     4   우리 대상이 아니다
    유출 알림           1   우리 대상이다

**대상이 아닌 것도 버리지 않고 넣는다.** `kind` 에 무엇으로 봤는지 적을 뿐이다.
2026-08-24 에 러시아 IT 뉴스의 휴대폰 렌더 기사가 `Data leak 95%` 로 왔다.
자동 분류를 믿고 걸렀으면 반대로 진짜를 버리는 일도 생긴다.

## 이 채널은 원 출처가 아니다

집계 채널이다. 원 출처는 글 안의 `Intel Source` 나 링크에 있다.
`post_url` 은 텔레그램 글 주소이고, 그것을 독립 출처로 세지 않는다.
"""
from __future__ import annotations

import argparse
import html as H
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from collect.fetch import Fetcher  # noqa: E402
from collect.store import Item, Store  # noqa: E402

VER = "telegram_web v1"

POST = re.compile(
    r'<div class="tgme_widget_message[ "].*?(?=<div class="tgme_widget_message[ "]|\Z)',
    re.S)
TEXT = re.compile(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', re.S)
ATTR = {
    "post": re.compile(r'data-post="([^"]+)"'),
    "when": re.compile(r'datetime="([^"]+)"'),
    "url": re.compile(r'class="tgme_widget_message_date"\s+href="([^"]+)"'),
    "views": re.compile(r'tgme_widget_message_views">([^<]+)<'),
    "chan": re.compile(r'tgme_widget_message_owner_name[^>]*>.*?<span[^>]*>([^<]{1,60})<', re.S),
}
LINK = re.compile(r'<a href="(https?://[^"]+)"')
LABEL = re.compile(r"^[•\-\*]?\s*([A-Za-z][A-Za-z /_]{2,30})\s*:\s*(.*)$")

# 글 종류를 무엇으로 가르나. **거르는 데 쓰지 않고 표시하는 데만 쓴다.**
# 칸 이름으로 가른다. 머리 줄의 이모지는 채널이 바꾸면 깨진다
KINDS = [
    ("유출 알림", {"target/title", "threat actor"}, True),
    ("랜섬 피해자", {"victim", "group"}, True),
    ("CVE 알림", {"cve id", "cvss score"}, False),
    ("악성코드 시그니처", {"signature", "file"}, False),
]

# 글 칸을 우리 칸으로. 없는 것은 안 넣는다
MAP = {
    "target/title": "target_org",
    "victim": "target_org",
    "threat actor": "actor",
    "group": "actor",
    "country": "country",
    "intel source": "via_note",
    "detection date": "seen_note",
    "published": "posted_note",
    "sector": "sector",
}


def plain(raw: str) -> str:
    t = re.sub(r"<br\s*/?>", "\n", raw)
    t = re.sub(r"<[^>]+>", "", t)
    return H.unescape(t).strip()


# 값 앞에 붙은 이모지를 뗀다. 그대로 두면 대상 조직 이름 대조가 깨진다.
# `👤 OctopusBF` 와 `OctopusBF` 는 다른 글자다
LEAD = re.compile(r"^[\s -㌀\U0001F000-\U0001FAFF️‍]+")


def clean(v: str) -> str:
    return LEAD.sub("", (v or "").strip()).strip()


def origin(links: list[str], body: str) -> str:
    """글 안에 적힌 **원 출처**를 찾는다.

    이 채널은 집계 채널이라 텔레그램 글 주소는 원 출처가 아니다.
    글 본문에 원 게시글 주소가 적혀 있으면 그것이 원 출처다.
    2026-08-27 실측: `Source Intelligence Link:` 아래에 포럼 주소가 있었다."""
    cand = [u for u in links if "t.me/" not in u]
    if cand:
        return cand[0]
    m = re.search(r"https?://(?!t\.me/)\S{8,}", body)
    return m.group(0).rstrip(").,。") if m else ""


def one(rx: re.Pattern, s: str, d: str = "") -> str:
    m = rx.search(s)
    return m.group(1).strip() if m else d


def parse(html: str, chan: str) -> tuple[list[dict], str]:
    """글 목록과 왜 비었는지를 돌려준다. 조용히 0을 돌려주지 않는다."""
    posts = POST.findall(html)
    if not posts:
        if "Preview channel" in html or "tgme_page_context_link" in html:
            return [], ("미리보기가 꺼져 있다. 이 채널은 공개 미리보기로 못 본다. "
                        "실계정 경로(나)가 필요하다")
        if "tgme_page" in html:
            return [], "채널 쪽은 받았는데 글 묶음이 없다. 채널이 비었거나 꼴이 바뀌었다"
        return [], "채널 쪽이 아닌 것을 받았다. 주소를 확인할 것"

    out = []
    for p in posts:
        m = TEXT.search(p)
        body = plain(m.group(1)) if m else ""
        fields, order = {}, []
        for ln in body.split("\n"):
            mm = LABEL.match(ln.strip())
            if mm:
                k = mm.group(1).strip().lower()
                fields[k] = mm.group(2).strip()
                order.append(k)
        kind, ours = "기타", None
        for name, need, mine in KINDS:
            if need <= set(fields):
                kind, ours = name, mine
                break
        out.append({
            "post": one(ATTR["post"], p),
            "when": one(ATTR["when"], p),
            "url": one(ATTR["url"], p),
            "views": one(ATTR["views"], p),
            "chan": one(ATTR["chan"], p, chan),
            "body": body,
            "fields": fields,
            "labels": order,
            "links": LINK.findall(m.group(1)) if m else [],
            "kind": kind,
            "ours": ours,
        })
    return out, ""


def to_item(d: dict, chan: str, today: str) -> Item:
    f = d["fields"]
    org = clean(f.get("target/title") or f.get("victim", ""))
    src = origin(d["links"], d["body"])
    venue = re.sub(r"^https?://([^/]+).*", r"\1", src) if src else ("t.me/" + chan)
    return Item(
        source="telegram",
        # 채널의 글 번호. 이것 하나로 줄이 갈린다.
        # 없으면 원 출처도 조직도 빈 글끼리 한 줄로 뭉친다
        src_id=d["post"],
        # 원 출처를 알면 그쪽 도메인을 적는다. 포럼명만 적지 않는다
        venue=venue,
        venue_kind="forum" if src and "t.me/" not in src else "telegram",
        actor=clean(f.get("threat actor") or f.get("group", "")),
        target_org=org,
        target_domain=org if re.match(r"^[\w.-]+\.[a-z]{2,}$", org, re.I) else "",
        title=(d["body"].split("\n")[0] if d["body"] else "")[:120],
        body=d["body"],
        # 이 채널 글은 집계 채널이 쓴 글이다. 유출 게시글 본문이 아니다
        body_kind="집계 채널 글",
        body_via="t.me/s",
        posted_at=d["when"],
        # **원 출처는 글 안에 적힌 주소다.** 텔레그램 글 주소가 아니다.
        # 집계 채널을 독립 출처로 세면 같은 건이 여러 출처로 읽힌다
        post_url=src,
        via=["t.me/s/" + chan],
        claimed_size=clean(f.get("size") or f.get("records", "")),
        country=clean(f.get("country", "")),
        kind={"유출 알림": "확인 못 함", "랜섬 피해자": "랜섬웨어 유출"}.get(d["kind"], ""),
        clues={"링크": d["links"][:10]} if d["links"] else {},
        raw={"글 번호": d["post"], "조회수": d["views"], "채널 이름": d["chan"],
             "글 종류": d["kind"], "우리 대상": d["ours"],
             "집계 채널 글 주소": d["url"],
             "본문 칸": {k: clean(v) for k, v in f.items() if k in MAP},
             "못 옮긴 칸": [k for k in d["labels"] if k not in MAP]},
        got_by=VER,
    )


def run(chan: str, db: Path | None, dry: bool) -> int:
    f = Fetcher(dry=dry)
    url = "https://t.me/s/" + chan
    try:
        code, body, _ = f.get(url, accept="text/html")
    except Exception as e:
        print("%s  못 받았다: %s" % (chan, e))
        return 1
    if code != 200:
        print("%s  HTTP %s" % (chan, code))
        return 1

    posts, why = parse(body.decode("utf-8", errors="replace"), chan)
    print("채널  t.me/%s" % chan)
    if not posts:
        print("글 0개 — %s" % why)
        return 1

    kinds: dict = {}
    for d in posts:
        kinds[d["kind"]] = kinds.get(d["kind"], 0) + 1
    print("글 %d개" % len(posts))
    for k, v in sorted(kinds.items(), key=lambda x: -x[1]):
        mark = "우리 대상" if any(n == k and m for n, _, m in KINDS) else ""
        print("    %-18s %2d  %s" % (k, v, mark))

    miss = sorted({k for d in posts for k in d["labels"] if k not in MAP})
    if miss:
        print("\n못 옮긴 칸 (버리지 않고 raw 에 넣는다): %s" % ", ".join(miss))

    if dry or not db:
        print("\ndry run. 아무것도 안 넣었다" if dry else "\n--db 를 주면 넣는다")
        return 0

    s = Store(db)
    today = date.today().isoformat()
    fresh = sum(1 for d in posts if s.put(to_item(d, chan, today), today))
    s.log_run(today, "telegram/" + chan, len(posts), fresh, VER)
    s.close()
    print("\n%d개 중 처음 보는 것 %d개" % (len(posts), fresh))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="텔레그램 공개 미리보기를 수집 표로")
    ap.add_argument("channel", help="채널 이름. t.me/ 뒤의 것")
    ap.add_argument("--db", help="수집 표 경로")
    ap.add_argument("--dry", action="store_true", help="요청을 안 보내고 무엇을 할지만")
    a = ap.parse_args()
    return run(a.channel.strip().lstrip("@"), Path(a.db) if a.db else None, a.dry)


if __name__ == "__main__":
    raise SystemExit(main())
