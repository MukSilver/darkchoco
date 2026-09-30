# -*- coding: utf-8 -*-
"""F-01 받기 — 정제 배치가 Supabase rag 스키마에 만든 표준 문서를 data/standard/ 로 받는다 (명세 판 1.6, AD-21).

    python scripts/fetch_docs.py            새 판이 있을 때만 받는다
    python scripts/fetch_docs.py --force    판이 같아도 다시 받는다

노션을 읽지 않는다. 노션 토큰이 필요 없다. 노션에서 읽고 표준 문서로 바꾸는 일(F-01 처리 1, F-04)은
정제 배치 저장소(darkchoco-data)가 매일 한다. 여기서는 받은 것을 standardize.py 가 쓰던 모양 그대로 파일로 둔다.
그래서 chunk.py 와 build_index.py 는 바뀌지 않는다.

끝나는 값: 0 새 판을 받음, 10 받을 새 판이 없음, 1 실패
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

import httpx
from dotenv import load_dotenv

load_dotenv()

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STD_DIR = os.path.join(ROOT, "data", "standard")
VER_FILE = os.path.join(ROOT, "data", "source_version.txt")
EXCLUDED_FILE = os.path.join(ROOT, "data", "excluded_rows.json")
PAGE = 500   # Data API 한 번에 최대 1,000줄. 여유를 둔다

NEW, NOTHING, FAIL = 0, 10, 1


def client():
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_KEY", "").strip()
    if not url or not key:
        print("SUPABASE_URL 과 SUPABASE_SERVICE_KEY 가 .env 에 없다 (배치 설정)")
        sys.exit(FAIL)
    return url, httpx.Client(timeout=60, headers={
        "apikey": key, "Authorization": "Bearer " + key, "Accept-Profile": "rag"})


def notion_time(s):
    """Data API 시각(2026-09-22T11:14:00+00:00)을 노션이 주던 모양(2026-09-22T11:14:00.000Z)으로."""
    if not s:
        return s
    t = datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    return t.strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (t.microsecond // 1000)


def read_all(c, url, table, select, order="document_id"):
    """표 하나를 끝까지 읽는다."""
    out, offset = [], 0
    while True:
        r = c.get("%s/rest/v1/%s" % (url, table),
                  params={"select": select, "order": order, "limit": PAGE, "offset": offset})
        if r.status_code != 200:
            raise RuntimeError("%s 읽기 %s: %s" % (table, r.status_code, r.text[:200]))
        rows = r.json()
        out.extend(rows)
        if len(rows) < PAGE:
            return out
        offset += PAGE


def fetch_excluded(c, url):
    """빠진 줄 명부를 받는다 (F-20 처리 2). 「DB 반영」이 꺼진 줄의 이름만 든 목록이고 본문이 없다.

    못 받으면 직전 명부를 그대로 둔다. 이 파일은 재조사 추출만 읽는다. 색인, 스냅샷, 질의 서버는 읽지 않는다 (SR-01).
    """
    try:
        rows = read_all(c, url, "excluded_rows", "kind,name,aliases,status,observed_at", order="notion_id")
    except Exception as e:
        print("빠진 줄 명부를 못 받았다 (%s). 직전 명부를 쓴다" % type(e).__name__)
        return None
    tmp = EXCLUDED_FILE + ".tmp"
    os.makedirs(os.path.dirname(EXCLUDED_FILE), exist_ok=True)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"made_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "rows": rows}, f, ensure_ascii=False)
    os.replace(tmp, EXCLUDED_FILE)
    return len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="판이 같아도 다시 받는다")
    a = ap.parse_args()

    url, c = client()
    with c:
        n = fetch_excluded(c, url)
        if n is not None:
            print("빠진 줄 명부 %d줄" % n)
        r = c.get("%s/rest/v1/versions" % url, params={"select": "*", "order": "version.desc", "limit": 1})
        if r.status_code != 200:
            print("판을 못 읽었다:", r.status_code, r.text[:200])
            return FAIL
        latest = r.json()
        if not latest:
            print("rag 판이 아직 없다. 정제 배치가 한 번 돌아야 한다")
            return FAIL
        ver = latest[0]["version"]
        mine = open(VER_FILE, encoding="utf-8").read().strip() if os.path.exists(VER_FILE) else ""
        if ver == mine and not a.force:
            print("받을 새 판이 없다 (지금 %s)" % ver)
            return NOTHING

        docs = read_all(c, url, "documents",
                        "document_id,kind,title,summary,visibility,sections,metadata,content_hash,notion_edited_at,form_version")
        priv = {p["document_id"]: p for p in read_all(c, url, "private", "document_id,aliases,source")}

    if len(docs) != latest[0]["documents"]:
        print("판 %s 은 문서 %d개인데 %d개를 받았다. 멈춘다" % (ver, latest[0]["documents"], len(docs)))
        return FAIL

    os.makedirs(STD_DIR, exist_ok=True)
    keep = set()
    for d in docs:
        p = priv.get(d["document_id"], {})
        doc = {
            "document_id": d["document_id"],
            "kind": d["kind"],
            "title": d["title"],
            "summary": d["summary"],
            "visibility": d["visibility"],
            "sections": d["sections"],
            "metadata": d["metadata"],
            "aliases": p.get("aliases") or [],      # 비반출. 넓히기 사전의 원천
            "source": p.get("source"),              # 비반출
            "revision": {
                "notion_edited": notion_time(d["notion_edited_at"]),
                "form_version": d["form_version"],
                "content_hash": d["content_hash"],
            },
        }
        name = d["document_id"] + ".json"
        keep.add(name)
        with open(os.path.join(STD_DIR, name), "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)

    # 판에서 빠진 문서는 파일도 지운다. chunk.py 가 이것을 보고 조각과 목록에서 뺀다 (F-06 처리 6의 철회)
    gone = [n for n in os.listdir(STD_DIR) if n.endswith(".json") and n not in keep]
    for n in gone:
        os.remove(os.path.join(STD_DIR, n))

    with open(VER_FILE, "w", encoding="utf-8") as f:
        f.write(ver + "\n")
    print("판 %s 를 받았다: 문서 %d개, 지운 파일 %d개 (새로 %s, 바뀜 %s, 빠짐 %s)"
          % (ver, len(docs), len(gone), latest[0].get("added"), latest[0].get("changed"), latest[0].get("removed")))
    return NEW


if __name__ == "__main__":
    sys.exit(main())
