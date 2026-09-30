# -*- coding: utf-8 -*-
"""평가 질문 (설계서 「검증」) — 실제로 물어볼 만한 질문 모음. 사전 답변(F-17)과 평가가 같이 쓴다.

평가 질문은 사람이 만들고 고친다. 질의 때 시스템이 질문을 지어내지 않는다.
평가 질문은 운영 기록 저장소(Supabase 의 rag.questions)에 있다. 깃허브 저장소에는 넣지 않는다.
반출하지 않는 줄의 이름이 들어 있다. 고칠 때는 파일로 받아 고친 뒤 올린다 (scripts/question_set.py).

    {"questions": [
      {"id": "Q1", "question": "질문", "rows": ["답이 있는 노션 줄 이름", ...]},
      {"id": "Q2", "question": "자료에 없는 질문", "none": true},
      {"id": "Q3", "question": "첫 화면에 보일 질문", "rows": [...], "example": true}
    ]}

rows 는 노션 줄 이름(명칭)이나 사건 번호(LEAK-12, INC-3)다. 반출 대상이 아닌 줄도 적는다.
none 이 참이면 「답 없음」이 정답이다. example 이 참이면 첫 화면 예시 질문이 되고 사전 답변을 만든다.
"""
import json
import re

from . import store
from .normalize import norm


def clean(items):
    """평가 질문 항목을 다듬는다. 질문이 빈 것은 버린다."""
    out = []
    for i, q in enumerate(items or [], 1):
        text = (q.get("question") or "").strip()
        if not text:
            continue
        out.append({"id": str(q.get("id") or "Q%d" % i), "question": text,
                    "rows": [r for r in (q.get("rows") or []) if isinstance(r, str) and r.strip()],
                    "none": bool(q.get("none")), "example": bool(q.get("example"))})
    return out


def load(st=None):
    """평가 질문을 저장소에서 읽는다. 비어 있으면 빈 목록. 오류가 아니다 (F-17 예외)."""
    return clean((st or store.connect()).questions())


def from_file(path):
    """파일에 적은 평가 질문 (위 모양). 올리기 전에 읽는다."""
    with open(path, encoding="utf-8") as f:
        return clean(json.load(f).get("questions") or [])


def _keys(name):
    """줄 이름 하나가 가리킬 수 있는 키. 이름 통째, 괄호 설명을 뗀 이름, 사건 번호."""
    keys = {norm(name), norm(re.sub(r"\s*[(（].*$", "", name or ""))}
    m = re.search(r"\b(LEAK|INC)-?(\d+)\b", name or "", re.I)
    if m:
        keys.add("%s-%s" % (m.group(1).lower(), m.group(2)))
    return {k for k in keys if k}


def resolver(docs, live, excluded_rows=None):
    """줄 이름을 문서로 잇는 함수를 만든다.

    docs: 표준 문서 목록. live: 색인에 든 document_id 모음. excluded_rows: 빠진 줄 명부의 줄 목록.
    돌려주는 함수는 (반출되는 document_id 목록, 반출되지 않는 줄 수, 못 찾은 줄 수) 를 낸다.
    """
    shown, hidden = {}, set()
    for d in docs:
        names = [d.get("title")] + [a for a in (d.get("aliases") or []) if isinstance(a, str)]
        m = re.search(r"-(leak|inc)-(\d+)$", d["document_id"])
        keys = set()
        for n in names:
            keys |= _keys(n or "")
        if m and d["kind"] == "사고":
            keys.add("%s-%s" % (m.group(1), m.group(2)))
        for k in keys:
            if d["document_id"] in live:
                shown.setdefault(k, []).append(d["document_id"])
            else:
                hidden.add(k)          # 받았지만 빼 둔 문서 (가리기 검사에 걸린 것 등)
    for r in excluded_rows or []:
        for n in [r.get("name")] + list(r.get("aliases") or []):
            hidden |= _keys(n or "")

    def resolve(rows):
        found, off, lost = [], 0, 0
        for name in rows:
            ids = [i for k in _keys(name) for i in shown.get(k, [])]
            if ids:
                found.extend(i for i in ids if i not in found)
            elif _keys(name) & hidden:
                off += 1
            else:
                lost += 1
        return found, off, lost
    return resolve


def kind_of(q, resolve):
    """질문의 갈래. answerable: 반출 자료에 답이 있음 / hidden: 답이 있는 줄이 전부 반출 대상이 아님 /
    none: 답 없음이 정답 / unknown: 줄 이름을 하나도 못 이음"""
    if q["none"]:
        return "none", []
    found, off, lost = resolve(q["rows"])
    if found:
        return "answerable", found
    if off:
        return "hidden", []
    return "unknown", []
