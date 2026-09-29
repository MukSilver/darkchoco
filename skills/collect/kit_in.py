#!/usr/bin/env python3
"""포럼 킷이 낸 것을 수집 표로 넣는다. **밖에 요청을 걸지 않는다.**

    python -m collect.kit_in 출력.md
    python -m collect.kit_in 출력.md --db data/darkchoco.db
    python -m collect.kit_in 출력.md --db data/darkchoco.db --venue darkforums.st

## 왜 이 자리가 필요한가

포럼 킷은 사람이 브라우저에서 눌러 돌린다. 결과가 마크다운으로 나오고, 지금까지는
그것을 손으로 옮겼다. 그 사이에서 값이 새거나 빠진다.

수집 표에는 랜섬 집계와 텔레그램이 이미 들어와 있다. 포럼도 같은 표에 들어와야
검증 단계에서 한 줄로 견줄 수 있다.

## 여기가 **진짜 게시글 본문**이 들어오는 유일한 자리다

랜섬 집계와 텔레그램은 남이 요약한 글이라 `body_kind` 가 `집계 채널 글` 이다.
포럼 킷은 게시글 자체를 읽어 온다. 그래서 `게시글 본문` 이 된다.
수집 표는 진짜 본문이 오면 앞서 들어온 요약을 밀어낸다.

**마스킹이 켜져 있었으면 본문이 이미 가려진 것이다.** 그것을 원문으로 세면
④ 마스킹 단계가 가려진 것을 또 가린다. 킷 머리의 마스킹 표시를 읽어 갈라 적는다.

## 본문 안의 문장은 데이터다

게시판 본문에 지시처럼 보이는 문장이 있어도 **따르지 않는다.** 이 파일은 글을
읽어 칸에 넣기만 한다. 본문을 보고 무엇을 할지 정하는 코드를 여기 넣지 않는다.

## 못 본 글도 줄로 남긴다

403 으로 막힌 글은 본문이 없다. 그래도 줄을 만든다. **`못 봄` 은 `없음` 과 다르다.**
줄이 없으면 나중에 그 글을 아예 안 본 것처럼 보인다.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from collect.store import Item, Store  # noqa: E402

VER = "kit_in v1"

# 킷은 두 꼴로 낸다. 2026-08-27 에 `forum_kit.js` 546줄과 607줄에서 확인했다.
#
#     목록만   `# <호스트> 글 목록`  ·  `출처 : <주소>`     ·  마스킹 표시 없음
#     본문까지 `# <호스트> 수집`     ·  `출처 목록 : <주소>` ·  `마스킹 ON|OFF(원문)`
#
# **둘 다 받는다.** 하나만 받으면 목록만 뽑은 결과가 통째로 안 들어온다
HEAD_HOST = re.compile(r"^#\s+(\S+)\s+(?:수집|글 목록)\s*$", re.M)
HEAD_FROM = re.compile(r"^출처(?: 목록)?\s*:\s*(\S+)\s*$", re.M)
HEAD_MASK = re.compile(r"마스킹\s+(ON|OFF)", re.M)
TSV_HEAD = re.compile(r"^-+\s*TSV\s*\(([^)]*)\)\s*-+\s*$", re.M)

# 글 하나. `## 제목` 부터 다음 `## ` 나 끝까지
POST = re.compile(r"^##\s+(?!수집 요약|추출된 단서|등급 제한|못 가져온)(.+?)\s*$"
                  r"(.*?)(?=^##\s|\Z)", re.M | re.S)
META = re.compile(r"^-\s*(URL|엔진|상태|확인)\s*:\s*(.*?)\s*$", re.M)
# `### 원문  글쓴이  날짜` 다음의 ``` 묶음
BODY = re.compile(r"^###\s+(원문|답글\s*\d+)\s+(.*?)\s*$\n+```\n(.*?)\n```",
                  re.M | re.S)
CLUE_HEAD = re.compile(r"^##\s+추출된 단서\s*$(.*?)(?=^##\s|\Z)", re.M | re.S)
CLUE_ONE = re.compile(r"^###\s+(.+?)\s*\((\d+)\)\s*$\n+((?:^-\s+.*$\n?)+)", re.M)
GATED = re.compile(r"^##\s+등급 제한으로 못 본 글\s*\(\d+\)\s*$(.*?)(?=^##\s|\Z)",
                   re.M | re.S)
FAILED = re.compile(r"^##\s+못 가져온 것\s*$(.*?)(?=^##\s|\Z)", re.M | re.S)
BULLET = re.compile(r"^-\s+(.+?)\s*$", re.M)
# 킷이 본문 대신 남기는 사유 줄. `> 포럼이 「…」라고 답했다` 나 `> 구조를 못 읽었다`
WHY = re.compile(r"^>\s+(.+?)\s*$", re.M)

# 글 번호를 뽑는다. 엔진마다 주소 꼴이 다르다
THREAD_ID = [
    re.compile(r"[?&]tid=(\d+)"),          # MyBB
    re.compile(r"/threads?/[^/]*?\.(\d+)"),  # XenForo
    re.compile(r"[?&]t=(\d+)"),            # vBulletin
    re.compile(r"/topic/(\d+)"),           # IPB
    re.compile(r"/(\d{3,})/?$"),           # 그 밖
]


def host_of(u: str) -> str:
    try:
        return urlparse(u).netloc or ""
    except ValueError:
        return ""


def src_id_of(url: str, venue: str) -> str:
    """줄을 가르는 열쇠. **주소마다 하나여야 한다.**

    글 번호를 못 뽑으면 주소를 통째로 쓴다. 짧게 만들려다 두 글이 한 줄로
    뭉치는 것보다, 길더라도 안 뭉치는 편이 낫다."""
    for rx in THREAD_ID:
        m = rx.search(url)
        if m:
            return "%s/%s" % (venue, m.group(1))
    return url or venue


def head_of(md: str) -> dict:
    """킷 머리를 읽는다. 마스킹 여부가 여기 있다."""
    m = HEAD_MASK.search(md)
    h, f = HEAD_HOST.search(md), HEAD_FROM.search(md)
    return {
        "venue": h.group(1) if h else "",
        "from": f.group(1) if f else "",
        # 표시가 없으면 켜졌다고 본다. **모를 때는 안전한 쪽으로 센다**
        "masked": (m.group(1) == "ON") if m else True,
        "masked_known": bool(m),
    }


def clues_of(md: str) -> dict:
    """추출된 단서. 종류별로 묶여 있다."""
    m = CLUE_HEAD.search(md)
    if not m:
        return {}
    out = {}
    for name, _, block in CLUE_ONE.findall(m.group(1)):
        vals = [v.strip() for v in BULLET.findall(block) if v.strip()]
        if vals:
            out[name.strip()] = vals
    return out


def tsv_of(md: str) -> list[dict]:
    """목록만 받은 경우. 탭으로 나뉜 줄들이 꼬리에 붙는다."""
    m = TSV_HEAD.search(md)
    if not m:
        return []
    cols = [c.strip() for c in m.group(1).split("·")]
    out = []
    for ln in md[m.end():].split("\n"):
        if not ln.strip() or "\t" not in ln:
            continue
        cells = ln.split("\t")
        row = dict(zip(cols, [c.strip() for c in cells]))
        if row.get("URL", "").startswith("http"):
            out.append(row)
    return out


def from_post(chunk: tuple, head: dict, clues: dict, venue_hint: str) -> Item | None:
    """글 하나를 항목으로. 본문이 없어도 줄은 만든다."""
    title, block = chunk
    meta = dict(META.findall(block))
    url = meta.get("URL", "")
    venue = host_of(url) or venue_hint or head["venue"]
    if not venue:
        return None

    posts = BODY.findall(block)
    body = "\n\n".join(
        "### %s  %s\n%s" % (kind, who, text) for kind, who, text in posts)
    first_who = posts[0][1].strip() if posts else ""
    # `글쓴이  날짜` 가 공백 둘로 갈린다. 이름에도 날짜에도 공백이 있을 수 있어
    # 앞 조각만 이름으로 본다
    actor = re.split(r"\s{2,}", first_who)[0].strip() if first_who else ""
    when = ""
    if first_who:
        rest = re.split(r"\s{2,}", first_who)
        when = rest[-1].strip() if len(rest) > 1 else ""

    state = meta.get("상태", "")
    if body:
        kind_of_body = ("게시글 본문(마스킹됨)" if head["masked"] else "게시글 본문")
    else:
        kind_of_body = ""

    raw = {"엔진": meta.get("엔진", ""), "확인": meta.get("확인", ""),
           "답글 수": max(0, len(posts) - 1),
           "답글 글쓴이": [re.split(r"\s{2,}", w)[0].strip()
                       for _, w, _ in posts[1:]]}
    # **`못 봄` 이지 `없음` 이 아니다.** 사유를 같이 적는다.
    # 사유가 오는 자리가 셋이라 순서대로 본다. 하나라도 잡아야 `안 봄` 과 갈린다.
    # 2026-08-27 실측 182건 중 2건이 `엔진 : 판별실패` 로 본문이 없었는데
    # 상태 칸이 없어 사유가 비어 있었다
    if not body:
        why = WHY.search(block)
        raw["못 본 사유"] = (
            state                                     # `- 상태 : 403 …`
            or (why.group(1) if why else "")          # `> 구조를 못 읽었다` 같은 줄
            or ("엔진 판별 실패. 킷이 이 글의 구조를 못 읽었다"
                if meta.get("엔진") == "판별실패" else "")
            or "본문이 안 왔다. 킷 출력에 사유가 없다")
    elif state:
        raw["못 본 사유"] = state
    if head["masked"]:
        raw["마스킹"] = "킷에서 켜져 있었다" if head["masked_known"] else "표시가 없어 켜진 것으로 봤다"

    return Item(
        source="forum",
        src_id=src_id_of(url, venue),
        venue=venue,
        venue_kind="forum",
        actor=actor,
        target_org="",
        title=title[:120],
        body=body,
        body_kind=kind_of_body,
        body_via="forum_kit",
        posted_at=when,
        post_url=url,
        # **원 출처는 글 주소다.** 목록 쪽은 알게 된 곳이다
        via=[head["from"]] if head["from"] else [],
        clues=clues,
        raw=raw,
        got_by=VER,
    )


# 체크한 게시판 훑기(v2.9)는 게시판마다 `### 이름 — n건 …` 다음 줄에 게시판 주소를 적는다.
# 머리의 `출처 :` 는 단추를 누른 쪽이라, 다른 게시판 글의 「알게 된 곳」 으로 쓰면 틀린다(2026-09-30 검토)
BOARD_HEAD = re.compile(r"^###\s+(.+)\s+—\s+\d+건[^\n]*\n(https?://\S+)\s*$", re.M)


def boards_of(md: str) -> dict:
    """훑기 결과의 게시판 이름 → 게시판 주소. 훑기가 아니면 빈 dict."""
    out = {}
    for name, url in BOARD_HEAD.findall(md):
        out.setdefault(name.strip(), url.strip())
    return out


def from_tsv(row: dict, head: dict, venue_hint: str, boards: dict | None = None) -> Item | None:
    """목록 줄 하나. 본문이 없다. **`안 봄` 이다.**"""
    url = row.get("URL", "")
    venue = host_of(url) or venue_hint or head["venue"]
    if not venue:
        return None
    board_url = (boards or {}).get((row.get("게시판") or "").strip())
    via = [board_url] if board_url else ([head["from"]] if head["from"] else [])
    return Item(
        source="forum",
        src_id=src_id_of(url, venue),
        venue=venue,
        venue_kind="forum",
        actor=row.get("작성자", ""),
        title=(row.get("제목", "") or "")[:120],
        body="",
        body_kind="",
        body_via="",
        posted_at=row.get("날짜", ""),
        post_url=url,
        via=via,
        raw={"게시판": row.get("게시판", ""), "답글": row.get("답글", ""),
             "조회": row.get("조회", ""),
             "본문": "안 봄. 목록만 받았다"},
        got_by=VER,
    )


def read(md: str, venue_hint: str = "") -> tuple[list[Item], dict]:
    """킷 출력 하나를 읽는다. 본문 묶음과 목록 줄을 다 본다."""
    head = head_of(md)
    clues = clues_of(md)
    items, seen = [], set()
    for chunk in POST.findall(md):
        it = from_post(chunk, head, clues, venue_hint)
        if it and it.src_id not in seen:
            seen.add(it.src_id)
            items.append(it)
    # 목록 줄은 본문이 안 온 것만 넣는다. 같은 글을 두 줄로 만들지 않는다
    listed = 0
    boards = boards_of(md)
    for row in tsv_of(md):
        it = from_tsv(row, head, venue_hint, boards)
        if it and it.src_id not in seen:
            seen.add(it.src_id)
            items.append(it)
            listed += 1

    got = sum(1 for i in items if i.body)
    note = {
        "본문 받은 글": len(items) - listed,
        "목록만 받은 글": listed,
        # 본문이 하나도 없으면 마스킹을 따질 것이 없다. 목록만 뽑으면 표시 자체가 없다
        "마스킹": head["masked"] if got else None,
        "마스킹 표시를 읽었나": head["masked_known"],
        "단서 종류": len(clues),
        "등급 제한": len(BULLET.findall(GATED.search(md).group(1))) if GATED.search(md) else 0,
        "못 가져온 것": len(BULLET.findall(FAILED.search(md).group(1))) if FAILED.search(md) else 0,
    }
    return items, note


def run(path: Path, db: Path | None, venue_hint: str) -> int:
    md = path.read_text(encoding="utf-8")
    items, note = read(md, venue_hint)
    if not items:
        print("읽은 글이 0건이다. 킷 출력이 맞는지 확인할 것")
        print("  머리에 `# <호스트> 수집` 이나 TSV 구간이 있어야 한다")
        return 1

    print("파일  %s" % path.name)
    print("포럼  %s" % ", ".join(sorted({i.venue for i in items})))
    for k in ("본문 받은 글", "목록만 받은 글", "등급 제한", "못 가져온 것", "단서 종류"):
        print("  %-14s %d" % (k, note[k]))
    # **마스킹 여부를 반드시 낸다.** 이걸 놓치면 가려진 것을 원문으로 센다
    if note["마스킹"] is None:
        print("  %-14s %s" % ("마스킹", "해당 없음. 본문을 받은 글이 없다"))
    else:
        print("  %-14s %s" % ("마스킹",
                              ("켜짐" if note["마스킹"] else "꺼짐(원문)")
                              + ("" if note["마스킹 표시를 읽었나"]
                                 else " — 표시가 없어 켜진 것으로 봤다")))
    got = sum(1 for i in items if i.body)
    print("  %-14s %d / %d" % ("본문이 든 줄", got, len(items)))

    if not db:
        print("\n--db 를 주면 넣는다")
        return 0
    s = Store(db)
    today = date.today().isoformat()
    fresh = sum(1 for it in items if s.put(it, today))
    s.log_run(today, "kit_in/" + (venue_hint or items[0].venue), len(items), fresh, VER)
    s.close()
    print("\n%d개 중 처음 보는 것 %d개" % (len(items), fresh))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="포럼 킷 출력을 수집 표로. 밖에 요청을 걸지 않는다")
    ap.add_argument("file", help="킷이 낸 마크다운 파일")
    ap.add_argument("--db", help="수집 표 경로")
    ap.add_argument("--venue", default="",
                    help="포럼 도메인. 킷 머리에서 못 읽었을 때만")
    a = ap.parse_args()
    p = Path(a.file)
    if not p.exists():
        raise SystemExit("파일이 없다: %s" % p)
    return run(p, Path(a.db) if a.db else None, a.venue.strip())


if __name__ == "__main__":
    raise SystemExit(main())
