# -*- coding: utf-8 -*-
"""문제집 평가 (명세 7.2) — 세 벌을 이 순서로 잰다.

    python scripts/evaluate.py                 검색만 잰다 (재순위를 켠 셋째 벌만 돈이 든다)
    python scripts/evaluate.py --answers       답변까지 잰다 (모델을 부른다. 질문 하나에 1센트쯤)
    python scripts/evaluate.py --only 1,2      고른 벌만

    ① 기준선            넓히기 끔, 재순위 없음
    ② 넓히기            넓히기 켬, 재순위 없음
    ③ 넓히기와 재순위    넓히기 켬, 재순위 켬

①과 ②의 차가 넓히기를, ②와 ③의 차가 재순위를 되돌릴지 판정한다. 네 벌로 늘리지 않는다.

지표 여섯
    후보 포함      필요한 문서가 후보 M개에 든 비율              분모: 반출 자료에 답이 있는 질문
    최종 포함      필요한 문서가 최종 K개에 든 비율              분모: 위와 같음
    근거 부합      답변 문장 가운데 출처가 붙은 문장의 비율        분모: 만들어진 답의 문장
    모름을 앎      답이 없는 질문에 근거 없음으로 답한 비율        분모: 「답 없음」이 정답인 질문
    답 안 함       답할 수 있는데 근거 없음으로 답한 비율          분모: 반출 자료에 답이 있는 질문
    반출 오제외    답이 있는 줄이 반출 대상이 아니어서 못 답한 비율  분모: 노션에 답이 있는 질문

어디를 고칠지 알려고 넷으로 나눠 센다: 후보 미포함(넓히기 몫), 재순위 탈락(재순위 몫), 생성 실패, 반출 오제외.
결과는 data/eval_log.jsonl 에 덧붙인다. 그때 쓴 문제집, 지시문, 모델, 넓히기 사전의 판을 함께 남긴다.
비용은 평가 실행 비용 칸에 따로 센다. 하루 차단기를 쓰지 않는다.
"""
import hashlib
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import chunk as C                                          # noqa: E402
from app import answer, pii, questions, rerank, store      # noqa: E402
from app import config as cfg                              # noqa: E402
from app.search import Searcher                            # noqa: E402

LOG = os.path.join(cfg.DATA_DIR, "eval_log.jsonl")
RUNS = {1: ("기준선", 0.0, False), 2: ("넓히기", None, False), 3: ("넓히기와 재순위", None, True)}


def sha(path):
    try:
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]
    except OSError:
        return None


def ratio(a, b):
    return round(a / b, 3) if b else None


def run_one(n, qs, searcher, con, with_answers):
    name, weight, use_rerank = RUNS[n]
    weight = cfg.EXPANSION_WEIGHT if weight is None else weight
    if use_rerank and not cfg.COHERE_API_KEY:
        return {"run": n, "name": name, "skipped": "재순위 열쇠(COHERE_API_KEY)가 없다"}

    c = {"answerable": 0, "hidden": 0, "none": 0, "unknown": 0, "in_m": 0, "in_k": 0,
         "miss_candidates": 0, "miss_rerank": 0, "miss_answer": 0, "sentences": 0, "cited": 0,
         "none_ok": 0, "answerable_refused": 0, "hidden_refused": 0, "answers": 0, "rerank_applied": 0}
    cost = 0.0
    for q in qs:
        kind, want = q["kind"], set(q["want"])
        c[kind] += 1
        text, _ = pii.mask(q["question"])
        found = searcher.search(text, weight=weight)
        cands = found["candidates"]
        bodies = {x["chunk_id"]: x for x in store.chunks_by_id(con, [x["chunk_id"] for x in cands])}
        full = [dict(bodies[x["chunk_id"]], **{k: x[k] for k in ("score", "bm25", "expand", "boost")})
                for x in cands if x["chunk_id"] in bodies]
        if use_rerank and full:
            chunks, applied, ms = rerank.rerank(text, full)
            cost += cfg.RERANK_PRICE_PER_SEARCH if ms else 0.0
            c["rerank_applied"] += 1 if applied else 0
        else:
            chunks = full[:cfg.FINAL_K]

        in_m = bool(want & {x["document_id"] for x in full})
        in_k = bool(want & {x["document_id"] for x in chunks})
        if kind == "answerable":
            c["in_m"] += in_m
            c["in_k"] += in_k
            if not in_m:
                c["miss_candidates"] += 1
            elif not in_k:
                c["miss_rerank"] += 1

        if not with_answers:
            continue
        grounded = False
        if chunks:
            res = None
            try:
                for ev, value in answer.generate(text, chunks):
                    if ev == "result":
                        res = value
            except answer.AnswerError:
                res = None
            if res is not None:
                cost += res["cost"]
                grounded = answer.grounded(res["blocks"])
                if grounded:
                    sents = answer.sentences(res["blocks"])
                    c["answers"] += 1
                    c["sentences"] += len(sents)
                    c["cited"] += sum(1 for s in sents if s["cited"])
        if kind == "none":
            c["none_ok"] += 0 if grounded else 1
        elif kind == "answerable":
            c["answerable_refused"] += 0 if grounded else 1
            if in_k and not grounded:
                c["miss_answer"] += 1
        elif kind == "hidden":
            c["hidden_refused"] += 0 if grounded else 1

    out = {"run": n, "name": name, "weight": weight, "rerank": use_rerank, "counts": c, "cost": round(cost, 4),
           "metrics": {"후보 포함": ratio(c["in_m"], c["answerable"]), "최종 포함": ratio(c["in_k"], c["answerable"])}}
    if with_answers:
        out["metrics"].update({
            "근거 부합": ratio(c["cited"], c["sentences"]),
            "모름을 앎": ratio(c["none_ok"], c["none"]),
            "답 안 함": ratio(c["answerable_refused"], c["answerable"]),
            "반출 오제외": ratio(c["hidden_refused"], c["answerable"] + c["hidden"]),
        })
    out["split"] = {"후보 미포함": c["miss_candidates"], "재순위 탈락": c["miss_rerank"],
                    "생성 실패": c["miss_answer"] if with_answers else None, "반출 오제외": c["hidden"]}
    return out


def main():
    qs = questions.load()
    if not qs:
        print("문제집(data/questions.json)이 없다. 문제집이 없는 동안은 scripts/measure.py 로 방향만 본다")
        return 0
    only = [1, 2, 3]
    for i, a in enumerate(sys.argv):
        if a == "--only" and i + 1 < len(sys.argv):
            only = [int(x) for x in sys.argv[i + 1].split(",")]
    with_answers = "--answers" in sys.argv

    searcher = Searcher()
    con = store.connect()
    docs = C.load_docs()
    live = {r[0] for r in con.execute("SELECT document_id FROM documents WHERE visibility = 1")}
    try:
        with open(os.path.join(cfg.DATA_DIR, "excluded_rows.json"), encoding="utf-8") as f:
            excluded = json.load(f).get("rows") or []
    except (OSError, ValueError):
        excluded = []
    resolve = questions.resolver(docs, live, excluded)
    for q in qs:
        q["kind"], q["want"] = questions.kind_of(q, resolve)

    kinds = {}
    for q in qs:
        kinds[q["kind"]] = kinds.get(q["kind"], 0) + 1
    print("판 %s · 질문 %d개 (답이 반출 자료에 있음 %d, 답이 있는 줄이 반출 대상이 아님 %d, 답 없음 %d, 줄을 못 이음 %d)" % (
        searcher.version, len(qs), kinds.get("answerable", 0), kinds.get("hidden", 0), kinds.get("none", 0), kinds.get("unknown", 0)))
    if kinds.get("unknown"):
        print("  줄을 못 이은 질문: %s" % ", ".join(q["id"] for q in qs if q["kind"] == "unknown")[:300])

    runs = [run_one(n, qs, searcher, con, with_answers) for n in only]
    total = sum(r.get("cost", 0) for r in runs)
    if total:
        store.add_usage(con, answer_cost=total, evaluation=True)
    con.close()

    print()
    for r in runs:
        if r.get("skipped"):
            print("%d %-10s 건너뜀: %s" % (r["run"], r["name"], r["skipped"]))
            continue
        print("%d %-10s %s" % (r["run"], r["name"], " · ".join(
            "%s %s" % (k, "없음" if v is None else "%.3f" % v) for k, v in r["metrics"].items())))
        print("    나눠 센 것: %s" % ", ".join("%s %s" % (k, "안 잼" if v is None else v) for k, v in r["split"].items()))

    line = {"at": store.now(), "version": searcher.version, "questions": len(qs), "questions_hash": sha(questions.PATH),
            "prompt_hash": sha(os.path.join(ROOT, "app", "prompts", "system.md")), "model": cfg.ANSWER_MODEL,
            "rerank_model": cfg.RERANK_MODEL, "terms": None if searcher.terms is None else len(searcher.terms),
            "m": cfg.CANDIDATE_M, "k": cfg.FINAL_K, "with_answers": with_answers, "runs": runs}
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    print("\n쓴 돈 %.2f달러 (평가 실행 비용). 결과는 data/eval_log.jsonl 에 덧붙였다" % total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
