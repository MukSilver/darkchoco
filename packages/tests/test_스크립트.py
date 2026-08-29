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


# 안 뒤질 곳입니다. .venv 는 리눅스에서 만들면 심볼릭 링크가 들어 있어
# 윈도우 파이썬이 rglob 중에 죽습니다(WinError 1920). 어차피 우리가
# 쓴 스크립트가 아닙니다.
_건너뜀 = {".venv", "venv", "node_modules", ".git", "__pycache__",
        "site-packages", ".tox"}


def _찾기(끝: str) -> list[Path]:
    """저장소가 가진 파일. 받아 온 것은 안 봅니다."""
    나온것 = []
    스택 = [ROOT]
    while 스택:
        d = 스택.pop()
        try:
            것들 = list(d.iterdir())
        except OSError:
            continue
        for x in 것들:
            try:
                if x.is_dir():
                    if x.name not in _건너뜀 and not x.is_symlink():
                        스택.append(x)
                elif x.suffix == 끝:
                    나온것.append(x)
            except OSError:
                continue
    return sorted(나온것)


def ps1들() -> list[Path]:
    return _찾기(".ps1")


def 스크립트들() -> list[Path]:
    """저장소가 가진 셸 스크립트. 받아 온 것은 안 봅니다."""
    나온것 = []
    스택 = [ROOT]
    while 스택:
        d = 스택.pop()
        try:
            것들 = list(d.iterdir())
        except OSError:
            continue                    # 못 읽는 곳은 건너뜁니다
        for x in 것들:
            try:
                if x.is_dir():
                    if x.name not in _건너뜀 and not x.is_symlink():
                        스택.append(x)
                elif x.suffix == ".sh":
                    나온것.append(x)
            except OSError:
                continue
    return sorted(나온것)


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


def test_ps1_에_BOM_이_있나():
    """윈도우 PowerShell 5.1 은 BOM 이 없으면 UTF-8 을 ANSI 로 읽습니다.

    한글이 깨지고 따옴표 짝이 어긋나 스크립트가 통째로 파싱 실패합니다.
    실제로 VM에-올리기.ps1 이 이랬습니다.

        '&&' 토큰은 이 버전에서 올바른 문 구분 기호가 아닙니다
        'bash scripts/?릴?리-만들?sh 2>&1 | sed ...

    PowerShell 7(pwsh)은 BOM 없이도 UTF-8 로 읽지만, 팀원이 무엇을 쓸지
    모릅니다. BOM 을 붙여 둡니다.
    """
    BOM = bytes([0xEF, 0xBB, 0xBF])
    한글없음, BOM없음 = [], []
    for p in ps1들():
        b = p.read_bytes()
        이름 = p.relative_to(ROOT).as_posix()
        if b.startswith(BOM):
            continue
        # 아스키만 있으면 BOM 이 없어도 안 깨집니다.
        try:
            b.decode("ascii")
            한글없음.append(이름)
        except UnicodeDecodeError:
            BOM없음.append(이름)
    assert not BOM없음, (
        "한글이 든 .ps1 에 BOM 이 없습니다. PowerShell 5.1 이 못 읽습니다: "
        + " · ".join(BOM없음))


def test_powershell_이_ps1_을_읽을_수_있나():
    """파싱만 합니다. 실행은 안 합니다."""
    ps = shutil.which("powershell") or shutil.which("pwsh")
    if not ps or not ps1들():
        return
    깨진것 = []
    for p in ps1들():
        코드 = (
            "$e=$null;"
            "[void][System.Management.Automation.Language.Parser]::ParseFile("
            f"'{p}',[ref]$null,[ref]$e);"
            "if($e.Count){exit 1}else{exit 0}")
        r = subprocess.run([ps, "-NoProfile", "-Command", 코드],
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if r.returncode != 0:
            깨진것.append(p.relative_to(ROOT).as_posix())
    assert not 깨진것, "PowerShell 이 못 읽습니다: " + " · ".join(깨진것)



def test_올릴_때_두드린_자취를_안_지운다():
    """`rm -rf ~/darkchoco` 가 hub/data 까지 지우고 있었습니다.

    거기에 「이 곳을 연달아 몇 번 못 두드렸나」가 들어 있습니다. 지워지면
    백오프가 **영영 안 걸립니다.** 매 판 461줄을 30초씩 다시 기다립니다.

    **오류가 안 납니다.** 크롤러는 잘 돌고, 그냥 계속 느립니다. 그래서
    눈으로는 못 찾습니다.
    """
    글 = (ROOT / "scripts" / "VM에-올리기.ps1").read_text(encoding="utf-8-sig")

    assert "rm -rf ~/darkchoco" in 글, "올리는 줄을 못 찾았습니다"

    # ① 저장소 밖으로 빼 두고 되돌려야 합니다
    assert "darkchoco-data" in 글, (
        "hub/data 를 저장소 밖에 안 빼 둡니다. rm -rf 에 같이 지워집니다")
    앞뒤 = 글[글.index("darkchoco-data"):]
    assert "cp -a ~/darkchoco/hub/data/." in 앞뒤, "빼 두는 줄이 없습니다"
    assert "cp -a ~/darkchoco-data/." in 앞뒤, "되돌리는 줄이 없습니다"

    # ② 내 PC 자취를 VM 것 위에 덮으면 안 됩니다
    assert "--exclude=./hub/data" in 글, (
        "묶음에 hub/data 가 들어갑니다. 내 PC 자취가 VM 것을 덮습니다")

    # ③ 순서가 맞아야 합니다. 되돌리기가 rm 뒤에 와야 합니다
    빼기 = 글.index("cp -a ~/darkchoco/hub/data/.")
    지우기 = 글.index("rm -rf ~/darkchoco &&")
    되돌리기 = 글.index("cp -a ~/darkchoco-data/.")
    assert 빼기 < 지우기 < 되돌리기, (
        f"순서가 틀렸습니다: 빼기 {빼기} · 지우기 {지우기} · 되돌리기 {되돌리기}")


def test_백오프가_쓰는_자리를_스크립트가_안다():
    """코드가 쓰는 경로와 스크립트가 지키는 경로가 같아야 합니다."""
    import sys as _sys
    _sys.path.insert(0, str(ROOT))
    from hub.places.run import 기본_표                       # noqa: PLC0415
    자리 = 기본_표().relative_to(ROOT).as_posix()
    assert 자리.startswith("hub/data/"), 자리
    글 = (ROOT / "scripts" / "VM에-올리기.ps1").read_text(encoding="utf-8-sig")
    assert "hub/data" in 글, f"코드는 {자리} 를 쓰는데 스크립트가 모릅니다"

if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_"):
            v()
            print(f"  OK  {k}")
            n += 1
    print(f"\n{n}개 통과")
