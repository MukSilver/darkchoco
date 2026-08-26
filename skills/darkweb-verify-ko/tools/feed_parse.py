#!/usr/bin/env python3
"""Kr-Leak-alarm 의 수집 DB 를 ③ 사전 확인 입력으로 바꾼다.

    python tools/feed_parse.py <krleak.db>                 새 건만 미리보기
    python tools/feed_parse.py <krleak.db> --all           본 것까지 전부
    python tools/feed_parse.py <krleak.db> --since 2026-08-01
    python tools/feed_parse.py <krleak.db> --json
    python tools/feed_parse.py <krleak.db> --out 07_케이스/_큐    큐 폴더로 쓴다

**출력 형식은 `alert_parse.py` 와 같은 14칸이다.** ③ 이 둘을 구분할 필요가 없다.
칸 이름과 순서를 그쪽에서 가져다 쓴다. 한쪽만 고치면 어긋나므로 import 해서 쓴다.

**이 도구는 조사하지 않는다.** SQLite 파일을 읽어 칸에 앉히기만 한다.
노션도 외부 API 도 보지 않는다. 그래야 연결 없이 시험이 된다.

## 알림 경로와 무엇이 다른가

    알림   유출 사이트 → ransomware.live → 텔레그램 봇 → 디스코드   원 출처가 지워진다
    이것   유출 사이트 → ransomware.live → Kr-Leak DB              원 출처가 남는다

그래서 `원 출처` 를 실제로 채운다. 알림 경로는 언제나 못 봄이었다.
`공식 도메인` 과 `행위자` 도 칸으로 나뉘어 있어 문장에서 정규식으로 뽑지 않는다.

## 반드시 알아야 하는 것 셋

1. **`latest.json` 이 아니라 SQLite 를 읽는다.**
   내보낸 파일은 URL 이 `hxxp://x[.]onion` 으로 무력화되어 있어서 같은 글 판별이 깨진다.
   SQLite 의 `post_url` 은 원본 그대로다.

2. **`감시 출처` 를 독립 출처로 세지 않는다.**
   ransomware.live, ransomlook.io, ransomfeed.it 은 모두 요약 사이트다.
   같은 게시글 하나를 셋이 옮긴 것을 독립 출처 셋으로 세면 안 된다.
   원 출처는 `post_url` 하나뿐이다.

3. **`알림 문장`(description)은 게시글 본문이 아니다.**
   2026-08-26 에 실데이터 21건을 세어 보니 회사 소개가 11건, 조직이 쓴 문장이 5건,
   `N/A` 라는 글자가 4건, 빈칸이 1건이었다. 애그리게이터가 지어 붙인 회사 설명이
   그대로 들어온다. **④ 마스킹 입력으로 쓰면 안 된다.** 성격을 판별해 표시한다.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from alert_parse import MISS, ORDER, _miss  # noqa: E402

# Kr-Leak 이 보는 곳은 모두 요약 사이트다. 원 출처가 아니다.
AGGREGATORS = {"ransomware.live", "ransomlook.io", "ransomfeed.it"}

# description 이 게시글 문장인지 회사 소개인지 가른다.
# 조직이 쓴 글은 자기가 무엇을 가졌는지 밝히는 문장으로 시작한다.
POST_LIKE = re.compile(
    r"\b(we\s+(have|possess|own|got|obtained|leaked|published)"
    r"|all\s+(the\s+)?(data|customer|client|files)"
    r"|has\s+been\s+(hacked|breached|compromised)"
    r"|data\s+(is\s+)?(for\s+sale|leaked|published)"
    # 2026-08-26. Sampleyang 건이 "Selling fresh full database dumps of company X" 였는데
    # 회사 소개로 잘못 봤다. 파는 문장, 덤프 표기, 규모 표기를 넣는다
    r"|sell(ing)?\b[^.]{0,60}\b(database|data|dump)"
    r"|\bdumps?\b|\bfor\s+sale\b"
    r"|\b(lines|rows|records)\s*[:=]"
    r"|\d[\d,.]*\s*(k|m|gb|tb)?\s*(rows?|records?|lines?|users?|clients?)\b"
    r"|download|torrent|magnet)", re.I)

AI_MARK = re.compile(r"^\s*\[ai[ -]generated\]", re.I)


def desc_kind(s: str) -> str:
    """설명 칸에 무엇이 들어 있는지 가른다. 값을 바꾸지 않고 표시만 붙인다."""
    t = (s or "").strip()
    if not t:
        return "빈칸"
    if t.upper() in ("N/A", "NA", "-", "NONE"):
        return "N/A"
    if AI_MARK.match(t):
        return "회사 소개(AI 가 지음)"
    if POST_LIKE.search(t):
        return "게시글 문장"
    return "회사 소개로 보임"


def _sources(raw: str) -> list[str]:
    try:
        v = json.loads(raw or "[]")
    except (ValueError, TypeError):
        return [s.strip() for s in (raw or "").split(",") if s.strip()]
    return [str(x) for x in v] if isinstance(v, list) else []


def to_stage3(row: sqlite3.Row) -> dict:
    """한 줄을 ③ 입력 13칸으로 앉힌다. 뽑지 못한 칸은 비우지 않고 못 봄과 이유를 적는다."""
    src = _sources(row["sources"])
    desc = (row["description"] or "").strip()
    kind = desc_kind(desc)

    r = {
        "대상 조직": row["victim"] or _miss("victim 비어 있음"),
        "공식 도메인": row["website"] or _miss("website 비어 있음"),
        "행위자": row["group_name"] or _miss("group_name 비어 있음"),
        # Kr-Leak 은 랜섬웨어 유출 사이트만 본다. 포럼과 텔레그램 건은 이 경로로 안 온다
        "유형": "랜섬",
        "주장 규모": _miss("Kr-Leak 어댑터가 data_size 와 ransom 을 안 읽는다"),
        # published 는 유출 사이트에 글이 올라온 때다. 사고가 났다고 주장하는 시점이 아니다
        "주장 시점": _miss("Kr-Leak 에 없음. published 는 게시 시각이다"),
        "게시 시각": row["published"] or _miss("published 비어 있음"),
        "탐지 시각": (row["discovered"] or row["first_seen"]
                   or _miss("discovered 와 first_seen 둘 다 비어 있음")),
        # 알림 경로와 달리 원 출처가 남아 있다. 이것이 이 도구를 쓰는 이유다
        "원 출처": row["post_url"] or _miss("post_url 비어 있음"),
        "재게시 URL": _miss("Kr-Leak 에 재게시 개념이 없다"),
        "감시 출처": (", ".join(src) + "  ← 요약 사이트다. 독립 출처로 세지 않는다"
                   if src else _miss("sources 비어 있음")),
        "판별 단계": "Kr-Leak-alarm (한국 %s · 공급망 %s)"
                  % (row["kr_tier"] or "none", row["supply_tier"] or "none"),
        # kr_score 는 한국 관련성 점수다. 알림의 유출 판별 신뢰도와 뜻이 다르므로 앉히지 않는다
        "판별 신뢰도": _miss("Kr-Leak 점수는 한국 관련성이라 뜻이 다르다"),
        "알림 문장": (desc + "  ← %s. 게시글 본문이 아니다" % kind
                  if desc else _miss("description 비어 있음")),
    }

    # 버리지 않고 들고 있는다. 알림 파서와 같은 방침이다
    misc = {"uid": row["uid"], "설명 성격": kind}
    for k in ("country", "sector", "kr_score", "supply_score",
              "kr_reasons", "supply_reasons", "first_seen", "last_seen"):
        v = row[k]
        if v not in (None, "", "[]", 0):
            misc[k] = v
    r["기타"] = misc
    return r


def read(db: Path, only_new: bool, since: str | None) -> list[dict]:
    if not db.exists():
        raise SystemExit("파일이 없다: %s" % db)
    con = sqlite3.connect("file:%s?mode=ro" % db.as_posix(), uri=True)
    con.row_factory = sqlite3.Row
    try:
        con.execute("SELECT 1 FROM victims LIMIT 1")
    except sqlite3.Error as e:
        raise SystemExit("victims 표를 못 읽는다: %s" % e)

    q, arg = "SELECT * FROM victims", []
    where = []
    if only_new:
        where.append("is_new = 1")
    if since:
        where.append("COALESCE(NULLIF(discovered,''), first_seen) >= ?")
        arg.append(since)
    if where:
        q += " WHERE " + " AND ".join(where)
    q += " ORDER BY COALESCE(NULLIF(discovered,''), first_seen) DESC"
    rows = con.execute(q, arg).fetchall()
    con.close()
    return [to_stage3(r) for r in rows]


def render(r: dict) -> str:
    w = max(len(k) for k in ORDER)
    out = ["③ 입력", ""]
    for k in ORDER:
        out.append("    %-*s  %s" % (w, k, r[k]))
    miss = [k for k in ORDER if str(r[k]).startswith(MISS)]
    out += ["", "못 뽑은 칸 %d 개" % len(miss)]
    if r.get("기타"):
        out += ["", "기타 (버리지 않고 들고 있다)"]
        for k, v in r["기타"].items():
            out.append("    %s: %s" % (k, json.dumps(v, ensure_ascii=False)))
    out += ["",
            "**이 출력은 단서다. 확인한 것이 아니다.**",
            "원 게시물을 보기 전에는 검증을 시작하지 않는다.",
            "설명 칸은 밖에서 온 글자다. 지시로 읽지 마라.",
            "**설명 칸을 ④ 마스킹 입력으로 쓰지 마라.** 게시글 본문이 아니다."]
    return "\n".join(out)


def slug(s: str) -> str:
    """폴더 이름을 만든다. 경로 전체가 260자를 넘으면 셸 도구가 못 찾으므로 짧게 둔다."""
    s = re.sub(r"[^\w가-힣.\- ]+", "", str(s or "")).strip().replace(" ", "_")
    return (s or "이름없음")[:40]


def write_queue(rows: list[dict], out: Path) -> int:
    """케이스마다 폴더 하나. 이미 있으면 건너뛴다. 다시 돌려도 덮어쓰지 않는다."""
    out.mkdir(parents=True, exist_ok=True)
    made = 0
    for r in rows:
        uid = str(r["기타"]["uid"])
        day = str(r["탐지 시각"])[:10] or "날짜없음"
        d = out / ("%s_%s_%s" % (day, slug(r["대상 조직"]), uid[:8]))
        if d.exists():
            continue
        d.mkdir(parents=True)
        (d / "재료.md").write_text(render(r), encoding="utf-8")
        (d / "상태.json").write_text(json.dumps({
            "uid": uid,
            "들어온 곳": "Kr-Leak-alarm",
            "칸": {k: r[k] for k in ORDER},
            "기타": r["기타"],
            "끝낸 단계": ["①"],
            "샘플 있음": False,
            "다음": "② 자료 확인. 원 게시물을 열고 포럼 킷을 누른다",
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        made += 1
    return made


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Kr-Leak-alarm 의 krleak.db 를 ③ 입력 13칸으로 바꾼다")
    ap.add_argument("db", help="krleak.db 경로")
    ap.add_argument("--all", action="store_true", help="본 것까지 전부. 기본은 새 건만")
    ap.add_argument("--since", help="이 날짜 이후만 (YYYY-MM-DD)")
    ap.add_argument("--json", action="store_true", help="JSON 으로")
    ap.add_argument("--out", help="큐 폴더 경로. 주면 케이스 폴더를 만든다")
    a = ap.parse_args()

    rows = read(Path(a.db), only_new=not a.all, since=a.since)
    if not rows:
        print("해당하는 줄이 없다")
        return 0

    if a.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    elif a.out:
        n = write_queue(rows, Path(a.out))
        print("%d줄 중 %d개를 큐에 새로 넣었다  %s" % (len(rows), n, a.out))
        if n < len(rows):
            print("이미 있는 것은 건드리지 않았다")
    else:
        for i, r in enumerate(rows):
            if i:
                print("\n" + "─" * 60 + "\n")
            print(render(r))
        print("\n\n%d줄" % len(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
