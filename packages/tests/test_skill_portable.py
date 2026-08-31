"""스킬을 cp -R 로 떼어 가도 도는지 확인합니다.

    python packages/tests/test_skill_portable.py

이 스킬은 툴킷의 일부라 저장소 밖으로 복사해 쓸 수 있어야 합니다.
공용 부품을 쓰게 바꾸면서 한 번 깨진 적이 있어 테스트로 막아 둡니다.

부품을 찾는 규칙은 _dcpath 를 직접 불러 시험합니다. 스크립트를 통째로
돌려 보는 방식은 부품이 깔린 환경에서 "안 깔린 상황" 을 못 만듭니다.
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages"))

from dc_console import use_utf8  # noqa: E402

use_utf8()

스킬 = ROOT / "skills" / "skills" / "darkweb-verify-ko"


def _떼어내기(dst: Path) -> Path:
    shutil.copytree(스킬, dst / 스킬.name)
    return dst / 스킬.name


def _dcpath(tools: Path):
    """떼어낸 자리의 _dcpath 를 그 자리 것으로 불러옵니다."""
    spec = importlib.util.spec_from_file_location(
        f"_dcpath_{abs(hash(str(tools)))}", tools / "_dcpath.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _돌리기(cwd: Path, *args: str) -> tuple[int, str]:
    r = subprocess.run(
        [sys.executable, *args], cwd=cwd, capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=60,
        env={**os.environ, "PYTHONPATH": "", "PYTHONIOENCODING": "utf-8"},
    )
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def test_떼어내도_import_가_된다():
    """부품을 못 찾아도 import 단계에서 죽으면 안 된다.

    이 스킬은 노션 없이도 ③④⑤⑥ 절이 돌기 때문이다.
    """
    with tempfile.TemporaryDirectory() as d:
        s = _떼어내기(Path(d))
        code, out = _돌리기(s, "tools/notion.py", "--help")
        assert "ModuleNotFoundError" not in out, f"떼어내면 import 가 깨진다\n{out[:400]}"
        assert code == 0 or "노션" in out, f"--help 가 안 뜬다\n{out[:400]}"


def test_부품이_없으면_찾기가_실패한다():
    """저장소 밖이고 옆에도 없으면 packages_dir 이 None 이어야 한다."""
    with tempfile.TemporaryDirectory() as d:
        s = _떼어내기(Path(d))
        m = _dcpath(s / "tools")
        assert m.packages_dir() is None, \
            f"부품이 없는데 있다고 한다: {m.packages_dir()}"


def test_못_찾으면_무엇을_할지_알려준다():
    with tempfile.TemporaryDirectory() as d:
        s = _떼어내기(Path(d))
        m = _dcpath(s / "tools")
        msg = m.missing_message()
        assert "pip install" in msg, "해결 방법을 안 알려준다"
        assert "_vendor" in msg, "옆에 두는 방법을 안 알려준다"
        assert "③" in msg or "노션" in msg, "무엇이 여전히 되는지 안 알려준다"


def test_부품을_옆에_두면_찾는다():
    with tempfile.TemporaryDirectory() as d:
        s = _떼어내기(Path(d))
        shutil.copytree(ROOT / "packages", s / "tools" / "_vendor",
                        ignore=shutil.ignore_patterns("tests", "__pycache__"))
        m = _dcpath(s / "tools")
        found = m.packages_dir()
        assert found is not None and found.name == "_vendor", \
            f"_vendor 를 못 찾는다: {found}"


def test_저장소_안에서는_packages_를_찾는다():
    m = _dcpath(스킬 / "tools")
    found = m.packages_dir()
    assert found is not None and found.name == "packages", \
        f"저장소 안인데 packages 를 못 찾는다: {found}"


def test_설치된_것이_우선이다():
    """ensure_packages 는 이미 깔린 것이 있으면 경로를 안 뒤진다."""
    m = _dcpath(스킬 / "tools")
    before = list(sys.path)
    try:
        assert m.ensure_packages() is True
    finally:
        sys.path[:] = before


def test_노션_안쓰는_도구는_그대로_돈다():
    with tempfile.TemporaryDirectory() as d:
        s = _떼어내기(Path(d))
        for t in ("inspect.py", "sample_stats.py", "tree_scan.py"):
            if not (s / "tools" / t).exists():
                continue
            _, out = _돌리기(s, f"tools/{t}", "--help")
            assert "usage" in out.lower(), f"{t} 가 떼어내면 안 된다\n{out[:300]}"


def test_부품_설치_설정이_있다():
    """pip install -e packages 가 되어야 한다."""
    t = (ROOT / "packages" / "pyproject.toml").read_text(encoding="utf-8")
    # dc_store 는 2026-08-31 까지 빠져 있었다. 검사도 다섯만 세고 있어서
    # 못 잡았다. 여섯을 다 센다.
    for n in ("dc_console", "dc_notion", "dc_safety", "dc_ransomfeed",
              "dc_store", "dc_telegram"):
        assert n in t, f"pyproject.toml 에 {n} 이 없다"
    assert "dependencies = []" in t, "기본 설치가 밖에서 무엇을 받으면 안 된다"


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_"):
            v(); print(f"  OK  {k}"); n += 1
    print(f"\n{n}개 통과")
