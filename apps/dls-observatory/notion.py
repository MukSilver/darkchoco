"""노션 래퍼 — packages/dc_notion 으로 옮겼습니다.

이 파일이 dc_notion 의 원본이 되었습니다. 여기서는 이름만 넘겨줍니다.
기존 `import notion as nt` · `nt.Notion(...)` · `nt.read_value(...)` 가
그대로 동작하므로 부르는 쪽은 고칠 것이 없습니다.

새 코드는 `from dc_notion import Notion` 을 쓰십시오.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages"))

from dc_notion.client import (  # noqa: F401,E402
    API,
    VERSION,
    Notion,
    NotionError,
)
from dc_notion.value import (  # noqa: F401,E402
    build_value,
    is_empty,
    plain_text,
    read_value,
)

# 예전 이름 유지 — 내부에서 _plain 을 쓰던 곳이 있으면 계속 돕니다.
_plain = plain_text
