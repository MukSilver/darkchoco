#!/usr/bin/env python3
"""텔레그램 공개 미리보기 파서 시험.

    python collect/sources/test_telegram_web.py

**밖에 나가지 않는다.** 지어낸 HTML 로만 돈다.
꼴은 2026-08-27 에 `t.me/s/osint_cti` 에서 실제로 본 것을 그대로 본떴다.
값은 전부 지어낸 것이라 실제 인물이나 조직이 아니다.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from collect.sources.telegram_web import clean, origin, parse, to_item  # noqa: E402

fails = []


def check(name: str, got, want) -> None:
    if got != want:
        fails.append("%s\n     받음 %r\n     기대 %r" % (name, got, want))


def post(num: int, when: str, body: str, links: str = "") -> str:
    return (
        '<div class="tgme_widget_message text_not_supported_wrap js-widget_message"'
        ' data-post="testchan/%d">'
        '<div class="tgme_widget_message_owner_name"><span dir="auto">시험 채널</span></div>'
        '<div class="tgme_widget_message_text js-message_text" dir="auto">%s%s</div>'
        '<span class="tgme_widget_message_views">7</span>'
        '<a class="tgme_widget_message_date" href="https://t.me/testchan/%d">'
        '<time datetime="%s"></time></a>'
        "</div>" % (num, body.replace("\n", "<br/>"), links, num, when))


LEAK = post(101, "2026-08-26T23:38:55+00:00",
            "⚠️ MEDIUM SEVERITY LEAK DETECTED ⚠️\n\n"
            "• Target/Title: example-target.test\n"
            "• Threat Actor: 👤 TestHandle\n"
            "• Country: 📍 Testland\n"
            "• Intel Source: 🌐 Dark Web Forum\n"
            "• Detection Date: 📅 26 August 2026\n"
            "• Risk Score: 📊 7/10\n\n🔗 Source Intelligence Link:\n",
            '<a href="https://example-forum.test/Thread-SELLING-test">'
            'https://example-forum.test/Thread-SELLING-test</a>')

RANSOM = post(102, "2026-08-26T20:00:00+00:00",
              "🔴 NEW RANSOMWARE VICTIM\n\n"
              "• Victim: 시험회사\n• Group: TestGroup\n"
              "• Sector: Manufacturing\n• Country: 🇰🇷 South Korea\n"
              "• Risk: High\n• Published: 2026-08-26")

CVE = post(103, "2026-08-26T18:00:00+00:00",
           "🛡 NEW HIGH SEVERITY CVE PUBLISHED\n\n"
           "• CVE ID: CVE-2026-00000\n• Product: TestProduct\n"
           "• CVSS Score: 8.8\n• Published: 2026-08-26")

# CVE 둘. 원 출처도 조직도 없어서 열쇠가 겹칠 수 있다. 그것이 이 시험의 핵심이다
CVE2 = post(104, "2026-08-26T17:00:00+00:00",
            "🛡 NEW HIGH SEVERITY CVE PUBLISHED\n\n"
            "• CVE ID: CVE-2026-11111\n• Product: OtherProduct\n"
            "• CVSS Score: 9.1\n• Published: 2026-08-26")

SIG = post(105, "2026-08-26T16:00:00+00:00",
           "🧬 NEW MALWARE SIGNATURE\n\n"
           "• Signature: Test.Sig.A\n• File: test.bin\n"
           "• Type: Loader\n• First Seen: 2026-08-25\n• Tags: test")

PAGE = "<html><body>" + LEAK + RANSOM + CVE + CVE2 + SIG + "</body></html>"

OFF = ('<html><body><div class="tgme_page">'
       "<div>Data Leak Monitor</div><div>Preview channel</div>"
       "</body></html>")

# ── 1. 글을 다 잡는다 ───────────────────────────
posts, why = parse(PAGE, "testchan")
check("다섯 건", len(posts), 5)
check("사유 없음", why, "")

# ── 2. 종류를 가른다. **거르지 않는다** ─────────
kinds = [p["kind"] for p in posts]
check("종류", kinds, ["유출 알림", "랜섬 피해자", "CVE 알림", "CVE 알림", "악성코드 시그니처"])
check("우리 대상 둘", sum(1 for p in posts if p["ours"]), 2)
check("대상 아닌 것도 버리지 않는다", sum(1 for p in posts if p["ours"] is False), 3)

# ── 3. 미리보기가 꺼져 있으면 왜인지 말한다 ─────
none, why2 = parse(OFF, "breachdetect")
check("0건", none, [])
if "미리보기가 꺼져" not in why2 or "실계정" not in why2:
    fails.append("미리보기 꺼짐 사유가 부실하다: %r" % why2)

none3, why3 = parse("<html><body>아무것도 아님</body></html>", "x")
check("엉뚱한 쪽도 0건", none3, [])
if not why3:
    fails.append("사유 없이 0건을 돌려줬다")

# ── 4. 값 앞의 이모지를 뗀다 ────────────────────
# 안 떼면 대상 조직 이름 대조가 깨진다
check("사람 이모지", clean("👤 TestHandle"), "TestHandle")
check("깃발", clean("🇰🇷 South Korea"), "South Korea")
check("핀", clean("📍 Testland"), "Testland")
check("없으면 그대로", clean("TestHandle"), "TestHandle")
check("빈칸", clean(""), "")
# 오탐 시험. 글자 안의 것은 안 건드린다
check("가운데는 안 건드린다", clean("A 👤 B"), "A 👤 B")

# ── 5. 원 출처를 글 안에서 찾는다 ───────────────
# 집계 채널 주소를 원 출처로 세면 안 된다
check("링크에서", origin(["https://example-forum.test/x"], ""),
      "https://example-forum.test/x")
check("t.me 는 원 출처가 아니다", origin(["https://t.me/testchan/1"], ""), "")
check("본문에서 줍기", origin([], "보라 https://example-forum.test/y 끝"),
      "https://example-forum.test/y")
check("없으면 빈칸", origin([], "아무것도 없다"), "")

# ── 6. 항목으로 바꾼다 ──────────────────────────
it = to_item(posts[0], "testchan", "2026-08-27")
check("원 출처가 포럼", it.post_url, "https://example-forum.test/Thread-SELLING-test")
check("venue 도 포럼 도메인", it.venue, "example-forum.test")
check("via 는 텔레그램", it.via, ["t.me/s/testchan"])
check("행위자 이모지 없음", it.actor, "TestHandle")
check("대상", it.target_org, "example-target.test")
check("도메인꼴이면 도메인칸에도", it.target_domain, "example-target.test")
check("본문 성격", it.body_kind, "집계 채널 글")
check("글 번호", it.src_id, "testchan/101")
if it.raw.get("집계 채널 글 주소") != "https://t.me/testchan/101":
    fails.append("집계 채널 주소를 안 남겼다: %r" % it.raw.get("집계 채널 글 주소"))

# 조직 이름이 도메인 꼴이 아니면 도메인 칸을 안 채운다
it2 = to_item(posts[1], "testchan", "2026-08-27")
check("한글 조직은 도메인 아님", it2.target_domain, "")
check("랜섬은 성격이 정해진다", it2.kind, "랜섬웨어 유출")
check("원 출처 없으면 venue 는 채널", it2.venue, "t.me/testchan")

# ── 7. 못 옮긴 칸을 버리지 않는다 ───────────────
it3 = to_item(posts[2], "testchan", "2026-08-27")
miss = it3.raw.get("못 옮긴 칸", [])
for k in ("cve id", "cvss score", "product"):
    if k not in miss:
        fails.append("못 옮긴 칸에 %s 가 없다: %r" % (k, miss))

# ── 8. CVE 둘이 한 줄로 뭉치지 않는다 ───────────
# 2026-08-27 에 실제로 스무 건이 열일곱 줄이 됐다
ids = [to_item(p, "testchan", "2026-08-27").uid() for p in posts]
check("다섯 줄이 다 다르다", len(set(ids)), 5)

# ── 결과 ────────────────────────────────────────
if fails:
    print("실패 %d" % len(fails))
    for f in fails:
        print("  - %s" % f)
    sys.exit(1)
print("통과. 시험 8 묶음")
