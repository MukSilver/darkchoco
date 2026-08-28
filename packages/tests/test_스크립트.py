"""저장소의 셸 스크립트가 실제로 파싱되는지 봅니다.

돌릴자리-만들기.sh 를 손으로 한 단계씩만 확인하고 통째로는 안 돌린 채
커밋한 적이 있습니다. **bash 는 한글 변수 이름을 못 받습니다.**
파이썬은 되니까 그대로 쓴 것인데, 그래서 스크립트가 첫 줄부터 안 돌고
있었습니다. 팀원이 쓸 수 있냐는 물음에 시험해 보고서야 알았습니다.

    터널포트="${DARKCHOCO_TOR_PORT:-9080}"
    → 터널포트=9080: command not found

이 검사는 무겁지 않습니다. bash -n 은 돌리지 않고 읽기만 합니다.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# bash 가 받는 이름입니다. 한글은 안 됩니다.
_이름 = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_대입 = re.compile(r"^\s*([^\s=]+)=[^=]")
_함수 = re.compile(r"^\s*([^\s(]+)\s*\(\)\s*\{")


def 스크립트들() -> list[Path]:
    return sorted(p for p in ROOT.rglob("*.sh")
                  if "node_modules" not in p.parts and ".venv" not in p.parts)


def test_스크립트가_하나는_있다():
    assert 스크립트들(), "볼 셸 스크립트가 없습니다"


def test_변수와_함수_이름이_bash_가_받는_것인가():
    나쁨 = []
    for p in 스크립트들():
        for i, 줄 in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            벗김 = 줄.strip()
            if not 벗김 or 벗김.startswith("#"):
                continue
            for rx, 무엇 in ((_대입, "변수"), (_함수, "함수")):
                m = rx.match(줄)
                if not m:
                    continue
                이름 = m.group(1)
                # export A=1 · local A=1 같은 꼴
                이름 = 이름.split()[-1]
                if 이름.startswith(("$", '"', "'", "[")) or "/" in 이름:
                    continue
                if not _이름.match(이름):
                    나쁨.append(
                        f"{p.relative_to(ROOT).as_posix()}:{i} "
                        f"{무엇} 이름 {이름!r}")
    assert not 나쁨, (
        "bash 가 못 받는 이름입니다. 한글 변수·함수 이름은 안 됩니다.\n  "
        + "\n  ".join(나쁨[:12]))


def test_bash_가_읽을_수_있나():
    """bash -n 은 파싱만 하고 실행은 안 합니다."""
    bash = shutil.which("bash")
    if not bash:
        return                          # 윈도우에 bash 가 없으면 건너뜁니다
    깨진것 = []
    for p in 스크립트들():
        r = subprocess.run([bash, "-n", str(p)], capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            깨진것.append(f"{p.relative_to(ROOT).as_posix()}: "
                       f"{(r.stderr or '').strip().splitlines()[:1]}")
    assert not 깨진것, "\n  ".join(깨진것)


def test_돌릴자리_스크립트가_할_일을_다_적었나():
    """단계가 빠지면 팀원이 그 단계를 손으로 해야 합니다."""
    p = ROOT / "scripts" / "돌릴자리-만들기.sh"
    assert p.exists(), "돌릴자리-만들기.sh 가 없습니다"
    글 = p.read_text(encoding="utf-8")
    for 낱말 in ("apt-get install", "HTTPTunnelPort", "ExcludeExitNodes {kr}",
                "StrictNodes 1", "check.torproject.org", "pip install",
                "TOR_SOCKS_PROXY", "doctor --net", "crontab"):
        assert 낱말 in 글, f"스크립트에 {낱말} 이 없습니다"
    # 토큰을 스크립트가 만지면 안 됩니다.
    assert "ntn_" not in 글, "스크립트에 토큰이 박혀 있습니다"


def test_셸_스크립트가_LF_인가():
    """CRLF 면 bash 가 캐리지리턴에 걸려 통째로 안 돕니다.

        scripts/돌릴자리-만들기.sh: line 16: command not found
        scripts/돌릴자리-만들기.sh: line 17: set: pipefail: invalid option

    윈도우에서 파일을 고치면 조용히 CRLF 가 됩니다. 실제로 파이썬으로
    스크립트를 고치다가 이렇게 됐습니다. .gitattributes 로도 막지만
    작업 디렉터리의 파일을 직접 봅니다.
    """
    CRLF = (chr(13) + chr(10)).encode()
    나쁨 = [p.relative_to(ROOT).as_posix() for p in 스크립트들()
          if CRLF in p.read_bytes()]
    assert not 나쁨, ("줄 끝이 CRLF 입니다. LF 로 바꾸십시오: "
                    + " · ".join(나쁨))


def test_gitattributes_가_sh_를_LF_로_묶는가():
    g = ROOT / ".gitattributes"
    assert g.exists(), ".gitattributes 가 없습니다"
    assert "*.sh text eol=lf" in g.read_text(encoding="utf-8"),         ".gitattributes 에 *.sh text eol=lf 가 없습니다"


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_"):
            v()
            print(f"  OK  {k}")
            n += 1
    print(f"\n{n}개 통과")
