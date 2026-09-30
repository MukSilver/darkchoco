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
from app.search import current_version             # noqa: E402
from snapshot import is_stale, version_files        # noqa: E402

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


def run(quiet=False, st=None):
    say = (lambda *a: None) if quiet else print
    if not cfg.FINGERPRINT_KEY:
        say("지문 키(FINGERPRINT_KEY)가 없어 대조하지 못한다")
        return None
    st = st or store.connect()
    docs = [d for d in C.load_docs() if d["kind"] != "용어"]
    live = {did: r for did, r in version_files(current_version())[0].items() if r.get("visibility")}

    shown = [(d["title"], [d["title"]] + [a for a in (d.get("aliases") or []) if isinstance(a, str)])
             for d in docs if d["document_id"] in live]
    hidden, have_list, made_at = [], False, None
    try:
        with open(EXCLUDED, encoding="utf-8") as f:
            data = json.load(f)
        rows = data.get("rows") or []
        made_at = data.get("made_at")
        hidden = [(r.get("name"), [r.get("name")] + list(r.get("aliases") or [])) for r in rows if r.get("name")]
        have_list = True
    except (OSError, ValueError, AttributeError):
        pass
    common = common_words([n for _, names in shown + hidden for n in names])
    exported = fingerprints(shown, common)
    missing = fingerprints(hidden, common)

    counts = {"반출 줄 겹침": 0, "빠진 줄 겹침": 0, "겹침 없음": 0, "대조 못함": 0, "오래됨": 0}
    # 처리 1, 4, 5: 근거를 못 찾은 질의. 평가 실행은 뺀다
    for r in st.no_evidence_rows():
        fps = r["word_fps"] or []
        hit = next((exported[f] for f in fps if f in exported), None)
        if hit:
            branch, name = "반출 줄 겹침", hit          # 찾기 문제. 개발로 돌린다
        else:
            hit = next((missing[f] for f in fps if f in missing), None)
            if hit:
                branch, name = "빠진 줄 겹침", hit      # 「DB 반영」 을 켤지 다시 볼 것
            else:
                branch, name = ("겹침 없음" if have_list else "대조 못함"), None
        counts[branch] += 1
        if name is not None or branch == "대조 못함":
            # 같은 갈래의 같은 줄이 대기 중이면 걸린 횟수만 오르고, 「그대로 둔다」 로 표시한 줄은 다시 들어가지 않는다
            st.recheck_put(branch, name, r["id"])
    # 처리 6: 확인일이 오래된 항목. 팀이 다시 확인하는 종류만 (사고와 판정의 날짜는 확인일이 아니다)
    for did, r in live.items():
        if is_stale(r.get("observed_at"), kind=r.get("kind")):
            counts["오래됨"] += 1
            st.recheck_put("오래됨", r.get("title"))
    # 처리 11: 쓴 질문 낱말 지문을 지운다
    st.clear_word_fps()
    st.drop_old_word_fps()

    # 처리 10: 주 1회 세는 값
    w = st.weekly_stats()
    n = w.get("n") or 0
    rr, aa = w.get("rerank_cost") or 0, w.get("answer_cost") or 0
    stats = {"branches": counts, "excluded_rows": have_list, "excluded_rows_made_at": made_at, "queue": w.get("queue") or 0,
             "rerank_not_applied": round(1 - (w.get("applied") or 0) / n, 3) if n else None,
             "rerank_ms_avg": round(w.get("ms_avg") or 0), "rerank_ms_max": w.get("ms_max"),
             "rerank_cost_share": round(rr / (rr + aa), 3) if (rr or aa) else None,
             "term_item_hits": w.get("term_items") or {}}
    say("재조사 후보 %d건 대기 · 이번에 본 질의: %s" % (stats["queue"], ", ".join("%s %d" % kv for kv in counts.items())))
    if not have_list:
        say("  빠진 줄 명부가 없어 겹치지 않은 질문은 「대조 못함」으로 두었다")
    return stats


if __name__ == "__main__":
    sys.exit(0 if run() is not None else 1)
