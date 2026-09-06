"""track.py 시험. 랜섬 게시 상태 추적.

    python collect/test_track.py

메모리 SQLite 만 쓴다. 밖에 요청을 보내지 않는다.
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collect import track as T  # noqa: E402
from collect.store import SCHEMA  # noqa: E402

KST = timezone(timedelta(hours=9))


def _db() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    T.ensure(c)
    return c


def _item(c, uid, org, actor="grp", posted="2026-08-17T00:00:00+09:00"):
    c.execute(
        "INSERT INTO items (uid, source, venue, actor, target_org, posted_at, seen_at, "
        "country, kind, first_seen, last_seen) VALUES (?, 'ransom', 'x.onion', ?, ?, ?, "
        "'2026-08-29', 'KR', '랜섬웨어 유출', '2026-08-29', '2026-08-29')",
        (uid, actor, org, posted))


# ── 카운트다운 ─────────────────────────────────────────

def test_카운트다운_한국어():
    assert T.parse_countdown("19일 7시간") == timedelta(days=19, hours=7)
    assert T.parse_countdown("9일 3시간 14분 37초") == timedelta(days=9, hours=3, minutes=14, seconds=37)
    assert T.parse_countdown("3시간") == timedelta(hours=3)


def test_카운트다운_영어와_시계꼴():
    assert T.parse_countdown("9 days 3 hours") == timedelta(days=9, hours=3)
    assert T.parse_countdown("9d 03:14:37") == timedelta(days=9, hours=3, minutes=14, seconds=37)
    assert T.parse_countdown("03:14:37") == timedelta(hours=3, minutes=14, seconds=37)


def test_카운트다운_모르면_None():
    assert T.parse_countdown("") is None
    assert T.parse_countdown("만료") is None
    assert T.parse_countdown("곧") is None


def test_만료_계산_두_관측이_같은_만료를_낸다():
    """8/19 와 8/29 dlenc 관측. 열흘 간격인데 같은 만료를 가리켜야 한다."""
    e1 = T.expiry_from("2026-08-19T13:43:16+09:00", "19일 7시간")
    e2 = T.expiry_from("2026-08-29T17:28:00+09:00", "9일 3시간 14분 37초")
    d1 = datetime.fromisoformat(e1)
    d2 = datetime.fromisoformat(e2)
    assert d1.strftime("%Y-%m-%d %H") == "2026-09-07 20", e1
    assert abs((d1 - d2).total_seconds()) < 120, (e1, e2)


def test_만료_없으면_빈칸():
    assert T.expiry_from("2026-08-19T13:43:16+09:00", "") == ""
    assert T.expiry_from("2026-08-19T13:43:16+09:00", "만료") == ""


# ── 대상 찾기 ─────────────────────────────────────────

def test_대상은_uid_또는_조직명_조각():
    c = _db()
    _item(c, "u-dl", "DL E&C")
    _item(c, "u-ny", "Namyang")
    assert T.resolve_uid(c, "u-dl") == "u-dl"
    assert T.resolve_uid(c, "dl e") == "u-dl"           # 대소문자 무시
    assert T.resolve_uid(c, "namyang") == "u-ny"


def test_대상이_여럿이거나_없으면_멈춘다():
    c = _db()
    _item(c, "u-1", "Hyundai Steel")
    _item(c, "u-2", "Hyundai Wia")
    for q in ("hyundai", "없는곳"):
        try:
            T.resolve_uid(c, q)
        except T.대상없음 as e:
            assert q in str(e) or "hyundai" in str(e).lower()
            continue
        raise AssertionError("멈추지 않았다: %r" % q)


# ── 기록 ─────────────────────────────────────────────

def test_사람_관측을_적으면_만료가_같이_계산된다():
    c = _db()
    _item(c, "u-dl", "DL E&C")
    T.record(c, "u-dl", src="origin", by="최현서", state="게시 중",
             countdown="19일 7시간", at="2026-08-19T13:43:16+09:00", size_claim="50GB")
    r = c.execute("SELECT * FROM post_obs").fetchone()
    assert r["expiry_est"].startswith("2026-09-07T20:43")
    assert r["size_claim"] == "50GB" and r["files_n"] is None


def test_상태는_정해진_여섯만():
    c = _db()
    _item(c, "u-dl", "DL E&C")
    try:
        T.record(c, "u-dl", src="origin", by="x", state="아무거나", at="2026-08-19T00:00:00+09:00")
    except ValueError:
        return
    raise AssertionError("모르는 상태를 받았다")


def test_집계처_표시는_보인_것과_안_보인_것을_가른다():
    c = _db()
    for u in ("u-a", "u-b", "u-c"):
        _item(c, u, "org " + u)
    n = T.mark_agg(c, seen={"u-a", "u-c"}, at="2026-09-06T09:00:00+09:00", by="ransomlive/kr")
    assert n == 3
    got = {r["uid"]: r["state"] for r in c.execute("SELECT uid, state FROM post_obs")}
    assert got == {"u-a": "게시 중", "u-b": "안 보임", "u-c": "게시 중"}
    assert all(r["src"] == "agg" for r in c.execute("SELECT src FROM post_obs"))


# ── 세 숫자 ───────────────────────────────────────────

def _obs(c, uid, state, at, src="origin", countdown="", expiry=""):
    T.record(c, uid, src=src, by="t", state=state, countdown=countdown, at=at, expiry_est=expiry)


def test_세_숫자():
    c = _db()
    for u in ("A", "B", "C", "D", "E", "F", "G"):
        _item(c, u, "org " + u)
    exp = "2026-09-07T20:43:00+09:00"
    # A 만료 전 게시 중, 만료 뒤 공개됨  → 공개
    _obs(c, "A", "게시 중", "2026-09-01T00:00:00+09:00", expiry=exp)
    _obs(c, "A", "공개됨", "2026-09-08T00:00:00+09:00")
    # B 원 출처에서 사라짐  → 사라짐
    _obs(c, "B", "사라짐", "2026-09-05T00:00:00+09:00")
    # C 집계처 두 판 연속 안 보임  → 사라짐
    _obs(c, "C", "안 보임", "2026-09-05T00:00:00+09:00", src="agg")
    _obs(c, "C", "안 보임", "2026-09-06T00:00:00+09:00", src="agg")
    # D 만료 지났는데 그 뒤 원 출처 관측 없음  → 불명
    _obs(c, "D", "게시 중", "2026-09-01T00:00:00+09:00", expiry=exp)
    # E 연장  → 연장
    _obs(c, "E", "연장", "2026-09-08T00:00:00+09:00", countdown="10일")
    # F 집계처 한 번만 안 보임 뒤 다시 보임  → 아무 데도 안 든다
    _obs(c, "F", "안 보임", "2026-09-05T00:00:00+09:00", src="agg")
    _obs(c, "F", "게시 중", "2026-09-06T00:00:00+09:00", src="agg")
    # G 만료 뒤 원 출처에서 불명  → 불명
    _obs(c, "G", "게시 중", "2026-09-01T00:00:00+09:00", expiry=exp)
    _obs(c, "G", "불명", "2026-09-08T00:00:00+09:00")

    n = T.numbers(c, now="2026-09-09T00:00:00+09:00")
    assert n["공개됨"] == ["A"], n
    assert sorted(n["사라짐"]) == ["B", "C"], n
    assert sorted(n["불명"]) == ["D", "G"], n
    assert n["연장"] == ["E"], n


def test_만료_전에는_불명으로_안_센다():
    c = _db()
    _item(c, "D", "org D")
    _obs(c, "D", "게시 중", "2026-09-01T00:00:00+09:00", expiry="2026-09-07T20:43:00+09:00")
    n = T.numbers(c, now="2026-09-06T00:00:00+09:00")
    assert n["불명"] == [] and n["공개됨"] == [], n


def test_만료_전의_불명은_아직_못_본_것이다():
    """9/6 dlenc — 사이트가 안 열려 불명을 적었지만 만료는 9/7 이다. 만료 뒤에야 「공개 여부 불명」 이다."""
    c = _db()
    _item(c, "D", "org D"); _item(c, "E", "org E")
    _obs(c, "D", "게시 중", "2026-08-29T17:28:00+09:00", countdown="9일 3시간")   # 만료 9/7 20:28
    _obs(c, "D", "불명", "2026-09-06T19:00:00+09:00")
    assert T.numbers(c, now="2026-09-06T20:00:00+09:00")["불명"] == []          # 만료 전
    assert T.numbers(c, now="2026-09-08T00:00:00+09:00")["불명"] == ["D"]       # 만료 뒤
    # 만료를 모르는 건의 불명은 그대로 센다
    _obs(c, "E", "불명", "2026-09-06T19:00:00+09:00")
    assert "E" in T.numbers(c, now="2026-09-06T20:00:00+09:00")["불명"]


def test_기록은_넣은_줄의_rowid_를_돌려준다():
    c = _db()
    _item(c, "A", "org A")
    r1 = T.record(c, "A", src="agg", by="t", state="게시 중", at="2026-09-06T09:00:00+09:00")
    r2 = T.record(c, "A", src="origin", by="t", state="게시 중",
                  countdown="1일", at="2026-08-19T00:00:00+09:00")   # 소급. 시각은 앞선다
    assert r2 == r1 + 1
    row = c.execute("SELECT expiry_est FROM post_obs WHERE rowid=?", (r2,)).fetchone()
    assert row["expiry_est"].startswith("2026-08-20")


def test_보고서는_집계처만_본_자리를_한_줄로_줄인다():
    c = _db()
    for u in ("A", "B", "C"):
        _item(c, u, "org " + u)
    T.mark_agg(c, seen={"A", "B", "C"}, at="2026-09-06T09:00:00+09:00", by="agg")
    md = T.report_md(c, now="2026-09-06T10:00:00+09:00")
    assert "집계처만 본 자리 3곳 — 게시 중 3" in md
    assert "| org A |" not in md
    # 원 출처 관측이 생기면 그 자리만 표에 오른다
    _obs(c, "A", "게시 중", "2026-09-06T09:30:00+09:00", countdown="2일")
    md = T.report_md(c, now="2026-09-06T10:00:00+09:00")
    assert "집계처만 본 자리 2곳" in md and "| org A |" in md and "| org B |" not in md


# ── 노션에서 끌어오기 ───────────────────────────────

def _notion_rows():
    """수집 DB 에서 관측 칸이 찬 줄을 흉내 낸다. 값은 지어낸 것이다."""
    return [
        {"page_id": "p1", "uid": "u-dl", "대상 조직": "DL E&C", "관측 시각": "2026-09-06T18:00:00.000+09:00",
         "게시 상태": "불명", "카운트다운 표기": "", "공개된 파일 수": None, "주장 규모": "50GB",
         "관측 근거": "사이트 접속 불가", "관측자": "최현서"},
        {"page_id": "p2", "uid": "", "대상 조직": "Namyang", "관측 시각": "2026-09-05T10:00:00.000+09:00",
         "게시 상태": "연장", "카운트다운 표기": "10일", "공개된 파일 수": None, "주장 규모": "",
         "관측 근거": "기한이 늘었다", "관측자": ""},                       # uid 없음 → 조직명으로 찾는다
        {"page_id": "p3", "uid": "", "대상 조직": "없는곳", "관측 시각": "2026-09-05T10:00:00.000+09:00",
         "게시 상태": "게시 중", "카운트다운 표기": "", "공개된 파일 수": None, "주장 규모": "",
         "관측 근거": "", "관측자": ""},                                   # 표에 없는 조직 → 건너뛴다
        {"page_id": "p4", "uid": "u-ny", "대상 조직": "Namyang", "관측 시각": "",
         "게시 상태": "공개됨", "카운트다운 표기": "", "공개된 파일 수": 3, "주장 규모": "",
         "관측 근거": "", "관측자": ""},                                   # 관측 시각 없음 → 건너뛴다
    ]


def test_노션_관측을_post_obs_로():
    c = _db()
    _item(c, "u-dl", "DL E&C"); _item(c, "u-ny", "Namyang")
    got = T.pull_rows(c, _notion_rows())
    assert got["넣음"] == 2 and got["건너뜀"] == 2, got
    rows = {r["uid"]: dict(r) for r in c.execute("SELECT * FROM post_obs")}
    assert rows["u-dl"]["state"] == "불명" and rows["u-dl"]["src"] == "origin"
    assert rows["u-dl"]["by"] == "최현서" and rows["u-dl"]["size_claim"] == "50GB"
    assert rows["u-dl"]["note"] == "사이트 접속 불가"
    assert rows["u-ny"]["state"] == "연장" and rows["u-ny"]["expiry_est"].startswith("2026-09-15")
    assert rows["u-ny"]["by"] == "노션"                  # 관측자 빈칸이면


def test_같은_관측을_두_번_끌어와도_한_줄():
    c = _db()
    _item(c, "u-dl", "DL E&C"); _item(c, "u-ny", "Namyang")
    T.pull_rows(c, _notion_rows())
    got = T.pull_rows(c, _notion_rows())
    assert got["넣음"] == 0 and got["이미 있음"] == 2, got
    assert c.execute("SELECT COUNT(*) FROM post_obs").fetchone()[0] == 2
    # 사람이 같은 행의 관측 시각을 고치면 (다시 봤으면) 새 줄이 쌓인다 — 이력은 여기서 생긴다
    rows = _notion_rows()
    rows[0]["관측 시각"] = "2026-09-07T21:00:00.000+09:00"; rows[0]["게시 상태"] = "공개됨"
    got = T.pull_rows(c, rows)
    assert got["넣음"] == 1
    hist = [r["state"] for r in c.execute("SELECT state FROM post_obs WHERE uid='u-dl' ORDER BY observed_at")]
    assert hist == ["불명", "공개됨"]


def test_모르는_게시_상태는_건너뛴다():
    c = _db()
    _item(c, "u-dl", "DL E&C")
    rows = _notion_rows()[:1]
    rows[0]["게시 상태"] = "아무거나"
    got = T.pull_rows(c, rows)
    assert got["넣음"] == 0 and got["건너뜀"] == 1 and "아무거나" in " ".join(got["사유"])


def test_보고서는_값을_안_낸다():
    """조직명과 상태·시각만 나간다. 주소·본문은 없다."""
    c = _db()
    _item(c, "A", "DL E&C")
    _obs(c, "A", "게시 중", "2026-08-19T13:43:16+09:00", countdown="19일 7시간")
    md = T.report_md(c, now="2026-09-06T00:00:00+09:00")
    assert "DL E&C" in md and "19일 7시간" in md and "2026-09-07" in md
    assert "x.onion" not in md and ".onion" not in md


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_"):
            v(); print("  OK  %s" % k); n += 1
    print("\n%d개 통과" % n)
