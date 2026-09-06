"""stats.py 시험. 한국 관련 랜섬웨어 게시 통계.

    python collect/test_stats.py

메모리 SQLite 만 쓴다. 노션에는 안 나간다 — 깔때기는 가짜 줄로 계산한다.
값은 전부 지어낸 것이다.
"""
from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
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


# ── 소스와 국가를 바꿔서 고르기 ─────────────────────────

def _fill_mixed(c):
    """소스와 국가가 섞인 표. 위의 _fill 은 안 건드린다 — 기존 시험의 숫자가 거기 걸려 있다."""
    _item(c, "r1", "Alpha Co", "qilin", "2026-08-17T10:00:00+00:00")                    # 랜섬 KR
    _item(c, "r2", "Beta Ltd", "qilin", "2026-08-18T10:00:00+00:00", country="US")
    _item(c, "t1", "", "handle1", "2026-08-19T10:00:00+00:00", country="", source="telegram")
    _item(c, "t2", "Gamma", "handle2", "2026-08-20T10:00:00+00:00", source="telegram")  # 텔레그램 KR
    _item(c, "f1", "", "poster", "2026-08-21T10:00:00+00:00", country="", source="forum")


def test_기본값은_예전과_같다():
    """인자를 안 주면 랜섬 KR 만. 기본값이 흔들리면 예전 보고서와 숫자가 어긋난다."""
    c = _db(); _fill_mixed(c)
    assert [r["uid"] for r in S.load_rows(c)] == ["r1"]
    assert S.load_rows(c) == S.load_rows(c, source="ransom", country="KR")


def test_소스를_텔레그램으로():
    c = _db(); _fill_mixed(c)
    assert [r["uid"] for r in S.load_rows(c, source="telegram")] == ["t2"]
    assert sorted(r["uid"] for r in S.load_rows(c, source="telegram", country="all")) == ["t1", "t2"]


def test_소스가_all_이면_소스_조건을_뺀다():
    c = _db(); _fill_mixed(c)
    assert sorted(r["uid"] for r in S.load_rows(c, source="all", country="all")) == [
        "f1", "r1", "r2", "t1", "t2"]
    assert sorted(r["uid"] for r in S.load_rows(c, source="all")) == ["r1", "t2"]  # 국가는 KR 로 남는다


def test_국가가_all_이면_국가가_빈_줄도_나온다():
    c = _db(); _fill_mixed(c)
    assert sorted(r["uid"] for r in S.load_rows(c, country="all")) == ["r1", "r2"]
    assert [r["uid"] for r in S.load_rows(c, source="forum", country="all")] == ["f1"]
    assert S.load_rows(c, source="forum") == []          # 포럼은 국가를 안 채운다


def test_소스_값이_이상해도_SQL_이_안_깨진다():
    """값은 바인딩(?)으로 들어간다. 이어 붙이면 바깥에서 온 값이 SQL 이 된다."""
    c = _db(); _fill_mixed(c)
    assert S.load_rows(c, source="ransom'; DROP TABLE items; --") == []
    assert S.load_rows(c, country="KR' OR '1'='1") == []
    assert [r["uid"] for r in S.load_rows(c)] == ["r1"]   # 표가 그대로 있다


def test_분모는_빈칸을_빈_것으로_센다():
    """'' 과 NULL 을 둘 다 빈 것으로 센다. 수집기마다 안 채운 칸의 꼴이 다르다."""
    c = _db(); _fill_mixed(c)
    c.execute("INSERT INTO items (uid, source, venue, actor, target_org, posted_at, seen_at, "
              "country, first_seen, last_seen) VALUES "
              "('t3','telegram','x','h',NULL,'2026-08-22T10:00:00+00:00','2026-08-29',NULL,"
              "'2026-08-29','2026-08-29')")
    d = S.denominator(c, source="telegram", country="all")
    assert d == {"소스": "telegram", "전체": 3, "국가 있음": 1, "대상 조직 있음": 1, "쓴 것": 3}, d
    assert S.denominator(c, source="telegram")["쓴 것"] == 1        # KR 은 한 줄뿐
    assert S.denominator(c, source="forum", country="all") == {
        "소스": "forum", "전체": 1, "국가 있음": 0, "대상 조직 있음": 0, "쓴 것": 1}


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


COLLECTED_SRC = [   # 「소스」 칸이 찬 줄과 빈 옛 줄이 섞인 수집 DB
    {"사건 ID": "LEAK-40", "소스": "랜섬웨어", "게시 성격": "랜섬웨어 유출", "국가": "한국"},
    {"사건 ID": "LEAK-41", "소스": "텔레그램", "게시 성격": "DB 판매", "국가": "한국"},
    # 소스 칸이 게시 성격보다 앞선다. 이 줄은 랜섬이 아니라 텔레그램이다
    {"사건 ID": "LEAK-42", "소스": "텔레그램", "게시 성격": "랜섬웨어 유출", "국가": "한국"},
    {"사건 ID": "LEAK-43", "게시 성격": "랜섬웨어 유출", "국가": "한국"},      # 소스 칸이 빈 옛 줄
    {"사건 ID": "LEAK-44", "게시 성격": "DB 판매", "국가": "한국"},           # 빈 줄이고 랜섬도 아님
    {"사건 ID": "LEAK-45", "소스": "랜섬웨어", "게시 성격": "랜섬웨어 유출", "국가": "미국"},
]


def test_깔때기는_소스_칸으로_고른다():
    f = S.funnel(0, COLLECTED_SRC, [], source="telegram")
    assert f["수집 DB"] == 2      # 41 · 42. 게시 성격이 무엇이든 소스 칸이 이긴다


def test_깔때기는_소스_칸이_비면_게시_성격으로_되짚는다():
    """「소스」 칸은 2026-09-06 에 만들었다. 옛 줄이 통째로 빠지면 안 된다."""
    f = S.funnel(0, COLLECTED_SRC, [], source="ransom")
    assert f["수집 DB"] == 2      # 40 (소스 칸) · 43 (되짚기). 42 는 텔레그램이라 뺀다
    # 국가 조건은 country 가 all 이 아닐 때만 건다
    assert S.funnel(0, COLLECTED_SRC, [], source="ransom", country="all")["수집 DB"] == 3


def test_깔때기는_소스_칸이_빈_줄을_텔레그램으로_안_센다():
    """빈 줄이 어느 소스인지는 알 방법이 없다. 되짚기는 ransom 일 때만 된다."""
    only_blank = [{"사건 ID": "LEAK-50", "게시 성격": "랜섬웨어 유출", "국가": "한국"}]
    assert S.funnel(0, only_blank, [], source="telegram")["수집 DB"] == 0
    assert S.funnel(0, only_blank, [], source="ransom")["수집 DB"] == 1


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


# ── 게시자 이름을 안 내는가 ─────────────────────────────

def _fill_actors(c):
    """actor 칸에 개인 계정 꼴 값이 든 표. 값은 전부 지어낸 것이다."""
    _item(c, "t1", "", "handle_one", "2026-08-19T10:00:00+00:00", country="", source="telegram")
    _item(c, "t2", "", "handle_two", "2026-08-20T10:00:00+00:00", country="", source="telegram")
    _item(c, "t3", "", "handle_one", "2026-08-21T10:00:00+00:00", country="", source="telegram")
    _item(c, "t4", "", "", "2026-08-22T10:00:00+00:00", country="", source="telegram")   # 빈칸
    _item(c, "r1", "Alpha Co", "qilin", "2026-08-17T10:00:00+00:00")                     # 랜섬 KR


def test_고유_게시자_수는_빈칸을_뺀다():
    c = _db(); _fill_actors(c)
    rows = S.load_rows(c, source="telegram", country="all")
    assert S.actor_unique(rows) == 2          # handle_one · handle_two. 빈칸은 안 센다
    assert S.actor_unique([]) == 0


def test_랜섬이_아니면_md_에_게시자_이름이_안_나온다():
    c = _db(); _fill_actors(c)
    rows = S.load_rows(c, source="telegram", country="all")
    md = S.render_md(rows, funnel=S.funnel(len(rows), None, None, "telegram", "all"),
                     now="2026-09-07T12:00:00+09:00", source="telegram", country="all")
    for name in ("handle_one", "handle_two"):
        assert name not in md, name
    assert "고유 게시자 2명" in md
    assert "행위자별" not in md               # 표 제목도 안 나온다


def test_랜섬이_아니면_행위자별_csv_를_안_만든다():
    c = _db(); _fill_actors(c)
    rows = S.load_rows(c, source="telegram", country="all")
    csvs = S.render_csv(rows, top=10, source="telegram")
    assert set(csvs) == {"월별", "업종별", "규모"}      # md 가 「게시자별」 인데 csv 만 남던 것을 없앤다
    for name in ("handle_one", "handle_two"):
        assert not any(name in t for t in csvs.values()), name
    assert set(S.render_csv(rows, top=10, source="ransom")) == {
        "월별", "행위자별", "업종별", "규모"}          # 랜섬일 때는 그대로 낸다


def test_소스가_all_이면_섞이니_게시자를_안_낸다():
    """all 은 랜섬 그룹명과 개인 계정명이 한 표에 섞인다. 가를 방법이 없으니 안 내는 쪽으로 간다."""
    c = _db(); _fill_actors(c)
    rows = S.load_rows(c, source="all", country="all")
    md = S.render_md(rows, funnel=S.funnel(len(rows), None, None, "all", "all"),
                     now="2026-09-07T12:00:00+09:00", source="all", country="all")
    assert "handle_one" not in md and "qilin" not in md
    assert "고유 게시자 3명" in md
    assert set(S.render_csv(rows, top=10, source="all")) == {"월별", "업종별", "규모"}


# ── 깔때기의 국가 ───────────────────────────────────────

def test_깔때기는_KR_이면_한국_줄을_고른다():
    f = S.funnel(0, COLLECTED, VERIFIED, source="ransom", country="KR")
    assert f["수집 DB"] == 4          # 국가가 「한국」 인 줄만. 「미국」 인 13 은 빠진다
    assert "국가 못 잇음" not in f


def test_깔때기는_짝을_모르는_국가면_안_낸다():
    """items 는 ISO 코드고 노션은 한글이다. 짝을 모르면 틀린 숫자를 내느니 안 내는 쪽이 맞다."""
    f = S.funnel(7, COLLECTED, VERIFIED, source="ransom", country="US")
    assert f["집계처"] == 7
    assert f["수집 DB"] is None and f["검증 완료"] is None and f["실제 데이터 확인"] is None
    assert "국가 US" in f["국가 못 잇음"] and "깔때기를 내지 않는다" in f["국가 못 잇음"]
    md = S.render_md([], f, now="2026-09-07T12:00:00+09:00", source="ransom", country="US")
    assert f["국가 못 잇음"] in md


# ── 분모와 기간 ────────────────────────────────────────

def test_분모는_기간을_건_숫자와_안_건_숫자를_둘_다_낸다():
    c = _db(); _fill(c)
    d = S.denominator(c, source="ransom", country="KR", since="2026-07-01")
    assert d["전체"] == 6                  # 랜섬 전체. 기간을 안 건 숫자
    assert d["기간 안"] == 5               # 2025-12 줄 하나가 빠진다
    assert d["쓴 것"] == 5                 # 랜섬 KR (국가 US 한 줄 제외)
    d2 = S.denominator(c, source="ransom", country="KR", since="2026-08-01", until="2026-08-18")
    assert d2["기간 안"] == 2 and d2["전체"] == 6
    assert "기간 안" not in S.denominator(c, source="ransom", country="KR")  # 기간을 안 주면 열쇠가 없다


def test_분모의_국가_칸_수는_기간_안에서_센다():
    """안 그러면 「기간 안 N줄」 밑에 그보다 큰 「국가가 찬 것」 이 나온다."""
    c = _db(); _fill_mixed(c)
    d = S.denominator(c, source="all", country="all", since="2026-08-20")
    assert d["전체"] == 5 and d["기간 안"] == 2          # t2 · f1
    assert d["국가 있음"] == 1                           # t2 만 국가가 차 있다
    assert d["국가 있음"] <= d["기간 안"]


# ── 산출물 전수 확인 ────────────────────────────────────
#
# 출력 자리마다 관문을 달다가 두 번 빠뜨렸다. 자리별 시험은 새 자리가 생기면 같이 늘려야 하는데
# 그것을 잊는 것이 빠뜨린 이유였다. 그래서 산출물 폴더를 통째로 훑는 시험을 둔다.

MARK_TG = "ZZTESTACTOR1"      # 텔레그램 actor 자리의 표식. 실제 계정명이 아니다
MARK_TG2 = "ZZTESTACTOR2"
MARK_RS = "ZZTESTGROUP1"      # 랜섬 actor 자리. 랜섬일 때는 이것이 나오는 것이 정상이다


def _file_db(path: Path) -> None:
    """파일 sqlite 에 랜섬 줄과 텔레그램 줄을 넣는다. main() 은 메모리 표를 못 읽는다."""
    from collect.store import Store
    s = Store(path)
    _item(s.con, "r1", "Alpha Co", MARK_RS, "2026-08-17T10:00:00+00:00", size="50GB", sector="건설")
    _item(s.con, "t1", "Chan One", MARK_TG, "2026-08-19T10:00:00+00:00", source="telegram")
    _item(s.con, "t2", "Chan Two", MARK_TG2, "2026-08-20T10:00:00+00:00", source="telegram")
    _item(s.con, "t3", "Chan One", MARK_TG, "2026-08-21T10:00:00+00:00", source="telegram")
    s.con.commit()
    s.close()


def _run(db: Path, out: Path, *extra) -> int:
    """main() 을 인자로 돌린다. 노션에는 안 나간다 (--no-notion)."""
    argv = sys.argv
    sys.argv = ["stats", "--db", str(db), "--out", str(out), "--no-notion",
                "--now", "2026-09-07T12:00:00+09:00", *extra]
    try:
        return S.main()
    finally:
        sys.argv = argv


def _scan(out: Path) -> list:
    """폴더 안 모든 파일에서 게시자 표식을 찾는다. 파일은 바이트로 읽어 글자만 훑는다."""
    hits = []
    for p in sorted(out.rglob("*")):
        if not p.is_file():
            continue
        text = p.read_bytes().decode("utf-8", "ignore")
        hits += [(p.name, m) for m in (MARK_TG, MARK_TG2) if m in text]
    return hits


def test_모든_인자_조합에서_게시자_표식이_안_나간다():
    """조합마다 산출물 폴더를 통째로 훑는다. 출력 자리를 새로 만들어도 여기서 걸린다."""
    combos = [
        ("--source", "telegram"),
        ("--source", "telegram", "--list"),
        ("--source", "telegram", "--country", "all"),
        ("--source", "telegram", "--country", "all", "--list"),
        ("--source", "all"),
        ("--source", "all", "--list"),
        ("--source", "all", "--country", "all"),
        ("--source", "all", "--country", "all", "--list"),
    ]
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        db = d / "t.db"
        _file_db(db)
        for i, c in enumerate(combos):
            out = d / ("o%d" % i)
            assert _run(db, out, *c) == 0, c
            assert (out / "통계_20260907.md").exists(), c      # 진짜로 냈는지부터 본다
            assert _scan(out) == [], (c, _scan(out))
        # 랜섬일 때는 그룹명(조직)이 나오는 것이 정상이다. 개인 계정 표식만 없으면 된다
        out = d / "ors"
        assert _run(db, out, "--source", "ransom", "--list") == 0
        assert _scan(out) == []
        assert MARK_RS in (out / "행위자별.csv").read_text(encoding="utf-8")


def test_소스를_바꿔_다시_돌리면_옛_행위자_산출물을_덮는다():
    """같은 --out 에 소스를 바꿔 다시 돌리는 것이 자연스러운 쓰임이다.

    안 만들기만 하면 앞서 랜섬으로 낸 판이 그대로 남는다. 지우지 않고 덮는다.
    """
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        db = d / "t.db"
        _file_db(db)
        out = d / "o"
        assert _run(db, out, "--source", "ransom", "--list") == 0
        csv_p = out / "행위자별.csv"
        lst = out / "목록_20260907.md"
        assert MARK_RS in csv_p.read_text(encoding="utf-8")
        assert MARK_RS in lst.read_text(encoding="utf-8")

        # --list 를 안 줘도 그 자리에 있던 옛 목록을 덮는다
        assert _run(db, out, "--source", "telegram") == 0
        assert MARK_RS not in csv_p.read_text(encoding="utf-8")
        assert "고유 게시자 수,2" in csv_p.read_text(encoding="utf-8")
        assert MARK_RS not in lst.read_text(encoding="utf-8")
        assert "행위자" not in lst.read_text(encoding="utf-8")   # 칸 자체가 빠진다
        assert "Chan One" in lst.read_text(encoding="utf-8")     # 남는 칸은 그대로 낸다
        assert _scan(out) == []


def test_랜섬이_아니면_목록에서_행위자_칸을_뺀다():
    """값은 main() 이 이미 지웠다. 빈칸만 늘어선 칸은 뜻이 없으니 칸 자체를 뺀다."""
    c = _db(); _fill_actors(c)
    rows = S.load_rows(c, source="telegram", country="all")
    t = S.list_table(rows, source="telegram")
    assert t.splitlines()[0] == "| 게시일 | 대상 | 규모 표기 | 업종 |", t.splitlines()[0]
    assert S.list_table(rows).splitlines()[0] == "| 게시일 | 대상 | 행위자 | 규모 표기 | 업종 |"


# ── 분모 문장 ──────────────────────────────────────────

def test_분모_경고는_같은_모집단끼리_견준다():
    """기간을 걸면 「국가 있음」 은 기간 안 값이다. 기간을 안 건 「전체」 와 견주면 헛나간다."""
    c = _db(); _fill(c)
    rows = S.load_rows(c, since="2026-08-01", country="all")
    den = S.denominator(c, source="ransom", country="all", since="2026-08-01")
    assert den["전체"] == 6 and den["기간 안"] == 3 and den["국가 있음"] == 3
    md = S.render_md(rows, funnel=S.funnel(len(rows), None, None, "ransom", "all"),
                     since="2026-08-01", now="2026-09-07T12:00:00+09:00",
                     source="ransom", country="all", den=den)
    assert "절반도 안 된다" not in md      # 기간 안 3줄이 다 차 있다


def test_국가_칸이_찬_몇_줄이라는_문장은_country_all_에서_안_낸다():
    """all 이면 국가 조건을 아예 안 걸어서 국가 칸이 비어도 분모에서 안 빠진다."""
    c = _db(); _fill_actors(c)
    rows = S.load_rows(c, source="telegram", country="all")
    den = S.denominator(c, source="telegram", country="all")
    md = S.render_md(rows, funnel=S.funnel(len(rows), None, None, "telegram", "all"),
                     now="2026-09-07T12:00:00+09:00", source="telegram", country="all", den=den)
    assert "절반도 안 된다" in md          # 국가가 찬 줄이 0 이라 경고는 나온다
    assert "국가 칸이 찬 몇 줄" not in md   # 그 문장만 뺀다


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_"):
            v(); print("  OK  %s" % k); n += 1
    print("\n%d개 통과" % n)
