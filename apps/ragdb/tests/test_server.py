# -*- coding: utf-8 -*-
"""질의 서버 시험 — 설계서 「API와 스냅샷 파일」. 모델, 재순위, Supabase 를 부르지 않는다. 0원.

pipeline.ask 를 가짜 제너레이터로 바꿔 SSE 이벤트 순서와 오류 코드만 본다. 자료는 지어낸 것이다.
"""
import json

import pytest
from fastapi.testclient import TestClient

from app import config as cfg
from server import main, turnstile


def parse_sse(text):
    """SSE 본문을 [(event, data)] 로. 주석 줄(keepalive)은 뺀다."""
    out = []
    for block in text.strip().split("\n\n"):
        name, data = None, None
        for line in block.split("\n"):
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                data = json.loads(line[5:].strip())
        if name:
            out.append((name, data))
    return out


@pytest.fixture()
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(turnstile, "secret", lambda: "")          # 검증 끔
    cur = tmp_path / "current.txt"                                # 판이 있는 것으로
    cur.write_text("20260901-000000", encoding="utf-8")
    monkeypatch.setattr(cfg, "CURRENT", str(cur))
    return TestClient(main.app)


def test_ask_without_version_is_503(client, monkeypatch, tmp_path):
    monkeypatch.setattr(cfg, "CURRENT", str(tmp_path / "없음.txt"))
    called = []
    monkeypatch.setattr(main.pipeline, "ask", lambda q, **kw: called.append(q) or iter(()))
    r = client.post("/api/ask", json={"question": "알파포럼 살아 있어?"})
    assert r.status_code == 503 and r.json()["code"] == "no_version"
    assert called == []                                           # 판이 없으면 질의 순서에 들어가지 않는다


def test_other_origin_is_allowed_only_when_listed(monkeypatch):
    import importlib
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://rag.example.org")
    m = importlib.reload(main)
    try:
        c = TestClient(m.app)
        ok = c.options("/api/ask", headers={"Origin": "https://rag.example.org", "Access-Control-Request-Method": "POST"})
        no = c.options("/api/ask", headers={"Origin": "https://evil.example.org", "Access-Control-Request-Method": "POST"})
        assert ok.headers.get("access-control-allow-origin") == "https://rag.example.org"
        assert "access-control-allow-origin" not in no.headers
    finally:
        monkeypatch.delenv("ALLOWED_ORIGINS")
        importlib.reload(main)


def fake_ask(events):
    def _ask(question, **kw):
        for e in events:
            yield e
    return _ask


def test_get_ask_is_405(client):
    assert client.get("/api/ask").status_code == 405


def test_empty_and_too_long_are_400(client, monkeypatch):
    assert client.post("/api/ask", json={"question": "  "}).json()["code"] == "empty"
    monkeypatch.setattr(cfg, "QUESTION_MAX_CHARS", 10)
    r = client.post("/api/ask", json={"question": "가" * 11})
    assert r.status_code == 400 and r.json()["code"] == "too_long"


def test_turnstile_failure_is_401(client, monkeypatch):
    monkeypatch.setattr(turnstile, "verify", lambda token, ip=None, **kw: (False, "failed"))
    r = client.post("/api/ask", json={"question": "알파포럼 살아 있어?", "turnstile": "bad"})
    assert r.status_code == 401 and r.json()["code"] == "turnstile"


def test_new_answer_event_order(client, monkeypatch):
    sources = [{"n": 1, "chunk_id": "포럼-alphaforum#s0", "document_id": "포럼-alphaforum", "kind": "포럼",
                "title": "AlphaForum", "section": "속성", "observed_at": "2026-09-01", "date_label": "확인일", "status": "online"}]
    done = {"kind": "new", "sentences": [{"text": "AlphaForum 은 online 상태입니다.", "sources": [1], "cited": True}],
            "version": "20260901-000000", "pii_masked": False, "rerank_applied": True, "truncated": False}
    monkeypatch.setattr(main.pipeline, "ask", fake_ask([
        ("received", {}), ("searching", {}), ("text", "AlphaForum 은 online 상태입니다."), ("sources", sources), ("done", done)]))
    r = client.post("/api/ask", json={"question": "알파포럼 살아 있어?"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(r.text)
    assert [e for e, _ in events] == ["received", "searching", "text", "sources", "done"]
    assert events[3][1][0]["date_label"] == "확인일"
    assert events[4][1]["kind"] == "new"


def test_no_evidence_and_replace(client, monkeypatch):
    monkeypatch.setattr(main.pipeline, "ask", fake_ask([
        ("received", {}), ("searching", {}), ("text", "첫 문장."), ("replace", "확인 가능한 근거를 찾지 못했습니다"),
        ("done", {"kind": "no_evidence", "sentences": [], "version": "v", "pii_masked": False})]))
    events = parse_sse(client.post("/api/ask", json={"question": "OO은행 자료 어디서 팔아?"}).text)
    assert [e for e, _ in events] == ["received", "searching", "text", "replace", "done"]
    assert events[3][1] == "확인 가능한 근거를 찾지 못했습니다"


def test_budget_error_stops_stream(client, monkeypatch):
    monkeypatch.setattr(main.pipeline, "ask", fake_ask([("received", {}), ("error", {"status": 503, "code": "budget"})]))
    events = parse_sse(client.post("/api/ask", json={"question": "질문"}).text)
    assert events[-1] == ("error", {"status": 503, "code": "budget"})


def test_unexpected_exception_becomes_error_event(client, monkeypatch):
    def boom(question, **kw):
        yield "received", {}
        raise RuntimeError("실제 자료 문자열이 여기 있어도 밖으로 나가면 안 된다")
    monkeypatch.setattr(main.pipeline, "ask", boom)
    r = client.post("/api/ask", json={"question": "질문"})
    events = parse_sse(r.text)
    assert events[-1] == ("error", {"status": 503, "code": "internal"})
    assert "실제 자료" not in r.text


def test_status_reports_version_and_budget(client, monkeypatch, tmp_path):
    cur = tmp_path / "current.txt"
    cur.write_text("20260901-000000", encoding="utf-8")
    monkeypatch.setattr(cfg, "CURRENT", str(cur))

    class St:
        def spent_today(self):
            return 0.5
    monkeypatch.setattr(main.store, "connect", lambda: St())
    monkeypatch.setattr(cfg, "DAILY_BUDGET_USD", 3.0)
    j = client.get("/api/status").json()
    assert j["ok"] and j["version"] == "20260901-000000" and j["accepting"] and j["turnstile"] is False
    assert j["budget"] == {"spent_usd": 0.5, "limit_usd": 3.0}


def test_status_budget_exhausted(client, monkeypatch, tmp_path):
    cur = tmp_path / "current.txt"
    cur.write_text("v", encoding="utf-8")
    monkeypatch.setattr(cfg, "CURRENT", str(cur))

    class St:
        def spent_today(self):
            return 3.2
    monkeypatch.setattr(main.store, "connect", lambda: St())
    monkeypatch.setattr(cfg, "DAILY_BUDGET_USD", 3.0)
    j = client.get("/api/status").json()
    assert j["accepting"] is False and j["reason"] == "budget"


def test_status_without_version_is_503(client, monkeypatch, tmp_path):
    monkeypatch.setattr(cfg, "CURRENT", str(tmp_path / "없음.txt"))
    r = client.get("/api/status")
    assert r.status_code == 503 and r.json()["reason"] == "no_version"


def test_slow_answer_keeps_alive_and_loses_no_event(client, monkeypatch):
    """답이 늦게 오면 주석 줄로 연결을 살린다. 그 사이에 온 이벤트가 빠지면 안 된다."""
    import time
    monkeypatch.setattr(main, "KEEPALIVE_SECONDS", 0.05)

    def slow(question, **kw):
        yield "received", {}
        time.sleep(0.3)                                           # 재순위가 늦는 자리
        yield "searching", {}
        time.sleep(0.3)                                           # 답 만들기가 늦는 자리
        yield "text", "첫 문장."
        yield "done", {"kind": "new", "sentences": [], "version": "v", "pii_masked": False}
    monkeypatch.setattr(main.pipeline, "ask", slow)
    r = client.post("/api/ask", json={"question": "질문"})
    assert ": keepalive" in r.text
    assert [e for e, _ in parse_sse(r.text)] == ["received", "searching", "text", "done"]


def test_pipeline_runs_to_end_after_client_leaves(client, monkeypatch):
    """방문자가 중간에 끊어도 질의 순서는 끝까지 돈다. 쓴 돈과 질의 기록이 남아야 하루 차단기가 맞는다."""
    import threading
    finished = threading.Event()

    def ask(question, **kw):
        yield "received", {}
        yield "text", "첫 문장."
        yield "done", {"kind": "new", "sentences": [], "version": "v", "pii_masked": False}
        finished.set()                                            # 질의 기록을 남기는 자리
    monkeypatch.setattr(main.pipeline, "ask", ask)
    with client.stream("POST", "/api/ask", json={"question": "질문"}) as r:
        next(r.iter_lines())                                      # 첫 줄만 받고 끊는다
    assert finished.wait(2)


class FakeHttp:
    def __init__(self, body=None, error=None):
        self.body, self.error, self.sent = body, error, None

    def post(self, url, data=None, timeout=None):
        self.sent = data
        if self.error:
            raise self.error

        class R:
            def json(_):
                return self.body
        return R()


def test_turnstile_verify(monkeypatch):
    monkeypatch.setattr(turnstile, "secret", lambda: "")
    assert turnstile.verify("아무거나") == (True, "disabled")       # 비밀값이 없으면 검증을 끈다

    monkeypatch.setattr(turnstile, "secret", lambda: "시험용-비밀값")
    assert turnstile.verify("") == (False, "missing")

    ok = FakeHttp({"success": True})
    assert turnstile.verify("tok", "203.0.113.5", client=ok) == (True, "ok")
    assert ok.sent == {"secret": "시험용-비밀값", "response": "tok", "remoteip": "203.0.113.5"}

    assert turnstile.verify("tok", client=FakeHttp({"success": False, "error-codes": ["timeout-or-duplicate"]})) == (False, "timeout-or-duplicate")
    assert turnstile.verify("tok", client=FakeHttp({"success": False})) == (False, "failed")
    # Cloudflare 가 안 닿으면 통과시키지 않는다
    assert turnstile.verify("tok", client=FakeHttp(error=OSError("연결 끊김"))) == (False, "unreachable")


def test_turnstile_is_checked_before_pipeline(client, monkeypatch):
    """사람 확인에 실패하면 돈이 드는 질의 순서에 들어가지 않는다. IP 는 터널이 준 머리말에서 읽는다."""
    seen, called = {}, []

    def verify(token, ip=None, **kw):
        seen.update(token=token, ip=ip)
        return False, "failed"
    monkeypatch.setattr(turnstile, "verify", verify)
    monkeypatch.setattr(main.pipeline, "ask", lambda q, **kw: called.append(q) or iter(()))
    r = client.post("/api/ask", json={"question": "질문", "turnstile": "tok"}, headers={"CF-Connecting-IP": "203.0.113.5"})
    assert r.status_code == 401 and called == []
    assert seen == {"token": "tok", "ip": "203.0.113.5"}
