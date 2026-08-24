#!/usr/bin/env python3
"""읽는 소스(.js)를 북마클릿 한 줄(.txt)로 만든다.

문법 검사를 통과해야만 파일을 쓴다. 실패하면 옛 txt를 그대로 둔다.
손으로 만들다가 js만 고치고 txt를 안 고치는 일을 막으려는 것이다.

    python bookmarklets/build_bookmarklet.py                       같은 폴더의 .js 전부
    python bookmarklets/build_bookmarklet.py bookmarklets/qilin_kit.js   하나만
    python bookmarklets/build_bookmarklet.py --no-check             node 없을 때
    python bookmarklets/build_bookmarklet.py --raw                  최소화 없이

foo.js  ->  foo.bookmarklet.txt

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
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIMIT = 60_000          # 이보다 길면 브라우저 주소 칸에서 잘릴 수 있다
NODE_TIMEOUT = 30


def to_one_line(src: str) -> str:
    """머리 주석을 떼고 한 줄로 만든다."""
    body = re.sub(r"^\s*/\*.*?\*/\s*", "", src, flags=re.S)
    body = re.sub(r"\n\s*", " ", body)
    body = re.sub(r"\s{2,}", " ", body)
    return "javascript:" + body.strip()


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


def build(js: Path, do_check: bool, raw: bool = False) -> bool:
    out = js.with_suffix("")
    out = out.with_name(out.name + ".bookmarklet.txt")
    src = js.read_text(encoding="utf-8")

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

    warn = "  (주소 칸에서 잘릴 수 있다)" if len(one) > LIMIT else ""
    before = len(out.read_text(encoding="utf-8")) if out.exists() else 0
    out.write_text(one, encoding="utf-8")
    delta = f"{before:,} -> " if before else ""
    print(f"  만듦    {out.name}  {delta}{len(one):,}자  [{how}]{warn}")
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*", help="비우면 같은 폴더의 .js 전부")
    ap.add_argument("--no-check", action="store_true", help="문법 검사를 건너뛴다")
    ap.add_argument("--raw", action="store_true", help="최소화 없이 줄만 합친다")
    args = ap.parse_args()

    targets = [Path(f) for f in args.files] if args.files else sorted(HERE.glob("*.js"))
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
