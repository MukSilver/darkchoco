# -*- coding: utf-8 -*-
"""F-12 처리 8 재순위 — 후보 M개를 바깥 재순위 API 로 다시 매겨 상위 K개를 고른다.

바깥으로 나가는 것은 질문(개인정보 꼴을 가린 뒤)과 반출 판정을 통과한 조각뿐이다 (SR-19).
넓힌 낱말, 넓힌 질문, 지시문, 열쇠는 보내지 않는다. 응답에서는 순서와 점수만 쓴다 (SR-20).
대기 상한을 넘거나 실패하면 다시 부르지 않고 낱말 점수 순서로 간다 (TC-23, QR-03).
"""
import concurrent.futures
import time

from . import config as cfg

_client = None
_pool = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="rerank")


def client():
    global _client
    if _client is None:
        import cohere
        _client = cohere.ClientV2(api_key=cfg.COHERE_API_KEY, timeout=cfg.RERANK_TIMEOUT_MS / 1000.0)
    return _client


def text_of(chunk):
    """재순위에 보내는 글. 제목과 소제목은 그 조각의 반출 칸이라 함께 보낸다 (본문에 이름이 안 나오는 구간이 있다)."""
    return "%s\n%s\n%s" % (chunk.get("title") or "", chunk.get("section") or "", chunk.get("body") or "")


def rerank(question, chunks, k=None, call=None):
    """(고른 조각 목록, 적용했는지, 걸린 시간 ms).

    chunks 는 낱말 점수 순서로 온다. 적용하지 못하면 그 순서의 앞 K개를 그대로 돌려준다.
    call 은 시험에서 바깥 호출을 바꿔 끼우는 자리다.
    """
    k = cfg.FINAL_K if k is None else k
    if not chunks:
        return [], False, 0
    fallback = [dict(c, rerank_rank=None, rerank_score=None) for c in chunks[:k]]
    if not cfg.RERANK_ENABLED or (call is None and not cfg.COHERE_API_KEY):
        return fallback, False, 0
    if any(not c.get("visibility") for c in chunks):
        raise ValueError("비반출 조각이 재순위로 가려 했다 (SR-19, TC-24)")

    docs = [text_of(c) for c in chunks]
    do = call or (lambda q, d, n: client().rerank(model=cfg.RERANK_MODEL, query=q, documents=d, top_n=n))
    t0 = time.monotonic()
    fut = _pool.submit(do, question, docs, min(k, len(docs)))
    try:
        res = fut.result(timeout=cfg.RERANK_TIMEOUT_MS / 1000.0)
    except Exception:                       # 시간 넘김, 연결 끊김, 사업자 오류 모두 같은 길로
        fut.cancel()
        return fallback, False, int((time.monotonic() - t0) * 1000)
    ms = int((time.monotonic() - t0) * 1000)

    out, seen = [], set()
    for rank, r in enumerate(getattr(res, "results", None) or [], 1):
        i = getattr(r, "index", None)
        if i is None or i in seen or not (0 <= i < len(chunks)):
            continue
        seen.add(i)
        out.append(dict(chunks[i], rerank_rank=rank, rerank_score=float(getattr(r, "relevance_score", 0.0))))
    if not out:
        return fallback, False, ms
    if cfg.RERANK_MIN_SCORE > 0:
        out = [c for c in out if c["rerank_score"] >= cfg.RERANK_MIN_SCORE]   # OI-22. 0 이면 쓰지 않음
    return out[:k], True, ms
