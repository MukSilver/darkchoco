"""kr_filter.py — 한국 관련 피해자 판별 엔진. 구현은 packages/dc_kr 로 옮겼습니다.

    from .kr_filter import TIER_SCORE, KrClassifier

부르는 쪽은 그대로입니다. 2026-09-07 에 노션에 올리는 쪽(hub/events/push.py)도
같은 판정을 써야 해서 공용으로 올렸고, 여기는 그것을 넘겨주기만 합니다.

옮긴 이유는 하나입니다. **같은 물음에 두 곳이 다른 답을 내면 안 됩니다.**
기업명·기관명 목록은 앞으로 계속 늘어나는데, 판정이 두 벌이면 늘릴 때마다
손으로 맞춰야 하고 언젠가 갈립니다. 키워드 파일도 부품 쪽으로 같이 갔습니다.

등급 뜻과 판정 차례는 packages/dc_kr/kr_filter.py 에 그대로 있습니다.
"""

from __future__ import annotations

import sys
from pathlib import Path

# 저장소 안에서 돌 때를 위한 자리입니다. `pip install -e packages` 를 했으면
# 이 줄은 하는 일이 없습니다.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "packages"))

from dc_kr.kr_filter import (  # noqa: E402,F401
    TIER_ORDER,
    TIER_SCORE,
    KrClassifier,
    _compile_boundary,
    _HANGUL_RE,
    _load_keywords,
    _max_tier,
)

__all__ = ["TIER_ORDER", "TIER_SCORE", "KrClassifier"]
