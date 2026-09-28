"""kr-leak-alarm — 랜섬웨어 DLS 한국 기업 피해 모니터링 수집기.

공용 부품(packages/dc_*)을 쓰기 위해 경로를 한 번 잡아 둡니다.
이 패키지 아래 어느 모듈이든 dc_safety · dc_ransomfeed 를 import 할 수 있습니다.
"""

# 통합하면서 위 경로 설정 docstring 이 앞에 붙는 바람에, 원본 모듈 설명
# ("Kr-Leak-alarm — 랜섬웨어 DLS ... 수집기.")이 두 번째 문자열이 되어
# 아무도 읽지 않는 죽은 식으로 남아 있었다. 설명을 docstring 첫 줄에 합치고
# 죽은 줄은 지운다. __doc__ 을 읽는 곳은 없어 동작은 그대로다.

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "packages"))

__version__ = "1.0.0"
