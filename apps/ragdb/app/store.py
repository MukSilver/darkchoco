# -*- coding: utf-8 -*-
"""운영 기록 저장 — Supabase rag 스키마 (설계서 「저장 위치」).

2026-09-30 김무근 결정으로 SQLite 를 쓰지 않는다. 사전 답변, 재사용 답변, 질의 기록, 비용, 재조사 후보,
문제집, 찾아 둔 조직 표기는 Supabase 에 있다. 그래서 저장소와 열쇠만 있으면 어느 기계에서든 돈다.
표와 함수는 darkchoco-data 의 migrations/0012_rag_runtime.sql 이 만든다.

여기 있는 것은 키로 꺼내고 덧붙이는 일뿐이다. 검색은 판 폴더의 색인 파일에서 한다.
조각과 문서 목록은 여기 없다. 판 폴더(chunks.json, documents.json)에 있다.

저장소가 닿지 않으면 StoreError 가 난다. 오류 글에 질문이나 자료를 싣지 않는다.
시험은 MemoryStore 를 끼워 쓴다 (바깥 호출 없음).
"""
import datetime
import json

from . import config as cfg

KST = datetime.timezone(datetime.timedelta(hours=9))


class StoreError(Exception):
    """저장소(Supabase)에 닿지 못했거나 거절당했다."""


def now():
    return datetime.datetime.now(KST).isoformat(timespec="seconds")


def today():
    """하루 차단기는 한국 시간 자정에 새로 센다 (F-18 처리 4)."""
    return datetime.datetime.now(KST).strftime("%Y-%m-%d")


def holds(docs, row):
    """사전 답변을 아직 써도 되는가. 답에 쓰인 근거 문서가 만든 때 그대로여야 한다 (F-16 처리 3, F-07 처리 2).

    docs 는 지금 판의 문서 목록 {document_id: {content_hash, visibility}} 이다 (판 폴더의 documents.json).
    상태가 offline 으로 바뀌면 내용 해시도 바뀌므로 따로 보지 않는다.
    """
    hashes = row.get("doc_hashes") or {}
    if not hashes:
        return False
    for did, h in hashes.items():
        d = (docs or {}).get(did)
        if not d or d.get("content_hash") != h or not d.get("visibility"):
            return False
    return True


QA_COLUMNS = ["at", "question_hash", "question_len", "sources", "no_evidence", "used_prepared", "reused", "evaluation",
              "pii_masked", "term_items", "score_sources", "no_dictionary", "expansion_truncated", "rerank_applied",
              "rerank_ms", "cost", "word_fps"]
QA_FLAGS = ("no_evidence", "used_prepared", "reused", "evaluation", "pii_masked", "no_dictionary", "expansion_truncated",
            "rerank_applied")


def qa_row(row):
    """질의 기록 한 줄을 다듬는다. 질문 원문, 답변 본문, IP 는 남기지 않는다 (SR-16, SR-23). 받는 칸이 애초에 없다."""
    row = dict(row)
    row.setdefault("at", now())
    extra = set(row) - set(QA_COLUMNS)
    if extra:
        raise ValueError("질의 기록에 없는 칸: %s" % ", ".join(sorted(extra)))
    out = {c: row.get(c) for c in QA_COLUMNS}
    for c in QA_FLAGS:
        out[c] = bool(out[c])
    return out


class SupabaseStore:
    """Supabase 의 rag 스키마를 REST 로 읽고 쓴다. 연결 하나를 계속 쓴다."""

    def __init__(self, url=None, key=None, timeout=15):
        import httpx
        url = (url or cfg.SUPABASE_URL).rstrip("/")
        key = key or cfg.SUPABASE_SERVICE_KEY
        if not url or not key:
            raise StoreError("SUPABASE_URL 과 SUPABASE_SERVICE_KEY 가 .env 에 없다")
        self._httpx = httpx
        self._c = httpx.Client(base_url=url + "/rest/v1", timeout=timeout, headers={
            "apikey": key, "Authorization": "Bearer " + key, "Accept-Profile": "rag", "Content-Profile": "rag"})

    def close(self):
        self._c.close()

    # ── 부품 ──
    def _do(self, method, path, **kw):
        try:
            r = self._c.request(method, path, **kw)
        except self._httpx.HTTPError as e:
            raise StoreError("저장소에 닿지 못함 (%s)" % type(e).__name__)
        if r.status_code >= 300:
            raise StoreError("저장소가 거절함 (%s %s %s)" % (method, path.split("?")[0], r.status_code))
        return r

    def _rows(self, table, **params):
        return self._do("GET", "/" + table, params=params).json()

    def _all(self, table, order, **params):
        """표 하나를 끝까지 읽는다. 한 번에 1,000줄까지라 나눠 읽는다."""
        out, offset = [], 0
        while True:
            rows = self._rows(table, order=order, limit=1000, offset=offset, **params)
            out.extend(rows)
            if len(rows) < 1000:
                return out
            offset += 1000

    def _insert(self, table, rows, on_conflict=None, back=False):
        prefer = ["return=representation" if back else "return=minimal"]
        params = {}
        if on_conflict:
            prefer.append("resolution=merge-duplicates")
            params["on_conflict"] = on_conflict
        r = self._do("POST", "/" + table, params=params, json=rows, headers={"Prefer": ",".join(prefer)})
        return r.json() if back else None

    def _rpc(self, name, **args):
        r = self._do("POST", "/rpc/" + name, json=args)
        return r.json() if r.content else None

    # ── 사전 답변 (F-16, F-17) ──
    def prepared_row(self, key):
        """검토를 통과한 것만 (TC-13). 아직 써도 되는지는 holds() 로 따로 본다."""
        rows = self._rows("answers", question_key="eq." + key, reviewed="is.true", limit=1)
        return rows[0] if rows else None

    def answer_row(self, key):
        rows = self._rows("answers", question_key="eq." + key, limit=1)
        return rows[0] if rows else None

    def answers_all(self):
        return self._all("answers", "reviewed.asc,created_at.asc,question_key.asc")

    def put_answer(self, key, question, answer, sources, model, doc_hashes):
        """답 하나를 검토 전으로 넣는다. 같은 질문 키가 있으면 바꾸고 검토 전으로 되돌린다."""
        self._insert("answers", [{"question_key": key, "question": question, "answer": answer, "sources": sources,
                                  "model": model, "created_at": now(), "reviewed": False, "doc_hashes": doc_hashes}],
                     on_conflict="question_key")

    def review_answer(self, key, who, passed=True):
        """통과시키거나 지운다. 누가 했는지 확인 기록에 남긴다."""
        if passed:
            self._do("PATCH", "/answers", params={"question_key": "eq." + key}, json={"reviewed": True},
                     headers={"Prefer": "return=minimal"})
        else:
            self._do("DELETE", "/answers", params={"question_key": "eq." + key}, headers={"Prefer": "return=minimal"})
        self._insert("review_log", [{"at": now(), "who": who, "what": "사전 답변 검토 통과" if passed else "사전 답변 지움",
                                     "target": key}])

    # ── 재사용 답변 (F-21) ──
    def cached_answer(self, version, key_fp):
        rows = self._rpc("cache_hit", p_version=version, p_key_fp=key_fp)
        return rows[0] if rows else None

    def save_cache(self, version, key_fp, answer, sources, model):
        self._insert("answer_cache", [{"version": version, "key_fp": key_fp, "answer": answer, "sources": sources,
                                       "model": model, "created_at": now()}], on_conflict="version,key_fp")

    def cache_count(self):
        return len(self._all("answer_cache", "version.asc,key_fp.asc", select="key_fp"))

    def drop_old_cache(self, version):
        """판이 바뀌면 옛 판의 재사용 답변을 지운다 (DR-10, TC-35)."""
        r = self._do("DELETE", "/answer_cache", params={"version": "neq." + version, "select": "key_fp"},
                     headers={"Prefer": "return=representation"})
        return len(r.json())

    # ── 사용량 (F-18) ──
    def spent_today(self):
        rows = self._rows("usage", day="eq." + today(), select="rerank_cost,answer_cost", limit=1)
        return float(rows[0]["rerank_cost"] + rows[0]["answer_cost"]) if rows else 0.0

    def add_usage(self, rerank_cost=0.0, answer_cost=0.0, new_answer=False, evaluation=False):
        """평가 실행은 하루 전체 비용이 아니라 평가 실행 비용 칸에 따로 센다 (F-18 처리 6)."""
        if evaluation:
            self._rpc("add_usage", p_day=today(), p_rerank=0, p_answer=0, p_eval=rerank_cost + answer_cost, p_new=0)
        else:
            self._rpc("add_usage", p_day=today(), p_rerank=rerank_cost, p_answer=answer_cost, p_eval=0,
                      p_new=1 if new_answer else 0)

    def usage_rows(self):
        return self._all("usage", "day.asc")

    # ── 질의 기록 (F-19) ──
    def log_query(self, **row):
        back = self._insert("qa_log", [qa_row(row)], back=True)
        return back[0]["id"] if back else None

    def no_evidence_rows(self):
        """근거를 못 찾은 방문자 질의 가운데 낱말 지문이 남은 것 (F-20 처리 1)."""
        return self._all("qa_log", "id.asc", select="id,word_fps", no_evidence="is.true", evaluation="is.false",
                         word_fps="not.is.null")

    def clear_word_fps(self):
        self._do("PATCH", "/qa_log", params={"word_fps": "not.is.null", "evaluation": "is.false"},
                 json={"word_fps": None}, headers={"Prefer": "return=minimal"})

    def drop_old_word_fps(self, days=None):
        """질문 낱말 지문은 재조사가 쓰고 나면 지우고, 안 돌아도 14일이 지나면 지운다 (F-19 처리 4)."""
        days = cfg.WORD_FP_TTL_DAYS if days is None else days
        limit = (datetime.datetime.now(KST) - datetime.timedelta(days=days)).isoformat(timespec="seconds")
        self._do("PATCH", "/qa_log", params={"word_fps": "not.is.null", "at": "lt." + limit},
                 json={"word_fps": None}, headers={"Prefer": "return=minimal"})

    def qa_count(self):
        return len(self._all("qa_log", "id.asc", select="id"))

    def qa_rows(self):
        return self._all("qa_log", "id.asc")

    # ── 재조사 (F-20) ──
    def recheck_put(self, branch, row_name, qa_id=None):
        return bool(self._rpc("recheck_put", p_branch=branch, p_row_name=row_name, p_qa_id=qa_id))

    def recheck_rows(self):
        return self._all("recheck_queue", "id.asc")

    def weekly_stats(self):
        return self._rpc("weekly_stats") or {}

    # ── 기록 ──
    def log_export(self, version, documents, chunks):
        """반출 기록 (SR-18). 판을 쓴 시각과 수만 남긴다."""
        self._insert("export_log", [{"at": now(), "version": version, "documents": documents, "chunks": chunks}])

    def log_batch(self, line):
        self._insert("batch_log", [{"at": now(), "line": line}])

    def log_eval(self, line):
        self._insert("eval_log", [{"at": now(), "line": line}])

    # ── 문제집 ──
    def questions(self):
        return self._all("questions", "position.asc,id.asc")

    def replace_questions(self, items):
        """문제집을 통째로 바꾼다. items 는 [{id, question, rows, none}]."""
        self._do("DELETE", "/questions", params={"id": "not.is.null"}, headers={"Prefer": "return=minimal"})
        rows = [{"id": str(q["id"]), "position": i, "question": q["question"], "rows": q.get("rows") or [],
                 "none": bool(q.get("none"))} for i, q in enumerate(items, 1)]
        for i in range(0, len(rows), 200):
            self._insert("questions", rows[i:i + 200])

    # ── 찾아 둔 조직 표기 ──
    def names_state(self):
        """{document_id: {hash, names}}. 피해 조직 이름 그 자체다. 어디로도 내보내지 않는다."""
        return {r["document_id"]: {"hash": r["content_hash"], "names": r["names"] or []}
                for r in self._all("found_names", "document_id.asc", select="document_id,content_hash,names")}

    def put_names(self, items):
        rows = [{"document_id": k, "content_hash": v.get("hash"), "names": v.get("names") or [], "checked_at": now()}
                for k, v in items.items()]
        for i in range(0, len(rows), 200):
            self._insert("found_names", rows[i:i + 200], on_conflict="document_id")

    def delete_names(self, ids):
        for did in ids:
            self._do("DELETE", "/found_names", params={"document_id": "eq." + did}, headers={"Prefer": "return=minimal"})


class MemoryStore:
    """시험용. SupabaseStore 와 같은 일을 메모리에서 한다."""

    def __init__(self):
        self.answers, self.cache, self.qa, self.usage = {}, {}, [], {}
        self.recheck, self.exports, self.reviews, self.batches, self.evals = [], [], [], [], []
        self._questions, self.names = [], {}

    def close(self):
        pass

    @staticmethod
    def _copy(v):
        return json.loads(json.dumps(v, ensure_ascii=False))

    def prepared_row(self, key):
        r = self.answers.get(key)
        return self._copy(r) if r and r["reviewed"] else None

    def answer_row(self, key):
        r = self.answers.get(key)
        return self._copy(r) if r else None

    def answers_all(self):
        return self._copy(sorted(self.answers.values(), key=lambda r: (r["reviewed"], r["created_at"], r["question_key"])))

    def put_answer(self, key, question, answer, sources, model, doc_hashes):
        self.answers[key] = self._copy({"question_key": key, "question": question, "answer": answer, "sources": sources,
                                        "model": model, "created_at": now(), "reviewed": False, "doc_hashes": doc_hashes})

    def review_answer(self, key, who, passed=True):
        if passed:
            self.answers[key]["reviewed"] = True
        else:
            self.answers.pop(key, None)
        self.reviews.append({"at": now(), "who": who, "what": "사전 답변 검토 통과" if passed else "사전 답변 지움", "target": key})

    def cached_answer(self, version, key_fp):
        r = self.cache.get((version, key_fp))
        if not r:
            return None
        r["hits"] += 1
        return self._copy(r)

    def save_cache(self, version, key_fp, answer, sources, model):
        self.cache[(version, key_fp)] = self._copy({"version": version, "key_fp": key_fp, "answer": answer,
                                                    "sources": sources, "model": model, "created_at": now(), "hits": 0})

    def cache_count(self):
        return len(self.cache)

    def drop_old_cache(self, version):
        old = [k for k in self.cache if k[0] != version]
        for k in old:
            del self.cache[k]
        return len(old)

    def spent_today(self):
        u = self.usage.get(today())
        return float(u["rerank_cost"] + u["answer_cost"]) if u else 0.0

    def add_usage(self, rerank_cost=0.0, answer_cost=0.0, new_answer=False, evaluation=False):
        u = self.usage.setdefault(today(), {"day": today(), "new_answers": 0, "rerank_cost": 0.0, "answer_cost": 0.0,
                                            "eval_cost": 0.0})
        if evaluation:
            u["eval_cost"] += rerank_cost + answer_cost
        else:
            u["rerank_cost"] += rerank_cost
            u["answer_cost"] += answer_cost
            u["new_answers"] += 1 if new_answer else 0

    def usage_rows(self):
        return self._copy(list(self.usage.values()))

    def log_query(self, **row):
        r = qa_row(row)
        r["id"] = len(self.qa) + 1
        self.qa.append(self._copy(r))
        return r["id"]

    def no_evidence_rows(self):
        return [{"id": r["id"], "word_fps": r["word_fps"]} for r in self.qa
                if r["no_evidence"] and not r["evaluation"] and r["word_fps"] is not None]

    def clear_word_fps(self):
        for r in self.qa:
            if not r["evaluation"]:
                r["word_fps"] = None

    def drop_old_word_fps(self, days=None):
        pass

    def qa_count(self):
        return len(self.qa)

    def qa_rows(self):
        return self._copy(self.qa)

    def recheck_put(self, branch, row_name, qa_id=None):
        last = next((r for r in reversed(self.recheck) if r["branch"] == branch and r["row_name"] == row_name), None)
        if last and last["handled"] == 2:
            return False
        if last and last["handled"] == 0:
            if qa_id is not None:
                last["hits"] += 1
            return False
        self.recheck.append({"id": len(self.recheck) + 1, "qa_log_id": qa_id, "branch": branch, "row_name": row_name,
                             "hits": 1, "handled": 0, "created_at": now()})
        return True

    def recheck_rows(self):
        return self._copy(self.recheck)

    def weekly_stats(self):
        q = [r for r in self.qa if not r["used_prepared"] and not r["reused"] and not r["no_evidence"]]
        ms = [r["rerank_ms"] or 0 for r in q]
        items = {}
        for r in self.qa:
            for i in r["term_items"] or []:
                items[str(i)] = items.get(str(i), 0) + 1
        return {"n": len(q), "applied": sum(1 for r in q if r["rerank_applied"]),
                "ms_avg": sum(ms) / len(ms) if ms else 0, "ms_max": max(ms) if ms else None,
                "rerank_cost": sum(u["rerank_cost"] for u in self.usage.values()),
                "answer_cost": sum(u["answer_cost"] for u in self.usage.values()),
                "term_items": items, "queue": sum(1 for r in self.recheck if r["handled"] == 0)}

    def log_export(self, version, documents, chunks):
        self.exports.append({"at": now(), "version": version, "documents": documents, "chunks": chunks})

    def log_batch(self, line):
        self.batches.append(self._copy(line))

    def log_eval(self, line):
        self.evals.append(self._copy(line))

    def questions(self):
        return self._copy(self._questions)

    def replace_questions(self, items):
        self._questions = [{"id": str(q["id"]), "position": i, "question": q["question"], "rows": q.get("rows") or [],
                            "none": bool(q.get("none"))} for i, q in enumerate(items, 1)]

    def names_state(self):
        return self._copy(self.names)

    def put_names(self, items):
        self.names.update(self._copy(items))

    def delete_names(self, ids):
        for did in ids:
            self.names.pop(did, None)


_default = None


def connect():
    """기본 저장소. 한 프로세스에서 하나를 계속 쓴다."""
    global _default
    if _default is None:
        _default = SupabaseStore()
    return _default


def use(st):
    """기본 저장소를 바꿔 끼운다 (시험)."""
    global _default
    _default = st
    return st
