"""stats.py 시험. 한국 관련 랜섬웨어 게시 통계.

    python collect/test_stats.py

메모리 SQLite 만 쓴다. 노션에는 안 나간다 — 깔때기는 가짜 줄로 계산한다.
값은 전부 지어낸 것이다.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collect import stats as S  # noqa: E402
from collect.store import SCHEMA  # noqa: E402


def _db() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c


def _item(c, uid, org, actor, posted, size="", sector="", found="", country="KR",
          source="ransom", venue="x.onion"):
    raw = {"산업 분야": sector}
    if found:
        raw["발견일"] = found
    c.execute(
        "INSERT INTO items (uid, source, venue, actor, target_org, posted_at, seen_at, country, "
        "kind, claimed_size, raw, first_seen, last_seen, post_url) VALUES "
        "(?,?,?,?,?,?,'2026-08-29',?,'랜섬웨어 유출',?,?,'2026-08-29','2026-08-29','http://x.onion/p')",
        (uid, source, venue, actor, org, posted, country, size, json.dumps(raw, ensure_ascii=False)))


def _fill(c):
    # posted_at 꼴 둘 (마이크로초 유무) 을 섞는다. 집계처가 둘 다 낸다
    _item(c, "a1", "Alpha Co", "qilin", "2026-08-17T10:00:00+00:00", size="50GB", sector="건설")
    _item(c, "a2", "Beta Ltd", "qilin", "2026-08-20T10:00:00.123456+00:00", size="-", sector="제조")
    _item(c, "a3", "Gamma", "panzer", "2026-07-01T00:00:00+00:00", size="", sector="제조",
          found="2026-07-03T00:00:00+00:00")
    _item(c, "a4", "Delta", "akira", "2026-07-15T00:00:00+00:00", size="---", sector="")
    _item(c, "a5", "Epsilon", "qilin", "2025-12-30T00:00:00+00:00", size="1.2 TB", sector="금융",
          found="2026-01-04T00:00:00+00:00")
    _item(c, "us", "Foreign", "qilin", "2026-08-01T00:00:00+00:00", country="US")   # 한국 아님
    _item(c, "tg", "Chan", "someone", "2026-08-01T00:00:00+00:00", source="telegram")  # 랜섬 아님


# ── 고르기 ─────────────────────────────────────────────

def test_한국_랜섬_줄만_고른다():
    c = _db(); _fill(c)
    rows = S.load_rows(c)
    assert sorted(r["uid"] for r in rows) == ["a1", "a2", "a3", "a4", "a5"]


def test_기간으로_거른다():
    c = _db(); _fill(c)
    rows = S.load_rows(c, since="2026-07-01", until="2026-07-31")
    assert sorted(r["uid"] for r in rows) == ["a3", "a4"]
    rows = S.load_rows(c, since="2026-08-01")
    assert sorted(r["uid"] for r in rows) == ["a1", "a2"]


# ── 가르기 ─────────────────────────────────────────────

def test_월별은_두_시각_꼴을_다_읽는다():
    c = _db(); _fill(c)
    m = S.by_month(S.load_rows(c))
    assert m == {"2025-12": 1, "2026-07": 2, "2026-08": 2}, m


def test_행위자별은_상위와_그_밖으로():
    c = _db(); _fill(c)
    a = S.by_actor(S.load_rows(c), top=1)
    assert a == [("qilin", 3), ("그 밖 (2개 그룹)", 2)], a
    a = S.by_actor(S.load_rows(c), top=10)
    assert a[0] == ("qilin", 3) and len(a) == 3 and "그 밖" not in a[-1][0]


def test_업종별은_빈칸을_따로_센다():
    c = _db(); _fill(c)
    i = S.by_industry(S.load_rows(c))
    assert i == [("제조", 2), ("건설", 1), ("금융", 1), ("(빈칸)", 1)], i


def test_규모는_셋으로_가른다():
    """값 있음 · 대시뿐 · 빈칸. 대시는 값이 아니고 빈칸은 「주장 없음」 이 아니다."""
    c = _db(); _fill(c)
    s = S.size_split(S.load_rows(c))
    assert s == {"값 있음": 2, "대시뿐": 2, "빈칸": 1}, s


def test_발견_지연은_발견일이_있는_줄만():
    c = _db(); _fill(c)
    d = S.discovery_lag(S.load_rows(c))
    assert d["줄"] == 2 and d["중앙값(일)"] == 3.5 and d["최대(일)"] == 5, d
    c2 = _db()
    _item(c2, "z", "Z", "g", "2026-08-01T00:00:00+00:00")
    assert S.discovery_lag(S.load_rows(c2))["줄"] == 0


# ── 깔때기 ─────────────────────────────────────────────

COLLECTED = [   # 노션 수집 DB 흉내. 사건 ID · 게시 성격 · 국가
    {"사건 ID": "LEAK-10", "게시 성격": "랜섬웨어 유출", "국가": "한국"},
    {"사건 ID": "LEAK-11", "게시 성격": "랜섬웨어 유출", "국가": "한국"},
    {"사건 ID": "LEAK-12", "게시 성격": "DB 판매", "국가": "한국"},        # 랜섬 아님
    {"사건 ID": "LEAK-13", "게시 성격": "랜섬웨어 유출", "국가": "미국"},    # 한국 아님
    {"사건 ID": "LEAK-14", "게시 성격": "랜섬웨어 유출", "국가": "한국"},
    # 수집기가 자동으로 넣은 줄. 사람이 아직 안 봤거나 사건이 아니라고 했다 → 「팀이 골라 올린 것」 이 아니다
    {"사건 ID": "LEAK-30", "게시 성격": "랜섬웨어 유출", "국가": "한국", "검토 여부": "미검토"},
    {"사건 ID": "LEAK-31", "게시 성격": "랜섬웨어 유출", "국가": "한국", "검토 여부": "사건 X"},
    {"사건 ID": "LEAK-32", "게시 성격": "랜섬웨어 유출", "국가": "한국", "검토 여부": "사건 O"},
]
VERIFIED = [    # 노션 검증 DB 흉내
    {"사건 ID": "LEAK-10", "진위 판정": "신뢰성 높음", "핵심 검증 결과": ["대상 일치", "샘플 확인"]},
    {"사건 ID": "LEAK-11", "진위 판정": "허위", "핵심 검증 결과": ["대상 일치"]},
    {"사건 ID": "LEAK-12", "진위 판정": "신뢰성 높음", "핵심 검증 결과": ["샘플 확인"]},   # 랜섬 아님 → 안 셈
    {"사건 ID": "LEAK-99", "진위 판정": "미확인", "핵심 검증 결과": []},                  # 수집 DB 에 없음
]


def test_깔때기():
    f = S.funnel(n_agg=119, collected=COLLECTED, verified=VERIFIED)
    assert f["집계처"] == 119
    assert f["수집 DB"] == 4          # 10 · 11 · 14 (빈칸 = 사건 O) · 32 (사건 O). 미검토 30 과 사건 X 31 은 뺀다
    assert f["검증 완료"] == 2        # 10 · 11
    assert f["실제 데이터 확인"] == 1  # 10 (신뢰성 높음 + 샘플 확인)
    assert f["판정"] == {"신뢰성 높음": 1, "허위": 1}, f["판정"]
    assert "키가 없다" in f["주의"] or "골라" in f["주의"]
    # 분모 밖 검증도 센다. 랜섬 KR 깔때기가 0 이어도 「검증을 안 했다」 로 읽히면 안 된다
    assert f["검증 DB 전체"] == 4
    assert f["분모 밖 검증"] == {"DB 판매": 1, "(수집 DB 에 없음)": 1}, f["분모 밖 검증"]


def test_깔때기_노션_없이():
    f = S.funnel(n_agg=119, collected=None, verified=None)
    assert f["집계처"] == 119 and f["수집 DB"] is None and f["검증 완료"] is None


# ── 내보내기 ───────────────────────────────────────────

def test_md_는_주소를_안_낸다():
    c = _db(); _fill(c)
    rows = S.load_rows(c)
    md = S.render_md(rows, funnel=S.funnel(5, COLLECTED, VERIFIED), since="2025-12-01",
                     until="2026-09-06", now="2026-09-06T12:00:00+09:00", top=10)
    for must in ("5건", "qilin", "제조", "대시뿐", "주장 없음", "집계처", "샘플 확인"):
        assert must in md, must
    assert ".onion" not in md and "http" not in md
    assert "Alpha Co" not in md               # 조직 목록은 기본으로 안 낸다


def test_list_는_따로_낸다():
    c = _db(); _fill(c)
    t = S.list_table(S.load_rows(c))
    assert "Alpha Co" in t and "qilin" in t and "2026-08-17" in t
    assert ".onion" not in t and "http" not in t


def test_csv_줄():
    c = _db(); _fill(c)
    rows = S.load_rows(c)
    csvs = S.render_csv(rows, top=10)
    assert set(csvs) == {"월별", "행위자별", "업종별", "규모"}
    assert csvs["월별"].splitlines()[0] == "월,건수"
    assert "2026-08,2" in csvs["월별"]


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_"):
            v(); print("  OK  %s" % k); n += 1
    print("\n%d개 통과" % n)
