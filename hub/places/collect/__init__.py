"""수집기. 한 곳을 깊게 봅니다.

`apps/forum-crawler` 의 수집기 일곱을 그대로 가져왔습니다. 겪어서 얻은
것이 들어 있어 새로 짜지 않았습니다. 이름만 짧게 했습니다.

    availability  (1) 사이트 상태
    structure     (2) 구조 · 운영 방식
    stats         (3) 활성화 정도
    content       (4) 게시글 표본 — 603줄. 제일 큽니다
    crossref      (5) 사이트 간 연결
    access        (6) 가입 조건
    activity      (7) 유저 활동

**대부분이 Playwright page 를 받습니다.** 브라우저로 안 열었으면 그
수집기는 못 돕니다. 조용히 빠뜨리지 않고 왜 못 했는지 적습니다.
"""

from __future__ import annotations

__all__ = ["차례", "필요한것", "page가필요한가"]

# 부르는 차례입니다. forum-crawler 의 investigate.py 가 쓰던 순서
# 그대로입니다. 앞엣것이 뒤엣것의 입력을 만듭니다 — 구조를 알아야
# 게시판을 고르고, 게시글을 읽어야 활동을 셉니다.
차례 = ("availability", "structure", "stats", "content",
       "crossref", "access", "activity")

# 무엇을 받아야 도는가. page 가 없으면 못 도는 것이 다섯입니다.
필요한것 = {
    "availability": "page",
    "structure": "page",
    "stats": "page",
    "content": "page",
    "crossref": "본문",      # 글자만 있으면 됩니다
    "access": "page",
    "activity": "게시글",    # content 가 만든 것을 받습니다
}


def page가필요한가(이름: str) -> bool:
    return 필요한것.get(이름) == "page"
