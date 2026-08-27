"""툴킷 뼈대가 성립하는지 확인합니다.

    python packages/tests/test_toolkit.py
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages"))

from dc_console import use_utf8  # noqa: E402

use_utf8()


def _dc(*args: str):
    r = subprocess.run([sys.executable, "dc.py", *args], cwd=ROOT,
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=90)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def test_루트문서가_다_있다():
    for f in ("LICENSE", "NOTICE", "CONTRIBUTING.md", "SECURITY.md", "CITATION.cff"):
        assert (ROOT / f).is_file(), f"{f} 가 없다"
    assert "Apache License" in (ROOT / "LICENSE").read_text(encoding="utf-8")


def test_tool_json_이_전부_읽힌다():
    필수 = {"name", "owner", "summary", "commands", "default", "run_cwd"}
    본것 = 0
    for p in ROOT.rglob("tool.json"):
        if ".git" in p.parts:
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        빠짐 = 필수 - set(d)
        assert not 빠짐, f"{p} 에 {빠짐} 이 없다"
        assert d["default"] in d["commands"], f"{p} 의 default 가 commands 에 없다"
        본것 += 1
    assert 본것 >= 7, f"tool.json 이 {본것}장뿐이다"


def test_명령에_이상문자가_없다():
    """윈도우 경로의 백슬래시가 제어문자로 바뀐 적이 있다."""
    for p in ROOT.rglob("tool.json"):
        if ".git" in p.parts:
            continue
        raw = p.read_text(encoding="utf-8")
        d = json.loads(raw)
        for v in list(d.get("commands", {}).values()) + [json.dumps(d, ensure_ascii=False)]:
            for ch in v:
                assert ord(ch) >= 32 or ch in "\n\t", f"{p} 에 제어문자 U+{ord(ch):04X}"


def test_list_가_돈다():
    code, out = _dc("list")
    assert code == 0, out
    assert "도구 7개" in out, out[:300]
    for n in ("kr-leak-alarm", "darkweb-verify-ko", "forum-crawler"):
        assert n in out, f"{n} 이 목록에 없다"


def test_info_가_돈다():
    code, out = _dc("info", "kr-leak-alarm")
    assert code == 0, out
    assert "안유빈" in out and "run.bat" in out, out[:300]
    code, _ = _dc("info", "없는도구")
    assert code == 1, "없는 도구인데 0 을 돌려준다"


def test_doctor_가_돈다():
    code, out = _dc("doctor", "dls-observatory")
    assert code == 0, out
    assert "파이썬" in out, out[:300]


def test_readme_표가_최신이다():
    code, out = _dc("readme", "--check")
    assert code == 0, out + "\n  python dc.py readme --write 를 돌리십시오"


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_"):
            v(); print(f"  OK  {k}"); n += 1
    print(f"\n{n}개 통과")
