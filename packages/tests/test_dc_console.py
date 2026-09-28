"""dc_console 과 그것을 붙인 자리를 확인합니다.

    python packages/tests/test_dc_console.py
"""
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
    "skills/collect/main.py",
]


def test_진입점에_use_utf8_이_붙어있다():
    for rel in 자리:
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "use_utf8()" in src, f"{rel} 에 use_utf8() 이 없다"


# 설치 없이 --help 가 뜨는지 보던 시험(tg-korea-alert 하나뿐)은 2026-09-26 에 그 앱을
# legacy/ 로 떼면서 지웠다(인계 E-1). 지금 도구의 --help 는 ci.yml 「네 진입점」 이 본다.


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_"):
            v(); print(f"  OK  {k}"); n += 1
    print(f"\n{n}개 통과")
