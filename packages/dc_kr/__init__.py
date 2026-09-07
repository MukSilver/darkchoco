"""dc_kr — 한국 관련인가를 가르는 판정기.

원본은 `apps/kr-leak-alarm/collector/` 에 있던 것입니다. 2026-09-07 에 공용으로
옮겼습니다. 코드는 그대로입니다.

옮긴 이유는 하나입니다. **같은 물음에 두 곳이 다른 답을 내면 안 됩니다.**
「이 유출이 한국과 관련 있나」 는 알림도 묻고 노션에 올릴 때도 묻고 통계도 묻습니다.
판정을 수집기마다 붙이면 규칙이 갈리고, 기업명 목록이 늘어날 때마다 여러 곳을
손으로 맞춰야 합니다. 이 저장소는 도구 사본이 갈려 스물넷 중 열셋이 서로 달랐던
일을 이미 겪었습니다.

축이 둘입니다. 서로 독립이고 같이 봅니다.

    KrClassifier       한국 기업이 직접 털렸나
    SupplyClassifier   한국 기업에 납품·연동하는 곳이 털렸나 (공급망)

둘 다 (등급, 점수, 근거 목록) 을 돌려줍니다. **근거를 버리지 마십시오.**
판정이 틀렸을 때 어느 신호에 걸렸는지가 남아야 되짚을 수 있습니다.

등급을 그대로 쓰지 말고 부르는 쪽이 문턱을 정합니다. 알림은 `likely` 위만 보내고,
노션에 올릴 때는 `review` 도 받습니다. 텔레그램·포럼 글은 피해자 칸이 비어 있어
아무리 잘 걸려도 `review` 가 천장이기 때문입니다.

`apps/kr-leak-alarm/collector/kr_filter.py` 와 `supply_filter.py` 는 이 모듈을
넘겨주는 전달 모듈로 남아 있습니다. 그쪽 `from .kr_filter import ...` 는 그대로 돕니다.
"""

from .kr_filter import TIER_ORDER as KR_TIER_ORDER
from .kr_filter import TIER_SCORE as KR_TIER_SCORE
from .kr_filter import KrClassifier
from .supply_filter import TIER_LABEL as SUPPLY_TIER_LABEL
from .supply_filter import TIER_ORDER as SUPPLY_TIER_ORDER
from .supply_filter import TIER_SCORE as SUPPLY_TIER_SCORE
from .supply_filter import SupplyClassifier, load_vendors

__all__ = [
    "KrClassifier",
    "KR_TIER_ORDER",
    "KR_TIER_SCORE",
    "SupplyClassifier",
    "SUPPLY_TIER_ORDER",
    "SUPPLY_TIER_SCORE",
    "SUPPLY_TIER_LABEL",
    "load_vendors",
]
