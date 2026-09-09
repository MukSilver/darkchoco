#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""다크초코 제어판. 도구를 골라 실행한다.

    python run.py

## 왜 만들었나

도구가 스물여섯 개인데 사용법이 파일 독스트링에 흩어져 있었다. 한 바퀴를 돌리려면
명령을 여러 번 치고, 설정 파일 자리를 외우고, 어느 폴더에서 쳐야 하는지도 알아야 했다.

**이 파일은 새 기능을 만들지 않는다.** 기존 도구를 고르고, 인자를 맞춰 부르고,
실행 전에 무엇을 돌리는지 보인다. 명령을 그대로 보이므로 나중에 직접 쳐도 된다.

## 여기서 막는 것 셋

    1  DB 자리가 갈리는 것       늘 절대경로로 준다
    2  큐가 비는 조합            --notify --go 와 --queue 를 같이 안 준다
    3  실수로 밖에 나가는 것      보내기·쓰기는 한 번 더 묻는다

## 필요한 것

    pip install questionary
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import date
from pathlib import Path

try:
    import questionary as q
    from questionary import Choice
except ImportError:
    raise SystemExit(
        "questionary 가 없다.\n\n"
        "    pip install questionary\n")

HERE = Path(__file__).resolve().parent
TOOLS = HERE / "skills" / "darkweb-verify-ko" / "tools"
CFG = Path(os.environ.get("DARKCHOCO_CONFIG_DIR",
                          Path.home() / ".config" / "darkchoco"))

# 수집 표. 2026-09-07 부터 **팀 레포 안 `hub/data/`** 다. 통합 수집기가 이미 쓰던
# 자리이고, 두 수집 경로가 같은 파일에 써야 같은 사건이 한 줄로 뭉친다.
#
# 전에는 「레포 밖에 둔다」 가 규칙이었다. 게시글 본문이 든 파일을 **공개** 레포에
# 두지 않으려던 것이다. 팀 레포는 비공개이고 `.gitignore` 의 `hub/data/` 가 막는다.
# 그래도 커밋에 안 들어가는지는 늘 확인한다 — 막는 것이 규칙 하나뿐이다.
#
# 셸 cwd 에 따라 다른 파일이 열리던 일이 있어 절대경로로 고정한다.
def _표자리() -> Path:
    쓸것 = os.environ.get("DARKCHOCO_DB")
    if 쓸것:
        return Path(쓸것)
    for p in (Path.home() / "darkchoco-team" / "hub" / "data" / "darkchoco.db",
              Path.home() / "data" / "darkchoco.db"):
        if p.is_file():
            return p
    return Path.home() / "darkchoco-team" / "hub" / "data" / "darkchoco.db"


DB = _표자리()

# 여기도 표가 생긴다. 문서의 수집 명령이 레포 안을 가리켜 왔고, 팀 통합 수집기는
# 자기 레포 안에 따로 쌓는다. 2026-09-02 에 세 자리에 서로 다른 표가 있었고
# **겹치는 줄이 하나도 없었다.** 현황 화면이 다 세어 보인다 — 어느 것을 쓰는지
# 모르면 「수집이 됐는데 안 보인다」 가 된다.
DB_ALSO = [
    HERE / "data" / "darkchoco.db",
    Path.home() / "data" / "darkchoco.db",
    Path.home() / "darkchoco-team" / "hub" / "data" / "darkchoco.db",
    # 2026-09-07 에 합치기 전 판. 되돌릴 일이 있으면 여기 있다
    Path.home() / "data" / "darkchoco.백업_20260907.db",
]

STYLE = q.Style([
    ("qmark", "fg:#8b7bd8 bold"),
    ("question", "bold"),
    ("pointer", "fg:#8b7bd8 bold"),
    ("highlighted", "fg:#8b7bd8 bold"),
    ("selected", "fg:#7dc4a0"),
    ("answer", "fg:#7dc4a0 bold"),
    ("instruction", "fg:#808080"),
])


# ── 프젝 폴더 ───────────────────────────────────
# 케이스 큐와 결과가 여기 쌓인다. 레포 밖이라 사람마다 자리가 다르다.
def proj() -> Path | None:
    p = os.environ.get("DARKCHOCO_PROJ")
    if p and Path(p).is_dir():
        return Path(p)
    guess = (Path.home() / "Documents" / "Q.E.D" / "화햇" / "화햇강의자료" / "프젝")
    return guess if guess.is_dir() else None


# ── 큐 폴더 ─────────────────────────────────────
# **재료가 있는 자리가 곧 큐다** (2026-09-09 확정). 전에는 `07_케이스/_큐` 를 가리켰는데
# 거기는 결과가 쌓이는 자리고 재료는 공유폴더에 들어온다. 두 자리를 갈라 두면
# 경로를 두 벌 관리하게 되고, 실제로 `_큐` 폴더는 만들어진 적이 없다.
#
# **사람마다 공유폴더 이름이 다르다.** VirtualBox 설정에서 정하는 것이라
# `VM공유폴더` 가 아닐 수 있다. 그래서 환경변수를 하나 더 둔다.
#
#   DARKCHOCO_QUEUE   이것이 있으면 무조건 이것
#   없으면            <프젝>/VM공유폴더
def queue_dir() -> Path | None:
    q = os.environ.get("DARKCHOCO_QUEUE")
    if q and Path(q).is_dir():
        return Path(q)
    p = proj()
    if not p:
        return None
    guess = p / "VM공유폴더"
    return guess if guess.is_dir() else None


# ── 설정 점검 ───────────────────────────────────
# (파일 이름, 무엇에 쓰나, 없으면 무엇이 막히나)
NEEDS = [
    ("notion_token", "노션 토큰", "노션 조회·기록, 지도 굽기"),
    ("telegram_channels", "볼 채널 목록", "텔레그램 수집"),
    ("discord_webhook", "알림 보낼 곳", "디스코드로 새 건 알리기"),
    ("discord_token", "디스코드 봇 토큰", "알림 채널 감시"),
    ("discord_channel", "감시할 채널 번호", "알림 채널 감시"),
    ("telegram_api", "텔레그램 api_id·api_hash", "미리보기가 꺼진 채널 읽기"),
]


def config_state() -> list[tuple[str, bool, str, str]]:
    out = []
    for name, what, blocks in NEEDS:
        p = CFG / name
        ok = p.exists() and p.stat().st_size > 0
        out.append((name, ok, what, blocks))
    return out


def show_config() -> None:
    print()
    print("설정 자리  %s" % CFG)
    print("-" * 66)
    for name, ok, what, blocks in config_state():
        mark = "있음" if ok else "없음"
        print("  %-4s %-20s %s" % (mark, name, what))
        if not ok:
            print("       %s└ 없으면 막히는 것: %s" % (" " * 20, blocks))
    print()
    miss = [n for n, ok, _, _ in config_state() if not ok]
    if miss:
        print("빠진 것 %d개. 아래처럼 파일을 만들면 된다." % len(miss))
        print()
        for n in miss:
            print("    %s" % (CFG / n))
        print()
        print("**값을 여기에 붙여 넣지 말고 파일로 만든다.** 화면에 남으면 새어 나간다.")
    else:
        print("전부 있다.")
    print()


# ── 수집 표 현황 ─────────────────────────────────
def show_db() -> None:
    print()
    print("수집 표  %s" % DB)
    if not DB.exists():
        print("  아직 없다. 수집을 한 번 돌리면 만들어진다.")
        print()
        return
    sys.path.insert(0, str(HERE))
    from collect.store import Store              # noqa: E402
    s = Store(DB)
    try:
        c = s.counts()
        print("-" * 66)
        if not c:
            print("  줄이 없다.")
        for src, n in sorted(c.items()):
            print("  %-10s 전체 %5d · 아직 안 본 것 %d" % (src, n["전체"], n["새 것"]))
        rows = list(s.con.execute(
            "SELECT started, source, got, fresh, note FROM runs "
            "ORDER BY started DESC LIMIT 5"))
        if rows:
            print()
            print("  최근 실행")
            for r in rows:
                print("    %-19s %-12s 받음 %4d · 새 것 %3d  %s"
                      % (r["started"][:19], r["source"], r["got"], r["fresh"],
                         (r["note"] or "")[:30]))
    finally:
        s.close()

    # **표가 갈린 적이 있다.** 문서의 수집 명령이 레포 안을 가리켜 온 탓이다.
    # 어느 쪽이 최신인지 사람이 알아야 하므로 다른 자리의 것도 세어 보인다.
    others = [p for p in DB_ALSO if p.exists() and p.resolve() != DB.resolve()]
    for p in others:
        n, b, last = peek(p)
        print()
        print("  ※ 다른 자리에도 표가 있다")
        print("     %s" % p)
        print("     줄 %d · 본문 있는 줄 %d · 마지막 실행 %s" % (n, b, last or "모름"))
        print("     이 제어판은 이것을 쓰지 않는다. 쓰려면 DARKCHOCO_DB 로 가리킨다.")
    print()


def peek(p: Path) -> tuple[int, int, str | None]:
    """읽기 전용으로 열어 건수만 센다. 값은 안 본다."""
    import sqlite3
    try:
        c = sqlite3.connect("file:%s?mode=ro" % p.as_posix(), uri=True)
    except sqlite3.Error:
        return (0, 0, None)
    try:
        n = c.execute("SELECT COUNT(*) FROM items").fetchone()[0]
        b = c.execute("SELECT COUNT(*) FROM items "
                      "WHERE body IS NOT NULL AND body <> ''").fetchone()[0]
        last = c.execute("SELECT MAX(started) FROM runs").fetchone()[0]
        return (n, b, last)
    except sqlite3.Error:
        return (0, 0, None)
    finally:
        c.close()


# ── 실행기 ─────────────────────────────────────
def run(cmd: list[str], *, danger: str = "", cwd: Path | None = None) -> None:
    """명령을 보이고, 위험하면 한 번 더 묻고, 실행한다.

    **무엇을 돌리는지 늘 보인다.** 제어판이 가려 버리면 나중에 직접 못 친다.
    """
    print()
    print("─" * 66)
    print("  " + " ".join(str(x) for x in cmd))
    print("─" * 66)
    if danger:
        print()
        print("  ⚠ %s" % danger)
        if not q.confirm("정말 실행하나?", default=False, style=STYLE).ask():
            print("  안 했다.")
            return
    print()
    try:
        subprocess.run([str(x) for x in cmd], cwd=str(cwd or HERE))
    except KeyboardInterrupt:
        print("\n  끊었다.")
    except FileNotFoundError as e:
        print("  못 찾았다: %s" % e)
    print()
    q.press_any_key_to_continue("계속하려면 아무 키나", style=STYLE).ask()


def PY(*args) -> list:
    return [sys.executable, *args]


def tool(name: str, *args) -> list:
    return PY(TOOLS / name, *args)


# ── 메뉴: 수집 ───────────────────────────────────
def menu_collect() -> None:
    while True:
        pick = q.select("수집", style=STYLE, choices=[
            Choice("한 바퀴 (텔레그램 + 랜섬)", "round"),
            Choice("한 바퀴 + 검증 큐까지", "round_queue"),
            Choice("랜섬웨어만 — ransomware.live", "ransom"),
            Choice("텔레그램 한 채널 — 공개 미리보기", "tg_one"),
            Choice("텔레그램 한 채널 — 실계정 (미리보기가 꺼진 곳)", "tg_api"),
            Choice("포럼 킷 출력 넣기", "kit"),
            Choice("받아 둔 것을 다시 읽기 (reparse)", "reparse"),
            Choice("← 뒤로", None),
        ]).ask()
        if pick is None:
            return

        if pick == "round":
            # 알림은 여기서 안 보낸다. 보내는 것은 「반출」 메뉴에서 따로 한다 —
            # 알림이 is_new 를 지워서 검증 큐가 비는 일이 있었다
            run(PY("-m", "collect.main", "--db", DB))

        elif pick == "round_queue":
            큐 = queue_dir()
            if not 큐:
                print("\n  큐 폴더를 못 찾았다. 공유폴더 자리를 DARKCHOCO_QUEUE 로 정한다.\n")
                q.press_any_key_to_continue(style=STYLE).ask()
                continue
            run(PY("-m", "collect.main", "--db", DB, "--queue", 큐))

        elif pick == "ransom":
            feed = q.select("어느 피드", style=STYLE, choices=[
                Choice("한국 건 (kr)", "kr"),
                Choice("최근 건 (recent)", "recent"),
            ]).ask()
            if feed:
                run(PY("-m", "collect.sources.ransomlive", feed, "--db", DB))

        elif pick == "tg_one":
            ch = ask_channel()
            if ch:
                run(PY("-m", "collect.sources.telegram_web", ch, "--db", DB))

        elif pick == "tg_api":
            if not (CFG / "telegram_api").exists():
                print("\n  telegram_api 설정이 없다. 「설정 점검」을 먼저 본다.\n")
                q.press_any_key_to_continue(style=STYLE).ask()
                continue
            ch = ask_channel()
            if ch:
                run(PY("-m", "collect.sources.telegram_api", ch, "--db", DB,
                       "--limit", "50"))

        elif pick == "kit":
            f = q.path("킷이 낸 마크다운 파일", style=STYLE).ask()
            if f and Path(f).exists():
                run(PY("-m", "collect.kit_in", f, "--db", DB))
            elif f:
                print("\n  그런 파일이 없다: %s\n" % f)
                q.press_any_key_to_continue(style=STYLE).ask()

        elif pick == "reparse":
            go = q.confirm("실제로 갈아 끼우나? (아니오면 무엇이 달라지는지만 본다)",
                           default=False, style=STYLE).ask()
            args = ["-m", "collect.reparse", "--db", DB]
            if go:
                args.append("--apply")
            run(PY(*args),
                danger="표의 값을 갈아 끼운다. 되돌리는 명령이 없다." if go else "")


def ask_channel() -> str | None:
    """채널 목록이 있으면 골라 쓰고, 없으면 직접 받는다."""
    lst = CFG / "telegram_channels"
    if lst.exists():
        names = [x.strip().lstrip("@") for x in
                 lst.read_text(encoding="utf-8").splitlines()
                 if x.strip() and not x.strip().startswith("#")]
        if names:
            names.append("── 직접 입력 ──")
            got = q.select("어느 채널", choices=names, style=STYLE).ask()
            if got and not got.startswith("──"):
                return got
            if got is None:
                return None
    got = q.text("채널 이름 (@ 없이)", style=STYLE).ask()
    return (got or "").strip().lstrip("@") or None


# ── 메뉴: 큐와 케이스 ─────────────────────────────
def menu_queue() -> None:
    queue = queue_dir()
    if not queue:
        print("\n  큐 폴더를 못 찾았다. 공유폴더 자리를 DARKCHOCO_QUEUE 로 정한다.")
        print("  프젝 폴더 아래 「VM공유폴더」 가 있으면 그것을 자동으로 쓴다.\n")
        q.press_any_key_to_continue(style=STYLE).ask()
        return
    while True:
        pick = q.select("큐와 케이스   (%s)" % queue, style=STYLE, choices=[
            Choice("큐 상태 보기", "state"),
            Choice("큐 한 바퀴 돌리기 — 다음 단계까지 진행", "go"),
            Choice("브리핑 만들기", "brief"),
            Choice("수집 표에서 큐 채우기", "feed"),
            Choice("← 뒤로", None),
        ]).ask()
        if pick is None:
            return
        if pick == "state":
            run(tool("run_queue.py", queue))
        elif pick == "go":
            run(tool("run_queue.py", queue, "--go"),
                danger="노션을 조회하고 케이스 상태를 바꾼다.")
        elif pick == "brief":
            out = p / "07_케이스" / ("브리핑_%s.md" % date.today().strftime("%Y%m%d"))
            run(tool("brief.py", queue, "--out", out))
        elif pick == "feed":
            allrows = q.confirm("이미 본 것까지 다시 넣나?", default=False,
                                style=STYLE).ask()
            args = [DB, "--out", queue]
            if allrows:
                args.append("--all")
            run(tool("feed_parse.py", *args))


# ── 메뉴: 재료 분석 ───────────────────────────────
def menu_material() -> None:
    while True:
        pick = q.select("재료 분석", style=STYLE, choices=[
            Choice("케이스 폴더 훑기 (inspect) — 무엇이 들어 있나", "inspect"),
            Choice("샘플 통계 (sample_stats) — 칸과 패턴", "stats"),
            Choice("파일 트리 (tree_scan)", "tree"),
            Choice("SQL 덤프 구조 (db_tree)", "db"),
            Choice("← 뒤로", None),
        ]).ask()
        if pick is None:
            return
        if pick == "inspect":
            d = q.path("케이스 폴더", style=STYLE).ask()
            if d and Path(d).is_dir():
                run(tool("inspect.py", d))
            elif d:
                print("\n  그런 폴더가 없다: %s\n" % d)
                q.press_any_key_to_continue(style=STYLE).ask()
        else:
            f = q.path("파일", style=STYLE).ask()
            if not f or not Path(f).exists():
                if f:
                    print("\n  그런 파일이 없다: %s\n" % f)
                    q.press_any_key_to_continue(style=STYLE).ask()
                continue
            run(tool({"stats": "sample_stats.py", "tree": "tree_scan.py",
                      "db": "db_tree.py"}[pick], f))


# ── 메뉴: 노션 ───────────────────────────────────
def menu_notion() -> None:
    while True:
        pick = q.select("노션", style=STYLE, choices=[
            Choice("문서 찾기 (search)", "search"),
            Choice("DB 에서 찾기 (notion_find)", "find"),
            Choice("DB 칸 보기 (notion_prop show)", "prop"),
            Choice("⑨ 출력을 DB 에 넣기 (notion_row)", "row"),
            Choice("← 뒤로", None),
        ]).ask()
        if pick is None:
            return
        if pick == "search":
            w = q.text("검색어", style=STYLE).ask()
            if w:
                run(tool("notion.py", "search", w))
        elif pick == "find":
            db = q.text("DB 이름 (예: 수집 DB)", style=STYLE).ask()
            w = q.text("검색어", style=STYLE).ask() if db else None
            if db and w:
                run(tool("notion_find.py", db, w))
        elif pick == "prop":
            db = q.text("DB 이름 또는 id", style=STYLE).ask()
            if db:
                run(tool("notion_prop.py", "show", db))
        elif pick == "row":
            db = q.text("어느 DB (수집 DB / 검증 DB)", style=STYLE).ask()
            f = q.path("⑨ 출력 파일", style=STYLE).ask() if db else None
            if not (db and f and Path(f).exists()):
                if f:
                    print("\n  그런 파일이 없다: %s\n" % f)
                    q.press_any_key_to_continue(style=STYLE).ask()
                continue
            go = q.confirm("실제로 노션에 쓰나? (아니오면 무엇이 들어갈지만 본다)",
                           default=False, style=STYLE).ask()
            args = [db, f]
            if go:
                args.append("--commit")
            run(tool("notion_row.py", *args),
                danger="노션에 새 줄을 만든다. 지우려면 사람이 노션에서 해야 한다."
                       if go else "")


# ── 메뉴: 알림 ───────────────────────────────────
def menu_alert() -> None:
    while True:
        pick = q.select("알림", style=STYLE, choices=[
            Choice("감시 채널 읽기 (alert_watch)", "watch"),
            Choice("알림 글 한 덩어리를 ③ 칸으로 (alert_parse)", "parse"),
            Choice("새 건을 디스코드로 보내기 (notify)", "notify"),
            Choice("← 뒤로", None),
        ]).ask()
        if pick is None:
            return
        if pick == "watch":
            run(tool("alert_watch.py", "--dry"))
        elif pick == "parse":
            f = q.path("알림 텍스트 파일", style=STYLE).ask()
            if f and Path(f).exists():
                run(tool("alert_parse.py", f))
            elif f:
                print("\n  그런 파일이 없다: %s\n" % f)
                q.press_any_key_to_continue(style=STYLE).ask()
        elif pick == "notify":
            if not (CFG / "discord_webhook").exists():
                print("\n  discord_webhook 설정이 없다. 「설정 점검」을 먼저 본다.\n")
                q.press_any_key_to_continue(style=STYLE).ask()
                continue
            go = q.confirm("실제로 보내나? (아니오면 미리보기)",
                           default=False, style=STYLE).ask()
            args = ["-m", "collect.notify", "--db", DB]
            if go:
                args.append("--go")
            run(PY(*args),
                danger="디스코드로 실제로 나간다. 보낸 것은 「본 것」으로 표시돼\n"
                       "    검증 큐 채우기에서 빠진다. 큐를 먼저 채우는 편이 낫다."
                       if go else "")


# ── 메뉴: 통계와 추적 ────────────────────────────
# A2 통계와 A3 랜섬 게시 상태 추적. 둘 다 같은 수집 표의 같은 줄(집계처 KR)을 본다.
# 통계는 「얼마나 올라왔고 얼마나 확인됐나」, 추적은 「그 뒤에 무엇이 됐나」다 (DEV 5-4 R3 · 5-5).
def menu_stats() -> None:
    while True:
        pick = q.select("통계와 추적 — 한국 관련 랜섬웨어 게시", style=STYLE, choices=[
            Choice("집계처 한 판 — 있나 없나 적기 (매일 한 번, 요청 1회)", "agg"),
            Choice("사람 관측 넣기 — 원 출처를 Tor 로 본 결과", "obs"),
            Choice("게시 상태 보고서 — 공개됨 · 사라짐 · 불명", "report"),
            Choice("통계 내기 — 월별 · 행위자별 · 업종별 · 깔때기", "stats"),
            Choice("← 뒤로", None),
        ]).ask()
        if pick is None:
            return

        if pick == "agg":
            run(PY("-m", "collect.track", "--db", DB, "agg"))

        elif pick == "obs":
            # 원 출처는 사람이 연다. 여기서는 본 것을 적기만 한다. 값·주소는 안 넣는다
            target = q.text("대상 — uid 또는 조직명 조각 (하나로 좁혀져야 한다)", style=STYLE).ask()
            if not target:
                continue
            state = q.select("상태", style=STYLE, choices=[
                Choice("게시 중 — 아직 안 풀렸고 카운트다운이 돈다", "게시 중"),
                Choice("공개됨 — 자료가 풀렸다", "공개됨"),
                Choice("사라짐 — 게시물이 내려갔다", "사라짐"),
                Choice("연장 — 카운트다운이 늘었다", "연장"),
                Choice("불명 — 열었는데 못 가렸다", "불명"),
            ]).ask()
            if not state:
                continue
            cd = q.text("카운트다운 표기 그대로 (없으면 비움)", style=STYLE).ask() or ""
            size = q.text("규모 표기 그대로 (없으면 비움)", style=STYLE).ask() or ""
            files = q.text("공개된 파일 수 (모르면 비움)", style=STYLE).ask() or ""
            note = q.text("근거 한 줄 — 값·주소는 넣지 않는다", style=STYLE).ask() or ""
            by = q.text("누가 봤나", default="사람", style=STYLE).ask() or "사람"
            args = ["-m", "collect.track", "--db", DB, "obs", target, "--state", state, "--by", by]
            if cd:
                args += ["--countdown", cd]
            if size:
                args += ["--size", size]
            if files:
                args += ["--files", files]
            if note:
                args += ["--note", note]
            run(PY(*args))

        elif pick == "report":
            out = q.text("md 를 쓸 자리 (비우면 화면에만)", style=STYLE).ask() or ""
            args = ["-m", "collect.track", "--db", DB, "report"]
            if out:
                args += ["--out", out]
            run(PY(*args))

        elif pick == "stats":
            since = q.text("게시일 하한 YYYY-MM-DD (비우면 전체)", default="2026-01-01",
                           style=STYLE).ask() or ""
            p = proj()
            out = q.text("결과 폴더 (md · csv · png)",
                         default=str(p / "07_케이스" / "_통계") if p else "", style=STYLE).ask()
            if not out:
                continue
            lst = q.confirm("대상 조직 목록도 따로 낼까? (기본은 건수만)", default=False,
                            style=STYLE).ask()
            notion = q.confirm("노션을 읽어 깔때기까지 낼까? (읽기만 한다)", default=True,
                               style=STYLE).ask()
            args = ["-m", "collect.stats", "--db", DB, "--out", out]
            if since:
                args += ["--since", since]
            if lst:
                args.append("--list")
            if not notion:
                args.append("--no-notion")
            run(PY(*args))


# ── 첫 화면 ─────────────────────────────────────
def main() -> None:
    while True:
        miss = [n for n, ok, _, _ in config_state() if not ok]
        tail = "  (빠진 설정 %d개)" % len(miss) if miss else ""
        print()
        pick = q.select("다크초코 제어판%s" % tail, style=STYLE, choices=[
            Choice("현황 보기", "state"),
            Choice("수집", "collect"),
            Choice("알림", "alert"),
            Choice("큐와 케이스", "queue"),
            Choice("재료 분석", "material"),
            Choice("통계와 추적 — 한국 관련 랜섬웨어 게시", "stats"),
            Choice("노션", "notion"),
            Choice("설정 점검", "config"),
            Choice("나가기", "quit"),
        ]).ask()

        if pick in (None, "quit"):
            print("\n  끝.\n")
            return
        if pick == "state":
            show_db()
            q.press_any_key_to_continue(style=STYLE).ask()
        elif pick == "config":
            show_config()
            q.press_any_key_to_continue(style=STYLE).ask()
        elif pick == "collect":
            menu_collect()
        elif pick == "alert":
            menu_alert()
        elif pick == "queue":
            menu_queue()
        elif pick == "material":
            menu_material()
        elif pick == "stats":
            menu_stats()
        elif pick == "notion":
            menu_notion()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  끝.\n")
