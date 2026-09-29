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
`post_url` 은 그 원 출처(글 안의 링크)다. 텔레그램 글 주소는 `raw` 「집계 채널 글 주소」 에 남고,
그것을 독립 출처로 세지 않는다. 노션 원문 URL 에는 텔레그램 글 주소가 올라간다
(`hub/events/push.py` `_원문`, 2026-09-28).
"""
from __future__ import annotations

import argparse
import html as H
import random
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from collect.fetch import Fetcher  # noqa: E402
from collect.sources import tg_post  # noqa: E402
from collect.store import Store  # noqa: E402

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


def plain(raw: str) -> str:
    t = re.sub(r"<br\s*/?>", "\n", raw)
    t = re.sub(r"<[^>]+>", "", t)
    return H.unescape(t).strip()


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
        # 읽는 규칙은 공통 자리에 있다. 채널마다 글 꼴이 다르다
        fields, shape, note = tg_post.read_post(body)
        kind, ours = tg_post.classify(fields)
        out.append({
            "꼴": shape,
            "못 읽은 것": note,
            "post": one(ATTR["post"], p),
            "when": one(ATTR["when"], p),
            "url": one(ATTR["url"], p),
            "views": one(ATTR["views"], p),
            "chan": one(ATTR["chan"], p, chan),
            "body": body,
            "fields": fields,
            "labels": list(fields),
            "links": LINK.findall(m.group(1)) if m else [],
            "kind": kind,
            "ours": ours,
        })
    return out, ""


def to_item(d: dict, chan: str, today: str):
    """공통 자리(`tg_post`)로 넘긴다. 실계정 길과 같은 것을 내야 한다."""
    return tg_post.to_item(
        chan=chan, src_id=d["post"], text=d["body"], links=d["links"],
        when=d["when"], perma=d["url"], got_by=VER, body_via="t.me/s")


# ── 쪽 넘기기 (2026-09-29 최현서, 인계 H-2 · E-5) ────────────────
#
# 첫 쪽만 읽으면 글이 빠른 채널에서 놓친다. 9/26 에 재 보니 osint_cti 는 첫 쪽 20개가 1.6시간 안이라,
# 6시간마다 읽으면 70개쯤 가운데 50개쯤을 놓쳤다. 그래서 **첫 쪽이 꽉 찼고 가장 오래된 글이
# 「지금 − 12시간」 보다 새것이면** `before=<가장 오래된 글 번호>` 로 한 쪽 더 읽는다. 채널당 8쪽까지.
# 12시간인 까닭: 수집은 6시간마다지만 한 판이 빠지면 12시간이 빈다. 겹쳐 읽은 글은 UID 가 거른다.
# 한가한 채널은 첫 쪽에서 멈추므로 요청이 안 는다.
되짚을시간 = 12      # 시간
쪽상한 = 8          # 채널당. 첫 쪽을 센다
꽉참 = 15           # 한 쪽이 이만큼 이상이면 꽉 찬 것으로 본다(t.me 는 한 쪽에 20개 안팎)
넘김더쉬기 = (1.0, 3.0)   # 넘겨 읽는 쪽은 Fetcher 간격(t.me 2.5~5초)에 이만큼 더 쉰다


def _시각(v: str):
    try:
        d = datetime.fromisoformat((v or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _번호(d: dict) -> int:
    try:
        return int(d["post"].rsplit("/", 1)[-1])
    except (ValueError, KeyError, AttributeError):
        return 0


def 쪽들(f, chan: str, 지금: datetime | None = None, 되짚을: float = 되짚을시간,
        상한: int = 쪽상한, 쉬기=time.sleep) -> tuple[list[dict], str, int]:
    """채널 첫 쪽부터 거슬러 읽는다. (글 목록, 첫 쪽이 빈 까닭, 읽은 쪽 수).

    **첫 쪽은 예전과 같다.** 요청이 실패하면 예외를 그대로 올리고, HTTP 가 200 이 아니면
    `([], "HTTP <코드>", 1)` 을 돌려준다. 부르는 쪽이 예전처럼 「막힌 것」 으로 적는다.
    **넘긴 쪽은 실패해도 멈추기만 한다.** 받은 만큼 쓴다. 한 채널 때문에 한 판이 죽지 않게 한다."""
    지금 = 지금 or datetime.now(timezone.utc)
    기준 = 지금 - timedelta(hours=되짚을)
    url = "https://t.me/s/" + chan
    code, body, _ = f.get(url, accept="text/html")
    if code != 200:
        return [], "HTTP %s" % code, 1
    글, 왜 = parse(body.decode("utf-8", errors="replace"), chan)
    if not 글:
        return [], 왜, 1

    모은, 본번호, 쪽수 = list(글), {d["post"] for d in 글}, 1
    while 쪽수 < 상한:
        가장오래된 = min(글, key=_번호)
        시각 = _시각(가장오래된["when"])
        if len(글) < 꽉참 or 시각 is None or 시각 <= 기준 or _번호(가장오래된) <= 1:
            break
        쉬기(random.uniform(*넘김더쉬기))
        쪽수 += 1
        try:
            code, body, _ = f.get("%s?before=%d" % (url, _번호(가장오래된)), accept="text/html")
        except Exception:  # noqa: BLE001  넘긴 쪽은 받은 만큼 쓰고 멈춘다
            break
        if code != 200:
            break
        글, _ = parse(body.decode("utf-8", errors="replace"), chan)
        새것 = [d for d in 글 if d["post"] not in 본번호 and _번호(d) < _번호(가장오래된)]
        if not 새것:
            break
        모은 += 새것
        본번호 |= {d["post"] for d in 새것}
        글 = 새것
    return 모은, "", 쪽수


def d_ours(posts: list, kind: str) -> bool:
    return any(d["ours"] for d in posts if d["kind"] == kind)


def run(chan: str, db: Path | None, dry: bool) -> int:
    f = Fetcher(dry=dry)
    try:
        posts, why, 쪽수 = 쪽들(f, chan)
    except Exception as e:
        print("%s  못 받았다: %s" % (chan, e))
        return 1
    print("채널  t.me/%s%s" % (chan, "  (%d쪽)" % 쪽수 if 쪽수 > 1 else ""))
    if not posts:
        print("글 0개 — %s" % why)
        return 1

    kinds: dict = {}
    shapes: dict = {}
    for d in posts:
        kinds[d["kind"]] = kinds.get(d["kind"], 0) + 1
        shapes[d["꼴"]] = shapes.get(d["꼴"], 0) + 1
    print("글 %d개 · 꼴 %s"
          % (len(posts), " · ".join("%s %d" % kv for kv in sorted(shapes.items()))))
    for k, v in sorted(kinds.items(), key=lambda x: -x[1]):
        print("    %-18s %2d  %s" % (k, v, "우리 대상" if d_ours(posts, k) else ""))

    hard = [d for d in posts if d["못 읽은 것"]]
    if hard:
        print("\n못 읽은 글 %d개. 버리지 않고 raw 에 사유를 적었다" % len(hard))

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
