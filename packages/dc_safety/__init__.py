"""dc_safety — 안전한 HTTP 와 텍스트 처리의 공용 부품.

kr-leak-alarm 의 것을 표준으로 올렸습니다.
새 출처를 붙일 때 ALLOWED_HOSTS 를 먼저 고쳐야 하는 구조라,
그 자체가 검토 지점이 됩니다.

이 패키지는 apps 를 import 하지 않습니다.
"""

from .http import (
    ALLOWED_CONTENT_TYPES, ALLOWED_HOSTS, BlockedHostError, FetchError,
    HttpStatusError, NotFoundError, SafeHttpClient,
)
from .text import defang_domain, defang_url, extract_domain, is_onion, sanitize_text

__all__ = [
    "SafeHttpClient", "ALLOWED_HOSTS", "ALLOWED_CONTENT_TYPES",
    "FetchError", "BlockedHostError", "HttpStatusError", "NotFoundError",
    "sanitize_text", "defang_url", "defang_domain", "is_onion", "extract_domain",
]
