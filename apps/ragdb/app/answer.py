# -*- coding: utf-8 -*-
"""F-13 답변 생성, F-14 출처 부여.

조각 하나를 문서 하나로 모델에 준다. 인용(Citations)을 켜고 구조화 출력은 켜지 않는다 (함께 못 켠다, 명세 2.3).
바깥으로 나가는 것은 질문(개인정보 꼴을 가린 뒤)과 반출 판정을 통과한 조각뿐이다 (SR-19).
"""
import os
import re

from . import config as cfg

NO_EVIDENCE = "확인 가능한 근거를 찾지 못했습니다"

_PROMPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts", "system.md")
_system = None
_client = None


class AnswerError(Exception):
    """모델 호출 실패. 「근거 없음」 과 다른 것이다 (F-13 예외). 글에 질문이나 자료를 싣지 않는다."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def system_prompt():
    """지시문 7개 (명세 4.6). 고치면 평가를 다시 돌린다 (7.2)."""
    global _system
    if _system is None:
        with open(_PROMPT, encoding="utf-8") as f:
            _system = f.read().strip()
    return _system


def client():
    global _client
    if _client is None:
        import anthropic
        _client = anthropic.Anthropic(api_key=cfg.ANTHROPIC_API_KEY)
    return _client


def document_text(chunk):
    """모델에 주는 문서 글. 조각 본문 뒤에 확인일 줄을 붙인다 (지시문 5).

    확인일을 설명(context)에 두면 인용할 수 없어 출처 없는 문장이 생긴다. 본문 뒤에 붙이므로
    본문 안의 인용 위치(글자 번호)는 조각 본문과 그대로 맞는다.
    """
    body = (chunk.get("body") or "").strip() or "(본문 없음)"
    return "%s\n\n확인일: %s" % (body, chunk.get("observed_at") or "없음")


def documents(chunks):
    """조각 목록 → 문서 블록 목록. 순서가 출처 번호다 (document_index + 1)."""
    out = []
    for c in chunks:
        if not c.get("visibility"):
            raise ValueError("비반출 조각이 모델로 가려 했다 (SR-19)")
        context = ["종류: %s" % (c.get("kind") or "")]
        if c.get("status"):
            context.append("상태: %s" % c["status"])
        out.append({
            "type": "document",
            "source": {"type": "text", "media_type": "text/plain", "data": document_text(c)},
            "title": ("%s / %s" % (c.get("title") or "", c.get("section") or ""))[:200],
            "context": "\n".join(context),
            "citations": {"enabled": True},
        })
    return out


def estimate_cost(question, chunks):
    """부르기 전에 보는 이번 호출의 최대 비용 (F-18 처리 4). 글자 하나를 토큰 1.2개로 넉넉히 센다."""
    chars = len(system_prompt()) + len(question) + sum(len(c.get("body") or "") + 200 for c in chunks)
    return (chars * 1.2 * cfg.PRICE_INPUT + cfg.ANSWER_MAX_TOKENS * cfg.PRICE_OUTPUT) / 1e6


def cost_of(usage):
    """실제 토큰 수로 센 비용 (F-18 처리 5)."""
    g = lambda k: getattr(usage, k, 0) or 0
    return (g("input_tokens") * cfg.PRICE_INPUT + g("cache_creation_input_tokens") * cfg.PRICE_CACHE_WRITE
            + g("cache_read_input_tokens") * cfg.PRICE_CACHE_READ + g("output_tokens") * cfg.PRICE_OUTPUT) / 1e6


def request(question, chunks):
    """모델에 보낼 요청. 즉석 질의와 사전 답변 만들기(F-17)가 같은 요청을 쓴다."""
    req = dict(
        model=cfg.ANSWER_MODEL,
        max_tokens=cfg.ANSWER_MAX_TOKENS,
        system=[{"type": "text", "text": system_prompt(), "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": documents(chunks) + [{"type": "text", "text": question}]}],
    )
    # 생각하기는 끈다 (F-13 처리 4). 모델을 바꾸면 이 값이 거절될 수 있다. 그때는 ANSWER_THINKING 을 바꾼다
    mode = (os.getenv("ANSWER_THINKING") or "disabled").strip()
    if mode != "omit":
        req["thinking"] = {"type": mode}
    return req


def generate(question, chunks, stream_factory=None):
    """모델을 불러 답을 만든다. 글자를 오는 대로 내고 (F-13 처리 5) 마지막에 결과를 낸다.

    내는 것: ("text", 글자 토막) 여러 번, 끝에 ("result", {blocks, usage, cost, stop_reason, model}) 한 번.
    blocks 하나는 {text, cites}. cites 하나는 {n(출처 번호), cited_text, start, end}.
    stream_factory 는 시험에서 바깥 호출을 바꿔 끼우는 자리다.
    """
    import anthropic

    req = request(question, chunks)
    open_stream = stream_factory or (lambda **kw: client().messages.stream(**kw))
    try:
        with open_stream(**req) as stream:
            for event in stream:
                if getattr(event, "type", None) != "content_block_delta":
                    continue
                d = event.delta
                if getattr(d, "type", None) == "text_delta" and d.text:
                    yield "text", d.text
            msg = stream.get_final_message()
    except anthropic.RateLimitError:
        raise AnswerError("upstream")
    except anthropic.APIStatusError:
        raise AnswerError("upstream")
    except anthropic.APIConnectionError:
        raise AnswerError("upstream")

    if msg.stop_reason == "refusal":
        raise AnswerError("refused")
    yield "result", result_of(msg, len(chunks))


def result_of(msg, n_chunks, discount=1.0):
    """모델이 돌려준 메시지에서 글과 출처를 꺼낸다. discount 는 배치 호출의 할인 (0.5)."""
    blocks = []
    for b in msg.content:
        if getattr(b, "type", None) != "text":
            continue
        cites = []
        for c in getattr(b, "citations", None) or []:
            i = getattr(c, "document_index", None)
            if i is None or not (0 <= i < n_chunks):
                continue
            cites.append({"n": i + 1, "cited_text": getattr(c, "cited_text", "") or "",
                          "start": getattr(c, "start_char_index", None), "end": getattr(c, "end_char_index", None)})
        blocks.append({"text": b.text, "cites": cites})
    return {"blocks": blocks, "usage": msg.usage, "cost": cost_of(msg.usage) * discount,
            "stop_reason": msg.stop_reason, "model": msg.model}


_END = re.compile(r"(?<=[.!?。])\s+|\n+")
_TAIL = re.compile(r"^(\([^()]{1,40}\)[.]?)(?:\s+(.*))?$", re.S)


def last_sentence_end(text):
    """글에서 마지막으로 문장이 끝난 자리. 끝난 문장이 없으면 0."""
    end = 0
    for m in _END.finditer(text):
        end = m.end()
    return end


def sentences(blocks):
    """블록 묶음을 문장으로 다시 나눈다 (F-14 처리 1, 3).

    모델은 인용이 붙는 주장과 그 사이를 잇는 말을 다른 블록으로 나눠 준다. 문장 하나가 여러 블록에
    걸치므로, 문장이 차지한 글자 구간에 든 블록의 출처를 모아 그 문장의 출처로 삼는다.
    돌려주는 것: [{text, sources(출처 번호 목록), cited(출처가 있는지)}]
    """
    text, spans, pos = "", [], 0
    for b in blocks:
        t = b["text"] or ""
        spans.append((pos, pos + len(t), b["cites"]))
        text += t
        pos += len(t)

    out, start = [], 0
    cuts = [m.end() for m in _END.finditer(text)] + [len(text)]
    for end in cuts:
        piece = text[start:end]
        if piece.strip():
            ns = sorted({c["n"] for s, e, cites in spans if cites and s < end and e > start for c in cites})
            p = piece.strip()
            m = _TAIL.match(p) if out else None
            if m:
                # 마침표 뒤에 붙은 「(확인일 2026-08-01)」 은 앞 문장의 꼬리다. 따로 세면 출처 없는 문장이 된다
                out[-1]["text"] += " " + m.group(1)
                p = (m.group(2) or "").strip()
                if not p:
                    out[-1]["sources"] = sorted(set(out[-1]["sources"]) | set(ns))
                    out[-1]["cited"] = bool(out[-1]["sources"])
            if p:
                out.append({"text": p, "sources": ns, "cited": bool(ns)})
        start = end
    return out


def grounded(blocks):
    """근거가 있는 답인가. 아니면 근거 없음으로 돌린다 (F-15, TC-11, TC-12).

    출처가 하나도 안 붙었거나, 모델이 스스로 근거를 못 찾았다고 적었으면 근거가 없는 것이다.
    뒤쪽은 출처가 붙어 있어도 그렇게 본다. 「그 문서에는 답이 없다」 는 말에 붙은 출처는 근거가 아니다.
    """
    text = "".join(b["text"] or "" for b in blocks)
    if NO_EVIDENCE in text:
        return False
    return any(b["cites"] for b in blocks)
