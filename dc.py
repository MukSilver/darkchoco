#!/usr/bin/env python3
"""다크초코 툴킷의 입구.

    python dc.py list                 어떤 도구가 있는지 봅니다
    python dc.py info <이름>          그 도구를 어떻게 쓰는지 봅니다
    python dc.py doctor [이름]        지금 돌 수 있는 상태인지 봅니다
    python dc.py readme --check       README 의 도구 표가 최신인지 봅니다
    python dc.py readme --write       README 의 도구 표를 다시 씁니다

도구를 대신 실행하지 않습니다. 무엇을 치면 되는지 알려 줄 뿐입니다.
각 도구는 만든 사람이 소유하고, 이 파일은 목록과 상태만 봅니다.

표준 라이브러리만 씁니다. 받을 것이 없습니다.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except (AttributeError, ValueError):
        pass

표시 = {"host": "내 PC", "docker": "도커", "vm": "VM"}


# ── 읽기 ────────────────────────────────────────────────────────────
def 도구들() -> list[dict]:
    """tool.json 을 전부 찾아 읽습니다. 이름 순으로 돌려줍니다."""
    out = []
    for p in sorted(ROOT.rglob("tool.json")):
        if ".git" in p.parts:
            continue
        try:
            spec = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"[!] {p.relative_to(ROOT)} 를 못 읽습니다: {e}", file=sys.stderr)
            continue
        spec["_dir"] = p.parent
        spec["_rel"] = p.parent.relative_to(ROOT).as_posix()
        out.append(spec)
    return sorted(out, key=lambda s: s.get("name", ""))


def 하나(name: str) -> dict | None:
    for t in 도구들():
        if t.get("name") == name:
            return t
    return None


def 비밀값수(t: dict) -> int:
    """꼭 채워야 하는 비밀값의 수입니다. 선택은 안 셉니다."""
    return sum(1 for s in t.get("secrets", []) if not s.get("optional"))


def 설치필요(t: dict) -> bool:
    inst = t.get("install") or {}
    return bool(inst.get("requirements"))


# ── list ────────────────────────────────────────────────────────────
def 폭(s: str) -> int:
    """한글은 두 칸으로 셉니다."""
    return sum(2 if ord(c) > 0x1100 else 1 for c in s)


def 채움(s: str, n: int) -> str:
    return s + " " * max(0, n - 폭(s))


def cmd_list(args) -> int:
    ts = 도구들()
    print(f"\n도구 {len(ts)}개\n")
    머리 = [("이름", 19), ("담당", 8), ("설치", 6), ("비밀값", 8), ("어디서", 8)]
    print("  " + "".join(채움(h, w) for h, w in 머리) + "무엇을 하나")
    print("  " + "─" * 78)
    for t in ts:
        칸 = [
            (t.get("name", "?"), 19),
            (t.get("owner", "-"), 8),
            ("필요" if 설치필요(t) else "없음", 6),
            (f"{비밀값수(t)}곳", 8),
            (표시.get(t.get("runs_in", "host"), t.get("runs_in", "-")), 8),
        ]
        print("  " + "".join(채움(v, w) for v, w in 칸) + t.get("summary", ""))
    print("\n  자세히:  python dc.py info <이름>")
    print("  상태:    python dc.py doctor <이름>\n")
    return 0


# ── info ────────────────────────────────────────────────────────────
def cmd_info(args) -> int:
    t = 하나(args.name)
    if not t:
        print(f"'{args.name}' 이라는 도구가 없습니다. python dc.py list 를 보십시오.",
              file=sys.stderr)
        return 1

    print(f"\n{t['name']}   {t.get('owner','-')} ({t.get('github','-')})")
    print(f"  폴더      {t['_rel']}")
    if t.get("docs"):
        print(f"  문서      {t['_rel']}/{t['docs']}")
    if t.get("license"):
        print(f"  라이선스  {t['license']}  (루트는 Apache-2.0 입니다. NOTICE 를 보십시오)")

    cmds = t.get("commands", {})
    기본 = t.get("default")
    if cmds:
        print("\n  명령")
        for k, v in cmds.items():
            print(f"    {'*' if k == 기본 else ' '} {채움(k, 9)}{v}")

    print(f"\n  작업 위치  {t['_rel']}" + (f"/{t['run_cwd']}" if t.get("run_cwd") not in (None, ".") else ""))

    inst = t.get("install") or {}
    받을것 = inst.get("requirements") or "없음"
    print(f"  받을 것    {받을것}")
    if inst.get("note"):
        print(f"             {inst['note']}")

    pre = t.get("preconditions") or {}
    필요 = [k for k, v in pre.items() if v]
    if 필요:
        print("  미리 필요  " + " · ".join(
            f"{k}({v})" if isinstance(v, str) else k for k, v in pre.items() if v))

    sec = t.get("secrets") or []
    if sec:
        print("  비밀값")
        for s in sec:
            꼬리 = "  (선택)" if s.get("optional") else ""
            print(f"    {채움(s['key'], 22)}{s.get('where','')}{꼬리}")
    else:
        print("  비밀값     없음")

    cfg = t.get("config_files") or []
    for c in cfg:
        ex = f"  ← {c['example']} 를 복사합니다" if c.get("example") else ""
        print(f"  설정 파일  {c['path']}{ex}")
        if c.get("note"):
            print(f"             {c['note']}")

    if t.get("packages"):
        print(f"  쓰는 부품  {' · '.join(t['packages'])}")
    if t.get("output"):
        print(f"  결과       {t['output']}")
    if t.get("note"):
        print(f"\n  알아 둘 것 {t['note']}")
    print()
    return 0


# ── doctor ──────────────────────────────────────────────────────────
def _requirements(t: dict) -> list[str]:
    """이 도구가 받아야 하는 것들. requirements.txt 와 직접 적은 것을 합칩니다."""
    inst = t.get("install") or {}
    out = list(inst.get("packages") or [])      # requirements.txt 없이 적는 경우
    name = inst.get("requirements")
    if not name:
        return out
    p = t["_dir"] / name
    if not p.is_file():
        return out
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.split("#")[0].strip()
        if not line:
            continue
        out.append(re.split(r"[<>=\[;!]", line)[0].strip())
    return out


def _깔렸나(mod: str) -> bool:
    별칭 = {"Telethon": "telethon", "qrcode[pil]": "qrcode", "pyyaml": "yaml",
            "defusedxml": "defusedxml", "python-dotenv": "dotenv"}
    이름 = 별칭.get(mod, mod).replace("-", "_").lower()
    try:
        return importlib.util.find_spec(이름) is not None
    except (ImportError, ValueError):
        return False


def _비밀값있나(key: str, d: Path) -> bool:
    if os.environ.get(key):
        return True
    for name in (".env", ".env.local"):
        f = d / name
        if f.is_file():
            txt = f.read_text(encoding="utf-8", errors="replace")
            if re.search(rf"^\s*{re.escape(key)}\s*=\s*\S", txt, re.M):
                return True
    return False


def _한도구(t: dict) -> int:
    """걸린 것의 수를 돌려줍니다."""
    d, 걸림 = t["_dir"], []
    print(f"\n[{t['name']}]")
    print(f"  파이썬     {sys.version.split()[0]}")

    reqs = _requirements(t)
    if reqs:
        빠짐 = [m for m in reqs if not _깔렸나(m)]
        if 빠짐:
            print(f"  깔림       " + " · ".join(f"{m} 없음" for m in 빠짐) + "        ← 여기서 막힙니다")
            걸림.append("설치")
        else:
            print(f"  깔림       {len(reqs)}개 전부 있음")
    else:
        print("  받을 것    없음")

    pre = t.get("preconditions") or {}
    for k, v in pre.items():
        if not v:
            continue
        꼬리 = f" ({v})" if isinstance(v, str) else ""
        print(f"  미리 필요  {k}{꼬리} — 이 검사는 안 합니다. 직접 확인하십시오")

    sec = [s for s in t.get("secrets", []) if not s.get("optional")]
    if sec:
        빈것 = [s["key"] for s in sec if not _비밀값있나(s["key"], d)]
        if 빈것:
            print("  비밀값     " + " · ".join(f"{k} 비어 있음" for k in 빈것))
            걸림.append("비밀값")
        else:
            print(f"  비밀값     {len(sec)}개 전부 있음")
    else:
        print("  비밀값     없음. 안 채워도 됩니다")

    for c in t.get("config_files", []):
        f = d / c["path"]
        if f.exists():
            print(f"  설정 파일  {c['path']} 있음")
        elif c.get("example") and (d / c["example"]).exists():
            print(f"  설정 파일  {c['path']} 없음 — {c['example']} 를 복사하십시오")
            걸림.append("설정")
        else:
            print(f"  설정 파일  {c['path']} 없음")
            걸림.append("설정")

    안내 = _어떻게(t, 걸림)
    if 안내:
        print(f"  이렇게 하십시오:  {안내}")
    print(f"\n  걸린 것 {len(걸림)}개" if 걸림 else "\n  바로 돌 수 있습니다")
    return len(걸림)


def _어떻게(t: dict, 걸림: list[str]) -> str:
    if not 걸림:
        return ""
    if t["name"] == "kr-leak-alarm":
        return "apps\\kr-leak-alarm\\scripts\\run.bat"
    조각 = []
    if "설치" in 걸림:
        조각.append(f"pip install -r {t['_rel']}/{(t.get('install') or {}).get('requirements')}")
    if "설정" in 걸림:
        for c in t.get("config_files", []):
            if c.get("example") and not (t["_dir"] / c["path"]).exists():
                조각.append(f"copy {t['_rel']}/{c['example']} {t['_rel']}/{c['path']}")
    if "비밀값" in 걸림:
        조각.append(f"python dc.py info {t['name']}  으로 어디서 받는지 보십시오")
    return "  그리고  ".join(조각)


def cmd_doctor(args) -> int:
    ts = [하나(args.name)] if args.name else 도구들()
    if args.name and not ts[0]:
        print(f"'{args.name}' 이라는 도구가 없습니다.", file=sys.stderr)
        return 1
    총 = sum(_한도구(t) for t in ts if t)
    if not args.name:
        print(f"\n─ 전체에서 걸린 것 {총}개\n")
    else:
        print()
    return 0


# ── readme ──────────────────────────────────────────────────────────
시작, 끝 = "<!-- 도구표 시작 -->", "<!-- 도구표 끝 -->"


def _표() -> str:
    줄 = ["| 도구 | 담당 | 설치 | 비밀값 | 어디서 | 무엇을 하나 |",
          "|---|---|:-:|:-:|:-:|---|"]
    for t in 도구들():
        줄.append(
            f"| [{t['name']}]({t['_rel']}) | {t.get('owner','-')} "
            f"| {'필요' if 설치필요(t) else '없음'} | {비밀값수(t)}곳 "
            f"| {표시.get(t.get('runs_in','host'), '-')} | {t.get('summary','')} |")
    return "\n".join(줄)


def cmd_readme(args) -> int:
    p = ROOT / "README.md"
    s = p.read_text(encoding="utf-8")
    if 시작 not in s or 끝 not in s:
        print(f"README.md 에 {시작} 과 {끝} 이 없습니다. 그 사이에 표가 들어갑니다.",
              file=sys.stderr)
        return 1
    앞, 뒤 = s.split(시작)[0], s.split(끝)[1]
    새것 = 앞 + 시작 + "\n" + _표() + "\n" + 끝 + 뒤
    if args.write:
        p.write_text(새것, encoding="utf-8")
        print(f"README.md 의 도구 표를 다시 썼습니다. 도구 {len(도구들())}개")
        return 0
    if 새것 != s:
        print("README.md 의 도구 표가 tool.json 과 다릅니다.")
        print("  python dc.py readme --write  로 맞추십시오.")
        return 1
    print("README.md 의 도구 표가 최신입니다.")
    return 0


# ── ── ──
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="dc.py", description="다크초코 툴킷의 입구",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="도구를 대신 실행하지 않습니다. 무엇을 치면 되는지 알려 줍니다.")
    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("list", help="어떤 도구가 있는지 봅니다").set_defaults(fn=cmd_list)

    p = sub.add_parser("info", help="그 도구를 어떻게 쓰는지 봅니다")
    p.add_argument("name")
    p.set_defaults(fn=cmd_info)

    p = sub.add_parser("doctor", help="지금 돌 수 있는 상태인지 봅니다")
    p.add_argument("name", nargs="?")
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("readme", help="README 의 도구 표를 보거나 다시 씁니다")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--write", action="store_true")
    p.set_defaults(fn=cmd_readme)

    args = ap.parse_args(argv)
    if not getattr(args, "fn", None):
        ap.print_help()
        return 0
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
