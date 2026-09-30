# -*- coding: utf-8 -*-
"""질의 한 건의 순서 — 설계서 4.3. 순서를 바꾸지 않는다. 자리마다 까닭이 있다.

사람 확인(순서 1의 앞 절반)은 질의 서버가 요청을 받는 자리에서 하고 여기로 넘긴다.
여기서 내는 이벤트는 5.3 의 SSE 이벤트와 같은 이름이다: received, searching, text, replace, sources, done, error.
"""
import hashlib
import hmac

import tokenize_ko as T

from . import answer, limits, pii, rerank, store
from . import config as cfg
from .normalize import norm
from .search import Searcher


def fingerprint(text):
    """지문 키로 해시한다. 지문 키가 없으면 None 이고, 그때는 질문 해시와 재사용 답변을 쓰지 않는다."""
    if not cfg.FINGERPRINT_KEY or not text:
        return None
    return hmac.new(cfg.FINGERPRINT_KEY.encode("utf-8"), text.encode("utf-8"), hashlib.sha256).hexdigest()


def word_fingerprints(tokens):
    """질문 낱말 지문 (F-19 처리 2). 낱말을 F-02 정규화로 키로 만들고 짧은 것은 버린다.

    이어진 낱말 둘, 셋을 붙인 것도 함께 남긴다. 이름이 여러 낱말로 쪼개지기 때문이다(감마포럼 → 감마, 포럼).
    지문에서 질문을 되살릴 수는 없다. 지문 키 없이는 같은 낱말인지도 알 수 없다.
    """
    keys = [norm(t) for t in tokens]
    keys = [k for k in keys if k]
    grams = list(keys)
    for n in (2, 3):
        grams.extend("".join(keys[i:i + n]) for i in range(len(keys) - n + 1))
    out = []
    for k in grams:
        if len(k) < cfg.WORD_FP_MIN_CHARS:
            continue
        fp = fingerprint(k)
        if fp and fp not in out:
            out.append(fp)
    return out


def source_list(chunks):
    """출처 목록. 번호, 조각, 날짜와 그 날짜의 이름 (F-14 처리 4)."""
    return [{"n": i, "chunk_id": c["chunk_id"], "document_id": c["document_id"], "kind": c.get("kind"),
             "title": c.get("title"), "section": c.get("section"), "observed_at": c.get("observed_at"),
             "date_label": answer.date_label(c), "status": c.get("status")} for i, c in enumerate(chunks, 1)]


def cleaned_answer(g, hit):
    """저장해 둔 답(사전 답변, 재사용 답변)을 내보내기 전에 지금 판의 지킴이로 한 번 더 가린다.

    답을 만든 뒤에 새로 찾은 조직 표기가 있을 수 있다. 새 답변만 가리고 저장해 둔 답은 그대로 내보내던 것을
    고쳤다 (2026-09-30 검토에서 찾음).
    """
    sents = [dict(s, text=g.clean(s.get("text"))) for s in hit["answer"]]
    sources = [dict(s, title=g.clean(s.get("title")), section=g.clean(s.get("section"))) for s in hit["sources"]]
    return sents, sources


def ask(question, evaluation=False, who=None, searcher=None, con=None, limiter=None,
        rerank_call=None, stream_factory=None):
    """질의 한 건. 이벤트 (이름, 값) 을 차례로 낸다.

    evaluation 이 참이면 관리 경로의 질의다. 사람별 제한과 하루 차단기를 거치지 않고 비용을 따로 센다 (F-18 처리 6).
    who 는 IP 해시다. IP 원문을 받지 않는다.
    """
    own = con is None
    con = con or store.connect()
    log = dict(question_len=len(question or ""), evaluation=1 if evaluation else 0, no_evidence=0, used_prepared=0,
               reused=0, pii_masked=0, no_dictionary=0, expansion_truncated=0, rerank_applied=0, rerank_ms=0, cost=0.0,
               sources=[], term_items=[], score_sources=[])
    entered = False
    try:
        # 1. 질문 길이
        if not question or not question.strip():
            yield "error", {"status": 400, "code": "empty"}
            return
        if len(question) > cfg.QUESTION_MAX_CHARS:
            yield "error", {"status": 400, "code": "too_long"}
            return
        # 2. 받음. 첫 바이트가 늦으면 터널이 끊는다
        yield "received", {}

        # 3. 개인정보 꼴 가리기. 아래로는 가린 질문만 흐른다 (SR-24)
        q, found = pii.mask(question.strip())
        log["pii_masked"] = 1 if found else 0

        searcher = searcher or Searcher()          # 판을 여기서 한 번 고른다 (F-12 처리 1)
        key = T.question_key(q)
        key_fp = None if found else fingerprint(key)
        log["question_hash"] = fingerprint(key)

        # 4. 사전 답변 (F-16)
        hit = store.prepared_answer(con, key) if key else None
        if hit:
            log.update(used_prepared=1, sources=[s["chunk_id"] for s in hit["sources"]])
            sents, sources = cleaned_answer(searcher.guard, hit)
            yield "text", "".join(s["text"] + " " for s in sents).strip()
            yield "sources", sources
            yield "done", {"kind": "prepared", "sentences": sents, "created_at": hit["created_at"],
                           "version": searcher.version, "pii_masked": bool(found)}
            return

        # 5. 재사용 답변 (F-21). 개인정보를 가렸으면 건너뛴다
        if key_fp:
            hit = store.cached_answer(con, searcher.version, key_fp)
            if hit:
                log.update(reused=1, sources=[s["chunk_id"] for s in hit["sources"]])
                sents, sources = cleaned_answer(searcher.guard, hit)
                yield "text", "".join(s["text"] + " " for s in sents).strip()
                yield "sources", sources
                yield "done", {"kind": "reused", "sentences": sents, "created_at": hit["created_at"],
                               "version": searcher.version, "pii_masked": False}
                return

        # 6. 사람별 제한. 새 답변만 센다
        if not evaluation and limiter is not None and who:
            ok, wait = limiter.enter(who)
            if not ok:
                yield "error", {"status": 429, "code": "rate", "retry_after": wait}
                return
            entered = True

        # 8. 반출 조각 선별, 넓히기, BM25, 종류 가산, 후보 M개 (F-12 처리 1부터 7)
        found_chunks = searcher.search(q)
        cands = found_chunks["candidates"]
        log.update(no_dictionary=1 if found_chunks["no_dictionary"] else 0,
                   expansion_truncated=1 if found_chunks["truncated"] else 0,
                   term_items=[it["id"] for it in found_chunks["items"]])

        chunks, applied, ms = [], False, 0
        if cands:
            bodies = {c["chunk_id"]: c for c in searcher.chunks(con, [c["chunk_id"] for c in cands])}
            full = [dict(bodies[c["chunk_id"]], **{k: c[k] for k in ("score", "bm25", "expand", "boost")})
                    for c in cands if c["chunk_id"] in bodies and bodies[c["chunk_id"]]["visibility"]]

            # 7. 하루 차단기. 거절할 요청에 비용을 쓰지 않는다
            if not evaluation:
                worst = answer.estimate_cost(q, full[:cfg.FINAL_K]) + cfg.RERANK_PRICE_PER_SEARCH
                if not limits.budget_allows(con, worst):
                    yield "error", {"status": 503, "code": "budget"}
                    return

            # 9. 찾는 중. 재순위가 늦어도 연결이 살아 있다
            yield "searching", {}
            # 10. 재순위 (F-12 처리 8)
            chunks, applied, ms = rerank.rerank(q, full, call=rerank_call)
            if ms:
                store.add_usage(con, rerank_cost=cfg.RERANK_PRICE_PER_SEARCH, evaluation=evaluation)
                log["cost"] += cfg.RERANK_PRICE_PER_SEARCH
        log.update(rerank_applied=1 if applied else 0, rerank_ms=ms,
                   sources=[c["chunk_id"] for c in chunks],
                   score_sources=[{"chunk_id": c["chunk_id"], "bm25": round(c["bm25"], 3), "expand": round(c["expand"], 3),
                                   "boost": round(c["boost"], 3), "rerank_rank": c.get("rerank_rank")} for c in chunks])

        # 11. 근거 없음 (F-15). 모델을 부르지 않는다
        if not chunks:
            log.update(no_evidence=1, word_fps=None if found else word_fingerprints(found_chunks["tokens"]))
            yield "text", answer.NO_EVIDENCE
            yield "done", {"kind": "no_evidence", "sentences": [], "version": searcher.version, "pii_masked": bool(found)}
            return

        # 12. 모델 호출과 스트리밍, 출처 (F-13, F-14)
        # 글자는 문장이 끝날 때마다 내보낸다. 내보내기 직전에 조직 이름과 도메인을 한 번 더 가린다 (guard.py)
        g = searcher.guard
        res, buf = None, ""
        try:
            for name, value in answer.generate(q, chunks, stream_factory=stream_factory):
                if name == "text":
                    buf += value
                    cut = answer.last_sentence_end(buf)
                    if cut:
                        yield "text", g.clean(buf[:cut])
                        buf = buf[cut:]
                else:
                    res = value
        except answer.AnswerError as e:
            yield "error", {"status": 503, "code": e.code}
            return
        if buf:
            yield "text", g.clean(buf)
        for b in res["blocks"]:
            b["text"] = g.clean(b["text"])
        store.add_usage(con, answer_cost=res["cost"], new_answer=True, evaluation=evaluation)
        log["cost"] += res["cost"]

        if not answer.grounded(res["blocks"]):
            # 출처가 하나도 안 붙었으면 답으로 내보내지 않는다 (TC-11, TC-12)
            log.update(no_evidence=1, sources=[], word_fps=None if found else word_fingerprints(found_chunks["tokens"]))
            yield "replace", answer.NO_EVIDENCE
            yield "done", {"kind": "no_evidence", "sentences": [], "version": searcher.version, "pii_masked": bool(found)}
            return

        sents = answer.sentences(res["blocks"])
        for s in sents:
            s["text"] = g.clean(s["text"])      # 블록을 이어 붙인 문장으로 한 번 더. 이름이 두 블록에 걸쳐 있을 수 있다
        used = sorted({n for s in sents for n in s["sources"]})
        sources = [s for s in source_list(chunks) if s["n"] in used]
        yield "sources", sources

        # 13. 재사용 답변 저장. 개인정보를 가린 질문은 저장하지 않는다
        if key_fp and res["stop_reason"] == "end_turn":
            store.save_cache(con, searcher.version, key_fp, sents, sources, res["model"])

        yield "done", {"kind": "new", "sentences": sents, "version": searcher.version, "pii_masked": bool(found),
                       "rerank_applied": applied, "truncated": res["stop_reason"] == "max_tokens"}
    finally:
        if entered:
            limiter.leave(who)
        # 14. 질의 기록 (F-19). 기록 실패가 답변 실패로 번지지 않게 맨 뒤에 둔다
        try:
            if "question_hash" in log:          # 길이 검사에서 돌려보낸 요청은 남기지 않는다
                store.log_query(con, **log)
        except Exception:
            pass
        if own:
            con.close()


def run(question, on_event=None, **kw):
    """ask() 를 끝까지 돌려 마지막 결과를 돌려준다. 터미널과 평가가 쓴다."""
    out = {"text": "", "sources": [], "done": None, "error": None}
    for name, value in ask(question, **kw):
        if on_event:
            on_event(name, value)
        if name == "text":
            out["text"] += value
        elif name == "replace":
            out["text"] = value
        elif name == "sources":
            out["sources"] = value
        elif name == "done":
            out["done"] = value
        elif name == "error":
            out["error"] = value
    return out
