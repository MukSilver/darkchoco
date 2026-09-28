"""시험 파일의 `__main__` 실행부가 마지막 시험보다 뒤에 있는지 본다.

    python packages/tests/test_실행부자리.py          CI 가 이렇게 돌린다

CI 는 시험 파일을 `python 파일` 로 돌린다. 실행부는 그 줄에 닿았을 때 `globals()` 에 있는
`test_*` 만 부른다. **실행부 아래에 적은 시험은 CI 에서 한 번도 안 돈다.** 2026-09-25 에
`test_crawler.py` 의 180일 시험 셋이 그랬다(「126개 통과」 로 초록불). 머지 전 검토에서 찾았다.

unittest.main() 을 쓰는 파일도 같다 — 실행부 아래의 클래스는 안 잡힌다.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _시험파일들() -> list[Path]:
    out = sorted((ROOT / "packages" / "tests").glob("test_*.py"))
    out += sorted(p for p in (ROOT / "skills").rglob("test_*.py") if "__pycache__" not in p.parts)
    return out


def _실행부_뒤의_시험(p: Path) -> list[str]:
    나무 = ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
    실행부줄 = None
    for 마디 in 나무.body:
        if (isinstance(마디, ast.If) and isinstance(마디.test, ast.Compare)
                and isinstance(마디.test.left, ast.Name) and 마디.test.left.id == "__name__"):
            실행부줄 = 마디.lineno
    if 실행부줄 is None:
        return []
    return [f"{마디.name} ({마디.lineno}줄)" for 마디 in 나무.body
            if isinstance(마디, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and 마디.lineno > 실행부줄
            and (마디.name.startswith("test_") or isinstance(마디, ast.ClassDef))]


def test_실행부_아래에_시험이_없다():
    틀림 = {}
    for p in _시험파일들():
        뒤 = _실행부_뒤의_시험(p)
        if 뒤:
            틀림[str(p.relative_to(ROOT))] = 뒤
    assert not 틀림, "실행부 아래에 있어 CI 에서 안 도는 시험: %s" % 틀림


def test_이_점검이_실제로_잡는다(tmp=None):
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "test_가짜.py"
        f.write_text("def test_a():\n    pass\n\nif __name__ == '__main__':\n    test_a()\n\n"
                     "def test_b():\n    assert False\n", encoding="utf-8")
        assert _실행부_뒤의_시험(f) == ["test_b (7줄)"], _실행부_뒤의_시험(f)


if __name__ == "__main__":
    시험들 = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    실패 = 0
    for 이름, f in 시험들:
        try:
            f()
            print("  OK  %s" % 이름)
        except Exception as e:  # noqa: BLE001
            실패 += 1
            print("  !!  %s — %s: %s" % (이름, type(e).__name__, e))
    print("\n%d개 중 %d개 실패" % (len(시험들), 실패))
    sys.exit(1 if 실패 else 0)
