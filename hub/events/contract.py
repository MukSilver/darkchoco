"""어댑터가 지켜야 할 약속.

어댑터는 "한 출처에서 항목을 긁어 오는 작은 물건" 입니다. 도구를 새로
만들지 않습니다. 이미 있는 도구를 부르고, 그 결과를 표에 들어갈 모양으로
바꿉니다.

지켜야 할 것은 셋입니다.

  1. `collect()` 를 갖습니다. Item 을 하나씩 내놓습니다(제너레이터).
  2. `NAME` 과 `NEEDS` 를 갖습니다. 무엇이 있어야 도는지 밝힙니다.
  3. 밖에 요청을 보내는 일은 원래 도구에 맡깁니다. 여기서 새로 짜지
     않습니다. 원래 도구에는 겪어서 얻은 방어가 들어 있습니다.

세 번째가 제일 중요합니다. 예를 들어 kr-leak-alarm 은 연속 세 번 실패하면
멈춥니다. IP 가 막힌 적이 있어서 넣은 방어입니다. 어댑터가 API 를 직접
치면 그 방어가 없는 길이 하나 더 생깁니다.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Protocol

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages"))

from dc_store import Item  # noqa: E402,F401  (어댑터가 여기서 가져다 씁니다)

__all__ = ["Item", "Adapter", "Needs", "Result", "Skip"]


class Skip(Exception):
    """이번엔 안 돕니다. 실패가 아닙니다.

    준비가 안 되어 못 도는 경우입니다(비밀값 없음, VM 꺼짐, 도커 없음).
    실패로 세면 "안 씀" 과 "못 봄" 이 뒤섞입니다. 그 둘은 다릅니다.
    """


@dataclass
class Needs:
    """이 어댑터가 돌려면 있어야 하는 것.

    돌리기 전에 봅니다. 없으면 Skip 이고, 화면에 무엇이 없는지 적습니다.
    """

    packages: list[str] = field(default_factory=list)   # 파이썬 모듈 이름
    secrets: list[str] = field(default_factory=list)    # 환경변수 이름
    files: list[str] = field(default_factory=list)      # 있어야 하는 파일
    docker: bool = False        # 참이면 docker 명령이 PATH 에 있어야 합니다
    tor: bool = False           # 참이면 TOR_SOCKS_PROXY 가 있어야 합니다

    def 모자란것(self, env: dict, root: Path) -> list[str]:
        import importlib.util
        import shutil

        모자람 = []
        for m in self.packages:
            try:
                if importlib.util.find_spec(m) is None:
                    모자람.append(f"{m} 안 깔림")
            except (ImportError, ValueError):
                모자람.append(f"{m} 안 깔림")
        for k in self.secrets:
            if not (env.get(k) or "").strip():
                모자람.append(f"{k} 비어 있음")
        for f in self.files:
            if not (root / f).exists():
                모자람.append(f"{f} 없음")
        # docker 와 tor 를 안 보고 있었습니다. 그 둘이 있어야 도는 어댑터를
        # 붙이면 모자란 줄 모르고 들어가 "실패" 로 잡힙니다. 준비가 안 된
        # 것은 실패가 아니라 "안 씀" 입니다.
        #
        # 여기서는 밖에 요청을 보내지 않고, 있는지만 봅니다.
        #   docker  PATH 에 명령이 있는가. 데몬이 떠 있는지까지 보려면
        #           docker info 를 돌려야 하는데, 돌리기 전에 훑는 자리라
        #           여기서 프로세스를 띄우지 않습니다
        #   tor     hub/places/egress.py 와 같은 기준입니다. 그쪽도
        #           TOR_SOCKS_PROXY 가 있어야 밖으로 나갑니다
        if self.docker and shutil.which("docker") is None:
            모자람.append("docker 없음")
        if self.tor and not (env.get("TOR_SOCKS_PROXY") or "").strip():
            모자람.append("TOR_SOCKS_PROXY 비어 있음")
        return 모자람


@dataclass
class Result:
    """한 판 돌린 결과."""

    name: str
    got: int = 0          # 어댑터가 내놓은 수
    fresh: int = 0        # 표에 새로 들어간 수
    skipped: str = ""     # 안 돈 이유. 비어 있으면 돈 것입니다
    error: str = ""       # 실패 이유
    seconds: float = 0.0

    @property
    def 됐나(self) -> bool:
        return not self.error and not self.skipped


class Adapter(Protocol):
    """어댑터의 모양. 이대로 만들면 됩니다."""

    NAME: str
    NEEDS: Needs

    def collect(self, ctx: "Ctx") -> Iterator[Item]:
        ...


@dataclass
class Ctx:
    """어댑터에게 주는 것들."""

    root: Path                       # 저장소 뿌리
    env: dict                        # 환경변수
    today: str                       # YYYY-MM-DD
    dry: bool = False                # 참이면 밖에 요청을 보내지 않습니다
    limit: int = 0                   # 0 이면 제한 없음

    def 앱(self, rel: str) -> Path:
        """앱 폴더 경로. 어댑터가 원래 도구를 부를 때 씁니다."""
        return self.root / rel
