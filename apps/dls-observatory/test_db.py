#!/usr/bin/env python3
"""DB 계층 검증. 실제 노션·API 없이 동작을 확인한다.  python test_db.py"""
import json
import os
import sys
from pathlib import Path
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 윈도우 콘솔(cp949)에서 한글·기호로 죽는 것을 막습니다.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages"))
from dc_console import use_utf8  # noqa: E402

use_utf8()
import db as D  # noqa: E402

TMP = tempfile.mkdtemp(prefix="dlsdb-")
DBP = os.path.join(TMP, "t.sqlite3")

# --- 1차 수집: 8/17 -------------------------------------------------------
RUN1 = [
    {"name": "THE MATRIX", "url": "https://thematrixstore.at",
     "checked_at": "2026-08-17T10:00:00+00:00", "reachable": True, "status": "online",
     "http_status": 200, "final_url": "https://thematrixstore.at/",
     "title": "TheMatrix - Sign In", "language": "영어",
     "signup_required": True, "gate_signals": ["캡차", "회원가입"],
     "how_to_enter": "캡차 있음, 회원가입 필요"},
    {"name": "Savastan0", "url": "https://savastan0.tools/",
     "checked_at": "2026-08-17T10:01:00+00:00", "reachable": False, "status": "offline",
     "error": "Tor 연결: 호스트 도달 불가"},
    {"name": "PREPAID CARD STORE (Deep)", "url": "http://prep.onion",
     "checked_at": "2026-08-17T10:02:00+00:00", "reachable": True, "status": "online",
     "http_status": 200, "title": "A Prepaid Credit - Card Supplier",
     "language": "영어", "signup_required": False, "gate_signals": [],
     "how_to_enter": "공개 접근 (로그인·캡차 신호 없음)"},
    # Tor 끊김 구간 — 들어가면 안 됨
    {"name": "GHOST", "url": "http://ghost.onion", "status": "미확인",
     "unreliable": "Tor 끊김 구간", "checked_at": "2026-08-17T10:03:00+00:00"},
]

# --- 2차 수집: 8/24 — MATRIX 가 죽고, Savastan0 는 주소를 바꿔 살아남 ------
RUN2 = [
    {"name": "THE MATRIX", "url": "https://thematrixstore.at",
     "checked_at": "2026-08-24T10:00:00+00:00", "reachable": False, "status": "offline",
     "error": "시간 초과"},
    {"name": "Savastan0", "url": "https://savastan0.cc/",
     "checked_at": "2026-08-24T10:01:00+00:00", "reachable": True, "status": "online",
     "http_status": 200, "final_url": "https://savastan0.cc/",
     "title": "Savastan0 CC Shop", "language": "영어, 러시아어",
     "signup_required": True, "gate_signals": ["로그인"], "how_to_enter": "로그인 필요"},
    {"name": "PREPAID CARD STORE (Deep)", "url": "http://prep.onion",
     "checked_at": "2026-08-24T10:02:00+00:00", "reachable": True, "status": "online",
     "http_status": 200, "title": "A Prepaid Credit - Card Supplier",
     "language": "영어", "signup_required": False, "how_to_enter": "공개 접근 (로그인·캡차 신호 없음)"},
]

RL_GROUPS = [
    {"name": "qilin", "altname": "Agenda", "added_date": "2022-10-01",
     "description": "Qilin ransomware group.",
     "locations": [{"slug": "http://qilin1.onion", "fqdn": "qilin1.onion",
                    "type": "DLS", "available": True, "title": "Qilin"},
                   {"slug": "http://qilinchat.onion", "fqdn": "qilinchat.onion",
                    "type": "Chat", "available": False, "title": "chat"}]},
]
VICTIMS = [
    {"group": "qilin", "victim": "SAMPLEMOTOR MOTOR", "country": "KR",
     "activity": "Manufacturing", "discovered": "2026-08-10T19:39:24+00:00"},
    {"group": "qilin", "victim": "Connections", "country": "BE",
     "activity": "Not Found", "discovered": "2026-08-14T14:34:23+00:00"},
]


def w(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False)
    return path


def main():
    db = D.DLSDatabase(DBP)

    print("=== 1차 수집 적재 (2026-08-17) ===")
    r1 = D.ingest_probe(db, w(os.path.join(TMP, "p1.json"), RUN1))
    assert r1["새 관측"] == 3, r1
    assert r1["신뢰불가 제외"] == 1, "Tor 끊김 구간은 제외돼야 함"
    assert r1["신규 사이트"] == 3

    print("\n=== 같은 파일 재적재 (중복 방지) ===")
    r1b = D.ingest_probe(db, os.path.join(TMP, "p1.json"), verbose=False)
    assert r1b["새 관측"] == 0 and r1b["중복 건너뜀"] == 3, r1b
    print("  ✅ 같은 관측이 두 번 들어가지 않음")

    print("\n=== API 데이터 적재 ===")
    print(" ", D.ingest_ransomware_live(db, RL_GROUPS))
    print("  피해자", D.ingest_victims(db, VICTIMS), "건")

    print("\n=== 2차 수집 적재 (2026-08-24) ===")
    r2 = D.ingest_probe(db, w(os.path.join(TMP, "p2.json"), RUN2), verbose=False)
    assert r2["새 관측"] == 3, r2
    assert r2["신규 사이트"] == 0, "이미 있는 사이트는 새로 만들지 않아야 함"
    print("  새 관측 3건, 신규 사이트 0")

    # --- 핵심: 시계열 질문에 답할 수 있는가 ---
    print("\n=== 상태 변화 (DB 없이는 불가능했던 것) ===")
    ch = db.status_changes()
    for c in ch:
        print(f"  {c['at'][:10]}  {c['name']:<26} {c['from']} → {c['to']}")
    names = {c["name"]: (c["from"], c["to"]) for c in ch}
    assert names["THE MATRIX"] == ("online", "offline"), names
    assert names["Savastan0"] == ("offline", "online"), names
    assert "PREPAID CARD STORE (Deep)" not in names, "안 바뀐 건 안 나와야 함"

    print("\n=== 주소 변경 이력 ===")
    for r in db.address_history("Savastan0"):
        print(f"  {'● 사용중' if r['active'] else '○ 이력'}  {r['url']}  "
              f"({r['first_seen'][:10]} ~ {r['last_seen'][:10]})")
    addrs = db.address_history("Savastan0")
    assert len(addrs) == 2, "주소가 바뀌면 두 줄로 남아야 함"
    assert sum(a["active"] for a in addrs) == 1

    print("\n=== 사이트 이력 ===")
    for r in db.history("THE MATRIX"):
        print(f"  {r['observed_at'][:10]}  {r['source']:<14} {r['status']:<8} "
              f"{r['how_to_enter'] or r['error'] or ''}")

    print("\n=== 한국 관련 유출 ===")
    for r in db.kr_victims():
        print(f"  {r['discovered'][:10]}  {r['group_name']:<10} {r['victim']}")
    assert len(db.kr_victims()) == 1

    print("\n=== 별칭 / 종류 ===")
    sid = db.site_id("qilin")
    al = db.conn.execute("SELECT alias FROM alias WHERE site_id=?", (sid,)).fetchall()
    print("  qilin 별칭:", [a["alias"] for a in al])
    assert al[0]["alias"] == "Agenda"

    print("\n=== 현황 ===")
    for k, v in db.stats().items():
        print(f"  {k:<14} {v}")

    print("\n=== 내보내기 (dls_fill --probe 형식) ===")
    cur = db.current()
    exp = [r["name"] for r in cur if r["status"] == "online"]
    print("  현재 online:", exp)
    assert "THE MATRIX" not in exp and "Savastan0" in exp

    db.close()
    print("\n✅ 모든 검증 통과")
    print(f"   (테스트 DB: {DBP})")


if __name__ == "__main__":
    main()
