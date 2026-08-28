"""조사기를 안 거치고 밖에 요청을 보내는 코드를 막습니다.

    python packages/tests/test_직접호출금지.py

조사기 안에는 겪어서 얻은 방어가 들어 있습니다.

  · ransomware.live 는 1req/분/엔드포인트 입니다. 62초 간격을 지킵니다
  · 연속 세 번 실패하면 멈춥니다. kr-leak-alarm 에서 IP 가 막힌 적이 있습니다
  · t.me 와 포럼도 각자 간격이 있습니다

조사기를 우회해 API 를 직접 치면 그 방어가 없는 길이 하나 더 생깁니다.
실제로 그렇게 해서 429 를 받은 적이 있습니다.
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages"))

from dc_console import use_utf8  # noqa: E402

use_utf8()

# 밖에 요청을 보내도 되는 자리. 여기에만 간격과 방어가 있습니다.
허용 = {
    "hub/crawler/probe/telegram.py",
    "hub/crawler/probe/forum.py",
    "hub/crawler/probe/ransom.py",
    "packages/dc_safety/http.py",
    "packages/dc_ransomfeed/fetch.py",
}

보는곳 = ["hub"]
요청함수 = {"urlopen", "urlretrieve", "get", "post", "request", "Session"}
요청모듈 = {"urllib", "requests", "http", "httpx", "aiohttp", "socket"}


def _밖으로_나가나(p: Path) -> list[str]:
    """이 파일이 밖에 요청을 보내는지 봅니다."""
    try:
        t = ast.parse(p.read_text(encoding="utf-8"))
    except SyntaxError:
        return []
    나감 = []
    for n in ast.walk(t):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.name.split(".")[0] in 요청모듈:
                    나감.append(f"import {a.name}")
        elif isinstance(n, ast.ImportFrom):
            if (n.module or "").split(".")[0] in 요청모듈:
                나감.append(f"from {n.module} import …")
    return 나감


def test_조사기_밖에서는_요청을_안_보낸다():
    샌곳 = []
    for 뿌리 in 보는곳:
        for p in (ROOT / 뿌리).rglob("*.py"):
            rel = p.relative_to(ROOT).as_posix()
            if rel in 허용 or "__pycache__" in rel:
                continue
            나감 = _밖으로_나가나(p)
            if 나감:
                샌곳.append(f"{rel}: {' · '.join(나감[:3])}")
    assert not 샌곳, (
        "조사기를 안 거치고 밖에 요청을 보내는 코드가 있습니다.\n  "
        + "\n  ".join(샌곳)
        + "\n\n조사기 안에는 간격과 실패 중단이 들어 있습니다. 그것을 지나가십시오."
    )


def test_조사기가_간격을_갖고_있다():
    """허용된 자리에는 반드시 간격이 있어야 합니다."""
    for rel in sorted(허용):
        if not rel.startswith("hub/"):
            continue
        s = (ROOT / rel).read_text(encoding="utf-8")
        assert "간격" in s or "min_interval" in s or "sleep" in s, \
            f"{rel} 에 간격이 없습니다"


def test_랜섬은_62초를_지킨다():
    s = (ROOT / "hub/crawler/probe/ransom.py").read_text(encoding="utf-8")
    import re
    m = re.search(r"^간격\s*=\s*([\d.]+)", s, re.M)
    assert m, "간격 상수를 못 찾았습니다"
    assert float(m.group(1)) >= 60, \
        f"1req/분/엔드포인트인데 간격이 {m.group(1)}초입니다"


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_"):
            v(); print(f"  OK  {k}"); n += 1
    print(f"\n{n}개 통과")
