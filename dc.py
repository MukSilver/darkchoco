#!/usr/bin/env python3
"""다크초코 툴킷의 입구.

    python dc.py list                 어떤 도구가 있는지 봅니다
    python dc.py info <이름>          그 도구를 어떻게 쓰는지 봅니다
    python dc.py doctor [이름]        지금 돌 수 있는 상태인지 봅니다
    python dc.py crawl [--apply]      명부를 조사해 노션에 반영합니다
    python dc.py auto                 수집 + 명부 조사 (스케줄러가 부릅니다)
    python dc.py run [--only 이름]    수집을 한 판 돌립니다
    python dc.py plan                 무엇이 언제 도는지 봅니다
    python dc.py run --due            주기가 찬 것만 돌립니다
    python dc.py install-task         스케줄러에 겁니다
    python dc.py readme --check       README 의 도구 표가 최신인지 봅니다
    python dc.py readme --write       README 의 도구 표를 다시 씁니다

list · info · doctor 는 도구를 대신 실행하지 않습니다. 무엇을 치면 되는지
알려 줄 뿐입니다. 각 도구는 만든 사람이 소유합니다.

run 은 다릅니다. hub/events/sources 에 등록된 것만 부르고, 결과를 한 표에 넣습니다.
어댑터는 원래 도구를 감싼 얇은 물건이라 그 도구의 방어가 그대로 삽니다.

이 파일 자체는 표준 라이브러리만 씁니다. run 이 부르는 어댑터는 각자
필요한 것을 밝히고, 없으면 그 어댑터만 건너뜁니다.
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
# 안 뒤질 폴더입니다. 우리가 쓴 것이 아니라 받아 온 것들입니다.
# .venv 를 리눅스에서 만들면 심볼릭 링크가 들어 있어 윈도우 파이썬이
# rglob 중에 죽습니다 — OSError: [WinError 1920]. 실제로 WSL 에서
# .venv 를 만든 뒤 윈도우에서 dc.py 가 통째로 안 돌았습니다.
_안뒤짐 = {".git", ".venv", "venv", "node_modules", "__pycache__",
        "site-packages", ".tox", ".mypy_cache", ".pytest_cache"}


def _tool_json찾기():
    """tool.json 을 찾습니다. 못 읽는 곳은 건너뜁니다."""
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
                    if x.name not in _안뒤짐 and not x.is_symlink():
                        스택.append(x)
                elif x.name == "tool.json":
                    나온것.append(x)
            except OSError:
                continue                # 심볼릭 링크가 깨진 것 등
    return sorted(나온것)


def _눌러(*조각: str) -> str:
    """`hub/../docs/흐름.md` 를 `docs/흐름.md` 로 눌러 줍니다.

    tool.json 의 경로는 그 도구 폴더 기준입니다. 그런데 저장소 뿌리에서
    돌리는 도구는 `run_cwd` 가 `..` 이라 화면에 `hub/..` 이 그대로
    나옵니다. 사람이 그걸 그대로 쳐도 되긴 하는데 읽기 나쁩니다.
    """
    import posixpath
    붙임 = posixpath.join(*[c for c in 조각 if c and c != "."])
    return posixpath.normpath(붙임) if 붙임 else "."


def 도구들() -> list[dict]:
    """tool.json 을 전부 찾아 읽습니다. 이름 순으로 돌려줍니다."""
    out = []
    for p in _tool_json찾기():
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
        print(f"  문서      {_눌러(t['_rel'], t['docs'])}")
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
    # 밖으로 나가는 길은 도구 하나의 사정이 아니라 크롤러 전체의 조건입니다.
    _나가는길(args.net)
    return 0

def _나가는길(자세히: bool = False) -> int:
    """밖으로 나갈 때 어떤 주소가 남는지 봅니다.

    다크웹 쪽을 여는 일은 저쪽 로그에 우리 주소를 남기는 일입니다.
    남는 것이 한국 주소이면 우리가 누구인지 좁혀집니다.
    """
    from hub.places import egress

    print()
    print("  ── 밖으로 나가는 길 ──")
    프록시 = egress.프록시주소()
    뺀것 = egress.뺀갈래()

    if not 프록시:
        if egress.맨연결_허락():
            print("  !! 맨 연결을 허락한 상태입니다 (DARKCHOCO_ALLOW_DIRECT=1)")
            print("     우리 IP 가 그대로 남습니다.")
        else:
            print("  Tor 가 없습니다. 크롤러가 밖으로 안 나갑니다.")
        print()
        for 줄 in egress.안내.splitlines():
            print("  " + 줄)
        print()
        return 1

    print(f"  프록시   {프록시}")
    if 뺀것:
        print(f"  !! Tor 를 뺀 갈래: {' · '.join(sorted(뺀것))}"
              f"  (이 갈래는 우리 IP 로 나갑니다)")

    if not 자세히:
        print("  실제로 무엇으로 나가는지 보려면  python dc.py doctor --net")
        print()
        return 0

    r = egress.출구확인(프록시)
    표 = "OK" if r["된다"] else "!!"
    print(f"  {표} {r['말']}")
    if r["된다"]:
        print("     한국 출구를 안 쓰려면 torrc 에 ExcludeExitNodes {kr} 를 넣으십시오.")
    print()
    return 0 if r["된다"] else 1




# ── crawl ────────────────────────────────────────
def cmd_crawl(args) -> int:
    """통합 크롤러. 세 갈래 명부를 조사해 노션에 반영합니다."""
    from hub.places import run as 크롤

    대상 = [x.strip() for x in (args.only or "").split(",") if x.strip()] or None
    if 대상:
        모름 = [x for x in 대상 if x not in 크롤.갈래들]
        if 모름:
            print(f"모르는 갈래입니다: {', '.join(모름)}", file=sys.stderr)
            print(f"쓸 수 있는 것: {', '.join(크롤.갈래들)}", file=sys.stderr)
            return 1

    if not args.apply:
        print()
        print("  미리보기입니다. 노션에 안 씁니다. --apply 를 주면 씁니다.")

    if args.due and not 대상:
        때된것 = 크롤.차례()
        if not 때된것:
            print("  아직 때가 안 됐습니다. 돌 갈래가 없습니다.")
            return 0
        print("  때가 된 갈래: "
              + " · ".join(f"{g}({이유})" for g, 이유 in 때된것))

    결과 = 크롤.여러갈래(대상, apply=args.apply, limit=args.limit,
                     tor=os.environ.get("TOR_SOCKS_PROXY"),
                     때된것만=args.due)
    print()
    print(크롤.표로(결과, apply=args.apply))
    print()
    return 1 if any(r.오류 for r in 결과) else 0


def cmd_auto(args) -> int:
    """스케줄러가 부르는 자리. 수집과 명부 조사를 한 번에 합니다.

    작업을 둘로 나누면 둘 다 등록해야 하고, 하나만 걸어 두고 나머지를
    잊습니다. 하나로 둡니다.

    둘 다 **때가 된 것만** 돕니다. 스케줄러는 자주 부르고, 무엇이 언제
    돌지는 차례표가 정합니다.
    """
    from hub.places import run as 크롤

    print()
    print("  ── 수집 ──")
    # **사용자가 친 --dry 를 그대로 넘깁니다.** 예전에는 False 가 박혀 있어서
    # auto --dry 를 쳐도 수집만 실제로 나갔습니다. 값을 두 곳에 따로 적으면
    # 한쪽이 어긋납니다. 등록 명령에서 이미 같은 사고가 있었습니다
    수집끝 = cmd_run(argparse.Namespace(
        only=None, dry=args.dry, limit=0, due=True, db=None))

    print()
    print("  ── 명부 조사 ──")
    때된것 = 크롤.차례()
    if not 때된것:
        print("  아직 때가 안 됐습니다.")
        return 수집끝
    print("  때가 된 갈래: "
          + " · ".join(f"{g}({이유})" for g, 이유 in 때된것))
    결과 = 크롤.여러갈래(None, apply=not args.dry, limit=0,
                     tor=os.environ.get("TOR_SOCKS_PROXY"), 때된것만=True)
    print()
    print(크롤.표로(결과, apply=not args.dry))
    print()
    return 수집끝 or (1 if any(r.오류 for r in 결과) else 0)


# ── run · plan ───────────────────────────────────
def cmd_run(args) -> int:
    from hub.events import run as 사건

    이름들 = [n.strip() for n in (args.only or "").split(",") if n.strip()] or None
    if args.dry:
        print()
        print("  미리보기입니다. 밖에 요청을 보내지 않고 표에도 안 넣습니다.")
    결과 = 사건.여러판(이름들, dry=args.dry, limit=args.limit,
                     때된것만=args.due)
    print()
    print(사건.표로(결과))
    print()
    return 1 if any(r.error for r in 결과) else 0


def cmd_plan(args) -> int:
    from hub.events import registry, run as 사건
    from hub.sched import Sched

    es = registry.목록()
    if not es:
        print()
        print("  등록된 어댑터가 없습니다. hub/events/sources/ 에 파일을 놓으십시오.")
        print()
        return 0

    sch = Sched(사건.기본_표())
    try:
        상태 = {r["name"]: r for r in sch.상태()}
        남은 = {e.name: sch.다음까지(e.name, e.every) for e in es}
    finally:
        sch.close()

    print()
    print(f"어댑터 {len(es)}개")
    print()
    print("  " + 채움("이름", 16) + 채움("담당", 8) + 채움("주기", 10)
          + 채움("다음", 12) + "무엇을")
    print("  " + "─" * 76)
    때된것 = 0
    for e in es:
        주기 = f"{e.every}분마다" if e.every else "부를 때만"
        r = 상태.get(e.name)
        if r is None:
            다음 = "아직 안 돎"
            때된것 += 1
        elif r["fails"]:
            다음 = f"{r['fails']}번 실패"
            때된것 += 1 if 남은[e.name] == 0 else 0
        elif not e.every:
            다음 = "-"
        elif 남은[e.name] <= 0:
            다음 = "지금"
            때된것 += 1
        else:
            분 = 남은[e.name]
            다음 = f"{분//60}시간 뒤" if 분 >= 60 else f"{분}분 뒤"
        print("  " + 채움(e.name, 16) + 채움(e.owner or "-", 8)
              + 채움(주기, 10) + 채움(다음, 12) + e.summary)

    print()
    print(f"  지금 돌 때가 된 것 {때된것}개")
    print()
    print("  때 된 것만:    python dc.py run --due")
    print("  전부:          python dc.py run")
    print("  하나만:        python dc.py run --only <이름>")
    print()
    return 0


# ── install-task ─────────────────────────────────
def cmd_install_task(args) -> int:
    """윈도우 작업 스케줄러에 등록합니다. 등록 명령을 만들어 줍니다."""
    이름 = "Darkchoco-Collect"
    파이썬 = sys.executable
    # **한 곳에서만 정합니다.** 예전에는 여기서 auto 를 만들어 두고 아래
    # 등록 명령에는 run --due 를 박아 둬서, 스케줄러가 auto 를 영영 안
    # 불렀습니다. 크롤러 자동화가 통째로 죽어 있었습니다.
    인자 = "auto"

    if args.show:
        print()
        print("  이 명령을 PowerShell 에 붙여 넣으면 등록됩니다.")
        print()
        print(f'    $a = New-ScheduledTaskAction -Execute "{파이썬}" '
              f'-Argument \'"{ROOT / "dc.py"}" {인자}\' -WorkingDirectory "{ROOT}"')
        print(f'    $t = New-ScheduledTaskTrigger -Once -At (Get-Date) '
              f'-RepetitionInterval (New-TimeSpan -Minutes {args.every})')
        print(f'    $s = New-ScheduledTaskSettingsSet -StartWhenAvailable '
              f'-MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 1)')
        print(f'    Register-ScheduledTask -TaskName "{이름}" -Action $a '
              f'-Trigger $t -Settings $s -Force')
        print()
        print("  끄려면")
        print(f'    Unregister-ScheduledTask -TaskName "{이름}" -Confirm:$false')
        print()
        print("  지금 걸려 있는지 보려면")
        print(f'    Get-ScheduledTask -TaskName "{이름}" -ErrorAction SilentlyContinue')
        print()
        return 0

    if os.name != "nt":
        print("윈도우가 아닙니다. cron 에 아래를 넣으십시오.", file=sys.stderr)
        print(f"  */{args.every} * * * * cd {ROOT} && {파이썬} dc.py {인자}")
        return 1

    ps = [
        f'$a = New-ScheduledTaskAction -Execute "{파이썬}" '
        f'-Argument \'"{ROOT / "dc.py"}" {인자}\' -WorkingDirectory "{ROOT}"',
        f'$t = New-ScheduledTaskTrigger -Once -At (Get-Date) '
        f'-RepetitionInterval (New-TimeSpan -Minutes {args.every})',
        '$s = New-ScheduledTaskSettingsSet -StartWhenAvailable '
        '-MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 1)',
        f'Register-ScheduledTask -TaskName "{이름}" -Action $a -Trigger $t '
        f'-Settings $s -Force | Out-Null',
        f'Write-Host "등록했습니다: {이름} ({args.every}분마다)"',
    ]
    r = subprocess.run(["powershell", "-NoProfile", "-Command", "; ".join(ps)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    print((r.stdout or "").strip() or (r.stderr or "").strip())
    if r.returncode == 0:
        print()
        print("  끄려면:  python dc.py install-task --remove")
    return r.returncode


def cmd_remove_task(args) -> int:
    이름 = "Darkchoco-Collect"
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         f'Unregister-ScheduledTask -TaskName "{이름}" -Confirm:$false; '
         f'Write-Host "지웠습니다: {이름}"'],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    print((r.stdout or "").strip() or (r.stderr or "").strip())
    return r.returncode


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
    p.add_argument("--net", action="store_true",
                   help="실제로 나가 보고 남는 주소를 확인합니다")
    p.add_argument("name", nargs="?")
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("crawl", help="명부를 조사해 노션에 반영합니다")
    p.add_argument("--only", help="쉼표로 나눈 갈래. telegram · forum · ransom")
    p.add_argument("--apply", action="store_true",
                   help="실제로 노션에 씁니다. 없으면 미리보기입니다")
    p.add_argument("--limit", type=int, default=0, help="갈래마다 최대 몇 줄까지")
    p.add_argument("--due", action="store_true",
                   help="주기가 찬 갈래만. 스케줄러가 이것을 씁니다")
    p.set_defaults(fn=cmd_crawl)

    p = sub.add_parser("auto", help="수집과 명부 조사를 한 번에 (스케줄러용)")
    p.add_argument("--dry", action="store_true",
                   help="밖에 요청을 안 보내고 노션에도 안 씁니다. 무엇이 돌지만 봅니다")
    p.set_defaults(fn=cmd_auto)

    p = sub.add_parser("run", help="수집을 한 판 돌립니다")
    p.add_argument("--only", help="쉼표로 나눈 어댑터 이름. 없으면 전부")
    p.add_argument("--dry", action="store_true",
                   help="밖에 요청을 안 보내고 준비만 봅니다")
    p.add_argument("--limit", type=int, default=0, help="어댑터마다 최대 몇 건까지")
    p.add_argument("--due", action="store_true",
                   help="주기가 찬 것만. 스케줄러가 이것을 씁니다")
    p.set_defaults(fn=cmd_run)

    sub.add_parser("plan", help="어떤 어댑터가 몇 분마다 도는지").set_defaults(fn=cmd_plan)

    p = sub.add_parser("install-task", help="작업 스케줄러에 등록합니다")
    p.add_argument("--every", type=int, default=10, help="몇 분마다 (기본 10)")
    p.add_argument("--show", action="store_true", help="등록 안 하고 명령만 보여 줍니다")
    p.add_argument("--remove", action="store_true", help="등록을 지웁니다")
    p.set_defaults(fn=lambda a: cmd_remove_task(a) if a.remove else cmd_install_task(a))

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
