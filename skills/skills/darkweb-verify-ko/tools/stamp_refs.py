#!/usr/bin/env python3
"""참조 문서 머리에 담당·도구·개정일을 찍는다.

    python tools/stamp_refs.py           찍는다
    python tools/stamp_refs.py --check   어긋난 파일만 알리고 안 고친다

**왜 필요한가.** 노션 사본과 깃허브 정본이 갈린 전력이 있다.
날짜가 적혀 있으면 어느 쪽이 최신인지 파일만 보고 안다.

**왜 손으로 안 적나.** 손으로 적은 날짜는 반드시 낡는다.
낡은 날짜는 없는 것보다 나쁘다. 최신이라고 잘못 알려 준다.

개정일은 git 의 마지막 커밋 날짜다. 아직 커밋 안 한 변경이 있으면 오늘로 찍는다.
도구 줄은 문서 안의 실행 줄에서 뽑는다. 문서가 바뀌면 같이 바뀐다.
"""
import argparse
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
REFS = HERE.parent / "references"
REPO = "MukSilver/darkchoco"   # 2026-09-06 까지는 grute02/darkchoco-skills 였다. 정본이 팀 레포 skills/ 로 옮겨 갔다

# 누가 돌리는가. SKILL.md 의 단계 표와 같은 내용이다.
# 여기가 바뀌면 SKILL.md 도 같이 고친다.
WHO = {
    "stage2-post.md": "사람. 스킬을 부르기 전에 한다",
    "stage3-precheck.md": "스킬",
    "stage4-masking.md": "스킬",
    "stage5-merge.md": "스킬",
    "stage6-toolkit.md": "스킬",
    "stage7-review.md": "사람. 스킬이 끝난 뒤에 한다",
    "stage8-verdict.md": "사람. 스킬이 끝난 뒤에 한다",
    "stage9-db.md": "스킬. 따로 부른다. 노션이 있을 때만",
    "tree-analysis.md": "스킬. ② 와 ③ 에서 부른다",
    "publish.md": "스킬. ⑨ 뒤에 부른다",
    "publishers.md": "자료. 사람이 찾아본다",
    "talk-en.md": "스킬. 따로 부른다. 흐름 밖이다",
}

RUN = re.compile(r"python3? +((?:tools/)?[a-z_]+\.py)")
BLOCK = re.compile(r"^    담당 .*\n    도구 .*\n    개정 .*\n", re.M)
ADAY = re.compile(r"^    개정 (\d{4}-\d{2}-\d{2})", re.M)
# 정본이 이 저장소로 옮겨 온 날. 이 이전의 개정 이력은 여기에 없다. keep_earlier 참조.
이전날 = "2026-09-06"


def bare(s: str) -> str:
    """머리 블록과 빈 줄 차이를 없앤 본문. 견주기용이다.

    블록을 빼면 그 자리에 빈 줄이 남는다. 그것 때문에 안 바뀐 파일이
    바뀐 것으로 잡히면 개정일이 매번 오늘로 밀린다.
    """
    return re.sub(r"\n{2,}", "\n\n", BLOCK.sub("", s)).strip()


def git(args: list[str]) -> str | None:
    """git 을 부른다. 실패하면 None."""
    try:
        r = subprocess.run(["git"] + args, capture_output=True, text=True,
                           encoding="utf-8", cwd=REFS, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def git_date(p: Path, body: str) -> str:
    """본문이 마지막으로 바뀐 날. 못 찾으면 오늘.

    **마지막 커밋 날짜를 그냥 쓰지 않는다.** 머리를 찍는 커밋 때문에
    본문이 안 바뀐 파일까지 날짜가 오늘로 밀린다. 한 번 밀리면 되돌릴 수 없다.

    이력을 최신부터 거슬러 올라가며 본문이 지금과 같은 마지막 자리를 찾는다.
    머리만 바뀐 커밋은 본문이 같으므로 그냥 지나간다.
    """
    # 저장소 뿌리 기준 경로를 **git 에게 물어서** 얻는다. 박아 두면 안 된다.
    # 2026-09-06 에 정본이 팀 레포 skills/ 아래로 옮겨 가면서 뿌리 기준 경로가
    # skills/skills/darkweb-verify-ko/references/ 로 한 겹 깊어졌다. 박힌 옛 경로로는
    # git log 가 빈 값을 내고 아래 today 로 떨어져, 본문이 안 바뀐 문서 열한 개의
    # 개정일이 전부 그날로 밀렸다. 이 함수가 막으려던 바로 그 일이다.
    prefix = git(["rev-parse", "--show-prefix"]) or ""
    rel = prefix.strip() + p.name
    # `:/` 를 붙여 저장소 뿌리 기준으로 읽게 한다.
    # 안 붙이면 이 파일이 도는 폴더 기준이라 경로를 못 찾고 빈 값이 나온다.
    log = git(["log", "--format=%H %ad", "--date=short", "--", ":/" + rel])
    if not log or not log.strip():
        return date.today().isoformat()

    now = bare(body)
    found = date.today().isoformat()
    # 이력이 길어도 50개면 충분하다. 그 위로는 안 본다.
    for line in log.strip().splitlines()[:50]:
        sha, _, when = line.partition(" ")
        old = git(["show", sha + ":" + rel])
        if old is None or bare(old) != now:
            break
        found = when.strip()
    return found


def keep_earlier(p: Path, t: str, found: str) -> str:
    """이전 이전의 개정일은 파일에 적힌 것이 정본이다. 이력이 그 시절을 모른다.

    2026-09-06 에 정본이 `grute02/darkchoco-skills` 에서 팀 레포 `skills/` 로 옮겨 왔다.
    **저장소를 옮기면 이력이 그 자리에서 새로 시작한다.** 참조 문서 열한 개가 한 커밋으로
    통째로 들어와서, 이 저장소 이력만 보면 8/21 에 마지막으로 고친 문서와 8/26 에 고친 문서가
    같은 날이 된다. 뭉갠 날짜는 되돌릴 수 없다. 그 시절은 파일에 적힌 값이 유일한 기록이다.

    **이전 날 이후는 이 저장소가 안다.** 그러니 계산값이 이전 날보다 뒤면 그것을 쓴다.
    안 그러면 본문을 새로 고쳐도 개정일이 옛 날짜에 얼어붙는다. 적힌 날짜가 전부 이전 날
    이후가 되면 이 함수는 하는 일이 없어진다.
    """
    m = ADAY.search(t)
    적힘 = m.group(1) if m else ""
    if not 적힘 or 적힘 >= 이전날:
        return found
    return found if found > 이전날 else 적힘


def tools_of(body: str) -> str:
    """문서 안의 실행 줄에서 도구를 뽑는다."""
    found = sorted({m if m.startswith("tools/") else "tools/" + m
                    for m in RUN.findall(body)})
    return " · ".join(found) if found else "없음"


def stamp(p: Path, check: bool) -> bool:
    """찍는다. 바뀌었으면 True."""
    t = p.read_text(encoding="utf-8")
    lines = t.split("\n")
    if not lines or not lines[0].startswith("# "):
        print("  건너뜀  %s  (첫 줄이 제목이 아니다)" % p.name)
        return False

    body = BLOCK.sub("", t)
    block = "    담당 %s\n    도구 %s\n    개정 %s · 정본은 %s\n" % (
        WHO.get(p.name, "확인 필요"), tools_of(body),
        keep_earlier(p, t, git_date(p, body)), REPO)

    rest = "\n".join(lines[1:]).lstrip("\n")
    rest = BLOCK.sub("", rest).lstrip("\n")
    new = lines[0] + "\n\n" + block + "\n" + rest

    if new == t:
        return False
    if not check:
        p.write_text(new, encoding="utf-8")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="참조 문서 머리에 담당·도구·개정일을 찍는다")
    ap.add_argument("--check", action="store_true", help="고치지 않고 어긋난 것만 알린다")
    args = ap.parse_args()

    if not REFS.is_dir():
        print("references 폴더가 없다: %s" % REFS, file=sys.stderr)
        return 2

    changed = [p.name for p in sorted(REFS.glob("*.md")) if stamp(p, args.check)]
    if args.check:
        if changed:
            print("머리가 어긋난 파일 %d" % len(changed))
            for n in changed:
                print("  " + n)
            print("\n    python tools/stamp_refs.py")
            return 1
        print("머리가 다 맞다")
        return 0
    print("찍음 %d / %d" % (len(changed), len(list(REFS.glob("*.md")))))
    for n in changed:
        print("  " + n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
