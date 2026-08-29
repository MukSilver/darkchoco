"""표준 라이브러리만 있는 환경에서도 되는 것을 확인합니다.

    python packages/tests/test_표준만.py

dls-observatory 는 표준 라이브러리만 쓰는 앱입니다. 공용 부품을 쓰게
바꾸면서 requests 가 딸려 들어가 한 번 깨진 적이 있어 막아 둡니다.

같은 프로세스에서 검사하면 이미 import 된 것이 통과시켜 버립니다.
그래서 자식 프로세스를 씁니다.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages"))

from dc_console import use_utf8  # noqa: E402

use_utf8()

# requests 도 telethon 도 없는 것처럼 만든다
막기 = (
    "import sys\n"
    "class _막개:\n"
    "    def find_spec(self, name, path=None, target=None):\n"
    "        if name.split('.')[0] in ('requests', 'telethon'):\n"
    "            raise ImportError(f'{name} 없음 (일부러 막음)')\n"
    "        return None\n"
    "sys.meta_path.insert(0, _막개())\n"
    f"sys.path.insert(0, r'{ROOT / 'packages'}')\n"
)


def _돌리기(코드: str) -> tuple[int, str]:
    r = subprocess.run([sys.executable, "-c", 막기 + 코드], cwd=ROOT,
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=60,
                       # 이것이 없으면 한글 콘솔에서 자식 출력이 cp949 로 나가
                       # 부모가 utf-8 로 읽다가 깨집니다. 검사가 거짓으로 실패합니다.
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def test_dc_console_은_맨몸으로_된다():
    code, out = _돌리기("import dc_console; dc_console.use_utf8(); print('ok')")
    assert code == 0 and "ok" in out, out[:400]


def test_dc_notion_은_맨몸으로_된다():
    code, out = _돌리기("import dc_notion; print(dc_notion.VERSION)")
    assert code == 0, out[:400]


def test_dc_ransomfeed_주소만_맨몸으로_된다():
    """dls-observatory 가 주소 상수만 가져다 쓴다. Fetcher 는 안 쓴다."""
    code, out = _돌리기(
        "from dc_ransomfeed import RANSOMWARE_LIVE, RANSOMLOOK, RANSOMFEED_RSS\n"
        "print(RANSOMWARE_LIVE)")
    assert code == 0, "주소 상수만 쓰는데 requests 가 딸려 온다\n" + out[:400]


def test_dc_safety_살균만_맨몸으로_된다():
    code, out = _돌리기(
        "from dc_safety import sanitize_text, defang_url, is_onion\n"
        "print(sanitize_text('가  나', 10))")
    assert code == 0, "살균만 쓰는데 requests 가 딸려 온다\n" + out[:400]


def test_dls_observatory_가_맨몸으로_돈다():
    """이 앱은 requirements.txt 가 없다. 표준 라이브러리만으로 돌아야 한다."""
    r = subprocess.run(
        [sys.executable, "-c", 막기 + "import runpy, sys\n"
         "sys.argv = ['diagnose.py', '--help']\n"
         "try: runpy.run_path('diagnose.py', run_name='__main__')\n"
         "except SystemExit: pass\n"],
        cwd=ROOT / "apps" / "dls-observatory", capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=60)
    합 = (r.stdout or "") + (r.stderr or "")
    assert "ModuleNotFoundError" not in 합, "표준 라이브러리만으로 안 돈다\n" + 합[:500]


def test_무거운것은_부를때만_요구한다():
    """늦은 import 가 반대로 너무 느슨해지지 않았는지 본다."""
    code, out = _돌리기("import dc_safety\n"
                        "try:\n"
                        "    dc_safety.SafeHttpClient\n"
                        "    print('샜다')\n"
                        "except ImportError:\n"
                        "    print('막힘')\n")
    assert "막힘" in out, "requests 없이 SafeHttpClient 가 만들어진다\n" + out[:400]


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_"):
            v(); print(f"  OK  {k}"); n += 1
    print(f"\n{n}개 통과")
