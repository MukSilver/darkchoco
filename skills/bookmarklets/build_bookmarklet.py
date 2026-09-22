#!/usr/bin/env python3
"""읽는 소스(.js)를 북마클릿 한 줄(.txt)로 만든다.

문법 검사를 통과해야만 파일을 쓴다. 실패하면 옛 txt를 그대로 둔다.
손으로 만들다가 js만 고치고 txt를 안 고치는 일을 막으려는 것이다.

    python bookmarklets/build_bookmarklet.py                       킷 둘
    python bookmarklets/build_bookmarklet.py bookmarklets/qilin_kit.js   소스 하나만
    python bookmarklets/build_bookmarklet.py --no-check             node 없을 때
    python bookmarklets/build_bookmarklet.py --raw                  최소화 없이

foo.js  ->  foo.bookmarklet.txt

**인자를 안 주면 `build_kit.py` 가 만든 킷 둘만 만든다.** 전에는 폴더 안
`.js` 전부를 훑어서 소스 다섯의 `.txt` 도 같이 났다. 쓰지도 않는 낱개
파일이 일곱 개 쌓였고, 지워도 다음 빌드에서 되살아났다.

소스 하나를 낱개로 만들 일이 있으면 경로를 직접 준다. 그 길은 살아 있다.

**순서가 있다.** 소스를 고쳤으면 `build_kit.py` 를 먼저 돌린다. 안 그러면
이 도구가 옛 킷을 다시 감쌀 뿐인데 화면에는 「만듦」 이라고 찍힌다.
성공처럼 보이는 실패라서, 그럴 때 경고를 찍는다.

**terser 가 있으면 최소화한다.** 변수명까지 줄여 절반이 된다.
없으면 줄만 합친다. 없다고 멈추지 않는다.

최소화하면 사람이 못 읽는다. 그래서 소스를 레포에 둔다.
forum_kit 이 소스를 잃었던 것이 그 규칙이 없어서였다.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIMIT = 60_000          # 이보다 길면 브라우저 주소 칸에서 잘릴 수 있다
NODE_TIMEOUT = 30

# 킷 목록은 build_kit.py 가 들고 있다. 여기서 또 적지 않는다
sys.path.insert(0, str(HERE))
from build_kit import KITS, MODS, 킷파일       # noqa: E402


def to_one_line(src: str) -> str:
    """머리 주석을 떼고 한 줄로 만든다."""
    body = re.sub(r"^\s*/\*.*?\*/\s*", "", src, flags=re.S)
    body = re.sub(r"\n\s*", " ", body)
    body = re.sub(r"\s{2,}", " ", body)
    return "javascript:" + body.strip()


def escape_percent(url: str) -> str:
    """코드 안의 `%` 를 `%25` 로 바꾼다. **이걸 안 하면 킷이 조용히 안 돈다.**

    `javascript:` 도 URL 이라 브라우저가 실행하기 전에 퍼센트 인코딩을 푼다.
    나머지 연산자가 뒤 두 글자와 붙어 다른 글자로 바뀐다.

        e%3600/60      %36 이 '6' 으로 풀려서   e600/60      문법 오류
        e%60+"초"       %60 이 '`' 로 풀려서     e`+"초"       문법 오류

    2026-08-27 에 겪었다. 조사 킷과 사진 킷과 목록 킷이 눌러도 아무 반응이 없었고
    콘솔에도 아무것도 안 찍혔다. 길이 문제로 오해했다.

    **전체를 URL 인코딩하지 않는다.** 킷에 한글이 많아 두 배가 넘게 부푼다.
    `%` 만 바꾸면 열한 자에 스물두 자가 는다."""
    head, code = url[:len("javascript:")], url[len("javascript:"):]
    return head + code.replace("%", "%25")


def minify(src: str) -> tuple[str, str]:
    """terser 로 줄인다. (결과, 어떻게 했나). 못 부르면 원본을 그대로 준다."""
    tmp = Path(tempfile.gettempdir()) / "_bookmarklet_min.js"
    tmp.write_text(src, encoding="utf-8")
    out = Path(tempfile.gettempdir()) / "_bookmarklet_min.out.js"
    try:
        p = subprocess.run(
            ["npx", "-y", "terser", str(tmp), "-c", "-m", "-o", str(out)],
            capture_output=True, timeout=180, encoding="utf-8",
            errors="replace", shell=(sys.platform == "win32"))
        if p.returncode == 0 and out.exists():
            r = out.read_text(encoding="utf-8")
            if r.strip():
                return r, "terser"
        return src, "terser 실패. 줄만 합침"
    except FileNotFoundError:
        return src, "terser 없음. 줄만 합침"
    except subprocess.TimeoutExpired:
        return src, "terser 가 180초를 넘김. 줄만 합침"
    finally:
        tmp.unlink(missing_ok=True)
        out.unlink(missing_ok=True)


def line_comments(src: str) -> list[int]:
    """// 주석을 찾는다. 줄 맨 앞이든 줄 끝이든 한 줄로 합치면 뒤가 통째로 죽는다."""
    out = []
    for i, l in enumerate(src.split("\n"), 1):
        if l.lstrip().startswith("//"):
            out.append(i)
        elif "://" not in l and re.search(r"(^|[^:/\\])//[^/]", l):
            out.append(i)          # 줄 끝 주석. 정규식 안의 \/\/ 는 뺀다
    return out


def node_check(code: str) -> tuple[bool, str]:
    """node --check 로 문법을 본다. node가 없으면 (None, 사유)."""
    tmp = Path(tempfile.gettempdir()) / "_bookmarklet_check.js"
    tmp.write_text(code, encoding="utf-8")
    try:
        p = subprocess.run(["node", "--check", str(tmp)],
                           capture_output=True, timeout=NODE_TIMEOUT,
                           encoding="utf-8", errors="replace")
        return p.returncode == 0, p.stderr.strip()
    except FileNotFoundError:
        return None, "node를 못 찾았다"
    except subprocess.TimeoutExpired:
        return False, f"node --check 가 {NODE_TIMEOUT}초를 넘겼다"
    finally:
        tmp.unlink(missing_ok=True)


SHELL_MARK = "/* @shell */"
SHELL_SRC = HERE / "kit_shell.js"


def put_shell(src: str) -> str:
    """`/* @shell */` 자리에 공통 껍데기를 넣는다.

    따로 쓰는 킷은 혼자 돌아야 하므로 껍데기가 파일 안에 있어야 한다.
    통합 킷은 build_kit.py 가 껍데기를 맨 앞에 한 번만 두고 이 표시를 지운다.
    """
    if SHELL_MARK not in src:
        return src
    if not SHELL_SRC.exists():
        raise SystemExit("공통 껍데기가 없다: %s" % SHELL_SRC)
    return src.replace(SHELL_MARK, SHELL_SRC.read_text(encoding="utf-8"), 1)


def build(js: Path, do_check: bool, raw: bool = False) -> bool:
    out = js.with_suffix("")
    out = out.with_name(out.name + ".bookmarklet.txt")
    src = put_shell(js.read_text(encoding="utf-8"))

    bad = line_comments(src)
    if bad:
        print(f"  건너뜀  // 주석이 있다: {bad[:8]}번 줄")
        print(f"          한 줄로 합치면 뒤가 통째로 주석이 된다. /* */ 로 바꿀 것")
        return False

    one = to_one_line(src)
    how = "줄만 합침"

    if not raw:
        code = one[len("javascript:"):]
        small, how = minify(code)
        if len(small) < len(code):
            one = "javascript:" + small.strip()

    if do_check:
        ok, err = node_check(one[len("javascript:"):])
        if ok is None:
            print(f"  건너뜀  {err}. 검사 없이 만들려면 --no-check")
            return False
        if not ok:
            print(f"  건너뜀  문법 오류. 옛 txt를 그대로 둔다")
            for l in err.split("\n")[:6]:
                print(f"          {l}")
            return False

    code_before = one[len("javascript:"):]
    one = escape_percent(one)

    # 브라우저가 푸는 것과 우리가 넣은 것이 같은지 본다. 다르면 조용히 안 돈다
    got = urllib.parse.unquote(one[len("javascript:"):], errors="strict")
    if got != code_before:
        print("  건너뜀  URL 로 풀면 코드가 달라진다. 옛 txt를 그대로 둔다")
        for i, (a, b) in enumerate(zip(code_before, got)):
            if a != b:
                print("          %d번째 글자부터: %r 이 %r 로 바뀐다"
                      % (i, code_before[i:i + 12], got[i:i + 12]))
                break
        return False

    warn = "  (주소 칸에서 잘릴 수 있다)" if len(one) > LIMIT else ""
    before = len(out.read_text(encoding="utf-8")) if out.exists() else 0
    out.write_text(one, encoding="utf-8")
    delta = f"{before:,} -> " if before else ""
    print(f"  만듦    {out.name}  {delta}{len(one):,}자  [{how}]{warn}")
    return True


def _낡았나(킷들: list[Path]) -> None:
    """소스가 킷보다 새것이면 알린다. 멈추지는 않는다.

    **이 경고가 없으면 조용히 물린다.** 소스를 고치고 이 도구만 돌리면
    옛 킷을 다시 감쌀 뿐인데 화면에는 「만듦」 이라고 찍힌다. 무엇이
    틀렸는지 알 길이 없어서, 브라우저에서 옛 동작을 보고서야 알게 된다.
    """
    소스들 = [HERE / src for _, _, src, _ in MODS] + [HERE / "kit_shell.js"]
    새것 = max((p.stat().st_mtime for p in 소스들 if p.exists()), default=0)
    낡은킷 = [k.name for k in 킷들
              if k.exists() and k.stat().st_mtime < 새것]
    if 낡은킷:
        print("!! 소스가 킷보다 새것이다 — %s" % " · ".join(낡은킷))
        print("   python bookmarklets/build_kit.py 를 먼저 돌려라.")
        print("   안 그러면 옛 코드가 담긴 .txt 가 나온다.\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*",
                    help="비우면 build_kit.py 가 만든 킷 둘")
    ap.add_argument("--no-check", action="store_true", help="문법 검사를 건너뛴다")
    ap.add_argument("--raw", action="store_true", help="최소화 없이 줄만 합친다")
    args = ap.parse_args()

    if args.files:
        targets = [Path(f) for f in args.files]
    else:
        targets = [HERE / 킷파일(k) for k in KITS]
        _낡았나(targets)
    if not targets:
        raise SystemExit("만들 .js 가 없다")

    made = 0
    for js in targets:
        if not js.exists():
            print(f"{js}\n  없는 파일")
            continue
        print(js.name)
        made += build(js, not args.no_check, args.raw)

    print(f"\n{made}/{len(targets)} 개 만듦")
    if made < len(targets):
        sys.exit(1)


if __name__ == "__main__":
    main()
