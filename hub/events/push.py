"""사건 수집 표(items)를 노션 수집 DB 로 올립니다.

    python hub/events/push.py                  미리보기. 노션에 안 씁니다
    python hub/events/push.py --kr             한국 건만
    python hub/events/push.py --limit 20 --apply   스무 줄만 실제로 씁니다

**여기까지가 끊겨 있었습니다.** 어댑터가 받아 온 것이 SQLite 에서 끝나고
사람 눈까지 안 갔습니다. 기사에 쓰려면 그것을 봐야 하는데 지금은
SQLite 를 직접 열어야만 보였습니다.

## 무엇을 올리나

**대상 조직이 있는 줄만 올립니다.** 수집 DB 는 유출 사건 하나가 한 줄인데,
items 표에는 채널 공지와 광고도 같이 들어 있습니다. 피해자가 없으면
사건이 아닙니다. 표에는 그대로 두고 노션에만 안 올립니다.

## 안 보내는 것

items 29칸 중 아홉만 보냅니다. **본문은 안 보냅니다.**

    body    411줄 (91%)   게시글 본문
    raw     448줄          원본 응답
    clues   448줄

수집 DB 에 본문 칸이 아예 없습니다. 그 설계를 그대로 따릅니다.
CLAUDE.md 의 「나가는 것은 필드명, 패턴, 건수뿐이다」와도 맞습니다.

## 겹치는 것을 어떻게 거르나

노션에 이미 있는 줄을 원문 URL 로 봅니다. URL 이 없는 줄은
자료 제목과 게시 플랫폼을 묶어 봅니다. **사람이 쓴 줄을 안 덮습니다.**
새로 만들기만 하고 있는 줄은 건드리지 않습니다.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages"))
sys.path.insert(0, str(ROOT))

from dc_notion import Notion  # noqa: E402

수집DB = "5160ce53-7ce2-4271-879e-06f3ad9957cf"
기본표 = ROOT / "hub" / "data" / "darkchoco.db"

# **items 의 country 는 ISO 두 글자입니다.** 노션 선택지는 한글 이름이라
# 그대로 보내면 3번 관문에서 버려집니다. 선택지에 있는 것만 옮깁니다.
나라 = {
    "KR": "한국", "US": "미국", "JP": "일본", "CN": "중국", "RU": "러시아",
    "TR": "터키", "IN": "인도", "BR": "브라질", "GB": "영국", "DE": "독일",
    "FR": "프랑스", "VN": "베트남", "ID": "인도네시아", "TW": "대만",
}

# items 의 kind 는 지금 「유출 게시」 하나뿐이라 노션 선택지와 안 맞습니다.
# venue_kind 가 실제로 갈리는 값이라 그것을 씁니다.
게시성격 = {
    "dls": "랜섬웨어 유출",
    "telegram": "확인 못 함",     # 채널 글은 무엇인지 사람이 봐야 갈립니다
    "forum": "확인 못 함",
}

보낼칸 = 9


def _글(v: str) -> dict:
    return {"rich_text": [{"text": {"content": (v or "")[:2000]}}]}


def _날(v: str) -> dict | None:
    """노션 date 는 ISO 를 받습니다. 꼴이 아니면 안 보냅니다."""
    v = (v or "").strip()
    if not v:
        return None
    if len(v) >= 10 and v[4] == "-" and v[7] == "-":
        return {"date": {"start": v[:10] if len(v) == 10 else v}}
    return None


def 만들기(줄: sqlite3.Row) -> dict:
    """items 한 줄을 노션 속성으로 옮깁니다. 빈 값은 아예 안 보냅니다."""
    p: dict = {
        "자료 제목": {"title": [{"text": {"content": (줄["title"] or "제목 없음")[:2000]}}]},
        "수집자": {"select": {"name": "최현서"}},
    }
    if 줄["target_org"]:
        p["대상 조직"] = _글(줄["target_org"])
    if 줄["actor"]:
        p["게시자 핸들"] = _글(줄["actor"])
    if 줄["venue"]:
        p["게시 플랫폼"] = _글(줄["venue"])
    if 줄["post_url"]:
        p["원문 URL"] = _글(줄["post_url"])

    d = _날(줄["posted_at"])
    if d:
        p["게시 시각"] = d
    d = _날(줄["first_seen"])
    if d:
        p["수집일"] = d

    이름 = 나라.get((줄["country"] or "").upper())
    if 이름:
        p["국가"] = {"select": {"name": 이름}}

    성격 = 게시성격.get(줄["venue_kind"] or "")
    if 성격:
        p["게시 성격"] = {"select": {"name": 성격}}

    return p


def _열쇠(url: str, 제목: str, 곳: str) -> str:
    """겹침을 보는 열쇠. URL 이 있으면 그것이 먼저입니다."""
    u = (url or "").strip()
    return u if u else "%s|%s" % ((제목 or "").strip(), (곳 or "").strip())


def 이미있는것(n: Notion) -> set[str]:
    """노션에 이미 있는 줄의 열쇠. 사람이 쓴 것도 여기 들어갑니다."""
    본것 = set()
    for r in n.query_all(수집DB):
        p = r.get("properties") or {}

        def 글(칸: str) -> str:
            v = (p.get(칸) or {}).get("rich_text") or []
            return "".join(x.get("plain_text", "") for x in v)

        제목 = "".join(x.get("plain_text", "")
                     for x in ((p.get("자료 제목") or {}).get("title") or []))
        본것.add(_열쇠(글("원문 URL"), 제목, 글("게시 플랫폼")))
    return 본것


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="사건 수집 표를 노션 수집 DB 로 올립니다")
    ap.add_argument("--apply", action="store_true",
                    help="실제로 노션에 씁니다. 없으면 미리보기입니다")
    ap.add_argument("--kr", action="store_true", help="국가가 KR 인 것만")
    ap.add_argument("--new", action="store_true", help="아직 안 본 것만")
    ap.add_argument("--limit", type=int, default=0, help="최대 몇 줄까지")
    ap.add_argument("--모두", action="store_true",
                    help="대상 조직이 없는 줄도 올립니다. 채널 공지까지 다 갑니다")
    ap.add_argument("--db", default=str(기본표), help="읽을 SQLite 파일")
    a = ap.parse_args(argv)

    f = Path(a.db)
    if not f.exists():
        print("  표가 없습니다: %s" % f)
        return 1

    c = sqlite3.connect(f)
    c.row_factory = sqlite3.Row
    # **대상 조직이 있어야 올립니다.** 수집 DB 는 유출 사건 하나가 한 줄인데,
    # items 표에는 채널 공지·광고·안내도 같이 들어 있습니다. 2026-09-02 에
    # 실제로 보니 텔레그램 133줄이 전부 그런 것이었습니다 — 「DarkForums
    # pinned a photo」 같은 것들이고 대상 조직이 하나도 안 채워져 있습니다.
    #
    # 피해자가 없으면 사건이 아닙니다. 그것이 가르는 가장 단순한 기준입니다.
    # 표에는 그대로 두고 노션에만 안 올립니다. 나중에 어댑터가 유출 글을
    # 가려내게 되면 그때 올라갑니다.
    조건, 값 = ["forgotten = 0", "target_org != ''"], []
    if a.모두:
        조건 = ["forgotten = 0"]
    if a.kr:
        조건.append("upper(country) = 'KR'")
    if a.new:
        조건.append("is_new = 1")
    q = "select * from items where " + " and ".join(조건) + " order by first_seen desc"
    if a.limit:
        q += " limit %d" % a.limit
    줄들 = list(c.execute(q, 값))

    전체 = c.execute("select count(*) from items where forgotten = 0").fetchone()[0]
    print()
    print("  items 표 %d줄 중 %d줄을 골랐습니다" % (전체, len(줄들)))
    if not a.모두:
        뺀것 = c.execute(
            "select count(*) from items where forgotten = 0 and target_org = ''"
        ).fetchone()[0]
        print("    대상 조직이 없는 %d줄은 뺐습니다. 유출 사건이 아닙니다" % 뺀것)
    if not 줄들:
        return 0

    n = Notion()
    print("  노션에 이미 있는 것을 봅니다...", flush=True)
    본것 = 이미있는것(n)
    print("  노션에 %d줄이 있습니다" % len(본것))

    # **표 안에서도 겹칩니다.** URL 이 없는 줄은 제목과 곳으로만 가리는데,
    # 같은 글이 여러 채널에 퍼지면 열쇠가 같아집니다. 448줄이 열쇠로는
    # 414개입니다. 그대로 밀면 노션에 34줄이 중복으로 생깁니다.
    새것, 본열쇠 = [], set(본것)
    for r in 줄들:
        k = _열쇠(r["post_url"], r["title"], r["venue"])
        if k in 본열쇠:
            continue
        본열쇠.add(k)
        새것.append(r)
    겹침 = len(줄들) - len(새것)
    print("  겹치는 %d줄을 뺐습니다. 올릴 것은 %d줄입니다" % (겹침, len(새것)))
    print()

    if not a.apply:
        print("  미리보기입니다. 노션에 안 씁니다. --apply 를 주면 씁니다.")
        print()
        print("  올라갈 칸 %d개" % 보낼칸)
        print("    자료 제목 · 대상 조직 · 게시자 핸들 · 게시 플랫폼 · 원문 URL")
        print("    게시 시각 · 수집일 · 국가 · 게시 성격 · 수집자(최현서)")
        print()
        print("  안 올라가는 것")
        print("    body · raw · clues · sample_path — 수집 DB 에 그 칸이 없습니다")
        print()
        for r in 새것[:5]:
            print("    %-46s %s · %s" % ((r["title"] or "")[:46],
                                        r["venue_kind"], r["country"] or "-"))
        if len(새것) > 5:
            print("    ... 그리고 %d줄 더" % (len(새것) - 5))
        return 0

    쓴것, 못쓴것 = 0, []
    for i, r in enumerate(새것, 1):
        try:
            n.request("POST", "/pages", {
                "parent": {"type": "data_source_id", "data_source_id": 수집DB},
                "properties": 만들기(r),
            })
            쓴것 += 1
        except Exception as e:  # noqa: BLE001
            못쓴것.append("%s: %s" % ((r["title"] or "")[:40], str(e)[:120]))
        if i % 25 == 0:
            print("    %d/%d" % (i, len(새것)), flush=True)

    print()
    print("  %d줄을 올렸습니다" % 쓴것)
    if 못쓴것:
        print("  못 올린 것 %d줄" % len(못쓴것))
        for m in 못쓴것[:5]:
            print("    " + m)
    return 1 if 못쓴것 else 0


if __name__ == "__main__":
    raise SystemExit(main())
