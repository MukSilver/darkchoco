# -*- coding: utf-8 -*-
"""문제집, 사전 답변(F-16, F-17), 평가(7.2), 빠진 줄 명부(F-20). 자료는 지어낸 것이다."""
import json
import os
import sqlite3

from app import answer, pipeline, questions, store
from app import config as cfg
from app.search import Searcher

QUESTIONS = {"questions": [
    {"id": "Q1", "question": "AlphaForum 지금 상태 알려줘", "rows": ["AlphaForum"]},
    {"id": "Q2", "question": "알파포럼 운영진 바뀌었어?", "rows": ["알파포럼"]},
    {"id": "Q3", "question": "LEAK-1 은 어떤 사고야?", "rows": ["LEAK-1"]},
    {"id": "Q4", "question": "감마포럼은 살아 있어?", "rows": ["GammaForum"]},
    {"id": "Q5", "question": "오늘 점심 뭐 먹지", "none": True},
    {"id": "Q6", "question": "없는 줄을 적은 질문", "rows": ["아무도모르는이름"]},
]}
EXCLUDED = {"made_at": "2026-09-30T00:00:00+00:00",
            "rows": [{"kind": "포럼", "name": "GammaForum", "aliases": ["감마포럼"], "status": "online", "observed_at": None}]}


def _write(world):
    (world.data / "questions.json").write_text(json.dumps(QUESTIONS, ensure_ascii=False), encoding="utf-8")
    (world.data / "excluded_rows.json").write_text(json.dumps(EXCLUDED, ensure_ascii=False), encoding="utf-8")


def _resolver(world):
    import chunk as C
    con = store.connect()
    live = {r[0] for r in con.execute("SELECT document_id FROM documents WHERE visibility = 1")}
    con.close()
    return questions.resolver(C.load_docs(), live, EXCLUDED["rows"])


def _fake_generate(blocks):
    class U:
        input_tokens, output_tokens, cache_creation_input_tokens, cache_read_input_tokens = 1000, 100, 0, 0

    def gen(question, chunks, stream_factory=None):
        yield "text", "".join(b["text"] for b in blocks)
        yield "result", {"blocks": [dict(b) for b in blocks], "usage": U(), "cost": 0.003, "stop_reason": "end_turn", "model": "fake-model"}
    return gen


# ── 문제집 ──
def test_rows_resolve_by_name_alias_and_number(world):
    _write(world)
    resolve = _resolver(world)
    kinds = {q["id"]: questions.kind_of(q, resolve) for q in questions.load()}
    assert kinds["Q1"] == ("answerable", ["포럼-alphaforum"])
    assert kinds["Q2"] == ("answerable", ["포럼-alphaforum"])          # 별칭으로 적어도 같은 문서
    assert kinds["Q3"] == ("answerable", ["사고-leak-1"])              # 사건 번호
    assert kinds["Q4"] == ("hidden", [])                              # 빠진 줄 명부에만 있는 줄
    assert kinds["Q5"] == ("none", [])
    assert kinds["Q6"] == ("unknown", [])


def test_no_question_file_is_not_an_error(world):
    assert questions.load() == []


# ── 사전 답변 ──
def test_prepared_answer_needs_review_and_fresh_evidence(world, fake_stream, monkeypatch):
    import prepare_answers as P
    _write(world)
    monkeypatch.setattr(P, "PENDING", str(world.data / "prepare_batch.json"))
    monkeypatch.setattr(answer, "generate", _fake_generate([{"text": "AlphaForum 은 접속이 확인됐습니다.", "cites": [{"n": 1}]}]))
    con = store.connect()
    s = Searcher()
    todo, same, empty, _ = P.plan(s, con)
    assert {t["id"] for t in todo} >= {"Q1", "Q2", "Q3"} and "Q5" not in {t["id"] for t in todo}
    t = next(x for x in todo if x["id"] == "Q1")
    res = next(v for k, v in answer.generate(t["question"], t["chunks"]) if k == "result")
    assert P.save(con, s, t, res)
    con.close()

    never = fake_stream([("모델을 부르면 안 된다", [0])])
    run = lambda: pipeline.run("AlphaForum 지금 상태 알려줘", evaluation=True, stream_factory=never)
    monkeypatch.undo()                                                # answer.generate 를 되돌린다
    # conftest 의 world 가 건 값도 같이 풀리므로 다시 건다
    for k, v in {"DATA_DIR": str(world.data), "SQLITE_PATH": str(world.data / "ragdb.sqlite"),
                 "INDEX_ROOT": str(world.data / "bm25_index"), "CURRENT": str(world.data / "current.txt"),
                 "FINGERPRINT_KEY": "test-key", "COHERE_API_KEY": ""}.items():
        monkeypatch.setattr(cfg, k, v)

    assert run()["done"]["kind"] == "new"                             # 검토 전에는 쓰이지 않는다
    con = sqlite3.connect(str(world.data / "ragdb.sqlite"))
    con.execute("DELETE FROM answer_cache")
    con.execute("UPDATE answers SET reviewed = 1")
    con.commit()
    never.request = None
    out = run()
    assert out["done"]["kind"] == "prepared" and never.request is None      # F-16. 모델을 부르지 않는다
    assert out["text"].startswith("AlphaForum 은 접속이 확인됐습니다")

    con.execute("UPDATE documents SET content_hash = '바뀜' WHERE document_id = '포럼-alphaforum'")
    con.commit()
    con.close()
    assert run()["done"]["kind"] == "new"                             # TC-13. 근거 문서가 바뀌면 옛 답은 안 나온다


def test_answer_without_source_is_not_saved(world, monkeypatch):
    import prepare_answers as P
    _write(world)
    con = store.connect()
    s = Searcher()
    t = P.plan(s, con)[0][0]
    res = {"blocks": [{"text": "출처 없이 한 말입니다.", "cites": []}], "stop_reason": "end_turn", "model": "fake", "cost": 0}
    assert not P.save(con, s, t, res)
    assert con.execute("SELECT COUNT(*) FROM answers").fetchone()[0] == 0
    con.close()


def test_prepared_answer_is_cleaned(world):
    import prepare_answers as P
    _write(world)
    con = store.connect()
    s = Searcher()
    t = P.plan(s, con)[0][0]
    res = {"blocks": [{"text": "가나다몰 자료가 올라왔습니다.", "cites": [{"n": 1}]}], "stop_reason": "end_turn", "model": "fake", "cost": 0}
    assert P.save(con, s, t, res)
    saved = con.execute("SELECT answer FROM answers").fetchone()[0]
    con.close()
    assert "가나다몰" not in saved


# ── 평가 ──
def test_evaluate_counts_by_kind(world, monkeypatch):
    import evaluate as E
    _write(world)
    monkeypatch.setattr(answer, "generate", _fake_generate([{"text": "근거 있는 문장입니다.", "cites": [{"n": 1}]},
                                                           {"text": " 덧붙인 문장입니다.", "cites": []}]))
    resolve = _resolver(world)
    qs = questions.load()
    for q in qs:
        q["kind"], q["want"] = questions.kind_of(q, resolve)
    con = store.connect()
    base = E.run_one(1, qs, Searcher(), con, with_answers=False)
    wide = E.run_one(2, qs, Searcher(), con, with_answers=True)
    skipped = E.run_one(3, qs, Searcher(), con, with_answers=False)
    con.close()
    assert base["counts"]["answerable"] == 3 and base["counts"]["hidden"] == 1 and base["counts"]["none"] == 1
    assert base["metrics"]["후보 포함"] == 1.0 and "근거 부합" not in base["metrics"]
    assert wide["weight"] == 0.3 and wide["metrics"]["근거 부합"] == 0.5
    assert wide["split"]["반출 오제외"] == 1
    assert "skipped" in skipped                                       # 재순위 열쇠가 없으면 셋째 벌은 건너뛴다


# ── 빠진 줄 명부 ──
def test_recheck_tells_hidden_rows_apart(world, fake_stream):
    import recheck
    _write(world)
    never = fake_stream([("x", [])])
    pipeline.run("감마포럼 zzqq", evaluation=False, stream_factory=never)          # 빠진 줄과 이름이 겹친다
    pipeline.run("yyyzzzqqq", evaluation=False, stream_factory=never)             # 아무것과도 안 겹친다
    st = recheck.run(quiet=True)
    assert st["branches"]["빠진 줄 겹침"] == 1 and st["branches"]["겹침 없음"] == 1      # TC-26
    con = store.connect()
    rows = con.execute("SELECT branch, row_name FROM recheck_queue WHERE branch = '빠진 줄 겹침'").fetchall()
    left = con.execute("SELECT COUNT(*) FROM qa_log WHERE word_fps IS NOT NULL").fetchone()[0]
    con.close()
    assert [tuple(r) for r in rows] == [("빠진 줄 겹침", "GammaForum")]
    assert left == 0                                                  # 쓴 질문 낱말 지문은 지운다


def test_excluded_names_are_counted_not_blocked(world):
    import snapshot
    _write(world)
    snapshot.bake(world.version)
    p = os.path.join(cfg.SNAPSHOT_ROOT, world.version, "doc", "포럼-alphaforum.json")
    with open(p, encoding="utf-8") as f:
        d = json.load(f)
    d["chunks"][0]["body"] += " GammaForum 으로 옮겼다는 글이 있다."
    with open(p, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    ex = snapshot.excluded_names(world.version)
    assert ex["files"] == 1 and ex["by_kind"] == {"포럼": 1}
    assert "GammaForum" not in json.dumps(ex, ensure_ascii=False)


# ── 2026-09-30 검토에서 고친 것 ──
def test_query_reads_bodies_of_its_own_version(world):
    """배치가 SQLite 의 조각을 고쳐도, 질의는 색인과 같은 판 폴더의 본문을 읽는다."""
    con = store.connect()
    s = Searcher()
    cid = "포럼-alphaforum#s1"
    before = s.chunks(con, [cid])[0]["body"]
    con.execute("UPDATE chunks SET body = '배치가 도는 중에 바뀐 본문' WHERE chunk_id = ?", (cid,))
    con.commit()
    assert s.chunks(con, [cid])[0]["body"] == before
    assert store.chunks_by_id(con, [cid])[0]["body"] != before
    con.close()


def test_stored_answer_is_cleaned_when_it_goes_out(world, fake_stream):
    """저장해 둔 답에 나중에 찾은 조직 표기가 들어 있어도 나갈 때 가려진다."""
    con = store.connect()
    key = __import__("tokenize_ko").question_key("AlphaForum 지금 상태 알려줘")
    h = con.execute("SELECT content_hash FROM documents WHERE document_id = '포럼-alphaforum'").fetchone()[0]
    sents = [{"text": "가나다몰 자료가 AlphaForum 에 올라왔습니다.", "sources": [1], "cited": True}]
    srcs = [{"n": 1, "chunk_id": "포럼-alphaforum#s1", "document_id": "포럼-alphaforum", "kind": "포럼",
             "title": "AlphaForum", "section": "가나다몰 글", "observed_at": "2026-09-01", "status": "online"}]
    with con:
        con.execute("INSERT INTO answers (question_key, question, answer, sources, model, created_at, reviewed, doc_hashes) "
                    "VALUES (?,?,?,?,?,?,1,?)", (key, "q", store.j(sents), store.j(srcs), "m", store.now(),
                                                 store.j({"포럼-alphaforum": h})))
    con.close()
    out = pipeline.run("AlphaForum 지금 상태 알려줘", evaluation=True, stream_factory=fake_stream([("x", [0])]))
    assert out["done"]["kind"] == "prepared"
    assert "가나다몰" not in json.dumps(out, ensure_ascii=False)


def test_only_checked_kinds_go_stale():
    import snapshot
    assert snapshot.is_stale("2020-01-01", kind="포럼") is True
    assert snapshot.is_stale("2020-01-01", kind="사고") is False          # 사고의 날짜는 공표 시점이나 수집일이다
    assert snapshot.is_stale("2020-01-01", kind="판정") is False


def test_date_label_tells_publication_from_check():
    inc = {"kind": "사고", "document_id": "사고-inc-3", "body": "본문", "observed_at": "2025-12-01"}
    leak = {"kind": "사고", "document_id": "사고-leak-3", "body": "본문", "observed_at": "2026-06-02"}
    assert answer.date_label(inc) == "공표 시점" and answer.document_text(inc).endswith("공표 시점: 2025-12-01")
    assert answer.date_label(leak) == "확인일" and answer.document_text(leak).endswith("확인일: 2026-06-02")
