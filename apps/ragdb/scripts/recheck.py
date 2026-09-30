# -*- coding: utf-8 -*-
"""F-20 재조사 추출 — 근거를 못 찾은 질문과 오래된 항목을 재조사 후보로 뽑는다.

    python scripts/recheck.py

질문 원문은 어디에도 없다. 남아 있는 것은 질문 낱말 지문(낱말을 지문 키로 해시한 값)뿐이고,
같은 방법으로 만든 이름 지문과 맞춰 봐서 어느 줄과 겹치는지만 안다.

빠진 줄 명부(data/excluded_rows.json)는 받기(fetch_docs.py)가 Supabase rag.excluded_rows 에서 받아 둔다.
「DB 반영」이 꺼진 줄의 이름만 든 목록이다. 이 시스템은 노션을 읽지 않으므로 정제 배치가 만들어 넘긴다 (판 1.6).
명부가 없으면 반출 줄과 겹치지 않는 질문의 갈래를 「대조 못함」으로 둔다 (F-20 예외).
"""
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import chunk as C                                   # noqa: E402
import tokenize_ko as T                             # noqa: E402
from app import pipeline, store                     # noqa: E402
from app import config as cfg                       # noqa: E402
from app.normalize import norm                      # noqa: E402
from snapshot import is_stale                       # noqa: E402

EXCLUDED = os.path.join(cfg.DATA_DIR, "excluded_rows.json")


def name_keys(name, common=()):
    """이름 하나에서 나오는 키. 이름 통째와, 이름을 쪼갠 낱말 가운데 흔하지 않은 것."""
    keys = {norm(name)}
    keys.update(k for k in (norm(t) for t in T.tokens(name or "")) if k not in common)
    return {k for k in keys if len(k) >= cfg.WORD_FP_MIN_CHARS}


def common_words(names):
    """여러 이름에 두루 나오는 낱말. 「포럼」 「leaks」 같은 것은 어느 줄인지 가려 주지 못한다.

    종류를 가리키는 낱말(kind_synonyms.json)과, 이름 셋 이상에 나오는 낱말이다.
    """
    from app import kinds
    out = {k for forms in kinds.table().values() for f in forms for k in f}
    seen = {}
    for n in names:
        for k in {norm(t) for t in T.tokens(n or "")}:
            seen[k] = seen.get(k, 0) + 1
    out.update(k for k, c in seen.items() if c >= 3)
    return out


def fingerprints(rows, common=()):
    """{지문: 줄 이름}. rows 는 (줄 이름, [이름과 별칭]) 의 목록."""
    out = {}
    for row_name, names in rows:
        for n in names:
            for k in name_keys(n, common):
                fp = pipeline.fingerprint(k)
                if fp:
                    out.setdefault(fp, row_name)
    return out


def queue(con, branch, row_name, qa_id=None):
    """같은 갈래의 같은 줄이 이미 있으면 걸린 횟수만 올린다. 「그대로 둔다」(handled = 2)로 표시한 줄은 다시 넣지 않는다."""
    r = con.execute("SELECT id, handled FROM recheck_queue WHERE branch = ? AND row_name IS ? ORDER BY id DESC LIMIT 1",
                    (branch, row_name)).fetchone()
    if r and r["handled"] == 2:
        return False
    if r and r["handled"] == 0:
        if qa_id is not None:
            con.execute("UPDATE recheck_queue SET hits = hits + 1 WHERE id = ?", (r["id"],))
        return False
    con.execute("INSERT INTO recheck_queue (qa_log_id, branch, row_name, hits, handled, created_at) VALUES (?,?,?,1,0,?)",
                (qa_id, branch, row_name, store.now()))
    return True


def run(quiet=False):
    say = (lambda *a: None) if quiet else print
    if not cfg.FINGERPRINT_KEY:
        say("지문 키(FINGERPRINT_KEY)가 없어 대조하지 못한다")
        return None
    docs = [d for d in C.load_docs() if d["kind"] != "용어"]
    con = store.connect()
    live = {r["document_id"]: r for r in con.execute("SELECT document_id, kind, title, observed_at FROM documents WHERE visibility = 1")}

    shown = [(d["title"], [d["title"]] + [a for a in (d.get("aliases") or []) if isinstance(a, str)])
             for d in docs if d["document_id"] in live]
    hidden, have_list = [], False
    try:
        with open(EXCLUDED, encoding="utf-8") as f:
            rows = json.load(f).get("rows") or []
        hidden = [(r.get("name"), [r.get("name")] + list(r.get("aliases") or [])) for r in rows if r.get("name")]
        have_list = True
    except (OSError, ValueError, AttributeError):
        pass
    common = common_words([n for _, names in shown + hidden for n in names])
    exported = fingerprints(shown, common)
    missing = fingerprints(hidden, common)

    made_at = None
    if have_list:
        try:
            with open(EXCLUDED, encoding="utf-8") as f:
                made_at = json.load(f).get("made_at")
        except (OSError, ValueError):
            pass

    counts = {"반출 줄 겹침": 0, "빠진 줄 겹침": 0, "겹침 없음": 0, "대조 못함": 0, "오래됨": 0}
    with con:
        # 처리 1, 4, 5: 근거를 못 찾은 질의. 평가 실행은 뺀다
        for r in con.execute("SELECT id, word_fps FROM qa_log WHERE no_evidence = 1 AND evaluation = 0 "
                             "AND word_fps IS NOT NULL").fetchall():
            fps = json.loads(r["word_fps"] or "[]")
            hit = next((exported[f] for f in fps if f in exported), None)
            if hit:
                branch, name = "반출 줄 겹침", hit          # 찾기 문제. 개발로 돌린다
            else:
                hit = next((missing[f] for f in fps if f in missing), None)
                if hit:
                    branch, name = "빠진 줄 겹침", hit      # 반출 판정을 다시 볼 것. 조사팀으로 넘긴다
                else:
                    branch, name = ("겹침 없음" if have_list else "대조 못함"), None
            counts[branch] += 1
            if name is not None or branch == "대조 못함":
                queue(con, branch, name, r["id"])
        # 처리 6: 확인일이 오래된 항목. 팀이 다시 확인하는 종류만 (사고와 판정의 날짜는 확인일이 아니다)
        for did, r in live.items():
            if is_stale(r["observed_at"], kind=r["kind"]):
                counts["오래됨"] += 1
                queue(con, "오래됨", r["title"])
        # 처리 11: 쓴 질문 낱말 지문을 지운다
        con.execute("UPDATE qa_log SET word_fps = NULL WHERE word_fps IS NOT NULL AND evaluation = 0")
    store.drop_old_word_fps(con)

    # 처리 10: 주 1회 세는 값
    q = con.execute("SELECT COUNT(*) n, SUM(rerank_applied) a, AVG(rerank_ms) ms, MAX(rerank_ms) mx, SUM(cost) c "
                    "FROM qa_log WHERE used_prepared = 0 AND reused = 0 AND no_evidence = 0").fetchone()
    u = con.execute("SELECT SUM(rerank_cost) r, SUM(answer_cost) a FROM usage").fetchone()
    per_item = {}
    for r in con.execute("SELECT term_items FROM qa_log WHERE term_items IS NOT NULL AND term_items <> '[]'"):
        for i in json.loads(r["term_items"]):
            per_item[str(i)] = per_item.get(str(i), 0) + 1
    waiting = con.execute("SELECT COUNT(*) FROM recheck_queue WHERE handled = 0").fetchone()[0]
    con.close()

    n = q["n"] or 0
    stats = {"branches": counts, "excluded_rows": have_list, "excluded_rows_made_at": made_at, "queue": waiting,
             "rerank_not_applied": round(1 - (q["a"] or 0) / n, 3) if n else None,
             "rerank_ms_avg": round(q["ms"] or 0), "rerank_ms_max": q["mx"],
             "rerank_cost_share": round((u["r"] or 0) / ((u["r"] or 0) + (u["a"] or 0)), 3) if (u["r"] or u["a"]) else None,
             "term_item_hits": per_item}
    say("재조사 후보 %d건 대기 · 이번에 본 질의: %s" % (waiting, ", ".join("%s %d" % kv for kv in counts.items())))
    if not have_list:
        say("  빠진 줄 명부가 없어 겹치지 않은 질문은 「대조 못함」으로 두었다")
    return stats


if __name__ == "__main__":
    sys.exit(0 if run() is not None else 1)
