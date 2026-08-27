"""dc_notion — 노션 API 공용 부품.

세 곳이 각자 래퍼를 갖고 있던 것을 HTTP 계층만 한 벌로 모은 것입니다.

  dls-observatory        재시도·지수 백오프·값 변환   → 여기로
  skills                 토큰 파일 탐색·읽기 도구      → 여기로
  tg-notion-report       안전 갱신 판정 로직            → 앱에 남김

앱마다 하는 일이 다르므로 판정·매칭 로직은 옮기지 않았습니다.
공통은 "노션에 요청을 보내고 답을 받는" 부분뿐입니다.

이 패키지는 apps 를 import 하지 않습니다.
"""

from .client import API, VERSION, Notion, NotionError
from .token import find_token, find_token_file
from .value import build_value, is_empty, plain_text, read_value

__all__ = [
    "API", "VERSION", "Notion", "NotionError",
    "find_token", "find_token_file",
    "plain_text", "read_value", "is_empty", "build_value",
]
