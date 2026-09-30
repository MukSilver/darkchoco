# -*- coding: utf-8 -*-
"""질문 넓히기 — F-12 처리 2, 3. 넓히기 사전(terms.json)에서 질문에 나온 표기를 찾는다.

넓힌 낱말은 바깥 사업자에게 보내지 않는다 (SR-19). 여기서 나온 표기는 BM25 점수에만 쓰인다.
사전의 뜻 칸은 읽지 않는다. 사전이 없거나 깨졌으면 넓히기를 건너뛰고 원 질문 낱말만으로 계속한다 (TC-21).
"""
import json
import os
import re

from . import config as cfg
from .normalize import has_hangul, norm


def load(version_dir):
    """사전을 읽는다. 없거나 깨졌으면 None."""
    p = os.path.join(version_dir, "terms.json")
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        items = data["items"]
        for it in items:
            it["_forms"] = [(form, norm(form)) for form in it["forms"] if norm(form)]
        return items
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _in_question(form, key, question_lower, question_key):
    """표기가 질문 안에 나오는가.

    한글이 든 표기는 조사가 바로 붙으므로 빈칸을 뗀 글에서 찾는다 (두 글자 이상).
    영문과 숫자뿐인 표기는 낱말 경계를 본다. 경계를 안 보면 「bf」 가 「bfd」 에 걸린다.
    """
    if has_hangul(form):
        return len(key) >= 2 and key in question_key
    if len(key) < 2:
        return False
    return re.search(r"(?<![0-9a-z])%s(?![0-9a-z])" % re.escape(form.lower().strip()), question_lower) is not None


def match(items, question, max_items=None, max_forms=None):
    """(맞은 항목 목록, 잘렸는지).

    맞은 항목 하나는 {id, head, forms(넓힌 표기)}. 원 질문에 이미 있는 표기는 넓힌 낱말로 삼지 않는다.
    """
    max_items = cfg.EXPANSION_MAX_ITEMS if max_items is None else max_items
    max_forms = cfg.EXPANSION_MAX_FORMS if max_forms is None else max_forms
    ql = (question or "").lower()
    qk = norm(question)
    hit, cut = [], False
    for it in items or []:
        if not any(_in_question(form, key, ql, qk) for form, key in it["_forms"]):
            continue
        rest = [form for form, key in it["_forms"] if not _in_question(form, key, ql, qk)]
        if not rest:
            continue
        if len(rest) > max_forms:
            rest, cut = rest[:max_forms], True
        hit.append({"id": it["id"], "head": it["head"], "forms": rest})
    if len(hit) > max_items:
        hit, cut = hit[:max_items], True
    return hit, cut
