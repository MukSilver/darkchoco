"""안전 HTTP — packages/dc_safety 로 옮겼습니다.

이 파일의 원본이 dc_safety 가 되었습니다. 여기서는 이름만 넘겨줍니다.
기존 `from .http_client import SafeHttpClient` 같은 import 가
그대로 동작하므로 부르는 쪽은 고칠 것이 없습니다.

새 코드는 `from dc_safety import SafeHttpClient` 를 쓰십시오.
"""

from __future__ import annotations

from dc_safety.http import (  # noqa: F401,E402
    ALLOWED_CONTENT_TYPES,
    ALLOWED_HOSTS,
    BlockedHostError,
    FetchError,
    HttpStatusError,
    NotFoundError,
    SafeHttpClient,
    _check_host,
)
