"""dc_ransomfeed — 랜섬웨어 피드 출처의 공용 부품.

두 앱이 같은 API 를 각자 긁고 있던 것을 정리했습니다.

무엇을 합쳤나 — 주소와 가져오는 계층뿐입니다.

  · 엔드포인트 주소 (endpoints.py)
  · 속도 제한을 지키는 fetcher (fetch.py)

무엇을 안 합쳤나 — 받은 것을 어떻게 해석하는지는 앱마다 다릅니다.

  dls-observatory  사이트 정보를 봅니다 (살아 있나·주소가 뭔가)
  kr-leak-alarm    피해 건을 봅니다 (누가 당했나·한국인가)

같은 API 를 부르지만 보는 대상이 달라서, 모델을 하나로 합치면
둘 다 망가집니다. 그래서 가져오는 곳까지만 공유합니다.

이 패키지는 apps 를 import 하지 않습니다.
"""

from .endpoints import (
    RANSOMFEED_RSS, RANSOMLOOK, RANSOMWARE_LIVE,
    look_detail, look_list, rl_country_victims, rl_groups, rl_recent_victims, rl_victims,
)

# Fetcher 는 requests 를 씁니다. 주소 상수만 쓰는 앱까지 requests 를 받게
# 하지 않으려고 늦게 부릅니다. dls-observatory 가 표준 라이브러리만 쓰는
# 앱인데 여기서 requests 가 딸려 오던 것을 고친 것입니다.
def __getattr__(name):
    if name == "Fetcher":
        from .fetch import Fetcher
        return Fetcher
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "RANSOMWARE_LIVE", "RANSOMLOOK", "RANSOMFEED_RSS",
    "rl_groups", "rl_country_victims", "rl_recent_victims", "rl_victims",
    "look_list", "look_detail",
    "Fetcher",
]
