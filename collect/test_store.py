#!/usr/bin/env python3
"""수집 표 시험.

    python collect/test_store.py

밖에 나가지 않는다. 임시 SQLite 로만 돈다.
값은 전부 지어낸 것이다. 실제 유출물에서 가져오지 않았다.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from collect.store import Item, Store  # noqa: E402

fails = []


def check(name: str, got, want) -> None:
    if got != want:
        fails.append("%s\n     받음 %r\n     기대 %r" % (name, got, want))


tmp = Path(tempfile.mkdtemp(prefix="store_"))
s = Store(tmp / "x.db")

RANSOM = dict(source="ransom", venue="titanblog.org", venue_kind="dls",
              actor="TITAN", target_org="어떤회사", target_domain="example.com",
              post_url="http://x.onion/post/1", posted_at="2026-08-20T10:00:00+00:00",
              body="A South Korean manufacturer of valves.",
              body_kind="회사 소개", body_via="api",
              via=["ransomware.live"], got_by="ransom.py v1")

# ── 1. 넣고 다시 넣기 ───────────────────────────
check("처음은 새 줄", s.put(Item(**RANSOM), "2026-08-27"), True)
check("같은 것은 안 늘어난다", s.put(Item(**RANSOM), "2026-08-27"), False)
check("줄 하나", len(s.rows()), 1)

# uid 는 열쇠 칸으로만 정해진다. 본문이 달라져도 같은 줄이다
a = Item(**dict(RANSOM, body="다른 본문", claimed_size="240K"))
check("본문이 달라도 같은 uid", a.uid(), Item(**RANSOM).uid())
s.put(a, "2026-08-27")
check("여전히 줄 하나", len(s.rows()), 1)
check("빈칸이던 규모가 찬다", s.rows()[0]["claimed_size"], "240K")

# ── 2. 본문 셋이 같이 움직인다 ──────────────────
# 본문만 바뀌고 body_kind 가 남으면 회사 소개를 게시글 본문으로 읽게 된다.
# 실제로 그 버그를 만들었다가 시험으로 잡았다
KIT = dict(RANSOM, source="forum", body="We have all data. 240,000 rows.",
           body_kind="게시글 본문", body_via="kit", via=["직접 확인"],
           got_by="kit_in.py v1")
s.put(Item(**KIT), "2026-08-27")
r = s.rows()[0]
check("본문이 바뀐다", r["body"][:14], "We have all da")
check("본문 성격도 같이", r["body_kind"], "게시글 본문")
check("본문 출처도 같이", r["body_via"], "kit")

# 반대로 회사 소개가 뒤에 와도 진짜 본문을 안 덮는다
s.put(Item(**dict(RANSOM, body="회사 소개가 또 왔다")), "2026-08-28")
r = s.rows()[0]
check("회사 소개가 본문을 못 덮는다", r["body_kind"], "게시글 본문")
check("본문 그대로", r["body"][:14], "We have all da")

# ── 3. 빈 값으로 덮지 않는다 ────────────────────
s.put(Item(source="ransom", venue="titanblog.org", actor="TITAN",
           target_org="어떤회사", post_url="http://x.onion/post/1"), "2026-08-28")
r = s.rows()[0]
check("종류가 남는다", r["venue_kind"], "dls")
check("도메인이 남는다", r["target_domain"], "example.com")
check("게시 시각이 남는다", r["posted_at"], "2026-08-20T10:00:00+00:00")

# ── 4. via 는 합친다. 독립 출처가 아니라 어디서 알았나다 ──
check("via 합쳐짐", sorted(json.loads(r["via"])), ["ransomware.live", "직접 확인"])

# ── 5. URL 을 손대지 않는다 ─────────────────────
# 팀원 도구는 내보낼 때 무력화해서 같은 글 판별이 깨졌다
for bad in ("hxxp", "[.]"):
    if bad in r["post_url"]:
        fails.append("URL 이 무력화됐다: %r" % r["post_url"])
check("URL 그대로", r["post_url"], "http://x.onion/post/1")

# ── 6. 확인일이 남는다 ──────────────────────────
check("처음 본 날", r["first_seen"], "2026-08-27")
check("마지막 본 날", r["last_seen"], "2026-08-28")

# ── 7. 지우면 본문만 사라지고 줄은 남는다 ───────
uid = r["uid"]
check("지움", s.forget(uid), True)
check("두 번은 안 지운다", s.forget(uid), False)
r = s.rows()[0]
check("본문이 비었다", r["body"], "")
check("지웠다고 표시", r["body_kind"], "지움")
check("단서도 지웠다", r["clues"], "{}")
check("줄은 남는다", len(s.rows()), 1)
check("조직명은 남는다", r["target_org"], "어떤회사")
check("주소도 남는다", r["post_url"], "http://x.onion/post/1")

# 지운 뒤에 다시 봐도 새 건이 아니다. 줄을 지웠으면 새 건으로 다시 들어온다
check("이미 아는 줄", s.seen(uid), True)

# ── 8. 보존기한 ─────────────────────────────────
s2 = Store(tmp / "y.db")
s2.put(Item(source="forum", venue="a.example", post_url="http://a/1",
            body="본문 있음", body_kind="게시글 본문"), "2026-07-01")
s2.put(Item(source="forum", venue="b.example", post_url="http://b/1",
            body="본문 있음", body_kind="게시글 본문"), "2026-08-27")
check("오래된 것만 지운다", s2.forget_older("2026-08-01"), 1)
남음 = [x for x in s2.rows() if x["body"]]
check("최근 것은 남는다", len(남음), 1)
check("남은 것은 b", 남음[0]["venue"], "b.example")

# ── 9. 샘플 값을 표에 안 넣는다 ─────────────────
s3 = Store(tmp / "z.db")
s3.put(Item(source="forum", venue="c.example", post_url="http://c/1",
            sample_path="07_케이스/_큐/어떤건/②샘플.txt"), "2026-08-27")
r3 = s3.rows()[0]
if "@" in r3["sample_path"] or "," in r3["sample_path"]:
    fails.append("sample_path 에 값이 들어간 것 같다: %r" % r3["sample_path"])
check("경로만", r3["sample_path"], "07_케이스/_큐/어떤건/②샘플.txt")

# ── 10. 소스별로 센다 ───────────────────────────
c = s.counts()
if "ransom" not in c:
    fails.append("소스별 갯수가 안 나온다: %r" % c)

# ── 결과 ────────────────────────────────────────
if fails:
    print("실패 %d" % len(fails))
    for f in fails:
        print("  - %s" % f)
    sys.exit(1)
print("통과. 시험 10 묶음")
