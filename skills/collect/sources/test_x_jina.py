#!/usr/bin/env python3
"""X(Jina Reader) 수집기 시험.

    python collect/sources/test_x_jina.py

**밖에 나가지 않는다.** 가짜 Fetcher 와 지어낸 응답으로만 돈다.
응답 꼴은 2026-09-25 에 `r.jina.ai` 로 실제로 받은 것(프로필 1쪽 JSON · 단건 글)을 본떴다.
계정 · 글 · 조직 · 주소는 전부 지어낸 것이다. 레포가 공개다.
"""
from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from collect import fetch  # noqa: E402
from collect.sources import x_jina as xj  # noqa: E402

fails = []


def check(name: str, got, want) -> None:
    if got != want:
        fails.append("%s\n     받음 %r\n     기대 %r" % (name, got, want))


계정 = "TestCtiAcct"
남 = "SomeoneElse123"          # Jina 오류 문구에 들어오는 제3자 계정 자리. 로그에 나오면 안 된다
N1, N2, N3 = "2100000000000000001", "2100000000000000002", "2100000000000000003"


def 쪽(links) -> bytes:
    """프로필 1쪽. 글 셋 — 한국 신호 · 이미지 없음 · 한국 신호 없음."""
    content = (
        "Test CTI\n\n1K\n\nposts\n\n"
        "[![Image 1](https://pbs.twimg.com/x)](https://x.com/%s/header_photo)\n\n"
        "@%s\n\nThreat intel feed.\n\n"
        "*   [![Image 3](https://pbs.twimg.com/a)](https://x.com/%s) 🚨🇰🇷 Data Breach Alert: "
        "Fakecorp ([fakecorp.co.kr](https://fakecorp.co.kr/)) customer DB allegedly for sale on a forum. "
        "Threat Actor: Seller9 Records: 1,000,000 [![Image 4](https://pbs.twimg.com/b)]"
        "(https://x.com/%s/status/%s/photo/1)    \n"
        "*   [![Image 5](https://pbs.twimg.com/c)](https://x.com/%s) DDoS Alert: some city portal targeted\n"
        "*   [![Image 6](https://pbs.twimg.com/d)](https://x.com/%s) 📢 Ransomware Alert: 🇩🇪 Othercorp "
        "has reportedly fallen victim to GroupZ [![Image 7](https://pbs.twimg.com/e)]"
        "(https://x.com/%s/status/%s/photo/1)"
        % (계정, 계정, 계정, 계정, N1, 계정, 계정, 계정, N3))
    return json.dumps({"code": 200, "status": 20000, "data": {
        "title": "Test CTI (@%s) on X" % 계정, "url": "https://x.com/" + 계정,
        "content": content, "links": links}}).encode()


def 시각링크(묶음=list):
    쌍 = [["Log in", "https://x.com/i/flow/login"],
          ["", "https://x.com/%s/status/%s/photo/1" % (계정, N3)],
          ["2h", "https://x.com/%s/status/%s" % (계정, N1)],
          ["fakecorp.co.kr", "https://fakecorp.co.kr/"],
          ["3h", "https://x.com/%s/status/%s" % (계정, N2)],
          ["5h", "https://x.com/%s/status/%s" % (계정, N3)]]
    return 쌍 if 묶음 is list else {k: v for k, v in 쌍}


단건 = json.dumps({"code": 200, "status": 20000, "data": {
    "title": "Test CTI (@%s) on X" % 계정, "publishedTime": "2026-09-20T16:30:00.000Z",
    "content": (
        "[![Image 1](https://pbs.twimg.com/p)](https://x.com/%s)\n\n"
        "[Test CTI](https://x.com/%s)[@%s](https://x.com/%s)\n\n"
        "🚨🇰🇷 Data Breach Alert: Fakecorp ([fakecorp.co.kr](https://fakecorp.co.kr/)) customer DB "
        "allegedly for sale on a forum.\n• Threat Actor: Seller9\n• Records: 1,000,000\n\n"
        "[![Image 2](https://pbs.twimg.com/q)](https://x.com/%s/status/%s/photo/1)\n\n"
        "[4:30 PM · Sep 20, 2026](https://x.com/%s/status/%s)\n\n"
        "[1,234 Views](https://x.com/%s/status/%s)"
        % (계정, 계정, 계정, 계정, 계정, N1, 계정, N1, 계정, N1))}}).encode()

차단 = json.dumps({"data": None, "code": 403, "name": "AbuseAlleviationError", "status": 40305,
                 "message": "Anonymous access to domain x.com blocked due to abuse found on "
                            "https://x.com/%s: DDoS attack suspected" % 남}).encode()
잔액 = json.dumps({"data": None, "code": 402, "name": "InsufficientBalanceError",
                 "message": "Account uid-secret-000 has insufficient balance"}).encode()


class 가짜Fetcher:
    """주소마다 정해 둔 응답을 낸다. 실제 Fetcher 처럼 403 이면 본문을 버리고 이름만 남긴다."""

    def __init__(self, 답: dict, dry: bool = False):
        self.답, self.dry, self.부름, self.last_err = 답, dry, [], ""

    def get(self, url, params=None, accept="application/json", headers=None):
        self.부름.append((url, dict(headers or {})))
        self.last_err = ""
        code, 몸 = self.답.get(url, (404, b""))
        if code in (403, 429) or code >= 500:
            self.last_err = json.loads(몸).get("name", "") if 몸 else ""
            return code, b"", ""
        return code, 몸, "application/json"


def _프로필(계정=계정):
    return xj.READER + "https://x.com/" + 계정


def _단건(번호):
    return xj.READER + "https://x.com/%s/status/%s" % (계정, 번호)


# ── 1. 글 번호에서 게시 시각 ──────────────────────
# 2026-09-25 실측 단건 글의 Published Time 이 2025-10-30T05:30:50Z 였고, 그 글 번호다
check("글 번호 시각", xj.글시각("1983768536414876030"), "2025-10-30T05:30:50+00:00")
check("글 번호가 아니면 빈 값", xj.글시각("abc"), "")

# ── 2. 봉투 — HTTP 상태만 믿지 않는다 ──────────────
data, 이름 = xj.봉투(단건)
check("성공 봉투", (bool(data), 이름), (True, ""))
check("200 안의 오류 봉투", xj.봉투(차단)[1], "AbuseAlleviationError")
check("오류 이름에 문구가 안 섞인다", 남 in xj.봉투(차단)[1], False)
check("JSON 이 아니면", xj.봉투(b"<html>")[1], "JSON 아님")

# ── 3. 프로필 쪽 — 글 번호는 목록 줄 또는 시각 링크 차례 ─────
for 묶음 in (list, dict):
    글들, 까닭 = xj.쪽읽기(계정, json.loads(쪽(시각링크(묶음)))["data"])
    check("쪽 %s: 글 셋" % 묶음.__name__, [g["번호"] for g in 글들], [N1, N2, N3])
    check("쪽 %s: 까닭 없음" % 묶음.__name__, 까닭, "")
글들, _ = xj.쪽읽기(계정, json.loads(쪽(시각링크()))["data"])
check("이미지 주소가 글에 없다", any("pbs.twimg.com" in g["글"] for g in 글들), False)
check("링크는 글자로 남는다", "fakecorp.co.kr" in 글들[0]["글"], True)
check("외부 링크만 모은다", 글들[0]["링크들"], ["https://fakecorp.co.kr/"])
check("남의 계정 글은 안 잡는다", xj.쪽읽기("OtherAcct", json.loads(쪽(시각링크()))["data"])[0], [])
check("빈 쪽은 까닭을 낸다", xj.쪽읽기(계정, {"content": ""})[1], "쪽이 비었다")

# ── 4. 단건 — 이름 · 시각 · 조회수 줄을 뗀다 ───────
글, 링크들, when = xj.단건읽기(json.loads(단건)["data"])
check("단건 글 첫머리", 글.startswith("🚨🇰🇷 Data Breach Alert: Fakecorp"), True)
check("단건에 조회수 줄 없음", "Views" in 글, False)
check("단건에 시각 줄 없음", "4:30 PM" in 글, False)
check("단건 게시 시각", when, "2026-09-20T16:30:00.000Z")
check("단건 외부 링크", 링크들, ["https://fakecorp.co.kr/"])

# ── 5. 한국 신호 ──────────────────────────────
check("국기", xj.한국신호("🚨🇰🇷 Breach"), True)
check(".kr 도메인", xj.한국신호("leak of shop.example.kr"), True)
check("Korea 낱말", xj.한국신호("South Korea telecom"), True)
check("신호 없음", xj.한국신호("🇩🇪 Othercorp ransomware"), False)

# ── 6. 항목 모양 ──────────────────────────────
it = xj.to_item(계정=계정, 번호=N1, 글=글, 링크들=링크들, when=when, 잘림=False)
check("source", it.source, "x")
check("src_id", it.src_id, "%s/%s" % (계정, N1))
check("venue", (it.venue, it.venue_kind, it.via), ("x.com/" + 계정, "x", ["x.com/" + 계정]))
check("원 출처가 아니다", it.post_url, "")
check("X 글 주소는 raw 에", it.raw["X 글 주소"], "https://x.com/%s/status/%s" % (계정, N1))
check("규모는 칸에 안 넣는다", it.claimed_size, "")
check("규모는 raw 에", it.raw.get("주장 규모"), "1,000,000")
check("행위자 라벨", it.actor, "Seller9")
check("국가", it.country, "KR")
check("게시 시각은 단건 것", it.posted_at, "2026-09-20T16:30:00.000Z")
잘린 = xj.to_item(계정=계정, 번호=N3, 글="📢 Ransomware Alert: 🇩🇪 Othercorp", 링크들=[], when="", 잘림=True)
check("시각이 없으면 글 번호에서", 잘린.posted_at, xj.글시각(N3))
check("잘린 글 표시", "잘린 글" in 잘린.raw, True)

# ── 7. 한 판 — 한국 신호 글만 단건으로, 키는 머리에만 ───
f = 가짜Fetcher({_프로필(): (200, 쪽(시각링크())), _단건(N1): (200, 단건)})
셈: dict = {}
항목들 = list(xj.모으기([계정], "test-key-not-real", f=f, 셈=셈))
check("항목 셋", len(항목들), 3)
check("단건은 한국 신호 글 하나만", [u for u, _ in f.부름], [_프로필(), _단건(N1)])
check("키는 Authorization 머리로", f.부름[0][1].get("Authorization"), "Bearer test-key-not-real")
check("링크 요약 all", f.부름[0][1].get("X-With-Links-Summary"), "all")
check("쿠키 · 프록시 머리를 안 쓴다", any(k.lower() in ("x-set-cookie", "x-proxy") for _, h in f.부름 for k in h), False)
check("첫 항목은 전문", 항목들[0].raw.get("잘린 글") is None, True)
check("셈", (셈["계정"], 셈["쪽"], 셈["글"], 셈["단건"]), (1, 1, 3, 1))

# 차단 — 이름만 세고 문구는 어디에도 안 남는다
f = 가짜Fetcher({_프로필(): (403, 차단)})
셈 = {}
check("차단이면 항목 없음", list(xj.모으기([계정], "k", f=f, 셈=셈)), [])
check("차단 이름을 센다", 셈["오류"], {"AbuseAlleviationError": 1})
요 = xj.요약(셈)
check("요약에 제3자 계정이 없다", 남 in 요, False)
check("요약에 우리 계정 이름이 없다", 계정 in 요, False)

# 잔액 부족 — 그 판을 멈추고 다음 계정을 안 부른다
f = 가짜Fetcher({_프로필(): (402, 잔액), _프로필("SecondAcct"): (200, 쪽(시각링크()))})
셈 = {}
list(xj.모으기([계정, "SecondAcct"], "k", f=f, 셈=셈))
check("잔액 부족이면 멈춘다", len(f.부름), 1)
check("잔액 부족 표시", 셈.get("잔액 부족으로 멈춤"), 1)
check("요약에 우리 계정 id 가 없다", "uid-secret" in xj.요약(셈), False)

# 미리보기 — 요청을 안 보내고 오류도 안 센다
f = 가짜Fetcher({}, dry=True)
셈 = {}
check("미리보기는 항목 없음", list(xj.모으기([계정], "k", f=f, 셈=셈, dry=True)), [])
check("미리보기는 오류 없음", 셈["오류"], {})

# ── 8. 설정 파일 — 저장소 밖, 값을 안 찍는다 ───────
import os  # noqa: E402
import tempfile  # noqa: E402
with tempfile.TemporaryDirectory() as d:
    (Path(d) / "acc").write_text("# 주석\n@TestCtiAcct\n\nbad acct!\nTestCtiAcct\n", encoding="utf-8")
    (Path(d) / "key").write_text("  test-key-not-real \n", encoding="utf-8")
    os.environ["DARKCHOCO_X_ACCOUNTS"] = str(Path(d) / "acc")
    os.environ["DARKCHOCO_JINA_KEY_FILE"] = str(Path(d) / "key")
    check("계정 목록", xj.계정들(), ["TestCtiAcct"])
    check("키", xj.키읽기(), "test-key-not-real")
    os.environ["DARKCHOCO_X_ACCOUNTS"] = str(Path(d) / "없음")
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = xj.run(None, dry=False)
    check("계정이 없으면 건너뛴다", (rc, "볼 계정이 없다" in buf.getvalue()), (0, True))
    os.environ.pop("DARKCHOCO_X_ACCOUNTS")
    os.environ.pop("DARKCHOCO_JINA_KEY_FILE")

# ── 9. fetch.py — 실패한 응답에서 이름만 ───────────
class 가짜응답:
    def __init__(self, 몸):
        self.몸 = 몸

    def iter_content(self, n):
        yield self.몸[:n]


check("오류 이름", fetch._오류이름(가짜응답(차단)), "AbuseAlleviationError")
check("JSON 이 아니면 빈 이름", fetch._오류이름(가짜응답(b"<html>403</html>")), "")
check("이상한 이름은 버린다", fetch._오류이름(가짜응답(json.dumps({"name": "a b <c>"}).encode())), "")
check("Jina 간격 하한 3.5초", fetch.GAP["r.jina.ai"][0] >= 3.5, True)

# ── 10. 소스에 박힌 키가 없다 ──────────────────────
src = Path(xj.__file__).read_text(encoding="utf-8")
check("키 꼴 글자가 소스에 없다", "jina_" in src.replace("jina_key", ""), False)

# ── 11. 워크플로 — 비밀값은 파일로, 끝나면 지운다, 이름을 안 찍는다 ─────
wf = (Path(__file__).resolve().parents[3] / ".github" / "workflows" / "collect.yml").read_text(encoding="utf-8")
단계 = wf[wf.index("- name: X (Jina Reader)"):wf.index("- name: 긁은 것 세기")]
check("X 단계가 모듈을 부른다", "python -m collect.sources.x_jina --db" in 단계, True)
check("X 단계는 실패해도 판을 안 멈춘다", "continue-on-error: true" in 단계, True)
check("키는 파일로 준다", "DARKCHOCO_JINA_KEY_FILE: ${{ runner.temp }}/cfg/jina_key" in 단계, True)
check("키 파일은 600", 'chmod 600 "$RUNNER_TEMP/cfg/jina_key"' in wf, True)
정리 = wf[wf.index("- name: 표를 안 남긴다"):]
check("끝나면 키와 계정 목록을 지운다", "cfg/jina_key" in 정리 and "cfg/x_accounts" in 정리, True)
check("계정 목록을 찍지 않는다", "cat \"$RUNNER_TEMP/cfg/x_accounts\"" in wf, False)

# ── 결과 ────────────────────────────────────────
if fails:
    print("실패 %d" % len(fails))
    for f_ in fails:
        print("  - %s" % f_)
    sys.exit(1)
print("통과. 시험 11 묶음")
