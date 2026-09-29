# -*- coding: utf-8 -*-
"""금지어 — 주소와 초대 링크 (명세 F-06 처리 1, SR-12).

표준 문서를 만들 때 가리는 일은 정제 배치(darkchoco-data, src/rag.mjs)가 한다(판 1.6, AD-21).
여기 같은 규칙을 두는 것은 build_index.py 가 반출 직전에 한 번 더 훑기 위해서다(TC-06).
두 곳의 규칙이 어긋나면 이 파일이 더 엄격해야 한다.
"""
import re

ADDRESS_PATTERNS = [
    re.compile(r"(?:https?|hxxps?|ftp)://\S+", re.I),                      # 링크
    re.compile(r"\bt\.me/\S+", re.I),                                      # 텔레그램 채널·초대 링크
    re.compile(r"\b[a-z2-7]{56}\b(?:\s*[.\[\]]*\s*onio\W?n\b)?", re.I),   # v3 어니언 (「onio@n」 꼴 포함)
    re.compile(r"\b[a-z0-9.-]+\.onion\b", re.I),                           # v2 어니언과 하위 도메인
]
MASK = "(주소 가림)"


def mask_addresses(s):
    """글 안의 주소와 링크를 「(주소 가림)」으로 바꾼다. 문자열이 아니면 그대로."""
    if not isinstance(s, str):
        return s
    for p in ADDRESS_PATTERNS:
        s = p.sub(MASK, s)
    return re.sub(r"(?:%s[\s,·/]*){2,}" % re.escape(MASK), MASK + " ", s).strip()
