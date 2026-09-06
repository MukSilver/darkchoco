"""수집 표. 구현은 packages/dc_store 로 옮겼습니다.

    from collect.store import Store, Item

부르는 쪽은 그대로입니다. 통합 수집기가 같은 표를 써야 해서 공용으로
올렸고, 여기는 그것을 넘겨주기만 합니다.

옮긴 이유는 하나입니다. 표를 두 벌 두면 같은 글이 두 곳에 서로 다른
모양으로 쌓입니다. 열쇠(KEY)와 그 주석에 담긴 판단도 한 곳에만 있어야
합니다.
"""

from __future__ import annotations

import sys
from pathlib import Path

# 저장소 안에서 돌 때를 위한 자리입니다. `pip install -e packages` 를 했으면
# 이 줄은 하는 일이 없습니다.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages"))

# SCHEMA 도 넘겨줍니다. collect/track.py 와 시험 파일이 표를 만들 때 씁니다 (2026-09-06).
from dc_store import KEY, SCHEMA, Item, Store  # noqa: E402,F401

__all__ = ["Item", "Store", "KEY", "SCHEMA"]
