# -*- coding: utf-8 -*-
"""질의 서버 (FastAPI) — 설계서 「API와 스냅샷 파일」.

    POST /api/ask      질문을 받아 답을 SSE 로 흘려보낸다. 돈이 드는 유일한 공개 경로
    GET  /api/status   살아 있는지, 지금 판, 오늘 새 답변을 받는지

이벤트 이름은 app/pipeline.py 가 내는 것 그대로다: received, searching, text, replace, sources, done, error.
오류: 400 질문 길이, 401 사람 확인 실패, 405 GET, 503 하루 차단기 또는 바깥 장애.

질의 한 건은 시작할 때 판을 한 번 읽어 끝까지 그 판을 쓴다 (Searcher 가 한다). 서버는 판을 쥐고 있지 않는다.
질문 원문, 답변 본문, IP 는 기록하지 않는다. 기록은 pipeline.py 가 남기는 질의 기록뿐이다.
"""
import asyncio
import json
import os
import queue
import sys
import threading

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)

from app import config as cfg            # noqa: E402
from app import pipeline, store          # noqa: E402
from app.search import current_version   # noqa: E402
from server import turnstile             # noqa: E402

app = FastAPI(title="다크웹 RAG DB 질의 서버", docs_url=None, redoc_url=None, openapi_url=None)

# 화면(rag.도메인)과 질의 서버(rag-api.도메인)는 주소가 다르다. 화면 주소에서 오는 요청만 받는다.
# ALLOWED_ORIGINS 가 비어 있으면 다른 주소의 요청을 받지 않는다 (개발 때는 화면 개발 서버가 /api 를 넘겨 주므로 필요 없다).
ALLOWED_ORIGINS = [o.strip().rstrip("/") for o in (os.getenv("ALLOWED_ORIGINS") or "").split(",") if o.strip()]
if ALLOWED_ORIGINS:
    app.add_middleware(CORSMiddleware, allow_origins=ALLOWED_ORIGINS, allow_methods=["GET", "POST"],
                       allow_headers=["Content-Type"], allow_credentials=False, max_age=600)

KEEPALIVE_SECONDS = float(os.getenv("SSE_KEEPALIVE_SECONDS") or 10)
_END = object()


def _sse(name, value):
    return "event: %s\ndata: %s\n\n" % (name, json.dumps(value, ensure_ascii=False))


def _client_ip(request):
    """터널 뒤에 있으므로 CF-Connecting-IP 를 먼저 본다. 기록하지 않고 Turnstile 검증에만 넘긴다."""
    return request.headers.get("cf-connecting-ip") or (request.client.host if request.client else None)


async def _events(question):
    """pipeline.ask 는 동기 제너레이터라 스레드에서 돌리고, 여기서는 큐를 비우며 SSE 줄을 낸다.
    이벤트가 뜸하면 주석 줄로 연결을 살린다 (재순위 첫 호출 6.7초, 답 만들기 2초부터 10초)."""
    q = queue.Queue()

    def work():
        try:
            for name, value in pipeline.ask(question):
                q.put((name, value))
        except Exception:                 # 예상 밖 오류. 자료 문자열을 싣지 않는다
            q.put(("error", {"status": 503, "code": "internal"}))
        finally:
            q.put(_END)

    threading.Thread(target=work, daemon=True).start()
    loop = asyncio.get_running_loop()
    while True:
        try:
            item = await asyncio.wait_for(loop.run_in_executor(None, q.get), timeout=KEEPALIVE_SECONDS)
        except asyncio.TimeoutError:
            yield ": keepalive\n\n"
            continue
        if item is _END:
            return
        name, value = item
        yield _sse(name, value)
        if name in ("done", "error"):
            return


@app.post("/api/ask")
async def ask(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    question = body.get("question") if isinstance(body, dict) else None
    if not isinstance(question, str) or not question.strip():
        return JSONResponse({"status": 400, "code": "empty"}, status_code=400)
    if len(question) > cfg.QUESTION_MAX_CHARS:
        return JSONResponse({"status": 400, "code": "too_long"}, status_code=400)
    try:
        current_version()                 # 판이 없으면 답할 수 없다. 사람 확인과 돈이 드는 호출 앞에서 돌려보낸다
    except OSError:
        return JSONResponse({"status": 503, "code": "no_version"}, status_code=503)
    ok, _why = turnstile.verify(body.get("turnstile"), _client_ip(request))
    if not ok:
        return JSONResponse({"status": 401, "code": "turnstile"}, status_code=401)
    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(_events(question), media_type="text/event-stream", headers=headers)


@app.get("/api/ask")
async def ask_get():
    return JSONResponse({"status": 405, "code": "method"}, status_code=405)


@app.get("/api/status")
async def status():
    """살아 있는지, 지금 판, 오늘 새 답변을 받는지. 값을 못 읽으면 그 칸만 비운다."""
    out = {"ok": True, "version": None, "accepting": True, "reason": None,
           "turnstile": turnstile.enabled(), "budget": {"spent_usd": None, "limit_usd": cfg.DAILY_BUDGET_USD}}
    try:
        out["version"] = current_version()
    except OSError:
        out["ok"], out["accepting"], out["reason"] = False, False, "no_version"
        return JSONResponse(out, status_code=503)
    try:
        spent = store.connect().spent_today()
        out["budget"]["spent_usd"] = round(spent, 4)
        if spent >= cfg.DAILY_BUDGET_USD:
            out["accepting"], out["reason"] = False, "budget"
    except store.StoreError:
        out["accepting"], out["reason"] = False, "upstream"
    return out
