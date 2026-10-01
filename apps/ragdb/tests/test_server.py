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
