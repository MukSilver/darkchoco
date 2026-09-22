"""PR 이 최현서 자리를 고쳤는지 봅니다.

**실패시키지 않습니다.** 고쳐야 할 이유가 있으면 고칩니다. 막으면 일이 멈칩니다.
보이게 하는 것이 목적이고, 알림이 떴는데 말이 없었으면 그때 묻습니다.

**2026-09-23 에 트랙 경계 검사를 뺐습니다.** 가지 이름으로 `feat/수집-*` 과
`feat/조사-*` 를 갈라 서로의 자리를 보던 부분입니다. 트랙이 둘로 줄면서 팀 레포를
한 세션이 통째로 보게 되어 늘 경고가 뜨게 됐습니다. 안 읽히는 경고는 없느니만
못합니다. `가지` 인자는 어느 PR 인지 적으려고 남겨 둡니다.

경계 정본은 `DEV.md` 0절입니다. 여기는 그것을 옮겨 적은 것이라
0절이 바뀌면 아래 표도 같이 고칩니다.

    python .github/boundary.py <가지이름> <파일목록파일>
"""
import sys
from pathlib import Path

# 윈도에서 손으로 돌릴 때 한글이 깨집니다. 러너는 UTF-8 이라 영향이 없습니다.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# 누가 고치든 최현서가 봅니다.
공용 = [
    ("packages/", "공용 부품입니다. packages/tests/ 도 여기입니다"),
    (".github/workflows/ci.yml", "공용 CI 입니다"),
    ("hub/events/push.py", "수집DB 상수와 상수 셋이 있어 대시보드 둘이 같이 깨집니다"),
]

# 파일 단위로는 못 가르는 것입니다. 이름이 보이면 알립니다.
낱말 = [
    ("dc.py", "cmd_auto",
     "cmd_auto() 는 사건 수집과 명부를 한 명령으로 묶습니다. 스케줄러가 여기만 부릅니다"),
]


def 걸린것(파일들: list[str], 디프: str = "") -> list[str]:
    """알릴 줄을 모읍니다. 없으면 빈 목록입니다."""
    난것 = []

    for 앞, 까닭 in 공용:
        맞은것 = [f for f in 파일들 if f.startswith(앞)]
        if 맞은것:
            난것.append(
                f"**`{앞}` 를 {len(맞은것)}개 고쳤습니다. 최현서 자리입니다.** {까닭}\n"
                + "\n".join(f"  - `{f}`" for f in 맞은것[:8])
                + (f"\n  - … 그리고 {len(맞은것) - 8}개" if len(맞은것) > 8 else "")
            )

    for 파일, 찾을말, 까닭 in 낱말:
        if 파일 in 파일들 and 찾을말 in 디프:
            난것.append(f"**`{파일}` 의 `{찾을말}` 가 바뀐 것 같습니다. 최현서 자리입니다.** {까닭}")

    return 난것


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print("쓰는 법: python .github/boundary.py <가지이름> <파일목록파일> [디프파일]")
        return 0

    가지 = argv[1]
    파일들 = [
        줄.strip() for 줄 in
        Path(argv[2]).read_text(encoding="utf-8").splitlines() if 줄.strip()
    ]
    디프 = ""
    if len(argv) > 3 and Path(argv[3]).exists():
        디프 = Path(argv[3]).read_text(encoding="utf-8", errors="replace")

    난것 = 걸린것(파일들, 디프)

    print(f"가지: {가지}")
    print(f"고친 파일: {len(파일들)}개")
    print()

    if not 난것:
        print("최현서 자리는 안 건드렸습니다.")
        return 0

    print("### 최현서 자리를 고쳤습니다")
    print()
    for 줄 in 난것:
        print(f"- {줄}")
        print()
    print("---")
    print()
    print("**막는 것이 아닙니다.** 고쳐야 할 이유가 있으면 고칩니다.")
    print("다만 `DEV.md` 0-0-4 대로 **손대기 전에 최현서에게 알렸어야 합니다.**")
    print("아직 안 알렸으면 지금 알리십시오.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
