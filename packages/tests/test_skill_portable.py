"""스킬을 cp -R 로 떼어 가도 도는지 확인합니다.

    python packages/tests/test_skill_portable.py

이 스킬은 툴킷의 일부라 저장소 밖으로 복사해 쓸 수 있어야 합니다.
공용 부품을 쓰게 바꾸면서 한 번 깨진 적이 있어 테스트로 막아 둡니다.
"""
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


def _돌리기(cwd: Path, *args: str) -> tuple[int, str]:
    r = subprocess.run(
        [sys.executable, *args], cwd=cwd, capture_output=True,
        text=True, encoding="utf-8", errors="replace", timeout=60,
        # 저장소 밖에서 도는 상황을 만든다. 부품이 경로에 딸려 들어가면
        # 시험이 무의미해지므로 PYTHONPATH 만 지운다.
        env={**os.environ, "PYTHONPATH": "", "PYTHONIOENCODING": "utf-8"},
    )
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def test_떼어내도_import_가_된다():
    """부품이 없어도 --help 는 떠야 한다. 노션 안 쓰는 절이 그대로 돌기 때문이다."""
    with tempfile.TemporaryDirectory() as d:
        s = _떼어내기(Path(d))
        _, out = _돌리기(s, "tools/notion.py", "--help")
        assert "ModuleNotFoundError" not in out, f"떼어내면 import 가 깨진다\n{out[:400]}"
        assert "노션" in out, f"안내가 안 나온다\n{out[:400]}"


def test_부품이_없으면_부를_때_알려준다():
    """죽더라도 무엇을 하면 되는지 말해야 한다."""
    with tempfile.TemporaryDirectory() as d:
        s = _떼어내기(Path(d))
        _, out = _돌리기(s, "tools/notion.py", "search", "x")
        assert "pip install" in out, f"해결 방법을 안 알려준다\n{out[:400]}"


def test_부품을_옆에_두면_찾는다():
    with tempfile.TemporaryDirectory() as d:
        s = _떼어내기(Path(d))
        shutil.copytree(ROOT / "packages", s / "tools" / "_vendor",
                        ignore=shutil.ignore_patterns("tests", "__pycache__"))
        code, out = _돌리기(s, "-c",
                            "import sys; sys.path.insert(0,'tools');"
                            "from _dcpath import ensure_packages;"
                            "assert ensure_packages(); import dc_notion; print('ok')")
        assert code == 0 and "ok" in out, f"_vendor 를 못 찾는다\n{out[:400]}"


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
    for n in ("dc_console", "dc_notion", "dc_safety", "dc_ransomfeed", "dc_telegram"):
        assert n in t, f"pyproject.toml 에 {n} 이 없다"
    assert "dependencies = []" in t, "기본 설치가 밖에서 무엇을 받으면 안 된다"


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_"):
            v(); print(f"  OK  {k}"); n += 1
    print(f"\n{n}개 통과")
