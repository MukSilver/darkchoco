"""supply_filter.py — 공급망 축 판별. 구현은 packages/dc_kr 로 옮겼습니다.

    from .supply_filter import TIER_SCORE, SupplyClassifier, load_vendors

부르는 쪽은 그대로입니다. kr_filter 와 같은 이유로 2026-09-07 에 공용으로
올렸습니다. 둘은 **독립된 두 축**이고 같이 봐야 해서 한 부품에 있습니다.

`load_vendors(root)` 가 읽는 `vendors.json` 은 사용자 소유 목록이라 부품으로
안 갔습니다. 부르는 쪽이 자기 폴더를 넘깁니다.

등급 뜻과 판정 차례는 packages/dc_kr/supply_filter.py 에 그대로 있습니다.
"""

from __future__ import annotations

import sys
from pathlib import Path

# 저장소 안에서 돌 때를 위한 자리입니다. `pip install -e packages` 를 했으면
# 이 줄은 하는 일이 없습니다.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "packages"))

from dc_kr.supply_filter import (  # noqa: E402,F401
    TIER_LABEL,
    TIER_ORDER,
    TIER_SCORE,
    SupplyClassifier,
    _category_ko,
    _compile_terms,
    _load_dataset,
    load_vendors,
)

__all__ = ["TIER_ORDER", "TIER_SCORE", "TIER_LABEL", "SupplyClassifier", "load_vendors"]
