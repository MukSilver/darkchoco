#!/usr/bin/env python3
"""ransomware.live 어댑터 시험.

    python collect/sources/test_ransomlive.py

**밖에 나가지 않는다.** 지어낸 줄로만 돈다.
칸 이름과 꼴은 2026-08-27 에 실제 응답에서 본 것을 그대로 본떴다.
값은 지어낸 것이라 실제 조직이 아니다.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from collect.sources.ransomlive import FEEDS, to_item  # noqa: E402

fails = []


def check(name: str, got, want) -> None:
    if got != want:
        fails.append("%s\n     받음 %r\n     기대 %r" % (name, got, want))


# `countryvictims/KR` 한 줄. 칸 11개
KR = {
    "activity": "Manufacturing",
    "country": "KR",
    "data_size": "120 GB",
    "description": "테스트회사 has operated in Testland for decades.",
    "discovered": "2026-08-25T20:57:25.789152+00:00",
    "group_name": "testgroup",
    "post_title": "test.example.kr",
    "post_url": "http://testgrouponion.onion/blog/post/testexample",
    "published": "2026-08-25T20:57:09.561479+00:00",
    "ransom": None,
    "website": "test.example.kr",
}

# `recentvictims` 한 줄. 칸 이름이 다르다
RECENT = {
    "activity": "Financial Services",
    "attackdate": "2026-11-18 00:00:00.000000",
    "claim_url": "http://otheronion.onion/leak/testco",
    "country": "US",
    "data_size": None,
    "description": "TestCo is an insuretech company.",
    "discovered": "2026-01-15T13:48:29.435004+00:00",
    "domain": "testco.test",
    "group": "akira",
    "infostealer": {"employees": 3},
    "press": {"link": "https://news.test/x"},
    "ransom": None,
    "screenshot": "",
    "url": "https://www.ransomware.live/id/VGVzdENvQGFraXJh",
    "victim": "TestCo",
}

# ── 1. KR 엔드포인트 ────────────────────────────
a = to_item(KR, FEEDS["kr"], "kr")
check("대상 조직", a.target_org, "test.example.kr")
check("도메인", a.target_domain, "test.example.kr")
check("행위자", a.actor, "testgroup")
check("원 출처", a.post_url, "http://testgrouponion.onion/blog/post/testexample")
check("게시 시각", a.posted_at, "2026-08-25T20:57:09.561479+00:00")
check("성격", a.kind, "랜섬웨어 유출")
check("나라", a.country, "KR")

# 팀원 어댑터가 안 읽는 칸이다. 우리는 읽는다
check("주장 규모", a.claimed_size, "120 GB")

# ── 2. description 은 회사 소개다 ───────────────
# 2026-08-26 에 이 칸을 게시글 본문으로 잘못 알았다
check("본문 성격", a.body_kind, "회사 소개")
if a.body_kind == "게시글 본문":
    fails.append("회사 소개를 게시글 본문으로 적었다")

# ── 3. 원 출처는 손대지 않는다 ──────────────────
for bad in ("hxxp", "[.]"):
    if bad in a.post_url:
        fails.append("원 출처를 무력화했다: %r" % a.post_url)
check("venue 는 원 출처 도메인", a.venue, "testgrouponion.onion")
check("via 는 알게 된 곳", a.via, ["ransomware.live"])

# ── 4. recent 엔드포인트. 칸 이름이 다르다 ──────
b = to_item(RECENT, FEEDS["recent"], "recent")
check("대상 조직", b.target_org, "TestCo")
check("도메인", b.target_domain, "testco.test")
check("행위자", b.actor, "akira")

# **이것이 이 시험의 핵심이다.**
# `url` 은 ransomware.live 자기 페이지다. 그것을 원 출처로 세면
# 요약 사이트를 독립 출처로 세게 된다
check("원 출처는 claim_url", b.post_url, "http://otheronion.onion/leak/testco")
if "ransomware.live" in b.post_url:
    fails.append("요약 사이트 주소를 원 출처로 세었다: %r" % b.post_url)
check("자기 페이지는 재게시 자리로", b.raw.get("재게시 자리"),
      "https://www.ransomware.live/id/VGVzdENvQGFraXJh")
check("venue 는 유출 사이트", b.venue, "otheronion.onion")

# ── 5. 두 엔드포인트가 같은 꼴을 낸다 ───────────
for k in ("source", "kind", "body_via", "got_by"):
    check("두 소스의 %s 가 같다" % k, getattr(a, k), getattr(b, k))

# ── 6. 못 알아본 칸을 버리지 않는다 ─────────────
for k in ("press", "infostealer", "claim_url", "url"):
    if k not in b.raw:
        fails.append("raw 에 %s 가 없다: %r" % (k, sorted(b.raw)))
check("산업 분야", b.raw.get("산업 분야"), "Financial Services")

# ── 7. 빈 칸이 문자열 'None' 이 되지 않는다 ─────
check("몸값 빈칸", a.price, "")
check("recent 규모 빈칸", b.claimed_size, "")

# ── 8. 줄이 뭉치지 않는다 ───────────────────────
check("uid 가 다르다", a.uid() != b.uid(), True)
same = to_item(dict(KR, discovered="2026-08-26T00:00:00+00:00"), FEEDS["kr"], "kr")
check("같은 건은 같은 uid", same.uid(), a.uid())

# 원 출처가 없는 줄이 여럿이어도 대상이 다르면 갈린다
n1 = to_item(dict(KR, post_url="", post_title="가"), FEEDS["kr"], "kr")
n2 = to_item(dict(KR, post_url="", post_title="나"), FEEDS["kr"], "kr")
check("대상이 다르면 갈린다", n1.uid() != n2.uid(), True)

# ── 결과 ────────────────────────────────────────
if fails:
    print("실패 %d" % len(fails))
    for f in fails:
        print("  - %s" % f)
    sys.exit(1)
print("통과. 시험 8 묶음")
