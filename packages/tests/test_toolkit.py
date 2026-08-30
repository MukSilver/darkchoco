"""툴킷 뼈대가 성립하는지 확인합니다.

    python packages/tests/test_toolkit.py
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# 찾는 규칙은 dc.py 것을 그대로 씁니다. 두 군데에 따로 두면 어긋납니다.
def _tool_json들():
    import importlib.util                       # noqa: PLC0415
    spec = importlib.util.spec_from_file_location("_dc", ROOT / "dc.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m._tool_json찾기()
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
    for p in _tool_json들():
        if ".git" in p.parts:
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        빠짐 = 필수 - set(d)
        assert not 빠짐, f"{p} 에 {빠짐} 이 없다"
        assert d["default"] in d["commands"], f"{p} 의 default 가 commands 에 없다"
        본것 += 1
    # 숫자를 박지 않습니다. 도구가 늘거나 줄 때마다 깨집니다 —
    # 2026-08-30 에 crawler 를 넣고 둘을 지우면서 세 번 걸렸습니다.
    assert 본것 >= 4, f"tool.json 이 {본것}장뿐이다. 너무 적습니다"


def test_명령에_이상문자가_없다():
    """윈도우 경로의 백슬래시가 제어문자로 바뀐 적이 있다."""
    for p in _tool_json들():
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
    # 숫자를 박아 두면 도구가 늘거나 줄 때마다 검사가 깨집니다. 실제로
    # crawler 를 넣을 때 「도구 7개」에서 걸렸고, 크롤링하던 앱 셋을
    # 지울 때 또 걸렸습니다. 세어서 봅니다.
    몇장 = len([x for x in _tool_json들() if ".git" not in x.parts])
    assert f"도구 {몇장}개" in out, f"{몇장}장인데 화면은: {out[:300]!r}"
    for n in ("kr-leak-alarm", "darkweb-verify-ko", "crawler"):
        assert n in out, f"{n} 이 목록에 없다"


def test_info_가_돈다():
    code, out = _dc("info", "kr-leak-alarm")
    assert code == 0, out
    assert "안유빈" in out and "run.bat" in out, out[:300]
    code, _ = _dc("info", "없는도구")
    assert code == 1, "없는 도구인데 0 을 돌려준다"


def test_doctor_가_돈다():
    code, out = _dc("doctor", "crawler")
    assert code == 0, out
    assert "파이썬" in out, out[:300]


def test_readme_표가_최신이다():
    code, out = _dc("readme", "--check")
    assert code == 0, out + "\n  python dc.py readme --write 를 돌리십시오"

def test_스케줄러가_auto_를_부른다():
    """만들어 둔 명령과 실제로 거는 명령이 갈라져 있었습니다.

    dc.py 가 「작업」 변수에 auto 를 담아 두고, 등록 명령에는 run --due 를
    박아 뒀습니다. 그래서 스케줄러가 auto 를 영영 안 불렀고 크롤러 자동화가
    통째로 죽어 있었습니다. 아무도 몰랐습니다.

    수집기만 도는 것과 명부 조사까지 도는 것은 전혀 다릅니다.
    """
    글 = (ROOT / "dc.py").read_text(encoding="utf-8")
    assert 'dc.py"}" run --due' not in 글, (
        "등록 명령에 run --due 가 박혀 있습니다. 인자 변수를 쓰십시오")

    r = subprocess.run(
        [sys.executable, str(ROOT / "dc.py"), "install-task", "--show"],
        capture_output=True, text=True, cwd=str(ROOT),
        encoding="utf-8", errors="replace",
        env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    나온것 = r.stdout or ""
    assert 'dc.py" auto' in 나온것, "등록 명령이 auto 를 안 부릅니다"
    assert "run --due" not in 나온것, "아직 run --due 를 겁니다"



def test_README_구조도가_실제_폴더를_다_담는다():
    """오늘 정확히 이것이 문제였습니다.

    hub/ 이 3,691줄로 저장소에서 제일 큰데 README 에 **낱말조차 없었습니다.**
    구조도가 dc.py · apps · packages · skills · docs 다섯만 적고 있었습니다.
    hub/ 과 scripts/ 가 생긴 뒤로 아무도 안 고친 것입니다.

    오류가 안 납니다. 처음 온 사람이 저장소를 잘못 이해할 뿐입니다.
    """
    글 = (ROOT / "README.md").read_text(encoding="utf-8")
    자리 = 글[글.index("## 구조"):]
    자리 = 자리[:자리.index("<!-- 도구표 시작")]

    안볼것 = {".git", ".github", ".venv", "venv", "__pycache__",
            "node_modules", ".pytest_cache"}
    실제 = sorted(d.name for d in ROOT.iterdir()
                if d.is_dir() and d.name not in 안볼것 and not d.name.startswith("."))
    빠짐 = [d for d in 실제 if f"{d}/" not in 자리]
    assert not 빠짐, f"README 구조도에 없는 폴더: {빠짐}"
    assert len(실제) >= 5, f"폴더를 {len(실제)}개만 찾았다"


def test_도구표가_최신이다():
    """tool.json 을 더해 놓고 README 표를 안 고치면 어긋납니다."""
    import subprocess
    r = subprocess.run([sys.executable, "dc.py", "readme", "--check"], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120,
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    assert r.returncode == 0, (
        "README 도구 표가 낡았습니다. python dc.py readme --write 로 다시 쓰십시오.\n"
        + (r.stdout or "") + (r.stderr or ""))


def test_크롤러도_툴킷에_있다():
    """제일 큰 것이 `dc.py list` 에 안 나오고 있었습니다.

    툴킷의 규칙은 「도구 하나에 tool.json 한 장」입니다. 크롤러만 그 밖에
    있어서 `dc.py info` 도 `dc.py doctor` 도 안 됐습니다.
    """
    import json
    p = ROOT / "hub" / "tool.json"
    assert p.exists(), "hub/tool.json 이 없습니다"
    d = json.loads(p.read_text(encoding="utf-8"))
    assert d["name"] == "crawler", d.get("name")
    assert d["preconditions"]["tor"] is True, "Tor 가 필요하다고 안 적혀 있습니다"
    # 다른 도구가 **전부** 갖고 있는 칸은 크롤러도 갖춰야 표가 안
    # 비뚤어집니다. 한 도구만 있는 칸(license · kind)은 안 봅니다.
    다른것 = [json.loads(x.read_text(encoding="utf-8"))
            for x in _tool_json들() if x.parent.name != "hub"]
    공통 = set(다른것[0])
    for x in 다른것[1:]:
        공통 &= set(x)
    빠짐 = sorted(공통 - set(d))
    assert not 빠짐, f"다른 도구가 다 갖고 있는데 crawler 에 없는 칸: {빠짐}"


def test_끝난_기록은_따로_둔다():
    """따라 하면 안 되는 문서가 살아 있는 문서와 섞여 있었습니다.

    구축절차.md 는 8/26 에 끝난 일회성 절차인데 286줄짜리라, 처음 온
    사람이 그것부터 따라 하기 쉽습니다.
    """
    기록 = ROOT / "docs" / "기록"
    assert 기록.is_dir(), "docs/기록/ 이 없습니다"
    for f in 기록.glob("*.md"):
        머리 = f.read_text(encoding="utf-8").split(chr(10))[:5]
        assert any("끝난 일의 기록" in l for l in 머리), (
            f"{f.name} 맨 위에 「끝난 일의 기록」 표시가 없습니다")

if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_"):
            v(); print(f"  OK  {k}"); n += 1
    print(f"\n{n}개 통과")

