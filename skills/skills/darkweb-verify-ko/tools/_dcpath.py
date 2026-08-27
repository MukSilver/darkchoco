"""공용 부품(packages/dc_*)을 어디서 실행하든 찾아 줍니다.

이 스킬은 `cp -R` 한 번으로 떼어 갈 수 있어야 합니다. 그런데 저장소 밖으로
복사하면 `packages/` 가 같이 안 따라옵니다. 그때 부품을 못 찾아 도구가
import 단계에서 죽습니다.

찾는 차례입니다. 먼저 되는 것을 씁니다.

  1. 이미 설치되어 있으면 그대로 씁니다 (`pip install -e packages`)
  2. 저장소 안에서 돌고 있으면 `packages/` 를 경로에 넣습니다
  3. 이 폴더 옆에 `_vendor/` 가 있으면 그것을 씁니다
  4. 셋 다 없으면 무엇을 하면 되는지 알려 줍니다

노션이 없어도 ③④⑤⑥ 절은 돌아야 하므로, 못 찾았다고 여기서 죽이지
않습니다. 실제로 부르는 자리에서 죽입니다.

    from _dcpath import ensure_packages
    ensure_packages()
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

__all__ = ["ensure_packages", "packages_dir", "missing_message", "use_utf8"]

HERE = Path(__file__).resolve().parent


def packages_dir() -> Path | None:
    """`packages/` 가 있는 자리를 찾습니다. 없으면 None 입니다.

    이 파일에서 위로 올라가며 봅니다. 저장소 구조가 바뀌어도 버팁니다.
    """
    for parent in [HERE, *HERE.parents]:
        candidate = parent / "packages"
        if (candidate / "dc_notion").is_dir():
            return candidate
    vendor = HERE / "_vendor"
    if (vendor / "dc_notion").is_dir():
        return vendor
    return None


def ensure_packages() -> bool:
    """부품을 찾아 경로에 넣습니다. 찾았으면 True 입니다.

    이미 설치되어 있으면 아무것도 하지 않습니다. 설치된 것이 우선입니다.
    """
    if importlib.util.find_spec("dc_notion") is not None:
        return True

    found = packages_dir()
    if found is None:
        return False

    path = str(found)
    if path not in sys.path:
        sys.path.insert(0, path)
    return True


def missing_message(module: str = "dc_notion") -> str:
    """부품을 못 찾았을 때 사람에게 할 말입니다."""
    return (
        f"공용 부품 {module} 을 못 찾았습니다.\n"
        "이 스킬을 저장소 밖으로 복사해 쓰고 계신 것 같습니다.\n\n"
        "셋 중 하나를 하시면 됩니다.\n"
        "  1. 저장소에서 부품을 설치합니다\n"
        "       pip install -e <darkchoco>/packages\n"
        "  2. 저장소 안에서 실행합니다\n"
        "       <darkchoco>/skills/skills/darkweb-verify-ko/tools/\n"
        "  3. 부품을 이 스킬 옆에 같이 둡니다\n"
        "       cp -R <darkchoco>/packages tools/_vendor\n\n"
        "노션을 안 쓰는 절(③④⑤⑥)은 이것 없이도 돕니다."
    )


def use_utf8() -> None:
    """윈도우 한글 콘솔(cp949)에서 결과를 찍다가 죽지 않게 합니다.

    packages/dc_console 에 같은 함수가 있지만 여기에 한 벌 더 둡니다.
    이 스킬은 부품 없이 떼어 가도 돌아야 하기 때문입니다.

    다른 도구에서도 쓰시려면 맨 위에 두 줄을 넣으면 됩니다.

        from _dcpath import use_utf8
        use_utf8()
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        except (AttributeError, ValueError):
            pass
