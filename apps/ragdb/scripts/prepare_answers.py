# -*- coding: utf-8 -*-
"""F-17 사전 답변 갱신 — 평가 질문 질문에 미리 답을 만들어 둔다. 사람이 검토해 통과시킨 것만 쓰인다.

    python scripts/prepare_answers.py --count          몇 개를 만들지, 얼마쯤 들지만 (모델은 안 부른다. 재순위 비용은 든다)
    python scripts/prepare_answers.py                  하나씩 바로 만든다
    python scripts/prepare_answers.py --batch          배치 호출로 한꺼번에 맡긴다 (비용 절반, 보통 한 시간 안에 끝남)
    python scripts/prepare_answers.py --collect        맡겨 둔 배치의 결과를 받는다

평가 질문(저장소의 questions 표)이 비어 있으면 아무것도 만들지 않는다. 오류가 아니다.
근거 문서의 내용 해시가 바뀐 질문만 다시 만든다. 처음 들어온 질문은 해시와 상관없이 만든다 (처리 3).
검색과 재순위는 즉석 질의와 똑같이 태운다 (처리 4, F-12 와 F-13 그대로).
만든 답은 검토 전(reviewed = 0)으로 들어간다. 통과는 scripts/review_answers.py 로 한다 (처리 6).
비용은 평가 실행 비용 칸에 센다.
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

import tokenize_ko as T                                          # noqa: E402
from app import answer, pii, pipeline, questions, rerank, store  # noqa: E402
from app import config as cfg                                    # noqa: E402
from app.search import Searcher                                  # noqa: E402

PENDING = os.path.join(cfg.DATA_DIR, "prepare_batch.json")


def evidence(searcher, con, q):
    """질문 하나의 근거 조각. 즉석 질의와 같은 길이다. (조각 목록, 재순위 비용)"""
    found = searcher.search(q)
    cands = found["candidates"]
    if not cands:
        return [], 0.0
    bodies = {c["chunk_id"]: c for c in searcher.chunks([c["chunk_id"] for c in cands])}
    full = [dict(bodies[c["chunk_id"]], **{k: c[k] for k in ("score", "bm25", "expand", "boost")})
            for c in cands if c["chunk_id"] in bodies and bodies[c["chunk_id"]]["visibility"]]
    chunks, applied, ms = rerank.rerank(q, full)
    return chunks, (cfg.RERANK_PRICE_PER_SEARCH if ms else 0.0)


def doc_hashes(searcher, ids):
    """답에 쓰인 문서의 내용 해시. 지금 판의 문서 목록에서 읽는다."""
    return {i: searcher.docs[i]["content_hash"] for i in sorted(set(ids)) if i in searcher.docs}


def plan(searcher, con):
    """만들 질문을 고른다. 돌려주는 것: [{id, question, key, chunks, hashes}], 건너뛴 수, 근거 없는 수"""
    todo, same, empty, spent = [], 0, 0, 0.0
    for item in questions.load(con):
        q, found = pii.mask(item["question"])
        if found or item["none"] or not item["example"]:
            continue          # 사전 답변은 예시 질문에만 만든다. 개인정보 꼴이 든 질문과 「답 없음」이 정답인 질문은 빼고
        key = T.question_key(q)
        chunks, cost = evidence(searcher, con, q)
        spent += cost
        if not chunks:
            empty += 1
            continue
        old = con.answer_row(key)
        if old and store.holds(searcher.docs, old):
            same += 1          # 답에 쓰인 근거 문서가 그대로다. 다시 만들지 않는다
            continue
        todo.append({"id": item["id"], "question": q, "key": key, "chunks": chunks})
    return todo, same, empty, spent


def save(con, searcher, item, res):
    """답 하나를 검토 전으로 넣는다. 출처가 없는 답은 넣지 않는다."""
    for b in res["blocks"]:
        b["text"] = searcher.guard.clean(b["text"])
    if not answer.grounded(res["blocks"]) or res["stop_reason"] != "end_turn":
        return False
    sents = answer.sentences(res["blocks"])
    used = sorted({n for s in sents for n in s["sources"]})
    sources = [s for s in pipeline.source_list(item["chunks"]) if s["n"] in used]
    hashes = doc_hashes(searcher, [s["document_id"] for s in sources])      # 답에 실제로 쓰인 문서만
    con.put_answer(item["key"], item["question"], sents, sources, res["model"], hashes)
    return True


def collect(con, searcher):
    """맡겨 둔 배치의 결과를 받는다."""
    try:
        with open(PENDING, encoding="utf-8") as f:
            pend = json.load(f)
    except (OSError, ValueError):
        print("맡겨 둔 배치가 없다")
        return 1
    batch = answer.client().messages.batches.retrieve(pend["batch_id"])
    if batch.processing_status != "ended":
        c = batch.request_counts
        print("아직 돌고 있다: 처리 중 %d, 끝남 %d" % (c.processing, c.succeeded + c.errored))
        return 10
    made = dropped = failed = 0
    spent = 0.0
    for r in answer.client().messages.batches.results(pend["batch_id"]):      # 순서는 보장되지 않는다. custom_id 로 잇는다
        item = pend["items"].get(r.custom_id)
        if item is None:
            continue
        if r.result.type != "succeeded":
            failed += 1
            continue
        item["chunks"] = searcher.chunks(item["chunk_ids"])
        res = answer.result_of(r.result.message, len(item["chunks"]), discount=0.5)
        spent += res["cost"]
        if res["stop_reason"] != "refusal" and len(item["chunks"]) == len(item["chunk_ids"]) and save(con, searcher, item, res):
            made += 1
        else:
            dropped += 1
    con.add_usage(answer_cost=spent, evaluation=True)
    os.remove(PENDING)
    print("받았다: 만든 것 %d, 출처가 없어 버린 것 %d, 실패 %d, %.2f달러" % (made, dropped, failed, spent))
    return 0


def main():
    con = store.connect()
    searcher = Searcher()
    if "--collect" in sys.argv:
        return collect(con, searcher)
    if not questions.load(con):
        print("평가 질문이 비어 있다. 만들 것이 없다 (scripts/question_set.py push 로 올린다)")
        return 0
    todo, same, empty, spent = plan(searcher, con)
    guess = sum(answer.estimate_cost(t["question"], t["chunks"]) for t in todo) * (0.5 if "--batch" in sys.argv else 1)
    print("만들 질문 %d개 · 근거가 그대로라 건너뛴 것 %d개 · 근거를 못 찾은 것 %d개 · 넉넉히 잡은 비용 %.2f달러" % (
        len(todo), same, empty, guess))
    if spent:
        con.add_usage(rerank_cost=spent, evaluation=True)
    if "--count" in sys.argv or not todo:
        return 0

    if "--batch" in sys.argv:
        from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
        from anthropic.types.messages.batch_create_params import Request
        reqs, items = [], {}
        for i, t in enumerate(todo):
            cid = "q%04d" % i
            reqs.append(Request(custom_id=cid, params=MessageCreateParamsNonStreaming(**answer.request(t["question"], t["chunks"]))))
            items[cid] = {"id": t["id"], "question": t["question"], "key": t["key"],
                          "chunk_ids": [c["chunk_id"] for c in t["chunks"]]}
        b = answer.client().messages.batches.create(requests=reqs)
        with open(PENDING, "w", encoding="utf-8") as f:
            json.dump({"batch_id": b.id, "version": searcher.version, "items": items}, f, ensure_ascii=False)
        print("배치에 맡겼다: %d개. 끝나면 --collect 로 받는다" % len(reqs))
        return 0

    made = dropped = failed = 0
    cost = 0.0
    for t in todo:
        res = None
        try:
            for name, value in answer.generate(t["question"], t["chunks"]):
                if name == "result":
                    res = value
        except answer.AnswerError:
            failed += 1
            continue
        cost += res["cost"]
        if save(con, searcher, t, res):
            made += 1
        else:
            dropped += 1
    con.add_usage(answer_cost=cost, evaluation=True)
    print("만든 것 %d, 출처가 없어 버린 것 %d, 실패 %d, %.2f달러. 검토는 scripts/review_answers.py" % (made, dropped, failed, cost))
    return 0


if __name__ == "__main__":
    sys.exit(main())
