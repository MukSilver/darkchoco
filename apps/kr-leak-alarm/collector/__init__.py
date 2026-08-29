"""kr-leak-alarm 수집기.

공용 부품(packages/dc_*)을 쓰기 위해 경로를 한 번 잡아 둡니다.
이 패키지 아래 어느 모듈이든 dc_safety · dc_ransomfeed 를 import 할 수 있습니다.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "packages"))

"""Kr-Leak-alarm — 랜섬웨어 DLS 한국 기업 피해 모니터링 수집기."""

__version__ = "1.0.0"
