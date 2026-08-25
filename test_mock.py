#!/usr/bin/env python3
"""오프라인 검증용 모의 테스트. 실제 API/노션 호출 없이 로직만 확인한다.
   python test_mock.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dls_fill  # noqa: E402
import notion as nt  # noqa: E402
import sources as src  # noqa: E402

# ---- 실제 API 응답 형태를 그대로 본뜬 픽스처 -------------------------------
RL_GROUPS = [
    {"added_date": "2026-01-28", "altname": None,
     "description": "The group appears unreliable. Most of its alleged victims cannot be verified.",
     "locations": [{"available": True, "enabled": True,
                    "fqdn": "oaptxiyisljt2kv3we2we34kuudmqda7f2geffoylzpeo7ourhtz4dad.onion",
                    "slug": "http://oaptxiyisljt2kv3we2we34kuudmqda7f2geffoylzpeo7ourhtz4dad.onion",
                    "title": "404 - Compromised", "type": "DLS"}],
     "name": "0apt", "tools": [], "ttps": [], "url": "https://www.ransomware.live/group/0apt"},
    {"added_date": "2022-06-29", "altname": "LockBit Black",
     "description": "LockBit 3.0 is one of the largest ransomware groups.",
     "locations": [
         {"available": False, "enabled": False, "fqdn": "lockbitsupn2h6be2cnq.onion",
          "slug": "http://lockbitsupn2h6be2cnq.onion", "title": "LockBit LOGIN", "type": "Chat"},
         {"available": True, "enabled": True, "fqdn": "ofj3oaltwaf67qtd7oafk.onion",
          "slug": "http://ofj3oaltwaf67qtd7oafk.onion", "title": "LockBit", "type": "DLS"},
         {"available": False, "enabled": True, "fqdn": "oldmirror7zzz.onion",
          "slug": "http://oldmirror7zzz.onion", "title": "mirror", "type": "DLS"}],
     "name": "lockbit3", "tools": [], "ttps": [],
     "url": "https://www.ransomware.live/group/lockbit3"},
]
RL_KR = [
    {"activity": "Manufacturing", "country": "KR", "group_name": "qilin",
     "post_title": "SAMPLEMOTOR MOTOR(critical data)", "discovered": "2026-08-10T19:39:24+00:00",
     "published": "2026-08-10T19:39:03+00:00", "website": "www.samplemotor.co.kr"},
]
RL_VICTIMS = [
    {"activity": "Healthcare", "attackdate": "2026-08-15T04:21:55+00:00", "country": "US",
     "discovered": "2026-08-15T04:22:13+00:00", "group": "lockbit3", "victim": "Interim HealthCare"},
    {"activity": "Manufacturing", "attackdate": "2026-08-14T00:18:22+00:00", "country": "DE",
     "discovered": "2026-08-14T00:21:25+00:00", "group": "lockbit3", "victim": "Alpine Electronics"},
    {"activity": "Manufacturing", "attackdate": "2026-08-10T19:39:24+00:00", "country": "KR",
     "discovered": "2026-08-10T19:39:24+00:00", "group": "qilin", "victim": "SAMPLEMOTOR MOTOR"},
]
LOOK_GROUPS = ["0apt", "lockbit3"]
LOOK_MARKETS = ["blacksprut", "darkfox market"]
LOOK_FORUMS = ["funkforum"]
LOOK_DETAIL = {
    "0apt": {"captcha": False,
             "meta": "This group is newly observed and appears not to be a serious group.",
             "locations": [{"slug": "http://oaptxiyisljt2kv3we2we34kuudmqda7f2geffoylzpeo7ourhtz4dad.onion",
                            "fqdn": "oaptxiyisljt2kv3we2we34kuudmqda7f2geffoylzpeo7ourhtz4dad.onion",
                            "available": True, "title": "404 - Compromised",
                            "updated": "2026-08-16 09:11:30.618", "screen": "BASE64" * 5000}]},
    "blacksprut": {"captcha": False, "meta": None,
                   "locations": [{"slug": "http://blacksprut2rprrt3.onion",
                                  "fqdn": "blacksprut2rprrt3.onion", "available": False,
                                  "title": "blackspfgh3bi6im.onion",
                                  "updated": "2025-04-01 10:22:13.504", "screen": "BASE64" * 5000}]},
}


def fake_get_json(self, url, **kw):
    if url.endswith("/v2/groups"):
        return RL_GROUPS
    if "/countryvictims/" in url:
        return RL_KR
    if "/v2/victims/" in url:
        return RL_VICTIMS if url.endswith("/2026/8") else []
    if url.endswith("/api/groups"):
        return LOOK_GROUPS
    if url.endswith("/api/markets"):
        return LOOK_MARKETS
    if url.endswith("/api/forums"):
        return LOOK_FORUMS
    for key, val in LOOK_DETAIL.items():
        if url.endswith("/" + key.replace(" ", "%20")):
            return json.loads(json.dumps(val))
    return kw.get("default")


def title(text):
    return {"type": "title", "title": [{"plain_text": text}]}


def empty(t):
    return {"type": t, t: [] if t in ("rich_text", "multi_select") else None}


PAGES = [
    {"id": "page-1", "properties": {
        "그룹 이름": title("0apt"),
        "주소": {"type": "url", "url": "oaptxiyisljt2kv3we2we34kuudmqda7f2geffoylzpeo7ourhtz4dad.onion"},
        "어떤 곳인지": empty("rich_text"), "종류": {"type": "multi_select", "multi_select": [{"name": "market"}]},
        "상태": {"type": "select", "select": {"name": "online"}},
        "출처": {"type": "multi_select", "multi_select": [{"name": "ransomlook.io"}]},
        "최근 활동": empty("date"), "피해 대상": empty("rich_text"),
        "한국 관련 유출": empty("rich_text"), "이전 이름·별칭": empty("rich_text"),
        "이전 주소": empty("rich_text"), "연결된 곳": empty("rich_text"),
        "확인일": {"type": "date", "date": {"start": "2026-08-03"}}, "비고": empty("rich_text"),
    }},
    {"id": "page-2", "properties": {
        "그룹 이름": title("lockbit3"), "주소": {"type": "url", "url": None},
        "어떤 곳인지": empty("rich_text"),
        "종류": {"type": "multi_select", "multi_select": [{"name": "미확인"}]},
        "상태": {"type": "select", "select": {"name": "미확인"}},
        "출처": empty("multi_select"), "최근 활동": empty("date"),
        "국가": {"type": "multi_select", "multi_select": [{"name": "미확인"}]},
        "피해 대상": empty("rich_text"), "한국 관련 유출": empty("rich_text"),
        "이전 이름·별칭": empty("rich_text"), "이전 주소": empty("rich_text"),
        "연결된 곳": empty("rich_text"), "확인일": empty("date"), "비고": empty("rich_text"),
    }},
    {"id": "page-3", "properties": {
        "그룹 이름": title("존재하지않는사이트"), "주소": {"type": "url", "url": None},
        "어떤 곳인지": empty("rich_text"), "종류": empty("multi_select"), "상태": empty("select"),
        "출처": empty("multi_select"), "최근 활동": empty("date"), "규모": empty("rich_text"),
        "피해 대상": empty("rich_text"), "한국 관련 유출": empty("rich_text"),
        "이전 이름·별칭": empty("rich_text"), "이전 주소": empty("rich_text"),
        "연결된 곳": empty("rich_text"), "확인일": empty("date"), "비고": empty("rich_text"),
    }},
]
SCHEMA = {"그룹 이름": "title", "주소": "url", "어떤 곳인지": "rich_text", "종류": "multi_select",
          "상태": "select", "출처": "multi_select", "최근 활동": "date", "피해 대상": "rich_text", "한국 관련 유출": "rich_text", "이전 이름·별칭": "rich_text",
          "이전 주소": "rich_text", "연결된 곳": "rich_text", "확인일": "date", "비고": "rich_text",
          "국가": "multi_select"}

WRITES = []


def main():
    src.Fetcher.get_json = fake_get_json
    nt.Notion.data_sources = lambda self, db: [
        {"id": "ds-1", "name": "전체"}, {"id": "ds-2", "name": "Ransomwhere 분류"}]
    nt.Notion.schema = lambda self, ds: SCHEMA
    nt.Notion.query_all = lambda self, ds, page_size=100: PAGES
    nt.Notion.update_page = lambda self, pid, props: WRITES.append((pid, props))
    os.environ["NOTION_TOKEN"] = "test"
    os.environ["NOTION_DATABASE_ID"] = "0" * 32
    dls_fill.load_env = lambda: None

    sys.argv = ["dls_fill.py", "--apply"]
    rc = dls_fill.main()

    print("\n\n===== 실제로 노션에 보낼 payload =====")
    for pid, props in WRITES:
        print(f"\n--- {pid} ---")
        print(json.dumps(props, ensure_ascii=False, indent=2)[:2600])

    # --- 검증 ---
    assert rc == 0
    assert len(WRITES) == 2, f"2개 행이 업데이트돼야 함, 실제 {len(WRITES)}"
    p1 = dict(WRITES)["page-1"]
    assert p1["어떤 곳인지"]["rich_text"][0]["text"]["content"].startswith("The group appears")
    assert {o["name"] for o in p1["출처"]["multi_select"]} == {"ransomlook.io", "ransomware.live"}
    assert "상태" not in p1, "이미 값이 있는 select 는 건드리면 안 됨"
    assert "확인일" not in p1, "이미 값이 있는 date 는 건드리면 안 됨"
    p2 = dict(WRITES)["page-2"]
    assert p2["이전 이름·별칭"]["rich_text"][0]["text"]["content"] == "LockBit Black"
    assert p2["주소"]["url"] == "http://ofj3oaltwaf67qtd7oafk.onion", p2["주소"]
    assert "oldmirror7zzz.onion" in p2["이전 주소"]["rich_text"][0]["text"]["content"]
    assert "Chat: lockbitsupn2h6be2cnq.onion" in p2["연결된 곳"]["rich_text"][0]["text"]["content"]
    assert p2["최근 활동"]["date"]["start"] == "2026-08-15"
    assert p2["상태"]["select"]["name"] == "online", "미확인 자리표시자는 덮어써야 함"
    assert [o["name"] for o in p2["종류"]["multi_select"]] == ["group"], p2["종류"]
    assert "Healthcare" in p2["피해 대상"]["rich_text"][0]["text"]["content"]
    assert "한국 관련 유출" not in p2, "lockbit3 는 KR 피해자가 없음"
    print("\n\n✅ 모든 검증 통과")


if __name__ == "__main__":
    main()
