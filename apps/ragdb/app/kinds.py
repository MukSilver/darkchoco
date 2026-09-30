# -*- coding: utf-8 -*-
"""종류 가산 — F-12 처리 6. 질문에서 종류를 알아내 그 종류의 조각에 점수를 더한다.

동의어 목록(kind_synonyms.json)은 사람이 고친다. 넓히기 사전과 다른 파일이고 색인 배치가 굽지 않는다.
다른 종류를 배제하지 않는다. 배제하면 포럼 글에 적힌 랜섬웨어 얘기를 놓친다.
"""
import json
import os

import tokenize_ko as T

from .normalize import norm

_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kind_synonyms.json")
_table = None


def table():
    """{종류: [낱말 묶음(정규화한 낱말의 튜플), ...]}"""
    global _table
    if _table is None:
        with open(_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        _table = {}
        for kind, words in raw.items():
            forms = []
            for w in words:
                toks = tuple(norm(t) for t in T.tokens(w) if norm(t))
                if toks:
                    forms.append(toks)
            _table[kind] = forms
    return _table


def detect(tokens):
    """질문을 쪼갠 낱말에서 맞은 종류 목록. 맞은 것이 없으면 빈 목록이고 가산을 걸지 않는다."""
    have = [norm(t) for t in tokens]
    hit = []
    for kind, forms in table().items():
        for f in forms:
            n = len(f)
            if any(tuple(have[i:i + n]) == f for i in range(len(have) - n + 1)):
                hit.append(kind)
                break
    return hit
