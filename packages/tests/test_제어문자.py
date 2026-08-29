"""스크립트의 문자열 안에 제어문자가 끼어 있는지 봅니다.

파이썬으로 파일을 고칠 때 역슬래시가 한 겹 벗겨지면 이스케이프가
실제 제어문자가 됩니다. 문법 오류가 안 나고 값만 틀립니다. 눈으로도
안 보입니다.

실제로 두 번 겪었습니다.

    "System32" + 역슬래시 + "tar.exe"   →  "System32" + 탭 + "ar.exe"
        Test-Path 가 "C:\\WINDOWS\\System32<탭>ar.exe" 를 찾다 실패
    정규식의 단어 경계                    →  백스페이스 문자
        "Members: 349,000" 을 못 찾아 포럼 회원수가 통째로 빔

둘 다 파일을 만들고 안 돌려 보면 못 잡습니다.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

_건너뜀 = {".venv", "venv", "node_modules", ".git", "__pycache__",
        "site-packages", ".tox", ".mypy_cache", ".pytest_cache"}

_볼끝 = {".sh", ".ps1", ".py"}

# 글자 사이에 끼면 안 되는 것들입니다. 줄 앞의 들여쓰기 탭은 봐 줍니다.
_나쁜것 = {8: "백스페이스", 11: "세로탭", 12: "폼피드", 0: "널",
        27: "이스케이프", 7: "벨"}


def 파일들() -> list[Path]:
    나온것, 스택 = [], [ROOT]
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
                elif x.suffix in _볼끝:
                    나온것.append(x)
            except OSError:
                continue
    return sorted(나온것)


def test_볼_파일이_있다():
    assert 파일들(), "볼 파일이 없습니다"


def test_제어문자가_안_끼어_있다():
    걸린것 = []
    for p in 파일들():
        try:
            글 = p.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            continue
        for i, 줄 in enumerate(글.splitlines(), 1):
            for 코드, 이름 in _나쁜것.items():
                if chr(코드) in 줄:
                    걸린것.append(
                        f"{p.relative_to(ROOT).as_posix()}:{i} {이름}({코드})")
                    break
    assert not 걸린것, (
        "문자열 안에 제어문자가 들어갔습니다. 값이 조용히 틀립니다.\n  "
        + "\n  ".join(걸린것[:10]))


def test_글자_사이에_탭이_안_낀다():
    """줄 앞 들여쓰기는 봐 주고, 글자 사이에 낀 탭만 봅니다."""
    탭 = chr(9)
    걸린것 = []
    for p in 파일들():
        if p.suffix == ".py":
            continue                    # 파이썬은 탭 들여쓰기를 쓸 수 있습니다
        try:
            글 = p.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            continue
        for i, 줄 in enumerate(글.splitlines(), 1):
            몸통 = 줄.lstrip(" " + 탭)
            if 탭 in 몸통:
                걸린것.append(f"{p.relative_to(ROOT).as_posix()}:{i}")
    assert not 걸린것, (
        "글자 사이에 탭이 끼었습니다. 경로나 정규식이 조용히 틀립니다.\n  "
        + "\n  ".join(걸린것[:10]))


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_"):
            v()
            print(f"  OK  {k}")
            n += 1
    print(f"\n{n}개 통과")
