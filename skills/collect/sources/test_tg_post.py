#!/usr/bin/env python3
"""텔레그램 글 읽기 공통 자리 시험.

    python collect/sources/test_tg_post.py

**밖에 나가지 않는다.** 지어낸 글로만 돈다.
꼴은 2026-08-27 에 `t.me/breachdetect` 와 `t.me/osint_cti` 에서 실제로 본 것을 본떴다.
값은 전부 지어낸 것이라 실제 인물이나 조직이 아니다.

아래 넷은 **회귀 시험**이다. 실제로 한 번 틀렸던 자리다.

    7묶음  `Source` 가 대상 조직 칸에 들어갔다
    8묶음  제목이 50건 전부 `{` 였다
    9묶음  `author` 의 괄호를 안 벗겨 이름 대조가 깨졌다
    12묶음 채널이 보낸 JSON 이 깨져 있어 칸을 하나도 못 잡았다
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from collect.sources import tg_post  # noqa: E402

fails = []


def check(name: str, got, want) -> None:
    if got != want:
        fails.append("%s\n     받음 %r\n     기대 %r" % (name, got, want))


def item(text: str, links: list | None = None, src_id: str = "t/1"):
    return tg_post.to_item(
        chan="testchan", src_id=src_id, text=text, links=links or [],
        when="2026-08-26T23:00:00+00:00", perma="https://t.me/testchan/1",
        got_by="시험", body_via="시험")


# ── 재료 ────────────────────────────────────────
# breachdetect 꼴. JSON 뒤에 꼬리줄이 붙는다
JSON_DOM = ('{\n'
            '"Source": "example-forum[.]test",\n'
            '"Content": "Actor claims a database of a test company",\n'
            '"author": " (TestHandle)",\n'
            '"Detection Date": "26 August 2026",\n'
            '"Type": "Data leak"\n'
            '}\n🔹 시험채널/시험채널 🔹')

JSON_URL = ('{"Source": "https://example-forum.test/thread-1",\n'
            ' "Content": "A test victim listed",\n'
            ' "author": "TestGroup",\n'
            ' "Type": "ransomware"}')

JSON_ODD = '{"Type": "phishing kit", "Content": "A test kit offered"}'

# osint_cti 꼴
LABELED = ("⚠️ MEDIUM SEVERITY LEAK DETECTED ⚠️\n\n"
           "• Target/Title: example-target.test\n"
           "• Threat Actor: 👤 TestHandle\n"
           "• Country: 📍 Testland\n"
           "• Detection Date: 📅 26 August 2026")

# 랜섬 알림 꼴. **첫 줄이 채널 머리말이라 글마다 똑같다**
RANSOM_LABEL = ("🔒 New Ransomware Victim\n\n"
                "• Victim: TestCorp\n"
                "• Group: TestGroup\n"
                "• Country: 🇰🇷 South Korea")

# 칸은 잡히는데 대상 조직만 없는 글
NO_ORG = ("🛡 NEW HIGH SEVERITY CVE PUBLISHED\n\n"
          "• CVE ID: CVE-2026-00000\n"
          "• CVSS Score: 8.8")

PLAIN = "그냥 문장이다. 칸이 하나도 없다."

# 잘린 글 둘. 하나는 닫는 짝이 없고, 하나는 값이 망가졌다
CUT_OPEN = '{"Source": "example[.]test", "Content": "여기서 끊겼'
CUT_BAD = '{"Source": "example[.]test", "Content": 없는값}'

# ── 1. 꼴을 가른다 ──────────────────────────────
for name, text, want in (("JSON 도메인", JSON_DOM, "JSON"),
                         ("JSON 주소", JSON_URL, "JSON"),
                         ("라벨", LABELED, "라벨"),
                         ("글자만", PLAIN, "글자만"),
                         ("빈 글", "", "빈 글")):
    check("꼴 · " + name, tg_post.read_post(text)[1], want)

# ── 2. JSON 을 라벨보다 먼저 본다 ───────────────
# 라벨 정규식이 JSON 을 만나면 아무것도 못 잡는다. 그래서 순서가 중요하다
f, shape, note = tg_post.read_post(JSON_DOM)
check("칸 다섯", sorted(f), ["author", "content", "detection date", "source", "type"])
check("사유 없음", note, "")
check("꼬리줄이 칸을 안 만든다", "🔹 시험채널/시험채널 🔹" in str(f), False)

# ── 3. 잘린 글을 버리지 않는다 ──────────────────
for name, text in (("닫는 짝 없음", CUT_OPEN), ("값이 망가짐", CUT_BAD)):
    _, sh, nt = tg_post.read_post(text)
    if not nt:
        fails.append("%s · 잘렸는데 사유를 안 남겼다 (꼴 %s)" % (name, sh))
# 잘려도 항목은 나온다. 조용히 사라지면 안 된다
it_cut = item(CUT_OPEN)
check("잘려도 항목이 나온다", bool(it_cut.uid()), True)
if "잘렸" not in str(it_cut.raw.get("못 읽은 것", "")):
    fails.append("잘린 사유가 raw 에 안 남았다: %r" % it_cut.raw.get("못 읽은 것"))

# ── 4. 무력화 표기를 되돌린다 ───────────────────
# 그대로 두면 같은 글 판별이 깨진다. **저장은 원래 꼴로 한다**
check("점", tg_post.refang("example[.]test"), "example.test")
check("괄호 점", tg_post.refang("example(.)test"), "example.test")
check("hxxp", tg_post.refang("hxxp://example.test"), "http://example.test")
check("hxxps 콜론", tg_post.refang("hxxps[:]//example.test"), "https://example.test")
check("없으면 그대로", tg_post.refang("example.test"), "example.test")
check("빈칸", tg_post.refang(""), "")

# ── 5. 종류를 가른다. **거르지 않고 표시만 한다** ─
check("Data leak", tg_post.classify({"type": "Data leak"}), ("유출 알림", True))
check("ransomware", tg_post.classify({"type": "ransomware"}), ("랜섬 피해자", True))
check("대소문자 무시", tg_post.classify({"type": "DATA LEAK"}), ("유출 알림", True))
check("라벨 꼴 유출", tg_post.classify({"target/title": "x", "threat actor": "y"}),
      ("유출 알림", True))
check("CVE 는 대상 아님", tg_post.classify({"cve id": "x", "cvss score": "9"}),
      ("CVE 알림", False))
# 모르는 type 을 버리지 않는다. 무엇으로 왔는지 그대로 적는다
check("모르는 type", tg_post.classify({"type": "phishing kit"}),
      ("기타(phishing kit)", None))
check("칸이 없으면", tg_post.classify({}), ("기타", None))

# ── 6. 원 출처는 집계 채널 주소가 아니다 ────────
check("링크에서", tg_post.origin(["https://example-forum.test/x"], "", {}),
      "https://example-forum.test/x")
check("t.me 는 원 출처가 아니다",
      tg_post.origin(["https://t.me/testchan/1"], "", {}), "")
check("본문에서 줍기", tg_post.origin([], "보라 https://example-forum.test/y 끝", {}),
      "https://example-forum.test/y")
check("source 칸이 주소면 그것",
      tg_post.origin([], "", {"source": "hxxps://example-forum.test/z"}),
      "https://example-forum.test/z")
check("source 가 도메인이면 원 출처가 아니다",
      tg_post.origin([], "", {"source": "example-forum[.]test"}), "")
check("없으면 빈칸", tg_post.origin([], "아무것도 없다", {}), "")

# ── 7. `Source` 는 대상 조직이 아니다 ───────────
# 2026-08-27 실측 50건. `Source` 는 전부 도메인이나 주소였다.
# 대상 조직 칸에 넣었더니 출처 도메인이 피해자로 들어갔다
it = item(JSON_DOM)
check("대상 조직을 안 지어낸다", it.target_org, "")
check("대상 도메인도 비운다", it.target_domain, "")
check("출처 도메인은 venue 로", it.venue, "example-forum.test")
check("venue 종류", it.venue_kind, "forum")
check("성격은 확인 못 함", it.kind, "확인 못 함")

it_url = item(JSON_URL)
check("주소 꼴 원 출처", it_url.post_url, "https://example-forum.test/thread-1")
check("주소 꼴 venue", it_url.venue, "example-forum.test")
check("랜섬은 성격이 정해진다", it_url.kind, "랜섬웨어 유출")

# 라벨 꼴은 대상 조직이 실제로 있다
it_lab = item(LABELED)
check("라벨 꼴 대상", it_lab.target_org, "example-target.test")
check("도메인 꼴이면 도메인 칸에도", it_lab.target_domain, "example-target.test")
check("라벨 꼴 행위자", it_lab.actor, "TestHandle")
check("나라", it_lab.country, "Testland")
check("원 출처가 없으면 venue 는 채널", it_lab.venue, "t.me/testchan")
check("그때는 venue 종류가 텔레그램", it_lab.venue_kind, "telegram")

# ── 8. 제목이 `{` 가 아니다 ─────────────────────
# JSON 꼴은 첫 줄이 여는 중괄호다. 실측 50건이 전부 그랬다
check("JSON 제목", it.title, "Actor claims a database of a test company")
for name, t_ in (("JSON 도메인", it), ("JSON 주소", it_url)):
    if t_.title.startswith("{"):
        fails.append("%s · 제목이 중괄호다: %r" % (name, t_.title))

# ── 8-2. 라벨 꼴 제목이 채널 머리말이 아니다 ────
# 2026-09-22 실측. 노션에 들어간 텔레그램 19줄이 전부 머리말 셋 중 하나였다.
# 17줄이 「🔒 New Ransomware Victim」 이라 표에서 서로 구분이 안 됐다
check("랜섬 제목은 피해 조직", item(RANSOM_LABEL).title, "TestCorp")
check("라벨 제목도 대상", it_lab.title, "example-target.test")
check("대상이 없으면 첫 줄로 물러난다",
      item(NO_ORG).title, "🛡 NEW HIGH SEVERITY CVE PUBLISHED")
check("칸이 아예 없어도 첫 줄", item(PLAIN).title, PLAIN)
for name, t_ in (("랜섬", item(RANSOM_LABEL)), ("유출", it_lab)):
    if t_.title == t_.body.split("\n")[0]:
        fails.append("%s · 제목이 아직 머리말이다: %r" % (name, t_.title))

# ── 9. 값 앞뒤의 군더더기를 뗀다 ────────────────
check("괄호만 있는 것", tg_post.clean(" (TestHandle)"), "TestHandle")
check("가운데 괄호는 안 건드린다", tg_post.clean("A (B)"), "A (B)")
check("사람 이모지", tg_post.clean("👤 TestHandle"), "TestHandle")
check("깃발", tg_post.clean("🇰🇷 South Korea"), "South Korea")
check("글자 안의 것은 안 건드린다", tg_post.clean("A 👤 B"), "A 👤 B")
check("빈칸", tg_post.clean(""), "")
check("JSON 꼴 행위자", it.actor, "TestHandle")

# 무력화된 값이 어느 칸에 와도 되돌아온다
check("칸 값도 되돌린다",
      tg_post.first({"victim": "example[.]test"}, tg_post.PICK["org"]), "example.test")

# ── 10. 본문은 게시글 본문이 아니다 ─────────────
# 집계 채널이 쓴 글이다. ④ 마스킹이 이걸 원문으로 착각하면 안 된다
for name, t_ in (("JSON", it), ("라벨", it_lab)):
    check("%s · 본문 성격" % name, t_.body_kind, "집계 채널 글")
check("via 는 채널", it.via, ["t.me/testchan"])
check("집계 채널 주소를 남긴다", it.raw.get("집계 채널 글 주소"),
      "https://t.me/testchan/1")
# 칸을 하나도 안 버린다
check("본문 칸을 다 남긴다", sorted(it.raw["본문 칸"]),
      ["author", "content", "detection date", "source", "type"])

# ── 11. 줄이 안 뭉친다 ──────────────────────────
# 2026-08-27 에 스무 건이 열일곱 줄이 됐다. `src_id` 가 열쇠 맨 앞에 있어야 한다
uids = [item(JSON_ODD, src_id="testchan/%d" % n).uid() for n in range(5)]
check("다섯 줄이 다 다르다", len(set(uids)), 5)
# 대상도 출처도 없는 글끼리도 안 뭉친다
check("모르는 type 도 버리지 않는다",
      item(JSON_ODD).raw["글 종류"], "기타(phishing kit)")

# ── 12. 채널이 깨진 JSON 을 보내도 읽는다 ───────
# 2026-08-27 실측. 50건 중 1건이 `Content` 안에 HTML 링크를 그대로 넣어
# 따옴표 짝이 안 맞았다. **채널 잘못이지만 버릴 이유는 아니다**
BROKEN = ('{\n'
          '  "Source": "https://example-forum.test/",\n'
          '  "Content": "Is this a test claim or not?", \n'
          '  "author": "<a href="https://example-forum.test/u?id=1&x=2">TestHandle</a>",\n'
          '  "Detection Date": "26 August 2026",\n'
          '  "Type": "Data leak"\n'
          '}\n🔹 시험채널/시험채널 🔹')

f_b, sh_b, nt_b = tg_post.read_post(BROKEN)
check("깨진 것도 꼴이 붙는다", sh_b, "JSON(깨짐)")
check("칸을 다 건진다", sorted(f_b),
      ["author", "content", "detection date", "source", "type"])
if not nt_b:
    fails.append("깨졌는데 사유를 안 남겼다")

it_b = item(BROKEN)
check("깨져도 종류가 붙는다", it_b.raw["글 종류"], "유출 알림")
check("깨져도 우리 대상", it_b.raw["우리 대상"], True)
check("깨져도 원 출처", it_b.post_url, "https://example-forum.test/")
# 값에 든 HTML 태그는 벗긴다. 우리 표에 태그가 들어갈 자리가 없다
check("태그를 벗긴다", it_b.actor, "TestHandle")
for name, v in (("행위자", it_b.actor), ("제목", it_b.title),
                ("대상 조직", it_b.target_org)):
    if "<" in v or ">" in v:
        fails.append("%s 에 태그가 남았다: %r" % (name, v))
# 물음표로 끝나는 문장이 값이어도 잘리지 않는다
check("제목이 온전하다", it_b.title, "Is this a test claim or not?")

# 아주 깨져서 줄 단위로도 못 읽으면 그때 물러선다
f_w, sh_w, nt_w = tg_post.read_post("{이건 JSON 도 아니고 라벨도 아니다}")
check("더 못 읽으면 글자만", sh_w, "글자만")
check("그래도 사유는 남긴다", bool(nt_w), True)

# ── 결과 ────────────────────────────────────────
if fails:
    print("실패 %d" % len(fails))
    for f_ in fails:
        print("  - %s" % f_)
    sys.exit(1)
print("통과. 시험 12 묶음")
