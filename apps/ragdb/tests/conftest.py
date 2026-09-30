# -*- coding: utf-8 -*-
"""시험이 같이 쓰는 것. 자료는 전부 지어낸 것이다. 실제 조사 기록과 실제 조직 이름을 넣지 않는다.

바깥 호출(모델, 재순위, 운영 기록 저장소)은 하지 않는다. 가짜를 끼운다. 그래서 시험은 0원이고 열쇠가 없어도 돈다.
"""
import json
import os
import sys
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "scripts")):
    if p not in sys.path:
        sys.path.insert(0, p)


def doc(document_id, kind, title, summary=None, metadata=None, sections=None, aliases=None, visibility=True, h="h1"):
    return {"document_id": document_id, "kind": kind, "title": title, "summary": summary, "visibility": visibility,
            "sections": [{"heading": s[0], "body": s[1], "visibility": True, "images": []} for s in sections or []],
            "metadata": metadata or {}, "aliases": aliases or [], "source": "page-" + document_id,
            "revision": {"notion_edited": "2026-09-01T00:00:00.000Z", "form_version": 1, "content_hash": h}}


DOCS = [
    doc("포럼-alphaforum", "포럼", "AlphaForum", "유출 자료가 올라오는 포럼",
        {"상태": "online", "확인일": "2026-09-01", "사용 언어": "영어", "어떤 곳인지": "유출 자료 게시판이 있는 곳"},
        [("지금 상태", "AlphaForum 은 2026년 9월에 접속이 확인됐다. 회원 가입 없이 게시판 목록을 볼 수 있다."),
         ("사라진 뒤", "예전 운영진이 떠난 뒤 새 운영진이 같은 이름으로 다시 열었다는 글이 올라와 있다.")],
        aliases=["알파포럼", "AF"]),
    doc("포럼-alphaforum-st", "포럼", "alphaforum.st", "AlphaForum 을 본뜬 곳",
        {"상태": "offline", "확인일": "2026-06-01", "어떤 곳인지": "이름이 비슷한 다른 포럼"},
        [("지금 상태", "alphaforum.st 는 2026년 6월에 접속되지 않았다. 운영진이 누구인지는 확인되지 않았다.")]),
    doc("랜섬웨어-betalock", "랜섬웨어", "BetaLock", "유출 사이트를 운영하는 랜섬웨어 그룹",
        {"상태": "online", "확인일": "2026-08-20", "연락수단": "betalock@example.org"},
        [("활동", "BetaLock 은 유출 사이트에 피해 조직 목록을 올린다. 가나다몰 자료를 올렸다고 주장했다.")]),
    doc("사고-leak-1", "사고", "유통 분야 유출 사고, 2026년 5월 (LEAK-1)", None,
        {"사건 ID": "LEAK-1", "산업 분야": "유통·이커머스", "상태": "검증 완료", "수집일": "2026-05-10",
         "한국 관련 근거": "가나다몰 회원 자료라고 적혀 있고 shop.ganadamall.example.kr 주소가 보인다", "UID": "x-1"},
        [("관측", "판매 글에는 회원 이름과 전화번호 항목이 있다고 적혀 있다. 표본은 공개되지 않았다.")]),
    doc("사고-leak-2", "사고", "교육 분야 유출 사고, 2026년 6월 (LEAK-2)", None,
        {"사건 ID": "LEAK-2", "산업 분야": "교육", "수집일": "2026-06-02", "메모": "작성 주소는 203.0.113.7 로 보인다"},
        [("관측", "게시판 자료로 보인다는 글이 올라왔다. 자세한 항목은 확인되지 않았다.")]),
    doc("행위자-seller1", "행위자", "seller1", None, {"역할": "판매자", "확인일": "2026-07-01"},
        [("활동", "seller1 은 AlphaForum 에서 유통 분야 자료를 판다고 글을 올렸다.")], aliases=["shadowpig77"]),
    doc("용어-콤보리스트", "용어", "콤보리스트", "아이디와 비밀번호 짝을 모은 목록", {"갈래": "자료"}, aliases=["combo list", "콤보"]),
    doc("포럼-hidden", "포럼", "HiddenPlace", "반출하지 않는 곳", {"상태": "online"},
        [("지금 상태", "HiddenPlace 는 반출 대상이 아닌 곳이다. AlphaForum 과 이름이 같이 나온다.")], visibility=False),
]

NAMES = {"사고-leak-1": ["가나다몰", "shop.ganadamall.example.kr"], "랜섬웨어-betalock": ["가나다몰"]}


@pytest.fixture()
def world(tmp_path, monkeypatch):
    """지어낸 표준 문서로 조각, 색인, 넓히기 사전까지 만든 작은 세상."""
    import build_index
    import chunk as C
    from app import config as cfg
    from app import store

    data = tmp_path / "data"
    std = data / "standard"
    std.mkdir(parents=True)
    for d in DOCS:
        (std / (d["document_id"] + ".json")).write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    names = {"docs": {d["document_id"]: {"hash": d["revision"]["content_hash"], "names": NAMES.get(d["document_id"], [])}
                      for d in DOCS if d["kind"] != "용어"}}
    (data / "names.json").write_text(json.dumps(names, ensure_ascii=False), encoding="utf-8")

    for k, v in {"DATA_DIR": str(data), "STAGING_DIR": str(data / "staging"), "INDEX_ROOT": str(data / "bm25_index"),
                 "SNAPSHOT_ROOT": str(data / "snapshot"), "CURRENT": str(data / "current.txt"),
                 "FINGERPRINT_KEY": "test-key", "EXPANSION_WEIGHT": 0.3,
                 "RERANK_ENABLED": True, "COHERE_API_KEY": "", "DAILY_BUDGET_USD": 3.0, "STALE_DAYS": 90}.items():
        monkeypatch.setattr(cfg, k, v)
    monkeypatch.setattr(C, "STD_DIR", str(std))
    monkeypatch.setattr(C, "STAGING", str(data / "staging"))
    monkeypatch.setattr(store, "_default", store.MemoryStore())          # 운영 기록은 메모리에. Supabase 를 부르지 않는다
    monkeypatch.setattr(C, "NAMES_FILE", str(data / "names.json"))
    monkeypatch.setattr(C, "REQUIRE_NAME_CHECK", True)
    monkeypatch.setattr(build_index, "STD_DIR", str(std))
    monkeypatch.setattr(build_index, "INDEX_ROOT", str(data / "bm25_index"))
    monkeypatch.setattr(build_index, "CURRENT", str(data / "current.txt"))

    stats = C.run(quiet=True)
    built = build_index.build(version="20260101-000000")
    return types.SimpleNamespace(data=data, std=std, stats=stats, built=built, version="20260101-000000")


# ── 가짜 모델 ──
class _Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class FakeStream:
    """anthropic 의 messages.stream() 흉내. blocks 는 [(글, [문서 번호(0부터)])] 의 목록."""

    def __init__(self, blocks, stop_reason="end_turn"):
        self.blocks, self.stop_reason, self.request = blocks, stop_reason, None

    def __call__(self, **request):
        self.request = request
        return self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __iter__(self):
        for text, _ in self.blocks:
            for i in range(0, len(text), 7):
                yield _Obj(type="content_block_delta", delta=_Obj(type="text_delta", text=text[i:i + 7]))

    def get_final_message(self):
        content = [_Obj(type="text", text=t, citations=[
            _Obj(type="char_location", document_index=i, cited_text="", start_char_index=0, end_char_index=1)
            for i in idx] or None) for t, idx in self.blocks]
        usage = _Obj(input_tokens=1000, output_tokens=100, cache_creation_input_tokens=0, cache_read_input_tokens=0)
        return _Obj(content=content, usage=usage, stop_reason=self.stop_reason, model="fake-model")


@pytest.fixture()
def fake_stream():
    return FakeStream
