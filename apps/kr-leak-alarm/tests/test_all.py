"""
tests/test_all.py — 의존성 없는 자체 테스트 러너.

실행: python -m tests.test_all   (프로젝트 루트에서)
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from collector.export import export                     # noqa: E402
from collector.http_client import (                    # noqa: E402
    BlockedHostError, HttpStatusError, NotFoundError, SafeHttpClient, _check_host,
)
from collector.kr_filter import TIER_SCORE, KrClassifier  # noqa: E402
from collector.safety import (                           # noqa: E402
    TorGateError, assert_tor_allowed, defang_url, extract_domain,
    detect_hypervisor, sanitize_text,
)
from collector.sources.base import LeakRecord, normalize_victim, parse_timestamp  # noqa: E402
from collector.sources.ransomlook import RansomLookSource   # noqa: E402
from collector.sources.ransomware_live import RansomwareLiveSource  # noqa: E402
from collector.store import Store                        # noqa: E402
from collector.supply_filter import (                 # noqa: E402
    TIER_SCORE as SUPPLY_SCORE, SupplyClassifier, load_vendors,
)
from tests.fixtures import (                          # noqa: E402
    DIRECT_VENDOR_CASE, MALICIOUS, MockClient, RANSOMLOOK, RANSOMWARE_LIVE_KR,
    SUPPLY_CASES, VENDORS_JSON,
)

PASS = FAIL = 0
FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  \033[32m✓\033[0m {name}")
    else:
        FAIL += 1
        FAILURES.append(f"{name} — {detail}")
        print(f"  \033[31m✗\033[0m {name}  {detail}")


def section(title: str) -> None:
    print(f"\n\033[1m── {title}\033[0m")


# ═══════════════════════════════════════════════════════════
def test_sanitize() -> None:
    section("1. 입력 살균 (safety.sanitize_text)")

    s = sanitize_text("</script><script>alert(1)</script>ACME Korea")
    check("스크립트 태그 제거", "<script>" not in s and "</script>" not in s, repr(s))
    check("본문 텍스트 보존", "ACME Korea" in s, repr(s))

    s2 = sanitize_text("&lt;script&gt;alert(2)&lt;/script&gt;")
    check("이중 인코딩 태그 제거", "<script" not in s2.lower(), repr(s2))

    s3 = sanitize_text("norm\x1b[31mal\x00text")
    check("제어문자/ANSI 제거", "\x1b" not in s3 and "\x00" not in s3, repr(s3))

    s4 = sanitize_text("safe\u202egnp.exe")
    check("BiDi override 제거", "\u202e" not in s4, repr(s4))

    s5 = sanitize_text("Z" * 50000)
    check("길이 상한 적용", len(s5) <= 2001, len(s5))

    s6 = sanitize_text('<img src=x onerror=alert(document.domain)>')
    check("이벤트 핸들러 태그 제거", "onerror" not in s6 or "<" not in s6, repr(s6))


def test_defang() -> None:
    section("2. URL 무력화 (defang)")

    d = defang_url("http://abc123.onion/site/blog?uuid=1")
    check("스킴 무력화", d.startswith("hxxp://"), d)
    check("점 무력화", ".onion" not in d and "[.]onion" in d, d)

    d2 = defang_url("https://evil.tld/x")
    check("https → hxxps", d2.startswith("hxxps://"), d2)

    for scheme in ("javascript:alert(1)", "data:text/html,<script>x</script>",
                   "vbscript:msgbox(1)", "file:///C:/Windows/system32/calc.exe"):
        out = defang_url(scheme)
        name = scheme.split(":")[0]
        check(f"위험 스킴 무력화: {name}:", f"{name}[:]" in out and f"{name}:" not in out, out)

    check("도메인 추출(www 제거)", extract_domain("www.higen.co.kr") == "higen.co.kr")
    check("URL 에서 도메인 추출", extract_domain("http://a.b.co.kr/path?x=1") == "a.b.co.kr")
    check("빈 입력 처리", extract_domain(None) == "" and defang_url(None) == "")


def test_http_allowlist() -> None:
    section("3. 네트워크 허용목록 (SSRF/피벗 차단)")

    ok = True
    try:
        _check_host("https://api.ransomware.live/v2/groups")
    except Exception as e:
        ok = False
        print(e)
    check("허용 호스트 통과", ok)

    for bad, label in [
        ("https://evil.tld/x", "임의 외부 호스트"),
        ("http://api.ransomware.live/v2", "평문 HTTP"),
        ("https://127.0.0.1:8080/", "로컬호스트(SSRF)"),
        ("https://169.254.169.254/latest/meta-data/", "클라우드 메타데이터"),
        ("https://api.ransomware.live.evil.tld/", "서브도메인 위장"),
        ("file:///etc/passwd", "file 스킴"),
    ]:
        blocked = False
        try:
            _check_host(bad)
        except BlockedHostError:
            blocked = True
        except Exception:
            blocked = True
        check(f"차단: {label}", blocked, bad)


def test_kr_filter() -> None:
    section("4. 한국 관련성 판별")

    clf = KrClassifier({"min_tier_to_report": "review"})

    def cls(victim="", website="", country="", desc="", group="x"):
        rec = LeakRecord(victim=victim, website=website, country=country,
                         description=desc, group=group).finalize()
        return clf.classify(rec)

    t, s, r = cls(victim="HIGEN MOTOR", website="www.higen.co.kr", country="KR")
    check("country=KR → confirmed", t == "confirmed", f"{t} {r}")

    t, s, r = cls(victim="Some Co", website="somecorp.co.kr")
    check(".co.kr → strong", t == "strong", f"{t} {r}")

    t, s, r = cls(victim="Hanmi Pharm", website="hanmi-pharm.com")
    check("한국 기업명 → likely 이상", t in ("likely", "strong"), f"{t} {r}")

    t, s, r = cls(victim="㈜대한테크놀로지")
    check("한글 기업명 → likely", t == "likely", f"{t} {r}")

    t, s, r = cls(victim="Global Logistics Inc", desc="Operations across Asia including Korea and Japan")
    check("설명문 언급만 → review", t == "review", f"{t} {r}")

    # ── 오탐 방어 ──
    t, s, r = cls(victim="Nokia Siemens Networks")
    check("오탐 방어: Nokia ≠ kia", t == "none", f"{t} {r}")

    t, s, r = cls(victim="Pyongyang Trading Co", desc="North Korea based entity")
    check("북한 관련 제외", t == "none", f"{t} {r}")

    t, s, r = cls(victim="Koreatown Dental Group", desc="Los Angeles clinic")
    check("Koreatown 제외", t == "none", f"{t} {r}")

    t, s, r = cls(victim="Random Corp", website="random.com", desc="nothing relevant")
    check("무관 건 제외", t == "none", f"{t} {r}")

    # 임계값 동작
    clf2 = KrClassifier({"min_tier_to_report": "likely"})
    check("임계값 likely: review 는 제외", not clf2.meets_threshold("review"))
    check("임계값 likely: strong 은 포함", clf2.meets_threshold("strong"))


def test_normalize_dedup() -> None:
    section("5. 정규화 및 중복 제거")

    a = LeakRecord(victim="HIGEN MOTOR(critical data)", website="www.higen.co.kr",
                   group="qilin", source="a").finalize()
    b = LeakRecord(victim="www.higen.co.kr", website="", group="Qilin", source="b").finalize()
    check("동일 피해자 uid 일치", a.uid == b.uid, f"{a.uid} vs {b.uid} ({a.victim_key}/{b.victim_key})")

    c = LeakRecord(victim="Acme", group="lockbit3", source="a").finalize()
    d = LeakRecord(victim="Acme Co., Ltd.", group="LockBit", source="b").finalize()
    check("그룹 별칭 통합 + 법인격 제거", c.uid == d.uid, f"{c.group_key}/{c.victim_key} vs {d.group_key}/{d.victim_key}")

    e = LeakRecord(victim="Acme", group="play", source="a").finalize()
    check("다른 그룹은 별건 유지", e.uid != c.uid)

    check("ISO 타임스탬프", parse_timestamp("2026-08-10T19:39:24.349878+00:00").startswith("2026-08-10"))
    check("naive 타임스탬프", parse_timestamp("2026-08-15 14:27:17.327011").startswith("2026-08-15"))
    check("RFC822 타임스탬프", parse_timestamp("Fri, 14 Aug 2026 11:21:21 +0200").startswith("2026-08-14"))
    check("잘못된 값 → 빈 문자열", parse_timestamp("garbage!!") == "" and parse_timestamp(None) == "")
    check("normalize_victim 안정성", normalize_victim("  ") == "")


def test_pipeline_and_store() -> None:
    section("6. 파이프라인 · 저장소 · NEW 상태")

    client = MockClient({
        "countryvictims/KR": RANSOMWARE_LIVE_KR + MALICIOUS,
        "recentvictims": [],
        "/recent": RANSOMLOOK,
    })

    rl = RansomwareLiveSource(client, {"modes": ["country"], "country_codes": ["KR"]})
    lk = RansomLookSource(client, {})
    records = list(rl.fetch()) + list(lk.fetch())
    check("수집 건수", len(records) == len(RANSOMWARE_LIVE_KR) + len(MALICIOUS) + len(RANSOMLOOK), len(records))

    clf = KrClassifier({"min_tier_to_report": "likely"})
    matched = []
    for rec in records:
        t, s, r = clf.classify(rec)
        rec.kr_tier, rec.kr_score, rec.kr_reasons = t, s, r
        if clf.meets_threshold(t):
            matched.append(rec)

    names = [m.victim for m in matched]
    check("한국 건 매칭됨", any("HIGEN" in n for n in names), names[:5])
    check("오탐 제외됨(Nokia/Pyongyang/Koreatown)",
          not any(k in " ".join(names) for k in ("Nokia", "Pyongyang", "Koreatown")), names)

    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "t.db"
        web = Path(tmp) / "web"

        with Store(db) as store:
            check("최초 실행 감지", store.is_first_run())
            newly = store.upsert_many(matched)
            check("최초 적재 = 전부 신규", len(newly) == len({m.uid for m in matched}),
                  f"{len(newly)} vs {len({m.uid for m in matched})}")

            # 중복 재수집 → 신규 0
            again = store.upsert_many(matched)
            check("재실행 시 신규 0건", len(again) == 0, len(again))

            # 새 건 1개 추가
            fresh = LeakRecord(victim="Newvictim Korea", website="newvic.co.kr",
                               group="akira", country="KR", source="test").finalize()
            t, s, r = clf.classify(fresh)
            fresh.kr_tier, fresh.kr_score, fresh.kr_reasons = t, s, r
            third = store.upsert_many([fresh])
            check("신규 1건 정확히 검출", len(third) == 1 and third[0]["victim"] == "Newvictim Korea", third)

            # 크로스소스 병합 확인
            higen = [v for v in store.list_victims() if "higen" in (v["website"] or "")]
            check("크로스소스 병합(중복 아님)", len(higen) == 1, [h["victim"] for h in higen])
            if higen:
                check("소스 2개 병합됨", len(higen[0]["sources"]) >= 2, higen[0]["sources"])

            st = store.stats()
            check("통계 집계 동작", st["total"] > 0 and st["new"] > 0, st)

            n = store.acknowledge()
            check("전체 읽음 처리", n > 0 and store.stats()["new"] == 0, n)

            payload = export(store, web, min_score=TIER_SCORE["likely"])
            return _check_export(web, payload)


def _check_export(web: Path, payload: dict) -> None:
    section("7. 웹 데이터 내보내기 (XSS 방어)")

    data_js = (web / "data.js").read_text(encoding="utf-8")
    latest = json.loads((web / "latest.json").read_text(encoding="utf-8"))

    check("data.js 생성", data_js.startswith("/*") and "window.KRLEAK" in data_js)
    check("latest.json 생성", latest["schema_version"] == 1 and "items" in latest)

    check("data.js 에 </script> 조각 없음", "</script>" not in data_js)
    check("data.js 에 살아있는 <script 태그 없음", "<script>" not in data_js)

    blob = json.dumps(latest, ensure_ascii=False)
    check("페이로드에 onerror= 없음", "onerror=" not in blob)
    check("페이로드에 javascript: 스킴 없음", "javascript:" not in blob.lower())

    onion_items = [i for i in latest["items"] if i["post_is_onion"]]
    check("onion 항목 존재", len(onion_items) > 0, len(onion_items))
    for i in onion_items:
        if ".onion" in i["post_url_defanged"] or i["post_url_defanged"].startswith("http"):
            check("onion URL 무력화", False, i["post_url_defanged"])
            break
    else:
        check("onion URL 전부 무력화", True)

    check("모든 항목에 판별 근거 존재",
          all(i["reasons"] for i in latest["items"] if i["tier"] != "none"))

    # 초대형 필드 절단 확인
    check("초대형 필드 절단됨",
          all(len(i["description"]) <= 1201 and len(i["victim"]) <= 301 for i in latest["items"]))


def test_sql_injection() -> None:
    section("8. SQL 인젝션 방어")

    with tempfile.TemporaryDirectory() as tmp:
        with Store(Path(tmp) / "inj.db") as store:
            evil = LeakRecord(
                victim="x'; DROP TABLE victims;--",
                group="g'; DELETE FROM victims WHERE '1'='1",
                website="a.co.kr", source="t",
            ).finalize()
            evil.kr_tier, evil.kr_score, evil.kr_reasons = "strong", 80, ["test"]
            store.upsert_many([evil])
            store.acknowledge(["'; DROP TABLE victims;--"])
            rows = store.list_victims()
            check("테이블 보존됨", len(rows) == 1, len(rows))
            check("악성 문자열이 데이터로만 저장됨", "DROP TABLE" in rows[0]["victim"])
            check("stats 정상 동작", store.stats()["total"] == 1)


def test_tor_gate() -> None:
    section("9. Tor 게이트 (호스트 보호의 핵심)")

    base = {"tor": {"enabled": False, "require_vmware": True}}
    blocked = False
    try:
        assert_tor_allowed(base, acknowledged=True)
    except TorGateError as e:
        blocked = "게이트1" in str(e)
    check("게이트1: config 비활성 시 차단", blocked)

    base2 = {"tor": {"enabled": True, "require_vmware": True}}
    blocked = False
    try:
        assert_tor_allowed(base2, acknowledged=False)
    except TorGateError as e:
        blocked = "게이트2" in str(e)
    check("게이트2: 동의 플래그 없으면 차단", blocked)

    env = detect_hypervisor()
    print(f"      (현재 환경: {env['system']} / vendor={env['vendor']!r} / VMware={env['is_vmware']})")
    if not env["is_vmware"]:
        blocked = False
        try:
            assert_tor_allowed(base2, acknowledged=True)
        except TorGateError as e:
            blocked = "게이트3" in str(e)
        check("게이트3: VMware 아니면 차단", blocked)
    else:
        check("게이트3: (현재 VMware 환경이라 통과 확인 생략)", True)

    # 모듈이 기본 경로에서 임포트되지 않는지
    check("tor 모듈이 기본 실행에 로드되지 않음", "tor.onion_crawler" not in sys.modules)


def test_onion_host_guard() -> None:
    section("10. Tor 크롤러 호스트 가드")

    from tor.onion_crawler import _check_socks_reachable, html_to_text

    ok, msg = _check_socks_reachable("socks5h://8.8.8.8:9050")
    check("원격 SOCKS 프록시 거부", not ok, msg)

    text = html_to_text(
        "<html><head><style>body{}</style><script>alert(1)</script></head>"
        "<body><h1>Victims</h1><p>ACME Korea</p><iframe src=x></iframe></body></html>"
    )
    check("스크립트/스타일 제거", "alert" not in text and "body{}" not in text, repr(text))
    check("본문 텍스트 유지", "ACME Korea" in text, repr(text))
    check("태그 전부 제거", "<" not in text, repr(text))


def test_api_schema_and_404() -> None:
    section("15. API 스키마 호환 · 404 처리 (실제 장애 회귀 테스트)")

    src = RansomwareLiveSource(MockClient({}), {})

    # ── 엔드포인트별 필드 이름이 다르다 ──
    country_style = {
        "post_title": "DL E&C", "group_name": "qilin", "country": "KR",
        "activity": "Manufacturing", "website": "dlenc.co.kr",
        "post_url": "http://pnzruro7.onion/company/dl-e-c",
        "published": "2026-08-10T00:00:00+00:00",
        "discovered": "2026-08-10T01:00:00+00:00", "description": "x",
    }
    rec = src._to_record(country_style)
    check("countryvictims 스키마 파싱", rec.victim == "DL E&C" and rec.group == "qilin", rec.victim)
    check("countryvictims 도메인", rec.website == "dlenc.co.kr", rec.website)
    check("countryvictims 원문 URL", ".onion" in rec.post_url, rec.post_url)

    recent_style = {
        "victim": "Integraduanas", "group": "qilin", "country": "UY",
        "activity": "Not Found", "domain": "www.integraduanas.com",
        "claim_url": "http://ijzn3sic.onion/site/blog?uuid=49409db9",
        "attackdate": "2026-08-19T09:30:28+00:00",
        "discovered": "2026-08-19T09:31:14+00:00", "description": "N/A",
    }
    rec2 = src._to_record(recent_style)
    check("recentvictims 스키마 파싱", rec2.victim == "Integraduanas" and rec2.group == "qilin", rec2.victim)
    check("★ recentvictims domain 필드 인식", rec2.website == "integraduanas.com", rec2.website)
    check("★ recentvictims claim_url 필드 인식", ".onion" in rec2.post_url, rec2.post_url)
    check("★ recentvictims attackdate 필드 인식",
          rec2.published.startswith("2026-08-19"), rec2.published)

    # 도메인이 살아야 .kr 판별이 동작한다 (이게 깨지면 한국 기업을 놓친다)
    kr_recent = dict(recent_style, victim="어떤회사", domain="somecorp.co.kr", country="")
    rec3 = src._to_record(kr_recent)
    kr = KrClassifier({"min_tier_to_report": "likely"})
    tier, _, reasons = kr.classify(rec3)
    check("★ recentvictims 건도 .kr 도메인으로 판별됨", tier == "strong", f"{tier} {reasons}")

    # ── 404 는 '결과 없음' 이지 오류가 아니다 ──
    class Search404Client(MockClient):
        def __init__(self):
            super().__init__({})
            self.hits = 0

        def get_json(self, url):
            self.hits += 1
            if "searchvictims/hyundai" in url:
                return [country_style]
            if "searchvictims" in url:
                raise NotFoundError()
            return []

    c = Search404Client()
    src2 = RansomwareLiveSource(c, {
        "modes": ["vendor_search"],
        "vendor_terms": ["moveit", "hyundai", "accellion", "snowflake"],
        "vendor_search_per_run": 4, "vendor_search_delay_seconds": 0,
    })
    got = list(src2.fetch())
    check("검색 404 를 결과없음으로 처리 (예외 전파 안 함)", len(got) == 1, len(got))
    check("404 여도 소스 오류로 기록하지 않음", src2.errors == [], src2.errors)
    check("호출 횟수 = 검색어 수 (404 재시도 없음)", c.hits == 4, c.hits)

    # ── 커서 순회 ──
    check("커서 다음 위치 저장", src2.next_vendor_cursor == 0, src2.next_vendor_cursor)
    src3 = RansomwareLiveSource(Search404Client(), {
        "modes": ["vendor_search"], "vendor_terms": ["a1111", "b2222", "c3333", "d4444"],
        "vendor_search_per_run": 2, "vendor_search_delay_seconds": 0, "_vendor_cursor": 0,
    })
    list(src3.fetch())
    check("커서 전진 (2개씩)", src3.next_vendor_cursor == 2, src3.next_vendor_cursor)

    # ── 4xx 재시도 금지 ──
    import collector.http_client as hc

    calls = {"n": 0}

    class FakeClient(SafeHttpClient):
        def _get_once(self, url, extra_headers):
            calls["n"] += 1
            raise NotFoundError()

    fc = FakeClient({"retries": 2})
    raised = False
    try:
        fc.get_bytes("https://api.ransomware.live/v2/searchvictims/x")
    except NotFoundError:
        raised = True
    fc.close()
    check("★ 404 는 재시도하지 않음 (1회만 호출)", calls["n"] == 1 and raised, calls["n"])

    calls["n"] = 0

    class Fake429(SafeHttpClient):
        def _get_once(self, url, extra_headers):
            calls["n"] += 1
            raise HttpStatusError(429, "rate limit")

    f2 = Fake429({"retries": 1})
    try:
        f2.get_bytes("https://api.ransomware.live/v2/recentvictims")
    except Exception:
        pass
    f2.close()
    check("429 는 재시도함", calls["n"] == 2, calls["n"])


def test_rate_limit_guards() -> None:
    section("16. 레이트리밋 방어 (어제 IP 차단 회귀 테스트)")

    # ── 회로 차단기: 핵심 조회가 전부 실패하면 벤더 검색을 아예 하지 않는다 ──
    class AllBlockedClient(MockClient):
        def __init__(self):
            super().__init__({})
            self.search_calls = 0
            self.core_calls = 0

        def get_json(self, url):
            if "searchvictims" in url:
                self.search_calls += 1
                raise NotFoundError()
            self.core_calls += 1
            raise NotFoundError()

    c = AllBlockedClient()
    src = RansomwareLiveSource(c, {
        "modes": ["country", "recent", "vendor_search"],
        "country_codes": ["KR"],
        "vendor_terms": ["alpha1", "beta22", "gamma3", "delta4", "eps555"],
        "vendor_search_per_run": 5, "vendor_search_delay_seconds": 0,
    })
    got = list(src.fetch())
    check("차단 상태 감지", src.rate_limited is True)
    check("★ 핵심 조회 실패 시 벤더 검색 0회 (추가 요청 안 함)", c.search_calls == 0, c.search_calls)
    check("핵심 조회는 시도됨", c.core_calls == 2, c.core_calls)
    check("결과 없음", got == [])

    # ── 벤더 검색 도중 연속 실패하면 중단 ──
    class FailAfterClient(MockClient):
        def __init__(self, ok_until):
            super().__init__({})
            self.ok_until = ok_until
            self.search_calls = 0

        def get_json(self, url):
            if "searchvictims" not in url:
                return []          # 핵심 조회는 성공(빈 결과)
            self.search_calls += 1
            if self.search_calls > self.ok_until:
                raise HttpStatusError(500, "boom")
            raise NotFoundError()  # 결과 없음 = 정상

    c2 = FailAfterClient(ok_until=1)
    src2 = RansomwareLiveSource(c2, {
        "modes": ["country", "recent", "vendor_search"],
        "country_codes": ["KR"],
        "vendor_terms": [f"term{i:03d}" for i in range(20)],
        "vendor_search_per_run": 20, "vendor_search_delay_seconds": 0,
    })
    list(src2.fetch())
    check("★ 연속 실패 시 조기 중단 (20개 다 쏘지 않음)", c2.search_calls < 8, c2.search_calls)
    check("조기 중단 시 차단 상태로 표시", src2.rate_limited is True)

    # ── --no-vendor-search ──
    class CountingClient(MockClient):
        def __init__(self):
            super().__init__({})
            self.search_calls = 0

        def get_json(self, url):
            if "searchvictims" in url:
                self.search_calls += 1
            return []

    c3 = CountingClient()
    src3 = RansomwareLiveSource(c3, {
        "modes": ["country", "recent", "vendor_search"],
        "country_codes": ["KR"], "vendor_terms": ["aaaaa", "bbbbb"],
        "vendor_search_per_run": 2, "vendor_search_delay_seconds": 0,
        "_skip_vendor_search": True,
    })
    list(src3.fetch())
    check("--no-vendor-search 로 검색 완전 차단", c3.search_calls == 0, c3.search_calls)

    # ── 커서는 실패 지점부터 재개 ──
    c4 = FailAfterClient(ok_until=0)
    src4 = RansomwareLiveSource(c4, {
        "modes": ["vendor_search"],
        "vendor_terms": [f"t{i:03d}" for i in range(10)],
        "vendor_search_per_run": 10, "vendor_search_delay_seconds": 0,
        "_vendor_cursor": 0,
    })
    list(src4.fetch())
    check("중단 지점부터 재개하도록 커서 저장",
          0 <= src4.next_vendor_cursor <= 5, src4.next_vendor_cursor)


def test_resync_guard() -> None:
    section("17. 재동기화 알림 폭주 방지")

    from collector.notify import filter_for_notification

    # DB 를 지운 뒤 150건이 한꺼번에 들어오는 상황을 재현
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "resync.db"
        kr = KrClassifier({"min_tier_to_report": "likely"})

        def make(n, prefix):
            out = []
            for i in range(n):
                rec = LeakRecord(victim=f"{prefix}회사{i}", website=f"{prefix}{i}.co.kr",
                                 group="qilin", country="KR", source="t").finalize()
                rec.kr_tier, rec.kr_score, rec.kr_reasons = kr.classify(rec)
                rec.supply_tier, rec.supply_score, rec.supply_reasons = "none", 0, []
                out.append(rec)
            return out

        with Store(db) as store:
            # 1) 소량만 들어간 상태 (API 차단으로 2건만 받은 상황)
            store.upsert_many(make(2, "a"))
            store.acknowledge()
            check("초기 상태: 미확인 0건", store.stats()["new"] == 0)

            # 2) API 복구 후 150건 유입
            newly = store.upsert_many(make(150, "b"))
            check("150건이 신규로 잡힘", len(newly) == 150, len(newly))

            # 3) 임계값(30) 초과 → 기준선 처리
            surge_limit = 30
            baseline = len(newly) > surge_limit
            check("★ 임계값 초과를 재동기화로 판정", baseline is True)

            if baseline:
                store.acknowledge()
            check("★ 재동기화 후 미확인 0건 (토스트 폭주 없음)",
                  store.stats()["new"] == 0, store.stats()["new"])
            check("데이터 자체는 정상 보존", store.stats()["total"] == 152,
                  store.stats()["total"])

            # 4) 그 뒤 정상 신규 2건은 알림이 가야 한다
            after = store.upsert_many(make(2, "c"))
            check("이후 소량 신규는 정상 알림 대상", len(after) == 2 and len(after) <= surge_limit,
                  len(after))
            notify = filter_for_notification(after, {"supply_min_tier": "critical"})
            check("알림 필터 통과", len(notify) == 2, len(notify))


def test_supply_chain() -> None:
    section("12. 공급망 위험 판별 (2번째 축)")

    clf = SupplyClassifier({"min_tier_to_store": "sector"})

    def cls(victim="", website="", country="", desc="", sector="", group="x"):
        rec = LeakRecord(victim=victim, website=website, country=country,
                         description=desc, sector=sector, group=group).finalize()
        return clf.classify(rec)

    t, s, r = cls(victim="Progress Software MOVEit", website="progress.com", country="US")
    check("글로벌 핵심 벤더(MOVEit) → critical", t == "critical", f"{t} {r}")

    t, s, r = cls(victim="Snowflake Inc", website="snowflake.com", country="US")
    check("클라우드 데이터 벤더 → critical", t == "critical", f"{t} {r}")

    t, s, r = cls(victim="TSMC supplier", website="tsmc.com", country="TW")
    check("반도체 공급망 → critical", t == "critical", f"{t} {r}")

    t, s, r = cls(victim="Continental Korea Ltd", website="continental-korea.com", country="DE")
    check("해외기업 한국법인 → korea_ops 이상", t in ("korea_ops", "critical"), f"{t} {r}")

    t, s, r = cls(victim="Acme Regional IT", website="acme-it.sg", country="SG",
                  desc="We are a managed service provider for regional enterprises")
    check("MSP 업종 지표 → sector", t == "sector", f"{t} {r}")

    # ── 오탐 방어 ──
    t, s, r = cls(victim="Padaria Silva", website="padariasilva.com.br", country="BR",
                  desc="local bakery chain")
    check("무관 소매업 제외", t == "none", f"{t} {r}")

    t, s, r = cls(victim="Boulangerie Dupont", website="dupont-boulangerie.fr",
                  country="FR", desc="small shop", group="Barracuda")
    check("★ 그룹명 Barracuda 가 벤더 매칭에 안 걸림", t == "none", f"{t} {r}")

    t, s, r = cls(victim="Negozio Rossi", website="rossi.it", country="IT",
                  desc="shop", group="titan")
    check("★ 그룹명 titan 이 벤더 매칭에 안 걸림", t == "none", f"{t} {r}")

    t, s, r = cls(victim="Oklahoma City Dental", website="okc-dental.com", country="US")
    check("단어경계: 'kla' 가 Oklahoma 에 안 걸림", t == "none", f"{t} {r}")

    t, s, r = cls(victim="Seoul Bakery", website="bakery.co.kr", country="KR")
    check("국내 건은 공급망 축에서 korea_ops 아님", t != "korea_ops", f"{t} {r}")

    # ── 사용자 벤더 목록 ──
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "vendors.json").write_text(
            json.dumps(VENDORS_JSON, ensure_ascii=False), encoding="utf-8")

        vendors = load_vendors(root)
        check("vendors.json 로드", len(vendors) == 2, vendors)

        clf2 = SupplyClassifier({"min_tier_to_store": "sector"}, root=root)
        rec = LeakRecord(
            victim=DIRECT_VENDOR_CASE["post_title"], website=DIRECT_VENDOR_CASE["website"],
            country=DIRECT_VENDOR_CASE["country"], group="qilin",
        ).finalize()
        tt, ss, rr = clf2.classify(rec)
        check("직거래 협력사 → direct(최상위)", tt == "direct" and ss == 100, f"{tt} {rr}")
        check("직거래 근거에 영향 메모 포함",
              any("생산 ERP" in x for x in rr), rr)

        rec2 = LeakRecord(victim="Nova Forwarding Ltd", website="nova-forwarding.com",
                          country="SG", group="play").finalize()
        tt2, _, rr2 = clf2.classify(rec2)
        check("도메인 매칭으로도 direct 판정", tt2 == "direct", f"{tt2} {rr2}")

        # 없는 회사는 안 걸려야 함
        rec3 = LeakRecord(victim="Zetamax Unrelated", website="zetamax.com",
                          country="US", group="play").finalize()
        tt3, _, _ = clf2.classify(rec3)
        check("유사 철자 회사는 direct 아님", tt3 != "direct", tt3)

    # ── 비활성화 ──
    off = SupplyClassifier({"enabled": False})
    t4, s4, _ = off.classify(LeakRecord(victim="Snowflake Inc", website="snowflake.com").finalize())
    check("공급망 판별 비활성화 동작", t4 == "none" and s4 == 0)


def test_dual_axis_storage() -> None:
    section("13. 이중 축 저장 · 마이그레이션")

    client = MockClient({"countryvictims/KR": RANSOMWARE_LIVE_KR,
                         "recentvictims": SUPPLY_CASES, "/recent": []})
    rl = RansomwareLiveSource(client, {"modes": ["country", "recent"],
                                       "country_codes": ["KR"],
                                       "recent_lookback_days": 3650})
    records = list(rl.fetch())

    kr = KrClassifier({"min_tier_to_report": "likely"})
    sup = SupplyClassifier({"min_tier_to_store": "sector"})

    matched = []
    for rec in records:
        rec.kr_tier, rec.kr_score, rec.kr_reasons = kr.classify(rec)
        rec.supply_tier, rec.supply_score, rec.supply_reasons = sup.classify(rec)
        if kr.meets_threshold(rec.kr_tier) or sup.meets_threshold(rec.supply_tier):
            matched.append(rec)

    names = " ".join(m.victim for m in matched)
    check("한국 건 유지", "HIGEN" in names, names[:80])
    check("공급망 건 추가 포착", "Snowflake" in names and "MOVEit" in names, names[:120])
    check("무관 건은 여전히 제외", "Padaria" not in names and "Rossi" not in names, names[:120])

    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "dual.db"

        # ── 구버전 스키마 DB 를 만들어 마이그레이션을 검증한다 ──
        import sqlite3
        legacy = sqlite3.connect(str(db))
        legacy.executescript("""
            CREATE TABLE victims (
                uid TEXT PRIMARY KEY, victim TEXT NOT NULL, victim_key TEXT NOT NULL,
                group_name TEXT NOT NULL, group_key TEXT NOT NULL, country TEXT DEFAULT '',
                sector TEXT DEFAULT '', website TEXT DEFAULT '', description TEXT DEFAULT '',
                published TEXT DEFAULT '', discovered TEXT DEFAULT '', post_url TEXT DEFAULT '',
                sources TEXT DEFAULT '[]', kr_tier TEXT DEFAULT 'none', kr_score INTEGER DEFAULT 0,
                kr_reasons TEXT DEFAULT '[]', first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
                is_new INTEGER NOT NULL DEFAULT 1, acknowledged_at TEXT DEFAULT '');
            INSERT INTO victims (uid,victim,victim_key,group_name,group_key,kr_tier,kr_score,
                                 first_seen,last_seen,is_new)
            VALUES ('legacy1','옛날기업','legacy','qilin','qilin','confirmed',100,
                    '2026-01-01T00:00:00+00:00','2026-01-01T00:00:00+00:00',0);
        """)
        legacy.commit(); legacy.close()

        with Store(db) as store:
            cols = {r["name"] for r in store.conn.execute("PRAGMA table_info(victims)")}
            check("마이그레이션: supply_* 컬럼 추가됨",
                  {"supply_tier", "supply_score", "supply_reasons"} <= cols, sorted(cols))

            old = store.conn.execute("SELECT * FROM victims WHERE uid='legacy1'").fetchone()
            check("마이그레이션: 기존 행 보존", old is not None and old["victim"] == "옛날기업")
            check("마이그레이션: 기존 KR 등급 유지", old["kr_tier"] == "confirmed")

            newly = store.upsert_many(matched)
            check("이중 축 저장 성공", len(newly) == len({m.uid for m in matched}),
                  f"{len(newly)} vs {len({m.uid for m in matched})}")

            st = store.stats()
            check("공급망 통계 집계", st.get("supply_total", 0) >= 3, st.get("by_supply"))
            check("핵심벤더 카운트", st.get("supply_critical", 0) >= 2, st.get("by_supply"))

            # OR 조회 확인
            kr_only = store.list_victims(min_score=60, min_supply_score=10_000)
            both = store.list_victims(min_score=60, min_supply_score=SUPPLY_SCORE["sector"])
            check("OR 조회: 공급망 포함 시 건수 증가", len(both) > len(kr_only),
                  f"{len(kr_only)} → {len(both)}")

            # 구버전 행 재업서트 시 supply 필드가 깨지지 않는지
            legacy_rec = LeakRecord(victim="옛날기업", group="qilin", source="t").finalize()
            legacy_rec.uid = "legacy1"
            legacy_rec.kr_tier, legacy_rec.kr_score = "likely", 60
            legacy_rec.supply_tier, legacy_rec.supply_score = "none", 0
            store.upsert_many([legacy_rec])
            after = store.conn.execute("SELECT * FROM victims WHERE uid='legacy1'").fetchone()
            check("구버전 행 재업서트 후에도 높은 등급 유지", after["kr_tier"] == "confirmed")


def test_notification_policy() -> None:
    section("14. 알림 임계값 정책")

    from collector.notify import filter_for_notification

    items = [
        {"victim": "한국확정", "kr_score": 100, "kr_tier": "confirmed", "supply_tier": "none", "supply_score": 0},
        {"victim": "한국추정", "kr_score": 60, "kr_tier": "likely", "supply_tier": "none", "supply_score": 0},
        {"victim": "직거래", "kr_score": 0, "kr_tier": "none", "supply_tier": "direct", "supply_score": 100},
        {"victim": "핵심벤더", "kr_score": 0, "kr_tier": "none", "supply_tier": "critical", "supply_score": 80},
        {"victim": "한국진출", "kr_score": 0, "kr_tier": "none", "supply_tier": "korea_ops", "supply_score": 65},
        {"victim": "업종위험", "kr_score": 0, "kr_tier": "none", "supply_tier": "sector", "supply_score": 50},
    ]

    got = [i["victim"] for i in filter_for_notification(items, {"supply_min_tier": "critical"})]
    check("기본 정책: 업종위험/한국진출은 알림 제외",
          "업종위험" not in got and "한국진출" not in got, got)
    check("기본 정책: 직거래·핵심벤더는 알림 포함",
          "직거래" in got and "핵심벤더" in got, got)
    check("기본 정책: 한국 건은 모두 포함", "한국확정" in got and "한국추정" in got, got)

    got2 = [i["victim"] for i in filter_for_notification(items, {"supply_min_tier": "direct"})]
    check("엄격 정책: 직거래만", "직거래" in got2 and "핵심벤더" not in got2, got2)

    got3 = [i["victim"] for i in filter_for_notification(items, {"supply_min_tier": "sector"})]
    check("느슨 정책: 전부 포함", len(got3) == 6, got3)


def test_dashboard_source() -> None:
    section("11. 대시보드 정적 검사")

    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    body = html.split("<script>", 1)[-1] if "<script>" in html else html

    check("CSP 헤더 존재", "Content-Security-Policy" in html)
    check("외부 연결 차단(connect-src 'none')", "connect-src 'none'" in html)
    check("원격 이미지 차단", "img-src data:" in html)
    check("innerHTML 미사용", ".innerHTML" not in body, "innerHTML 사용 발견")
    check("outerHTML/insertAdjacentHTML 미사용",
          ".outerHTML" not in body and "insertAdjacentHTML" not in body)
    check("eval/Function 생성자 미사용",
          "eval(" not in body and "new Function(" not in body)
    check("document.write 미사용", "document.write" not in body)
    check("외부 스크립트/CDN 없음", "//cdn" not in html and "https://" not in body)
    check("CSV 인젝션 방어 포함", "^[=+\\-@" in body or "CSV 인젝션" in body)
    check("공급망 탭 존재", 'data-view="supply"' in html)
    check("공급망 필터 존재", 'id="supply"' in html)
    check("공급망 컬럼 존재", 'data-sort="supply"' in html)


# ═══════════════════════════════════════════════════════════
def main() -> int:
    print("\033[1m\nKr-Leak-alarm 테스트\033[0m")
    for fn in (test_sanitize, test_defang, test_http_allowlist, test_kr_filter,
               test_normalize_dedup, test_pipeline_and_store, test_sql_injection,
               test_tor_gate, test_onion_host_guard, test_api_schema_and_404,
               test_rate_limit_guards, test_resync_guard, test_supply_chain,
               test_dual_axis_storage, test_notification_policy, test_dashboard_source):
        try:
            fn()
        except Exception as exc:  # 테스트 자체 오류도 실패로 집계
            global FAIL
            FAIL += 1
            FAILURES.append(f"{fn.__name__} 예외: {exc!r}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*60}")
    print(f"  통과 {PASS} / 실패 {FAIL}")
    if FAILURES:
        print("\n  실패 항목:")
        for f in FAILURES:
            print(f"    · {f}")
    print(f"{'='*60}\n")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
