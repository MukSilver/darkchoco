"""
scripts/make_demo_data.py — 네트워크 없이 대시보드를 미리 보기 위한 샘플 데이터 생성기.

실제 ransomware.live 공개 API 에서 가져온 한국(country=KR) 실데이터 스냅샷을
그대로 파이프라인에 태워 web/data/ 를 만든다. DB 는 건드리지 않는다.

    python scripts/make_demo_data.py

실제 수집을 하려면 `python -m collector.main run` 을 쓰십시오.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from collector.export import export            # noqa: E402
from collector.kr_filter import TIER_SCORE, KrClassifier  # noqa: E402
from collector.supply_filter import TIER_SCORE as SUPPLY_SCORE  # noqa: E402
from collector.supply_filter import SupplyClassifier  # noqa: E402
from collector.sources.base import LeakRecord, parse_timestamp  # noqa: E402
from collector.store import Store              # noqa: E402

# ransomware.live /v2/countryvictims/KR 실제 응답 스냅샷 (2026-08 기준)
SAMPLE = [
    ("Manufacturing", "qilin", "HIGEN MOTOR(critical data)", "www.higen.co.kr",
     "N/A", "2026-08-10T19:39:24+00:00",
     "http://ijzn3sicrcy7guixkzjkib4ukbiilwc3xhnmby4mcbccnsd7j2rekvqd.onion/site/blog?uuid=42480710"),
    ("Manufacturing", "Barracuda", "Namyang Industrial Co., Ltd.", "nynexmo.com",
     "Selling fresh full database dumps of company Namyang Industrial Co., Ltd. (renamed to Namyang Nexmo)",
     "2026-08-06T08:32:06+00:00",
     "http://darkfoxaqhfpxkrbt7vxns2z2u2k72sgmqbzeorupaiottw3ecm2wgyd.onion/Thread-Selling-South-Korea"),
    ("Technology", "gunra", "worldtube", "worldtube.co.kr",
     "Sector: Manufacturer of new automotive parts | Revenue: US$ 20,000,000",
     "2026-08-04T13:23:14+00:00", ""),
    ("Manufacturing", "CRPxO", "HYUNDAI", "hyundai.com",
     "Sector: Automotive | Data leaked: 1.5 GB", "2026-07-31T23:50:43+00:00", ""),
    ("Technology", "Global Secret Group", "Nexon Corp.", "nexon.com",
     "Internal infrastructure audit revealed multiple critical entry points across distributed network segments.",
     "2026-07-26T18:12:59+00:00", ""),
    ("Technology", "spacebears", "DoAllTech", "doalltech.com",
     "The Company is leading the construction IT industry. Personal information of employees and clients, financial documents and other files.",
     "2026-07-21T09:09:13+00:00",
     "http://5butbkrljkaorg5maepuca25oma7eiwo6a2rlhvkblb4v6mf3ki2ovid.onion/companies/61/doalltech"),
    ("Not Found", "dragonforce", "stni.co.kr", "stni.co.kr",
     "Creating accurate virtual replicas involves production facilities, workshops, and equipment.",
     "2026-06-29T12:54:14+00:00",
     "http://z3wqggtxft7id3ibr7srivv5gjof5fwg76slewnzwwakjuf3nlhukdid.onion/blog/?post_uuid=2050a4f3"),
    ("Manufacturing", "settra", "doosan.com", "doosan.com",
     "How Doosan / Geith / Bobcat Buries Defects and Protects Its Secrets — 3.27 TERABYTES OF FILES",
     "2026-06-28T19:53:53+00:00",
     "http://settra5ldqwgtw5q7z5awbsvlksakyfojuc5slgrz5lvapune4fantqd.onion/leaks/ff440359"),
    ("Manufacturing", "qilin", "Lee International", "www.leeinternational.com",
     "N/A", "2026-06-23T20:23:54+00:00",
     "http://ijzn3sicrcy7guixkzjkib4ukbiilwc3xhnmby4mcbccnsd7j2rekvqd.onion/site/blog?uuid=81f498aa"),
    ("Professional Services", "Black X", "Daechang Solution", "dsol.co.kr",
     "We possess all the core technical data of Daechang Solution (Technical Research Institute, Valve Team, Cryogenic Team, Sales, Finance, Quality, Production).",
     "2026-06-13T10:16:38+00:00",
     "http://blackxppq2jvqyg4slyg3sbszv7ib2avaaycvhff5qipgdoepqi57xyd.onion/target/RsSsfhdJMFFjSS"),
    ("Technology", "qilin", "Bitek System", "www.bitek.co.kr", "N/A",
     "2026-06-11T06:53:30+00:00",
     "http://ijzn3sicrcy7guixkzjkib4ukbiilwc3xhnmby4mcbccnsd7j2rekvqd.onion/site/blog?uuid=1bf9d880"),
    ("Manufacturing", "ULose", "HIZE Aero", "hizeaero.com",
     "We have all PDM Server's data of HIZEAERO Company, partner Boeing. 1TB. country: South Korea",
     "2026-06-09T00:00:00+00:00", ""),
    ("Financial Services", "ULose", "KyungRok", "kyungrok.com",
     "We have all customer's data of KyungRok. country: South Korea status: public",
     "2026-06-09T00:00:00+00:00", ""),
    ("Financial Services", "ULose", "MSICapital", "money-store.co.kr", "",
     "2026-06-09T00:00:00+00:00", ""),
    ("Healthcare", "ULose", "HanDok", "www.handok.co.kr",
     "We have all customer's data of HanDok. country: South Korea status: public",
     "2026-06-09T00:00:00+00:00", ""),
    ("Financial Services", "ULose", "NRCapital", "nrcapital.co.kr",
     "We have all data of nrcapital company. 1TB. country: South Korea", "2026-06-09T00:00:00+00:00", ""),
    ("Manufacturing", "qilin", "JNP ENG", "www.jnpeng.co.kr", "N/A",
     "2026-06-03T09:09:21+00:00",
     "http://ijzn3sicrcy7guixkzjkib4ukbiilwc3xhnmby4mcbccnsd7j2rekvqd.onion/site/blog?uuid=aee7cde8"),
    ("Education", "nova", "Daegu University AI Department", "daegu.ac.kr",
     "Daegu University offers a range of educational services including online employment solutions and academic information systems.",
     "2026-05-29T23:53:06+00:00",
     "http://novadmrkp4vbk2padk5t6pbxolndceuc7hrcq4mjaoyed6nxsqiuzyyd.onion/daegu-university-ai-department"),
    ("Transportation", "titan", "Apex Maritime Co., Inc.", "k-apex.kln.com",
     "[AI generated] Freight forwarding and logistics company. Air and ocean freight, customs brokerage, cargo consolidation.",
     "2026-05-30T03:55:32+00:00", "https://titanblog.org/post/apex-maritime-co-inc-9qyivv46pa"),
    ("Manufacturing", "nova", "URG OEM", "urg.co.kr",
     "urg.co.kr — URG was founded with a sincere desire to provide solutions for customers facing skin concerns. Starting in 1990 with Shangpree Spa.",
     "2026-05-17T12:23:35+00:00",
     "http://novadmrkp4vbk2padk5t6pbxolndceuc7hrcq4mjaoyed6nxsqiuzyyd.onion/urg-oem"),
    ("Healthcare", "coinbasecartel", "Alpinion", "alpinion.com",
     "[AI generated] Alpinion is a South Korean medical device company specializing in ultrasound imaging systems, founded in 2010 as a spin-off from Samsung, headquartered in Seoul.",
     "2026-05-11T13:52:01+00:00",
     "http://fjg4zi4opkxkvdz7mvwp7h6goe4tcby3hhkrz43pht4j3vakhy75znyd.onion/companies/alpinion"),
]


# 공급망 축 미리보기용 샘플 (한국 기업이 아니지만 국내로 번질 수 있는 유형)
SUPPLY_SAMPLE = [
    ("Technology", "US", "cl0p", "Progress Software MOVEit Transfer", "progress.com",
     "Managed file transfer product exploited; downstream customer data exposed worldwide",
     "2026-08-14T09:10:00+00:00", "http://clop5tpqhmrjyxlxbvwmyhrgnrpbjxlnbmqzmjfvbgt2rjxqid.onion/moveit"),
    ("Technology", "US", "shinyhunters", "Snowflake Inc.", "snowflake.com",
     "Cloud data warehouse; customer tenant credentials abused for downstream access",
     "2026-08-13T04:20:00+00:00", ""),
    ("Manufacturing", "TW", "lockbit", "Wistron Corporation", "wistron.com",
     "Electronic manufacturing services provider; contract manufacturer for major OEMs",
     "2026-08-12T22:05:00+00:00", "http://lockbitaptxyzabcd1234efgh5678ijkl9012mnop3456qrst.onion/wistron"),
    ("Manufacturing", "DE", "play", "Continental Korea Ltd.", "continental-korea.com",
     "German automotive tier 1 supplier, Korea subsidiary; component supplier data",
     "2026-08-11T15:40:00+00:00", ""),
    ("Professional Services", "SG", "akira", "Apex Managed IT Services",
     "apex-msp.sg", "Regional managed service provider holding remote admin access to client estates",
     "2026-08-10T11:00:00+00:00", ""),
    ("Technology", "US", "qilin", "ConnectWise ScreenConnect", "connectwise.com",
     "Remote monitoring and management platform used to administer client endpoints",
     "2026-08-09T08:30:00+00:00", ""),
]


def main() -> int:
    clf = KrClassifier({"min_tier_to_report": "review"})
    sup = SupplyClassifier({"min_tier_to_store": "sector"}, root=ROOT)
    records = []

    for sector, group, title, site, desc, when, url in SAMPLE:
        rec = LeakRecord(
            victim=title, group=group, country="KR", sector=sector, website=site,
            description=desc, published=parse_timestamp(when), discovered=parse_timestamp(when),
            post_url=url, source="ransomware.live",
        ).finalize()
        rec.kr_tier, rec.kr_score, rec.kr_reasons = clf.classify(rec)
        rec.supply_tier, rec.supply_score, rec.supply_reasons = sup.classify(rec)
        records.append(rec)

    for sector, country, group, title, site, desc, when, url in SUPPLY_SAMPLE:
        rec = LeakRecord(
            victim=title, group=group, country=country, sector=sector, website=site,
            description=desc, published=parse_timestamp(when), discovered=parse_timestamp(when),
            post_url=url, source="ransomware.live",
        ).finalize()
        rec.kr_tier, rec.kr_score, rec.kr_reasons = clf.classify(rec)
        rec.supply_tier, rec.supply_score, rec.supply_reasons = sup.classify(rec)
        records.append(rec)

    web_dir = ROOT / "web" / "data"
    with tempfile.TemporaryDirectory() as tmp:
        with Store(Path(tmp) / "demo.db") as store:
            run_id = store.start_run()
            store.upsert_many(records)          # 전부 is_new=1 로 들어가 NEW 탭 미리보기 가능
            store.finish_run(run_id, fetched=len(records), kr_matched=len(records),
                             new_count=len(records), status="ok", detail="demo data")
            payload = export(store, web_dir, min_score=TIER_SCORE["review"],
                             min_supply_score=SUPPLY_SCORE["sector"])

    print(f"샘플 {len(payload['items'])}건을 {web_dir} 에 생성했습니다.")
    print("대시보드 확인:  python -m collector.main serve")
    print("실제 수집:      python -m collector.main run   (이때 데모 데이터는 대체됩니다)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
