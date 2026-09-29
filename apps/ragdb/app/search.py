# -*- coding: utf-8 -*-
"""F-12 조각 검색 — 처리 1부터 7. 재순위(처리 8)는 rerank.py.

순서가 뜻이 있다 (명세 5.5). 반출 거르기가 가장 앞이다. 그래야 비반출 조각이 후보 자리를
차지하지 않고 바깥으로도 나가지 않는다. 넓히기가 후보를 만들고, 재순위는 그 후보 안에서만 다시 매긴다.
"""
import json
import os

import bm25s
import numpy as np

import tokenize_ko as T

from . import config as cfg
from . import expand, guard, kinds


def current_version():
    with open(cfg.CURRENT, encoding="utf-8") as f:
        return f.read().strip()


class Searcher:
    """판 하나를 읽어 쥔다. 질의는 시작할 때 고른 판을 끝까지 쓴다 (F-12 처리 1, TC-28)."""

    def __init__(self, version=None):
        self.version = version or current_version()
        d = os.path.join(cfg.INDEX_ROOT, self.version)
        self.bm25 = bm25s.BM25.load(d, load_corpus=False)
        with open(os.path.join(d, "ids.json"), encoding="utf-8") as f:
            self.ids = json.load(f)
        n = len(self.ids)
        self.visible = np.array([bool(x.get("visibility")) for x in self.ids], dtype=bool)
        self.offline = np.array([x.get("status") == "offline" for x in self.ids], dtype=bool)
        self.kind = np.array([x.get("kind") or "" for x in self.ids], dtype=object)
        self.terms = expand.load(d)          # 없거나 깨졌으면 None (TC-21)
        self.guard = guard.load(os.path.join(d, "guard.json"))
        assert n == len(self.visible)

    def _scores(self, tokens):
        """낱말 목록의 BM25 점수. 색인에 없는 낱말뿐이면 0."""
        if not tokens:
            return np.zeros(len(self.ids), dtype=np.float32)
        try:
            return np.asarray(self.bm25.get_scores(list(tokens)), dtype=np.float32)
        except (KeyError, ValueError, IndexError):
            return np.zeros(len(self.ids), dtype=np.float32)

    def search(self, question, m=None, weight=None, kind_boost=None, exported_only=True):
        """후보 M개와 그 내역을 돌려준다.

        돌려주는 것: {candidates, tokens, items, truncated, no_dictionary, kinds}
        candidates 하나는 조각 식별 칸에 score(합), bm25(원 질문), expand(넓힌 낱말, 무게 곱한 뒤),
        boost(종류 가산)가 붙은 것.
        """
        m = cfg.CANDIDATE_M if m is None else m
        weight = cfg.EXPANSION_WEIGHT if weight is None else weight
        kind_boost = cfg.KIND_BOOST if kind_boost is None else kind_boost

        tokens = T.tokens(question)
        base = self._scores(tokens)                                  # 처리 4: 소스 하나

        # 처리 2, 3, 5: 넓히기. 무게가 0 이면 꺼진 것과 같다
        items, truncated = [], False
        add = np.zeros_like(base)
        no_dictionary = self.terms is None
        if not no_dictionary and weight > 0:
            items, truncated = expand.match(self.terms, question)
            for it in items:
                best = np.zeros_like(base)
                for form in it["forms"]:
                    best = np.maximum(best, self._scores(T.tokens(form)))   # 항목마다 표기별 점수 가운데 가장 큰 것 하나
                add += best
            add *= weight

        total = base + add
        if exported_only:
            total = np.where(self.visible, total, 0.0)               # 처리 1, SR-01
        total = np.where(self.offline, total * cfg.OFFLINE_FACTOR, total)   # F-07 처리 1

        # 처리 6: 종류 가산. 점수가 있는 조각에만 더한다
        found = kinds.detect(tokens)
        boost = np.zeros_like(total)
        if found and kind_boost > 0 and total.max() > 0:
            hit = np.isin(self.kind, found) & (total > 0)
            boost = np.where(hit, kind_boost * float(total.max()), 0.0).astype(np.float32)
            total = total + boost

        # 처리 7: 후보 M개
        order = np.argsort(-total, kind="stable")[:m]
        out = []
        for i in order:
            if total[i] <= 0:
                break
            c = dict(self.ids[int(i)])
            c.update(score=float(total[i]), bm25=float(base[i]), expand=float(add[i]), boost=float(boost[i]))
            out.append(c)
        return {"candidates": out, "tokens": tokens, "items": items, "truncated": truncated,
                "no_dictionary": no_dictionary, "kinds": found}
