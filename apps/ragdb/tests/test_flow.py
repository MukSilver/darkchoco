# -*- coding: utf-8 -*-
"""지어낸 자료로 끝까지 태우는 시험 — 조각, 색인, 검색, 질의 순서, 스냅샷과 반출 관문.

번호는 설계서 7.2 의 확인 항목이다.
"""
import json
import os
import sqlite3

from app import answer, guard, pipeline, store
from app import config as cfg
from app.search import Searcher


def _all_text(world):
    con = sqlite3.connect(str(world.data / "ragdb.sqlite"))
    rows = con.execute("SELECT title || ' ' || section || ' ' || body FROM chunks").fetchall()
    con.close()
    return "\n".join(r[0] for r in rows)


# ── 조각 (F-03, F-05, DR-07) ──
def test_chunks_hide_names_domains_and_contact(world):
    text = _all_text(world)
    assert "가나다몰" not in text and "ganadamall" not in text          # 조직 이름과 그 도메인
    assert "betalock@example.org" not in text                          # 연락수단은 반출하는 칸이 아니다
    assert "UID" not in text                                           # 작업 관리용 칸
    assert guard.NAME_MASK in text and "alphaforum.st" in text         # 장소 이름으로 쓰이는 도메인은 남는다


def test_pii_is_masked_in_place(world):
    assert world.stats["excluded"] == []
    assert [e["document_id"] for e in world.stats["pii_masked"]] == ["사고-leak-2"]
    assert world.stats["pii_masked"][0]["hits"] == [{"where": "칸 메모", "what": "[IP]"}]
    text = _all_text(world)
    assert "203.0.113.7" not in text and "[IP]" in text                 # TC-03. 값은 안 나가고 문서는 남는다


def test_pii_document_is_excluded_when_asked(world, monkeypatch):
    import chunk as C
    monkeypatch.setattr(C, "PII_POLICY", "exclude")
    st = C.run(quiet=True)
    assert [e["document_id"] for e in st["excluded"]] == ["사고-leak-2"]      # 통째로 빼는 설정일 때 (F-03)
    assert "203.0.113.7" not in _all_text(world)


def test_terms_are_not_chunks_or_documents(world):
    con = sqlite3.connect(str(world.data / "ragdb.sqlite"))
    assert con.execute("SELECT COUNT(*) FROM documents WHERE kind = '용어'").fetchone()[0] == 0      # QR-05
    assert con.execute("SELECT COUNT(*) FROM chunks WHERE kind = '용어'").fetchone()[0] == 0
    con.close()
    assert world.stats["terms"] == 1


def test_unchecked_document_waits(world, monkeypatch):
    import chunk as C
    p = world.data / "names.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    d["docs"]["포럼-alphaforum"]["hash"] = "옛 해시"
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    st = C.run(quiet=True)
    waiting = [e["document_id"] for e in st["excluded"] if e["hits"][0]["what"] == "이름 찾기 전"]
    assert waiting == ["포럼-alphaforum"]


# ── 색인과 사전 (F-06) ──
def test_terms_skip_actor_aliases_and_keep_term_forms(world):
    with open(os.path.join(cfg.INDEX_ROOT, world.version, "terms.json"), encoding="utf-8") as f:
        items = json.load(f)["items"]
    heads = {i["head"] for i in items}
    assert "AlphaForum" in heads and "콤보리스트" in heads
    assert "seller1" not in heads                                      # OI-18
    assert not any("shadowpig77" in i["forms"] for i in items)


def test_index_stops_on_forbidden_word(world, monkeypatch):
    import build_index
    con = sqlite3.connect(str(world.data / "ragdb.sqlite"))
    con.execute("UPDATE chunks SET body = body || ' 주소는 http://leak.example/abc' WHERE chunk_id = '포럼-alphaforum#s1'")
    con.commit()
    con.close()
    assert build_index.build(version="20260101-000001") is None        # TC-06
    assert Searcher().version == world.version                         # current.txt 는 그대로


# ── 검색 (F-12) ──
def test_search_never_returns_hidden_chunks(world):
    s = Searcher()
    r = s.search("HiddenPlace 지금 상태")
    assert all(c["visibility"] for c in r["candidates"])              # 처리 1, SR-01
    assert not any(c["document_id"] == "포럼-hidden" for c in r["candidates"])


def test_search_tells_similar_names_apart(world):
    s = Searcher()
    assert s.search("alphaforum.st 지금 상태")["candidates"][0]["document_id"] == "포럼-alphaforum-st"      # TC-05
    assert s.search("AlphaForum 지금 상태")["candidates"][0]["document_id"] == "포럼-alphaforum"


def test_alias_question_needs_expansion(world):
    s = Searcher()
    q = "알파포럼 운영진 바뀌었어?"
    off = s.search(q, weight=0)
    on = s.search(q, weight=0.3)
    assert off["items"] == [] and all(c["expand"] == 0 for c in off["candidates"])
    assert on["candidates"][0]["document_id"] == "포럼-alphaforum"       # TC-20
    assert on["candidates"][0]["expand"] > 0
    assert [i["head"] for i in on["items"]] == ["AlphaForum"]


def test_search_works_without_dictionary(world):
    os.remove(os.path.join(cfg.INDEX_ROOT, world.version, "terms.json"))
    r = Searcher().search("AlphaForum 지금 상태")
    assert r["no_dictionary"] and r["candidates"]                      # TC-21


def test_kind_boost_does_not_exclude_other_kinds(world):
    r = Searcher().search("AlphaForum 포럼에서 활동한 seller1")
    kinds = {c["kind"] for c in r["candidates"]}
    assert r["kinds"] == ["포럼"] and {"포럼", "행위자"} <= kinds        # TC-10


# ── 질의 순서 (5.5) ──
def _run(q, stream, **kw):
    return pipeline.run(q, evaluation=True, stream_factory=stream, **kw)


def test_new_answer_then_reuse(world, fake_stream):
    stream = fake_stream([("AlphaForum 은 접속이 확인됐습니다(확인일 2026-09-01).", [0])])
    a = _run("AlphaForum 지금 살아 있나요?", stream)
    assert a["done"]["kind"] == "new" and a["sources"] and a["done"]["sentences"][0]["cited"]
    sent = stream.request["messages"][0]["content"]
    assert sent[-1] == {"type": "text", "text": "AlphaForum 지금 살아 있나요?"}
    assert all(b["citations"] == {"enabled": True} for b in sent[:-1])
    assert "thinking" in stream.request and "output_config" not in stream.request      # 인용과 구조화 출력은 함께 못 켠다

    again = fake_stream([("다시 부르면 안 되는 답", [0])])
    b = _run("AlphaForum은 지금 살아 있어?", again)                     # 조사와 어미가 달라도 같은 질문 키
    assert b["done"]["kind"] == "reused" and again.request is None      # F-21. 모델을 부르지 않는다
    assert b["text"] == a["text"]


def test_no_candidates_means_no_model_call(world, fake_stream):
    stream = fake_stream([("부르면 안 된다", [0])])
    r = _run("zzzzqqqq", stream)
    assert r["done"]["kind"] == "no_evidence" and r["text"] == answer.NO_EVIDENCE      # F-15, TC-12
    assert stream.request is None


def test_answer_without_citation_is_replaced(world, fake_stream):
    r = _run("AlphaForum 운영진은 누구야?", fake_stream([("아마 누구일 것입니다.", [])]))
    assert r["done"]["kind"] == "no_evidence" and r["text"] == answer.NO_EVIDENCE      # TC-11
    con = store.connect()
    assert con.execute("SELECT COUNT(*) FROM answer_cache").fetchone()[0] == 0          # 근거 없음은 저장하지 않는다
    con.close()


def test_pii_question_is_masked_and_not_stored(world, fake_stream):
    marker = "010-9876-5432"
    stream = fake_stream([("AlphaForum 기록에는 그런 내용이 있습니다.", [0])])
    r = _run("AlphaForum 에 %s 번호가 올라왔어?" % marker, stream)
    assert r["done"]["pii_masked"]
    assert marker not in json.dumps(stream.request["messages"], ensure_ascii=False)     # TC-34
    assert "[전화번호]" in stream.request["messages"][0]["content"][-1]["text"]
    con = store.connect()
    assert con.execute("SELECT COUNT(*) FROM answer_cache").fetchone()[0] == 0
    con.close()


def test_nothing_about_the_question_is_stored(world, fake_stream):
    marker = "표지문자열XYZ123"
    _run("AlphaForum %s 지금 상태" % marker, fake_stream([("AlphaForum 은 접속이 확인됐습니다.", [0])]))
    _run("%s zzzzqqqq" % marker, fake_stream([("x", [])]))
    con = store.connect()
    dump = "\n".join(str(tuple(r)) for t in ("qa_log", "answer_cache", "usage", "recheck_queue")
                     for r in con.execute("SELECT * FROM %s" % t))
    n = con.execute("SELECT COUNT(*) FROM qa_log").fetchone()[0]
    con.close()
    assert n == 2 and marker not in dump                                # TC-36, SR-16


def test_output_is_cleaned_before_it_leaves(world, fake_stream):
    stream = fake_stream([("이 자료는 가나다몰 것이고 shop.ganadamall.example.kr 에서 나왔습니다.", [0])])
    r = _run("AlphaForum 에 올라온 자료는 어디 거야?", stream)
    assert "가나다몰" not in r["text"] and "ganadamall" not in r["text"]
    assert "가나다몰" not in json.dumps(r["done"]["sentences"], ensure_ascii=False)


def test_rerank_failure_falls_back_to_word_order(world, fake_stream):
    def broken(q, docs, n):
        raise RuntimeError("사업자 장애")
    seen = {}

    def spy(q, docs, n):
        seen.update(q=q, docs=docs)
        raise RuntimeError("사업자 장애")
    import pytest
    monkey = pytest.MonkeyPatch()
    monkey.setattr(cfg, "COHERE_API_KEY", "x")
    try:
        r = pipeline.run("알파포럼 지금 상태", evaluation=True, rerank_call=spy,
                         stream_factory=fake_stream([("AlphaForum 은 접속이 확인됐습니다.", [0])]))
    finally:
        monkey.undo()
    assert r["done"]["kind"] == "new" and r["done"]["rerank_applied"] is False          # TC-23, QR-03
    assert seen["q"] == "알파포럼 지금 상태"                                              # 넓힌 낱말은 보내지 않는다 (SR-19)
    assert not any("HiddenPlace" in d for d in seen["docs"])                            # TC-24


def test_rerank_order_is_used_but_not_its_text(world, fake_stream):
    class R:
        def __init__(self, i, s):
            self.index, self.relevance_score, self.document = i, s, {"text": "사업자가 돌려준 글"}

    def call(q, docs, n):
        return type("Res", (), {"results": [R(len(docs) - 1, 0.9), R(0, 0.5)]})()
    from app import rerank
    s = Searcher()
    con = store.connect()
    cands = s.search("AlphaForum 지금 상태")["candidates"]
    full = [dict(c, **{"body": b["body"]}) for c in cands for b in store.chunks_by_id(con, [c["chunk_id"]])]
    con.close()
    import pytest
    monkey = pytest.MonkeyPatch()
    monkey.setattr(cfg, "COHERE_API_KEY", "x")
    try:
        out, applied, _ = rerank.rerank("AlphaForum 지금 상태", full, k=2, call=call)
    finally:
        monkey.undo()
    assert applied and out[0]["chunk_id"] == full[-1]["chunk_id"] and out[0]["rerank_rank"] == 1
    assert all("사업자가 돌려준 글" not in c["body"] for c in out)                       # SR-20, TC-25


def test_budget_breaker_stops_visitors_only(world, fake_stream, monkeypatch):
    monkeypatch.setattr(cfg, "DAILY_BUDGET_USD", 0.0)
    stream = fake_stream([("AlphaForum 은 접속이 확인됐습니다.", [0])])
    r = pipeline.run("AlphaForum 지금 상태", evaluation=False, stream_factory=stream)
    assert r["error"] == {"status": 503, "code": "budget"} and stream.request is None   # TC-33
    assert _run("AlphaForum 지금 상태", stream)["done"]["kind"] == "new"                 # 관리 질의는 따로 센다


def test_question_length_limit(world, fake_stream):
    r = _run("가" * (cfg.QUESTION_MAX_CHARS + 1), fake_stream([("x", [0])]))
    assert r["error"] == {"status": 400, "code": "too_long"}


def test_version_change_drops_old_reuse(world, fake_stream):
    _run("AlphaForum 지금 상태", fake_stream([("AlphaForum 은 접속이 확인됐습니다.", [0])]))
    con = store.connect()
    assert con.execute("SELECT COUNT(*) FROM answer_cache").fetchone()[0] == 1
    assert store.drop_old_cache(con, "20260202-000000") == 1                             # TC-35, DR-10
    con.close()


# ── 스냅샷과 반출 관문 (F-22) ──
def test_snapshot_holds_only_exported(world):
    import snapshot
    r = snapshot.bake(world.version)
    root = os.path.join(cfg.SNAPSHOT_ROOT, world.version)
    assert not os.path.exists(os.path.join(root, "doc", "포럼-hidden.json"))             # TC-09
    with open(os.path.join(root, "doc", "사고-leak-2.json"), encoding="utf-8") as f:
        assert "203.0.113.7" not in f.read()
    assert os.path.exists(os.path.join(root, "doc", "포럼-alphaforum.json"))
    ids = [fn[:-5] for fn in os.listdir(os.path.join(root, "doc"))]
    assert "포럼-hidden" not in ids and r["documents"] == len(ids)
    # 목록과 전체 내려받기는 굽지 않는다 (2026-09-30, 설계서 판 1.5)
    assert not os.path.exists(os.path.join(root, "list.json")) and not os.path.exists(os.path.join(root, "export"))
    with open(os.path.join(root, "doc", "포럼-alphaforum-st.json"), encoding="utf-8") as f:
        d = json.load(f)
    assert d["stale"] is True and all(c["images"] == [] for c in d["chunks"])
    assert snapshot.gate(world.version) == []


def test_gate_catches_what_must_not_leave(world):
    import snapshot
    snapshot.bake(world.version)
    p = os.path.join(cfg.SNAPSHOT_ROOT, world.version, "doc", "포럼-alphaforum.json")
    with open(p, encoding="utf-8") as f:
        d = json.load(f)
    d["chunks"][0]["body"] += " 가나다몰 자료. 문의 010-1234-5678. 같은 사람으로 보이는 shadowpig77. victim.example.com"
    d["aliases"] = ["알파포럼"]
    d["attributes"]["들어가는 법"] = "초대 필요"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    what = {b["what"] for b in snapshot.gate(world.version)}
    assert {"조직 이름", "개인정보 꼴 [전화번호]", "행위자의 다른 이름", "내보내지 않는 칸",
            "반출하는 칸 목록 밖의 칸"} <= what                                          # TC-18, TC-22
    assert all("가나다몰" not in json.dumps(b, ensure_ascii=False) for b in snapshot.gate(world.version))


def test_strip_active_removes_scripts_and_links():
    import snapshot
    out = snapshot.strip_active('글 <script>alert(1)</script> 과 [자료](http://x.example/a) 와 <b onclick="x()">굵게</b>')
    assert "script" not in out and "http" not in out and "<" not in out and "자료" in out and "굵게" in out      # TC-19
