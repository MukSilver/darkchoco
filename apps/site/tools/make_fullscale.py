# DB가 다 채워졌을 때의 모습을 만듭니다.
#
# 지금 노션에 있는 실제 개수를 그대로 씁니다.
#   포럼 DB     269   (조사에 손댄 곳 39 · 어니언 주소가 있는 곳 42)
#   랜섬웨어 DB 514   (마켓 101 · 한국 관련 유출이 올라온 곳 57)
#   수집 DB      17   (검증 완료 12) — 이건 앞으로 채워질 자리라 300건으로 둡니다
#
# 이름은 이미 조사해서 발표에 낸 곳만 씁니다. 나머지는 칸만 두고 이름을 넣지 않습니다.
# 화면에 800개 이름표를 달 수 없기도 하고, 안 본 곳의 이름을 파일로 내보낼 이유도 없습니다.
# 「일부러 반출하지 않음」과 「웹에 올림: 아니오」를 아직 못 걸렀기 때문이기도 합니다.

import io, json, math, random

random.seed(20260828)          # 같은 그림이 나와야 합니다

# ── 조사해서 이름을 아는 자리. 이건 실제로 들여다본 곳입니다.
NAMED = [
    # 오픈웹
    ("fo-darkforums",  "DarkForums",      "sky",  "forum",    "online", 17),
    ("fo-repost",      "재게시 게시판",     "sky",  "forum",    "online",  7),
    ("ar-public",      "공개 아카이브",     "sky",  "archive",  "online", 12),
    ("ar-mirror",      "DLS 미러",         "sky",  "archive",  "online",  6),
    ("ar-exposed",     "노출된 저장소",     "sky",  "archive",  "미확인",   5),
    ("tg-relay",       "유출 중계 채널",    "sky",  "telegram", "online",  9),
    # 다크웹
    ("fo-breach",      "BreachForums",    "deep", "forum",    "seized",  8),
    ("fo-xss",         "XSS",             "deep", "forum",    "online",  5),
    ("fo-exploit",     "Exploit",         "deep", "forum",    "online",  3),
    ("rw-qilin",       "Qilin",           "deep", "ransom",   "online", 14),
    ("rw-gunra",       "GUNRA",           "deep", "ransom",   "online",  6),
    ("rw-nightspire",  "nightspire",      "deep", "ransom",   "offline", 4),
    ("rw-dragonforce", "DragonForce",     "deep", "ransom",   "online",  9),
    ("rw-exfilsquad",  "ExfilSquad",      "deep", "ransom",   "online",  5),
    ("rw-gentlemen",   "The Gentlemen",   "deep", "ransom",   "offline", 4),
    ("rw-clop",        "Cl0p",            "deep", "ransom",   "offline", 7),
    ("tg-private",     "판매 전용 채널",    "deep", "telegram", "online",  4),
    ("br-iab",         "초기 접근 중개자",  "deep", "broker",   "online",  3),
]

# ── 이름을 아직 안 붙이는 자리. 개수는 노션 그대로입니다.
#    (층, 업종, 상태, 몇 개)
UNNAMED = [
    # 포럼 269 - 조사한 6 = 263. 어니언이 있는 42 중 조사한 3을 빼고 39가 아래층
    ("deep", "forum",     "online",  22),
    ("deep", "forum",     "offline",  9),
    ("deep", "forum",     "미확인",    8),
    ("sky",  "forum",     "online",  61),
    ("sky",  "forum",     "offline", 42),
    ("sky",  "forum",     "미확인",  121),
    # 랜섬웨어 514 - 조사한 7 = 507. 마켓 101 중 3을 뺀 98은 오픈웹 마켓으로 둡니다
    ("deep", "ransom",    "online",  74),
    ("deep", "ransom",    "offline", 291),
    ("deep", "ransom",    "미확인",   14),
    ("deep", "ransom",    "seized",   3),
    ("sky",  "market",    "online",  47),
    ("sky",  "market",    "offline", 51),
    # 텔레그램 · 브로커 — 아직 세는 중이라 어림으로 둡니다
    ("sky",  "telegram",  "online",  34),
    ("sky",  "telegram",  "미확인",   18),
    ("deep", "telegram",  "online",  12),
    ("deep", "broker",    "online",   9),
    ("deep", "broker",    "미확인",   14),
    # 오픈웹 노출 — 닥스훈트 팀이 맡는 자리
    ("sky",  "archive",   "online",  23),
    ("sky",  "archive",   "미확인",   16),
]

places, pid = [], 0
for i, (id_, nm, layer, kind, st, cases) in enumerate(NAMED):
    places.append({"id": id_, "name": nm, "layer": layer, "kind": kind, "status": st,
                   "investigated": True, "cases": cases,
                   "korea": kind in ("forum", "ransom") and i % 3 == 0})
for layer, kind, st, n in UNNAMED:
    for _ in range(n):
        pid += 1
        places.append({"id": "u%04d" % pid, "layer": layer, "kind": kind, "status": st,
                       "investigated": False, "cases": 1})

# ── 길. 이름 있는 자리 사이만 그립니다. 800개를 다 이으면 그림이 안 됩니다.
FLOWS = [
    ("fo-darkforums", "fo-repost",      "flat",       "같은 층 재게시",        "confirmed"),
    ("fo-darkforums", "fo-breach",      "drop",       "내려가 팔림",          "confirmed"),
    ("ar-exposed",    "fo-xss",         "exposure",   "노출된 자료가 거래로",   "probable"),
    ("ar-exposed",    "rw-dragonforce", "exposure",   "열린 저장소에서 갈취로", "probable"),
    ("br-iab",        "rw-qilin",       "flat",       "접근 권한 판매",        "probable"),
    ("br-iab",        "rw-dragonforce", "flat",       "접근 권한 판매",        "probable"),
    ("rw-qilin",      "fo-breach",      "flat",       "유출 사이트에서 포럼으로", "confirmed"),
    ("rw-clop",       "fo-breach",      "flat",       "갈취 자료가 포럼으로",   "confirmed"),
    ("rw-gunra",      "fo-xss",         "flat",       "판매글로 옮김",         "probable"),
    ("fo-breach",     "fo-xss",         "flat",       "되팔이 재게시",         "confirmed"),
    ("fo-breach",     "fo-exploit",     "succession", "압수 뒤 후계",          "probable"),
    ("fo-breach",     "tg-relay",       "rise",       "채널로 다시 풀림",       "confirmed"),
    ("fo-xss",        "ar-public",      "rise",       "기간이 지나 무상 공개",   "confirmed"),
    ("tg-private",    "tg-relay",       "rise",       "닫힌 채널에서 열린 채널로", "probable"),
    ("rw-nightspire", "ar-mirror",      "rise",       "미러가 받아 감",         "confirmed"),
    ("rw-exfilsquad", "tg-private",     "flat",       "채널로 넘김",           "probable"),
    ("rw-gentlemen",  "fo-breach",      "flat",       "판매 게시",             "confirmed"),
    ("tg-relay",      "ar-public",      "flat",       "아카이브가 받아 감",     "confirmed"),
]

# ── 사고. 수집 DB가 채워졌을 때를 300건으로 둡니다.
ITEMS = ["name", "phone", "email", "address", "account", "rrn", "finance", "internal", "etc"]
IND = ["금융", "의료", "교육", "공공·행정", "통신", "유통·이커머스", "제조",
       "IT·플랫폼", "게임", "운송·물류", "숙박·여행", "미디어", "건설·부동산", "법률", "에너지"]
VERDICT = [("확인됨", "full", .17), ("신뢰성 높음", "full", .23), ("미확인", "partial", .34),
           ("신뢰성 낮음", "partial", .18), ("허위", "blocked", .08)]
START = ["rw-qilin", "rw-dragonforce", "rw-clop", "rw-gunra", "rw-exfilsquad",
         "rw-gentlemen", "rw-nightspire", "fo-darkforums", "ar-exposed", "br-iab"]
NEXT = {}
for a, b, k, lab, conf in FLOWS:
    NEXT.setdefault(a, []).append((b, lab))
BY = {p["id"]: p for p in places}

def pick_verdict():
    r, acc = random.random(), 0
    for v, g, w in VERDICT:
        acc += w
        if r < acc: return v, g
    return VERDICT[-1][0], VERDICT[-1][1]

def reach_of(hops):
    if not hops: return {"state": "unknown", "places_n": 0}
    last = BY[hops[-1]["place"]]
    st = "deep-only" if last["layer"] == "deep" else \
         ("public" if last["kind"] == "archive" else "surfaced")
    return {"state": st, "layer": last["layer"], "kind": last["kind"], "places_n": len(hops)}

cases = []
for i in range(300):
    verdict, gate = pick_verdict()
    cur = random.choice(START)
    hops = [{"place": cur, "name": BY[cur].get("name"), "layer": BY[cur]["layer"],
             "kind": BY[cur]["kind"], "relation": "여기서 처음 나왔습니다"}]
    while cur in NEXT and random.random() < .62 and len(hops) < 5:
        nxt, lab = random.choice(NEXT[cur])
        if any(h["place"] == nxt for h in hops): break
        cur = nxt
        hops.append({"place": cur, "name": BY[cur].get("name"), "layer": BY[cur]["layer"],
                     "kind": BY[cur]["kind"], "relation": lab})
    n = random.randint(2, 6)
    picked = random.sample(ITEMS, n)
    items = {}
    for it in picked:
        # 허위로 판정한 사고에서는 아무것도 확인되지 않습니다
        items[it] = "claimed" if gate == "blocked" else \
                    ("confirmed" if (gate == "full" and random.random() < .62) else "claimed")
    cases.append({
        "id": i + 1, "title": "사고 %03d" % (i + 1), "industry": random.choice(IND),
        "posted": "2026-%02d-%02d" % (random.randint(3, 8), random.randint(1, 28)),
        "verdict": verdict, "gate": gate, "items": items, "hops": hops,
        "reach": reach_of(hops), "evidence_kind": random.choice(["샘플", "스크린샷", "텍스트"]),
    })

# 선의 건수를 사고에서 셉니다. 지어내지 않습니다.
from collections import Counter
cnt = Counter()
for c in cases:
    for a, b in zip(c["hops"], c["hops"][1:]):
        cnt[(a["place"], b["place"])] += 1
flows = [{"from": a, "to": b, "kind": k, "label": lab, "confidence": conf,
          "cases": cnt.get((a, b), 0)} for a, b, k, lab, conf in FLOWS]

# 자리의 사고 수도 사고에서 다시 셉니다. 선이 자리보다 클 수 없게 됩니다.
seat = Counter()
for c in cases:
    for h in c["hops"]:
        seat[h["place"]] += 1
for p in places:
    if p["investigated"]:
        p["cases"] = max(p["cases"], seat.get(p["id"], 0))

data = {
    "meta": {"basis_date": "2026-08-19", "edition": "2026.09",
             "counts": {"forum": 269, "ransom": 514, "collected": 17},
             "note": "자리 개수는 노션 그대로입니다. 아직 안 본 자리는 이름을 넣지 않습니다."},
    "layers": [{"id": "sky", "name": "오픈웹", "sub": "검색하면 나오는 세계"},
               {"id": "deep", "name": "다크웹", "sub": "주소나 계정을 알아야 열리는 세계"}],
    "kinds": [{"id": "forum", "name": "해킹 포럼", "color": "#8b6fe0"},
              {"id": "ransom", "name": "랜섬웨어 그룹", "color": "#dc5f4c"},
              {"id": "telegram", "name": "텔레그램 채널", "color": "#3f9bd6"},
              {"id": "archive", "name": "공개 · 미러", "color": "#3fae8f"},
              {"id": "market", "name": "판매 마켓", "color": "#d08b3a"},
              {"id": "broker", "name": "접근 브로커", "color": "#c76fa8"}],
    "places": places, "flows": flows, "cases": cases,
    "stats": {"reported": 316, "matched": 199, "circulating": 108, "judged": 12},
}
io.open("data/leak-map.json", "w", encoding="utf-8").write(
    json.dumps(data, ensure_ascii=False, indent=1))

named = sum(1 for p in places if p["investigated"])
print("자리 %d  (이름 있음 %d · 칸만 %d)" % (len(places), named, len(places) - named))
print("길 %d · 사고 %d" % (len(flows), len(cases)))
for l in data["layers"]:
    print("  %s %d칸" % (l["name"], sum(1 for p in places if p["layer"] == l["id"])))
print("판정:", dict(Counter(c["verdict"] for c in cases)))
