#!/usr/bin/env python3
"""feed_parse 시험.

    python tools/test_feed_parse.py

Kr-Leak 의 실제 DB 없이 돈다. 임시 SQLite 를 만들어 태운다.
표본 다섯은 2026-08-26 에 팀원 레포의 실데이터 스냅샷 21건을 세어 보고
거기서 실제로 나온 네 가지 설명 형태를 그대로 본떴다.

    회사 소개 11 · 조직이 쓴 문장 5 · N/A 라는 글자 4 · 빈칸 1
"""
from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import alert_parse as A  # noqa: E402
import feed_parse as F  # noqa: E402

fails = []


def check(name: str, got, want) -> None:
    if got != want:
        fails.append("%s\n     받음 %r\n     기대 %r" % (name, got, want))


def miss(name: str, r: dict, key: str, why: str = "") -> None:
    """못 봄으로 나왔는지 본다. why 를 주면 이유까지 본다."""
    v = str(r[key])
    if not v.startswith(A.MISS):
        fails.append("%s: %s 가 못 봄이 아니다 (%r)" % (name, key, v))
    elif why and why not in v:
        fails.append("%s: %s 이유가 다르다 (%r)" % (name, key, v))


COLS = ("uid victim victim_key group_name group_key country sector website "
        "description published discovered post_url sources kr_tier kr_score "
        "kr_reasons supply_tier supply_score supply_reasons first_seen "
        "last_seen is_new acknowledged_at").split()

# (uid, victim, group, website, description, published, post_url, sources, is_new)
ROWS = [
    ("u1", "나무생각", "qilin", "treethink.kr",
     "We have all customer's data of treethink. country: South Korea",
     "2026-06-09T00:00:00+00:00", "http://ijzn3sic.onion/site/blog?uuid=1b",
     '["ransomware.live"]', 1),
    ("u2", "어떤의료기기", "coinbasecartel", "example-med.com",
     "[AI generated] A South Korean medical device company founded in 2010.",
     "2026-05-11T13:52:01+00:00", "http://fjg4zi4o.onion/companies/x",
     '["ransomware.live", "ransomlook.io"]', 1),
    ("u3", "어떤제조", "qilin", "www.example-mfg.co.kr", "N/A",
     "2026-06-23T20:23:54+00:00", "http://ijzn3sic.onion/site/blog?uuid=81",
     '["ransomlook.io"]', 1),
    ("u4", "어떤금융", "ULose", "example-fin.co.kr", "",
     "2026-06-09T00:00:00+00:00", "", '[]', 1),
    # 이미 사람이 본 줄. 기본 조회에서는 안 나와야 한다
    ("u5", "지난건", "play", "old.example.com", "Old one.",
     "2026-04-01T00:00:00+00:00", "http://old.onion/p", '["ransomfeed.it"]', 0),
]


def build(path: Path) -> None:
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE victims (%s)" % ", ".join(t + " TEXT" for t in COLS))
    for uid, vic, grp, site, desc, pub, url, src, new in ROWS:
        d = dict.fromkeys(COLS, "")
        d.update(uid=uid, victim=vic, victim_key=vic.lower(), group_name=grp,
                 group_key=grp.lower(), country="KR", sector="Manufacturing",
                 website=site, description=desc, published=pub, discovered=pub,
                 post_url=url, sources=src, kr_tier="confirmed", kr_score="90",
                 kr_reasons='["country=KR"]', supply_tier="none", supply_score="0",
                 supply_reasons="[]", first_seen=pub, last_seen=pub,
                 is_new=str(new), acknowledged_at="")
        con.execute("INSERT INTO victims VALUES (%s)" % ",".join("?" * len(COLS)),
                    [d[c] for c in COLS])
    con.commit()
    con.close()


tmp = Path(tempfile.mkdtemp(prefix="feedparse_"))
db = tmp / "krleak.db"
build(db)

# ── 1. 새 건만 나온다 ───────────────────────────
rows = F.read(db, only_new=True, since=None)
check("새 건만 넷", len(rows), 4)
check("본 것까지 다섯", len(F.read(db, only_new=False, since=None)), 5)

by = {r["기타"]["uid"]: r for r in rows}

# ── 2. 칸이 그대로 앉는다 ───────────────────────
r = by["u1"]
check("대상 조직", r["대상 조직"], "나무생각")
check("공식 도메인", r["공식 도메인"], "treethink.kr")
check("행위자", r["행위자"], "qilin")
check("유형", r["유형"], "랜섬")
check("게시 시각", r["게시 시각"], "2026-06-09T00:00:00+00:00")

# ── 3. 원 출처가 실제로 채워진다 ────────────────
# 알림 경로는 이 칸이 언제나 못 봄이었다. 이것이 이 도구를 쓰는 이유다
check("원 출처", r["원 출처"], "http://ijzn3sic.onion/site/blog?uuid=1b")
if r["원 출처"].startswith(A.MISS):
    fails.append("원 출처가 못 봄이면 이 도구를 쓸 이유가 없다")
# 무력화된 형태가 섞여 들어오면 안 된다
for k in ("원 출처",):
    if "hxxp" in r[k] or "[.]" in r[k]:
        fails.append("%s 에 무력화된 주소가 들어왔다: %r" % (k, r[k]))

# ── 4. 없는 것은 못 봄과 이유로 ─────────────────
miss("규모", r, "주장 규모", "data_size")
miss("재게시", r, "재게시 URL", "재게시 개념이 없다")
miss("신뢰도", r, "판별 신뢰도", "뜻이 다르다")
miss("빈 URL", by["u4"], "원 출처", "post_url 비어 있음")
miss("빈 설명", by["u4"], "알림 문장", "description 비어 있음")

# ── 5. 요약 사이트를 독립 출처로 세지 않는다 ────
if "독립 출처로 세지 않는다" not in r["감시 출처"]:
    fails.append("감시 출처에 요약 사이트 표시가 없다: %r" % r["감시 출처"])
miss("빈 sources", by["u4"], "감시 출처", "sources 비어 있음")

# ── 6. 설명 성격을 가른다 ───────────────────────
check("게시글 문장", F.desc_kind(ROWS[0][4]), "게시글 문장")
check("AI 회사 소개", F.desc_kind(ROWS[1][4]), "회사 소개(AI 가 지음)")
check("N/A", F.desc_kind(ROWS[2][4]), "N/A")
check("빈칸", F.desc_kind(ROWS[3][4]), "빈칸")
check("표시 없는 회사 소개",
      F.desc_kind("Daegu University offers a range of educational services."),
      "회사 소개로 보임")

# 실데이터에서 실제로 나온 꼴들. 2026-08-26 에 Namyang 건을 회사 소개로 잘못 봤다
for s, want in [
    ("Selling fresh full database dumps of company Namyang Industrial", "게시글 문장"),
    ("We possess all the core technical data of Daechang Solution", "게시글 문장"),
    ("Lines:73.481.539 / size: 3Gb zipped", "게시글 문장"),
    ("9 000 000 rows", "게시글 문장"),
    ("[AI generated] Freight forwarding and logistics company.", "회사 소개(AI 가 지음)"),
    # 오탐 시험. 회사 소개에 data 나 customer 가 들어가도 게시글 문장이 아니다
    ("Managed file transfer product exploited; downstream customer data exposed",
     "회사 소개로 보임"),
    ("A medical device company specializing in ultrasound imaging systems.",
     "회사 소개로 보임"),
]:
    check("성격 %r" % s[:28], F.desc_kind(s), want)
for uid in ("u1", "u2", "u3"):
    v = by[uid]["알림 문장"]
    if not str(v).startswith(A.MISS) and "게시글 본문이 아니다" not in v:
        fails.append("%s 알림 문장에 경고가 없다: %r" % (uid, v))

# ── 7. 알림 파서와 칸이 같다 ────────────────────
check("칸 이름과 순서가 같다", [k for k in F.ORDER], A.ORDER)
for k in A.ORDER:
    if k not in r:
        fails.append("칸이 빠졌다: %s" % k)

# ── 8. 버리지 않고 들고 있는다 ──────────────────
for k in ("uid", "설명 성격", "country", "sector", "kr_score"):
    if k not in r["기타"]:
        fails.append("기타에 %s 가 없다" % k)

# ── 9. 큐 폴더를 만든다. 두 번 돌려도 안 늘어난다 ──
q = tmp / "_큐"
n1, held1 = F.write_queue(rows, q)
n2, held2 = F.write_queue(rows, q)
check("처음에 넷", n1, 4)
check("두 번째는 안 늘어난다", n2, 0)
# Kr-Leak 표에는 성격 칸이 없다. 하나도 거르지 않아야 한다
check("krleak 는 안 거른다", (held1, held2), (0, 0))
check("성격 칸이 없으면 다 올린다", F.case_worthy({"기타": {"uid": "x"}}), True)
check("우리 표인데 성격이 비면 안 올린다",
      F.case_worthy({"기타": {"소스": "telegram"}}), False)
check("우리 표이고 성격이 있으면 올린다",
      F.case_worthy({"기타": {"소스": "telegram", "kind": "랜섬웨어 유출"}}), True)
# 못 봄 값이 폴더 이름에 안 들어간다
check("못 봄은 대상미상", F.slug("못 봄(target_org 비어 있음)"), "대상미상")
check("정상 이름은 그대로", F.slug("나무생각"), "나무생각")
made = sorted(p.name for p in q.iterdir())
check("폴더 넷", len(made), 4)
for d in q.iterdir():
    for f in ("재료.md", "상태.json"):
        if not (d / f).exists():
            fails.append("%s 에 %s 가 없다" % (d.name, f))
    if len(str(d.resolve())) > 200:
        fails.append("경로가 너무 길다 (%d자): %s" % (len(str(d.resolve())), d.name))

body = (q / made[0] / "재료.md").read_text(encoding="utf-8")
if "④ 마스킹 입력으로 쓰지 마라" not in body:
    fails.append("재료.md 에 ④ 경고가 없다")

# ── 10. --since 가 먹는다 ───────────────────────
# 다섯 중 6월 이후는 셋이다. u2 는 5월, u5 는 4월이다
check("6월 이후만", len(F.read(db, only_new=False, since="2026-06-01")), 3)
check("7월 이후는 없다", len(F.read(db, only_new=False, since="2026-07-01")), 0)

# ── 11. 표가 없으면 멈춘다 ──────────────────────
bad = tmp / "빈.db"
sqlite3.connect(bad).close()
try:
    F.read(bad, only_new=True, since=None)
    fails.append("victims 표가 없는데 안 멈췄다")
except SystemExit:
    pass

# ── 결과 ────────────────────────────────────────
if fails:
    print("실패 %d" % len(fails))
    for f in fails:
        print("  - %s" % f)
    sys.exit(1)
print("통과. 시험 11 묶음")
