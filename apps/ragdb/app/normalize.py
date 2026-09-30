# -*- coding: utf-8 -*-
"""이름 정규화 — F-02 중복 검출, F-12 질문 넓히기, F-20 재조사 대조가 같이 쓴다 (TC-02).

한 곳만 바꾸면 사람은 중복 경고를 받는데 검색은 두 이름을 잇지 못한다.
"""
import re
import unicodedata

_DROP = re.compile(r"[^0-9a-z가-힣ぁ-んァ-ヶ一-龥а-яё]+")


def norm(s):
    """소문자로 바꾸고 기호와 빈칸을 뗀다. breached.st 와 breached.su 는 끝 글자가 달라 그대로 갈린다."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", str(s)).lower()
    return _DROP.sub("", s)


def has_hangul(s):
    return bool(re.search(r"[가-힣]", s or ""))
