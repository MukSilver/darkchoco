"""dc_safety — 안전한 HTTP 와 텍스트 처리의 공용 부품.

kr-leak-alarm 의 것을 표준으로 올렸습니다.
새 출처를 붙일 때 ALLOWED_HOSTS 를 먼저 고쳐야 하는 구조라,
그 자체가 검토 지점이 됩니다.

이 패키지는 apps 를 import 하지 않습니다.
"""

# http 는 requests 를 씁니다. 살균 함수(text)만 쓰는 곳까지 requests 를
# 받게 하지 않으려고 늦게 부릅니다.
_HTTP = ['ALLOWED_CONTENT_TYPES', 'ALLOWED_HOSTS', 'BlockedHostError', 'FetchError', 'HttpStatusError', 'NotFoundError', 'SafeHttpClient', 'check_host']


def __getattr__(name):
    if name in _HTTP:
        from . import http
        return getattr(http, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
from .text import defang_domain, defang_url, extract_domain, is_onion, sanitize_text

__all__ = [
    "check_host",
    "SafeHttpClient", "ALLOWED_HOSTS", "ALLOWED_CONTENT_TYPES",
    "FetchError", "BlockedHostError", "HttpStatusError", "NotFoundError",
    "sanitize_text", "defang_url", "defang_domain", "is_onion", "extract_domain",
]
