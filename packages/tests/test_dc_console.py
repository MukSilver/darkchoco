"""dc_console 과 그것을 붙인 자리를 확인합니다.

    python packages/tests/test_dc_console.py
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages"))

import dc_console  # noqa: E402


def test_use_utf8_가_있고_두번_불러도_된다():
    dc_console.use_utf8()
    dc_console.use_utf8()


def test_reconfigure_없는_스트림에서도_안죽는다():
    class Dumb:
        pass
    real_out, real_err = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = Dumb()
    try:
        dc_console.use_utf8()          # AttributeError 를 삼켜야 한다
    finally:
        sys.stdout, sys.stderr = real_out, real_err


# 붙여 둔 자리. 여기가 빠지면 한글 콘솔에서 결과가 틀리게 보인다.
자리 = [
    "apps/kr-leak-alarm/collector/main.py",
    "apps/kr-leak-alarm/tests/test_all.py",
    "apps/dls-observatory/test_db.py",
    "apps/forum-crawler/investigate.py",
    "skills/collect/main.py",
]


def test_진입점에_use_utf8_이_붙어있다():
    for rel in 자리:
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "use_utf8()" in src, f"{rel} 에 use_utf8() 이 없다"


def test_설치_안해도_help_가_뜬다():
    """무거운 import 를 함수 안으로 내린 것이 되돌아가지 않게 한다."""
    경우 = [
        ("apps/forum-crawler", ["python", "investigate.py", "--help"]),
        ("apps/tg-korea-alert", ["python", "korea_alert_monitor.py", "--help"]),
        ("apps/tg-notion-report", ["python", "telegram_pipeline.py", "--help"]),
    ]
    for cwd, cmd in 경우:
        r = subprocess.run(cmd, cwd=ROOT / cwd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
        합 = (r.stdout or "") + (r.stderr or "")
        assert "ModuleNotFoundError" not in 합, f"{cwd}: 설치 없이는 --help 가 안 뜬다\n{합[:300]}"
        assert "usage" in 합.lower(), f"{cwd}: usage 가 안 나온다\n{합[:300]}"


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_"):
            v(); print(f"  OK  {k}"); n += 1
    print(f"\n{n}개 통과")
