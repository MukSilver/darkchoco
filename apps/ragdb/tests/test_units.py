# -*- coding: utf-8 -*-
"""자료 없이 도는 시험 — 가리기, 정규화, 넓히기, 지킴이, 문장 나누기, 사람별 제한."""
from app import answer, expand, guard, limits, pii
from app.normalize import norm


# ── 개인정보 꼴 (SR-24, SR-04) ──
def test_pii_masks_six_shapes():
    cases = {
        "메일은 someone@example.org 입니다": "[이메일]",
        "연락처 010-1234-5678 로": "[전화번호]",
        "번호 900101-1234567 이 나왔다": "[주민등록번호]",
        "카드 1234-5678-9012-3456 결제": "[카드번호]",
        "입금 110-234-567890 으로": "[계좌번호]",
        "접속 주소 203.0.113.7 에서": "[IP]",
    }
    for text, label in cases.items():
        out, found = pii.mask(text)
        assert label in out and found == [label], text
        assert pii.has_pii(text) == label


def test_pii_leaves_dates_and_ids():
    for text in ["확인일 2026-09-08 기준", "판 20260930-023841 을 받았다", "LEAK-170 과 INC-242", "회원 1,234,567명", "버전 1.2.3"]:
        assert pii.mask(text) == (text, []), text
        assert pii.has_pii(text) is None


def test_business_number_is_masked():
    assert pii.has_pii("사업자등록번호 123-45-67890") == "[계좌번호]"


# ── 정규화 (F-02, TC-02) ──
def test_norm_keeps_similar_names_apart():
    assert norm("Breached.ST") == "breachedst"
    assert norm("breached.st") != norm("breached.su")
    assert norm(" Alpha-Forum (원본) ") == "alphaforum원본"
    assert norm(None) == ""


# ── 넓히기 (F-12 처리 2, 3) ──
def _items():
    items = [{"id": 1, "head": "AlphaForum", "forms": ["AlphaForum", "알파포럼", "AF"]},
             {"id": 2, "head": "BetaLock", "forms": ["BetaLock", "베타락"]}]
    for it in items:
        it["_forms"] = [(f, norm(f)) for f in it["forms"]]
    return items


def test_expand_matches_hangul_with_particle():
    hit, cut = expand.match(_items(), "알파포럼은 아직 살아있어?")
    assert [h["id"] for h in hit] == [1] and not cut
    assert hit[0]["forms"] == ["AlphaForum", "AF"]          # 질문에 이미 있는 표기는 넓힌 낱말이 아니다


def test_expand_latin_needs_word_boundary():
    assert expand.match(_items(), "AFK 상태인 포럼")[0] == []
    assert [h["id"] for h in expand.match(_items(), "AF 지금 상태")[0]] == [1]


def test_expand_caps_and_reports_truncation():
    hit, cut = expand.match(_items(), "알파포럼과 베타락", max_items=1, max_forms=1)
    assert len(hit) == 1 and len(hit[0]["forms"]) == 1 and cut


# ── 지킴이 (조직 이름과 주소) ──
def test_guard_masks_domains_but_keeps_place_names_and_files():
    g = guard.Guard(names=[], keep=["alphaforum.st"])
    out = g.clean("alphaforum.st 에 shop.ganadamall.example.kr 자료와 dump.sql 파일이 올라왔다")
    assert "alphaforum.st" in out and "dump.sql" in out
    assert "ganadamall" not in out and guard.ADDR_MASK in out
    assert g.leak(out) is None
    assert g.leak("문의는 victim-site.example.com 으로") == "도메인"


def test_guard_masks_names_korean_and_latin():
    g = guard.Guard(names=["가나다몰", "EXAMPLECO"], keep=["AlphaForum"])
    assert g.clean("가나다몰에서 나온 자료, exampleco 직원") == "%s에서 나온 자료, %s 직원" % (guard.NAME_MASK, guard.NAME_MASK)
    assert g.clean("EXAMPLECOMPANY 는 다른 곳") == "EXAMPLECOMPANY 는 다른 곳"
    assert g.leak("가나다몰 회원") == "조직 이름"


def test_guard_never_masks_places_and_platforms():
    g = guard.Guard(names=["AlphaForum", "Telegram", "가나다몰"], keep=["AlphaForum"])
    assert g.names == ["가나다몰"]
    assert g.clean("AlphaForum 과 Telegram 채널") == "AlphaForum 과 Telegram 채널"


def test_guard_merges_adjacent_marks():
    g = guard.Guard(names=["가나다몰", "가나다"])
    assert g.clean("가나다몰 (가나다)").count(guard.NAME_MASK) == 1


# ── 문장과 출처 (F-14) ──
def test_sentences_collect_sources_across_blocks():
    blocks = [{"text": "기록에 따르면 ", "cites": []},
              {"text": "포럼은 살아 있습니다", "cites": [{"n": 2}]},
              {"text": "(확인일 2026-09-01). 덧붙인 말입니다.", "cites": []}]
    s = answer.sentences(blocks)
    assert [x["sources"] for x in s] == [[2], []]
    assert s[0]["cited"] and not s[1]["cited"]


def test_date_tail_joins_previous_sentence():
    blocks = [{"text": "포럼은 살아 있습니다.", "cites": [{"n": 1}]}, {"text": " (확인일 2026-09-01)", "cites": []},
              {"text": " 다른 문장입니다.", "cites": []}]
    s = answer.sentences(blocks)
    assert [x["text"] for x in s] == ["포럼은 살아 있습니다. (확인일 2026-09-01)", "다른 문장입니다."]
    assert s[0]["cited"] and not s[1]["cited"]


def test_grounded_needs_citation_and_no_giving_up():
    assert not answer.grounded([{"text": "출처 없는 말", "cites": []}])
    assert answer.grounded([{"text": "근거 있는 말", "cites": [{"n": 1}]}])
    assert not answer.grounded([{"text": answer.NO_EVIDENCE + ". 그 문서는 다른 내용입니다", "cites": [{"n": 1}]}])


def test_document_text_keeps_body_offsets():
    c = {"body": "본문 첫 문장.", "observed_at": "2026-09-01"}
    t = answer.document_text(c)
    assert t.startswith(c["body"]) and t.endswith("확인일: 2026-09-01")


def test_document_text_puts_status_where_it_can_be_cited():
    # 설명 칸의 값은 인용할 수 없다. 상태는 본문 뒤에 붙이고, 본문에 이미 있으면 다시 붙이지 않는다
    c = {"body": "가상의 포럼 Alpha 소개.", "status": "online", "observed_at": "2026-09-01"}
    t = answer.document_text(c)
    assert t.startswith(c["body"]) and "상태: online\n확인일: 2026-09-01" in t
    c2 = {"body": "이름: Alpha\n상태: online", "status": "online", "observed_at": "2026-09-01"}
    assert answer.document_text(c2).count("상태: online") == 1
    doc = answer.documents([dict(c, visibility=1, kind="장소")])[0]
    assert "상태" not in doc["context"]


def test_documents_refuse_hidden_chunks():
    import pytest
    with pytest.raises(ValueError):
        answer.documents([{"body": "x", "visibility": 0}])


# ── 사람별 제한 (F-18 처리 3) ──
def test_limiter_off_by_default_values():
    lim = limits.Limiter(concurrent=0, per_minute=0, per_hour=0)
    assert all(lim.enter("a")[0] for _ in range(50))


def test_limiter_blocks_when_set():
    lim = limits.Limiter(concurrent=1, per_minute=5, per_hour=30)
    assert lim.enter("a")[0]
    assert not lim.enter("a")[0]                  # 동시에 둘
    lim.leave("a")
    for _ in range(4):
        assert lim.enter("a")[0]
        lim.leave("a")
    ok, wait = lim.enter("a")                     # 1분에 여섯 번째
    assert not ok and wait > 0
    assert lim.enter("b")[0]                      # 다른 사람은 따로 센다


def test_ip_hash_hides_ip():
    lim = limits.Limiter()
    h = lim.ip_hash("203.0.113.7")
    assert "203" not in h and len(h) == 64 and h == lim.ip_hash("203.0.113.7")


def test_latin_name_with_korean_particle_is_masked():
    """영문 이름 뒤에 조사가 바로 붙어도 가린다. 영문 낱말 안에 든 것은 가리지 않는다 (2026-09-30)."""
    from app import guard
    g = guard.Guard(names=["Acme Corp", "Zeta"])
    assert g.clean("Acme Corp은 검색되지 않음") == "(조직명 가림)은 검색되지 않음"
    assert g.clean("Zeta에서 나온 자료, Zeta의 회원") == "(조직명 가림)에서 나온 자료, (조직명 가림)의 회원"
    assert g.clean("Zetas 와 AZeta 는 다른 낱말") == "Zetas 와 AZeta 는 다른 낱말"
    assert g.leaks("Acme Corp은") == ["조직 이름"]


def test_heading_line_joins_next_sentence():
    """출처 없는 제목 줄은 다음 문장에 붙고, 굵은 글씨 표시는 떨어진다 (2026-09-30)."""
    from app import answer
    blocks = [{"text": "**INC-7 (의료 분야 유출 사고)**\n", "cites": []},
              {"text": "환자 정보 3만 건이 유출됐습니다.", "cites": [{"n": 1}]},
              {"text": "\n네, 더 있습니다.", "cites": []}]
    out = answer.sentences(blocks)
    assert out[0] == {"text": "INC-7 (의료 분야 유출 사고): 환자 정보 3만 건이 유출됐습니다.", "sources": [1], "cited": True}
    assert out[1]["text"] == "네, 더 있습니다." and not out[1]["cited"]              # 문장으로 끝나는 줄은 붙이지 않는다


def test_lead_in_without_source_is_dropped():
    from app import answer
    out = answer.sentences([{"text": "확인되는 그룹은 다음과 같습니다.\n", "cites": []},
                            {"text": "AlphaLock 은 한국 피해가 1건 있습니다.", "cites": [{"n": 1}]}])
    assert [s["text"] for s in out] == ["AlphaLock 은 한국 피해가 1건 있습니다."]


def test_other_lead_ins_are_dropped_too():
    # 「다음이 있습니다」, 「다음 인물들이 확인됩니다」, 쌍점으로 끝나는 줄. 제목 줄로 붙이지도 않는다
    from app import answer
    cited = {"text": "가상의 판매자 Beta 는 자료를 팝니다.", "cites": [{"n": 1}]}
    for lead in ("가상의 포럼으로는 다음이 있습니다.", "판매자로는 다음 인물들이 확인됩니다.", "찾은 자료:"):
        out = answer.sentences([{"text": lead + "\n", "cites": []}, cited])
        assert [s["text"] for s in out] == [cited["text"]], lead
    # 출처가 있으면 「다음」 이 들어가도 그대로 둔다
    out = answer.sentences([{"text": "Beta 는 다음 달에 문을 닫았다고 적혀 있습니다.", "cites": [{"n": 1}]}])
    assert len(out) == 1
