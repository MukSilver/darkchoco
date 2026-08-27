#!/usr/bin/env python3
"""케이스 폴더 하나를 분석 도구에 태운다.

    python tools/inspect.py <케이스폴더>
    python tools/inspect.py <케이스폴더> --out <결과폴더>

결과는 **케이스 폴더 옆에 두지 않는다.** 지금 폴더의 `07_케이스/<케이스이름>/` 에 쓴다.
공유폴더는 통로라서 분석이 끝나면 비운다. 결과가 거기 있으면 같이 지워진다.

파일마다 **앞바이트로 진짜 종류를 판정하고** 종류에 맞는 도구를 돌린다.
실행 파일과 압축과 문서는 건드리지 않고 경고만 적는다.

확장자를 믿지 않는다. 유출물은 이름을 속인다.
이름에 숨은 방향 제어 문자도 본다. 화면에 보이는 확장자와 실제가 다를 수 있다.
글자로만 된 파일은 시그니처가 없으므로 첫머리로 가른다.
이 스크립트는 파일을 읽기만 한다. 실행하지 않고 셸을 부르지 않는다.
"""
from __future__ import annotations

import argparse
import codecs
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TIMEOUT = 600          # 도구 하나당 상한
HEAD = 8192            # 종류를 볼 때 읽는 앞부분
SAFE = "텍스트"

# 앞바이트로 가리는 종류. 위는 전부 건드리지 않는다.
MAGIC = [
    (b"MZ",                  "실행 파일(MZ)"),
    (b"\x7fELF",             "실행 파일(ELF)"),
    (b"\xca\xfe\xba\xbe",    "실행 파일(Mach-O)"),
    (b"PK\x03\x04",          "zip 계열(zip·docx·xlsx·jar)"),
    (b"Rar!",                "rar"),
    (b"7z\xbc\xaf\x27\x1c",  "7z"),
    (b"\x1f\x8b",            "gzip"),
    (b"BZh",                 "bzip2"),
    (b"\xfd7zXZ",            "xz"),
    (b"%PDF",                "pdf"),
    (b"\xd0\xcf\x11\xe0",    "옛 office(doc·xls·ppt)"),
    (b"{\\rtf",              "rtf"),
    (b"\x89PNG",             "png"),
    (b"\xff\xd8\xff",        "jpeg"),
    (b"SQLite format 3",     "sqlite 파일"),
]

# 종류마다 어울리는 확장자. 여기 없으면 이름을 속인 것으로 본다
EXT_OK = {
    "실행 파일(MZ)": {".exe", ".dll", ".sys", ".msi", ".scr", ".ocx"},
    "실행 파일(ELF)": {".so", ".elf", ".bin", ""},
    "실행 파일(Mach-O)": {".dylib", ".bin", ""},
    "zip 계열(zip·docx·xlsx·jar)": {".zip", ".docx", ".xlsx", ".pptx", ".jar",
                                    ".apk", ".odt", ".ods", ".epub", ".whl"},
    "rar": {".rar"}, "7z": {".7z"}, "gzip": {".gz", ".tgz", ".tar"},
    "bzip2": {".bz2"}, "xz": {".xz"}, "pdf": {".pdf"},
    "옛 office(doc·xls·ppt)": {".doc", ".xls", ".ppt", ".hwp", ".msg"},
    "rtf": {".rtf"}, "png": {".png"}, "jpeg": {".jpg", ".jpeg"},
    "sqlite 파일": {".db", ".sqlite", ".sqlite3"},
}

# 이름에 숨어 글자 순서를 뒤집거나 사라지는 문자.
# invoice + U+202E + gnp.js 는 화면에 invoicesj.png 로 보인다. 실제는 .js 다.
HIDDEN = {
    "\u202a": "LRE", "\u202b": "RLE", "\u202c": "PDF", "\u202d": "LRO",
    "\u202e": "RLO", "\u2066": "LRI", "\u2067": "RLI", "\u2068": "FSI",
    "\u2069": "PDI", "\u200b": "ZWSP", "\u200c": "ZWNJ", "\u200d": "ZWJ",
    "\u200e": "LRM", "\u200f": "RLM", "\u061c": "ALM", "\ufeff": "BOM",
}


def hidden_chars(s: str) -> list[str]:
    """이름에 숨은 방향 제어 문자. 있으면 확장자가 거짓말일 수 있다."""
    return sorted({HIDDEN[c] for c in s if c in HIDDEN})


# 윈도우가 못 쓰는 문자와 예약어. 공유폴더가 호스트와 이어져 있어서 걸린다.
BAD_CHARS = set('<>:"|?*') | {chr(c) for c in range(32)}
RESERVED = {"con", "prn", "aux", "nul"} | {"com%d" % i for i in range(1, 10)} \
    | {"lpt%d" % i for i in range(1, 10)}


def win_unsafe(name: str) -> list[str]:
    """윈도우에서 문제가 되는 이름인가. 리눅스 VM 에서 온 것이 걸린다."""
    out = []
    bad = sorted({c for c in name if c in BAD_CHARS})
    if bad:
        out.append("못 쓰는 문자 " + " ".join(repr(c) for c in bad))
    stem = name.split(".")[0].lower().rstrip(" ")
    if stem in RESERVED:
        out.append("예약된 장치 이름 %s" % stem.upper())
    if name != name.rstrip(" ."):
        out.append("끝에 공백이나 점")
    return out


def streams(path: Path) -> list[str]:
    """NTFS 대체 데이터 스트림. 본 스트림 뒤에 숨은 것을 찾는다.

    윈도우가 아니면 빈 목록을 낸다. 없다고 단정하지 않는다.
    """
    if os.name != "nt":
        return []
    try:
        import ctypes
        from ctypes import wintypes
    except ImportError:
        return []

    class WIN32_FIND_STREAM_DATA(ctypes.Structure):
        _fields_ = [("StreamSize", ctypes.c_longlong),
                    ("cStreamName", ctypes.c_wchar * 296)]

    k32 = ctypes.windll.kernel32
    # 핸들은 포인터 크기다. 타입을 안 알려주면 int 로 넘어가 넘친다.
    k32.FindFirstStreamW.restype = wintypes.HANDLE
    k32.FindFirstStreamW.argtypes = [wintypes.LPCWSTR, ctypes.c_int,
                                     ctypes.c_void_p, wintypes.DWORD]
    k32.FindNextStreamW.restype = wintypes.BOOL
    k32.FindNextStreamW.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
    k32.FindClose.restype = wintypes.BOOL
    k32.FindClose.argtypes = [wintypes.HANDLE]

    INVALID = ctypes.cast(ctypes.c_void_p(-1), wintypes.HANDLE).value
    data = WIN32_FIND_STREAM_DATA()
    h = k32.FindFirstStreamW(str(path), 0, ctypes.byref(data), 0)
    if not h or h == INVALID:
        return []
    out = []
    try:
        while True:
            nm = data.cStreamName
            if nm and not nm.startswith("::$DATA"):
                out.append("%s (%d바이트)" % (nm.strip(":").split(":")[0], data.StreamSize))
            if not k32.FindNextStreamW(h, ctypes.byref(data)):
                break
    finally:
        k32.FindClose(h)
    return out


def escape_hidden(s: str) -> str:
    """산출물에 실을 때 눈에 보이게 바꾼다. 원문 그대로 실으면 이 문서도 같이 속는다."""
    return "".join("<U+%04X>" % ord(c) if c in HIDDEN else c for c in s)


# 글자로만 된 파일은 앞바이트 시그니처가 없다. 첫머리로 종류를 가린다.
# 여기 걸렸는데 확장자가 다르면 표 파일로 위장한 스크립트다.
TEXT_SIGN = [
    ("#!",             "셔뱅 스크립트", {".sh", ".bash", ".py", ".pl", ".rb", ""}),
    ("<?php",          "php",         {".php", ".phtml", ".php5"}),
    ("<!doctype html", "html",        {".html", ".htm"}),
    ("<html",          "html",        {".html", ".htm"}),
    ("<script",        "스크립트",      {".html", ".htm", ".js", ".hta"}),
    ("@echo",          "배치",         {".bat", ".cmd"}),
    ("<?xml",          "xml",         {".xml", ".xhtml", ".svg", ".rels",
                                       ".config", ".plist", ".resx"}),
]

# 텍스트일 때 확장자로 도구를 고른다
TOOL = {
    ".sql": "db_tree",
    ".csv": "sample_stats",
    ".tsv": "sample_stats",
}


def sniff(path: Path) -> tuple[str, str, bytes]:
    """(종류, 이유, 앞부분). 종류가 '텍스트' 일 때만 도구에 태운다."""
    try:
        with path.open("rb") as f:
            head = f.read(HEAD)
    except OSError as e:
        return "못 읽음", str(e), b""

    if not head:
        return "빈 파일", "0 바이트", head

    for sig, name in MAGIC:
        if head.startswith(sig):
            return name, "앞바이트 " + repr(sig)[1:], head

    if b"\x00" in head:
        return "이진", "앞 %d바이트에 널바이트가 있다" % len(head), head

    # 앞부분을 자르면 여러 바이트 글자가 반으로 잘린다. 그것을 오류로 세지 않는다.
    for enc in ("utf-8", "cp949"):
        try:
            codecs.getincrementaldecoder(enc)().decode(head, False)
            return SAFE, enc + " 로 읽힌다", head
        except UnicodeDecodeError:
            continue
    return "이진", "utf-8 도 cp949 도 아니다", head


def text_kind(head: bytes):
    """글자로만 된 파일의 첫머리로 종류를 가린다. (종류, 허용확장자) 또는 None."""
    s = head.decode("utf-8", "ignore").lstrip("\ufeff \t\r\n").lower()
    for mark, name, ok in TEXT_SIGN:
        if s.startswith(mark):
            return name, ok
    return None


def lied(path: Path, kind: str, tk) -> bool:
    """확장자가 실제 종류와 어긋나나. 이름을 속인 파일이 제일 위험하다."""
    if kind in ("빈 파일", "못 읽음"):
        return False
    ok = tk[1] if tk else EXT_OK.get(kind)
    if ok is None:
        return False
    return path.suffix.lower() not in ok


def shown(r: dict) -> str:
    """표에 적을 종류. 텍스트로 위장한 것은 진짜 종류를 괄호로 붙인다."""
    return "%s(%s)" % (r["kind"], r["astext"]) if r["astext"] else r["kind"]


def human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return "%.1f%s" % (n, unit) if unit != "B" else "%dB" % n
        n /= 1024.0
    return "%dB" % n


def run(tool: str, args: list[str]) -> tuple[bool, str]:
    """도구를 돌린다. (성공, 메시지)"""
    cmd = [sys.executable, str(HERE / (tool + ".py"))] + args
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return False, "%d초를 넘겨 멈췄다" % TIMEOUT
    except OSError as e:
        return False, str(e)
    if p.returncode != 0:
        msg = (p.stderr or p.stdout or "").strip().split("\n")
        return False, msg[-1] if msg else "코드 %d" % p.returncode
    return True, (p.stdout or "").strip().split("\n")[-1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("case", help="케이스 폴더")
    ap.add_argument("--out", default="", help="결과 폴더. 안 주면 <지금폴더>/07_케이스/<케이스이름>")
    ap.add_argument("--rows", type=int, default=0, help="샘플에서 읽을 행 상한. 0이면 전부")
    args = ap.parse_args()

    case = Path(args.case).resolve()
    if not case.is_dir():
        raise SystemExit("폴더가 아니다: %s" % case)

    # 케이스 폴더 옆에 두지 않는다. 공유폴더는 분석이 끝나면 비우는 자리다.
    if args.out:
        out = Path(args.out).resolve()
    else:
        # 기본값은 지금 폴더 아래다. 컨테이너에서 cwd 가 / 면 뿌리에 쓰게 된다.
        cwd = Path.cwd()
        if cwd == Path(cwd.anchor):
            raise SystemExit(
                "지금 폴더가 뿌리(%s)라 결과를 둘 자리를 못 정한다.\n"
                "--out 으로 쓸 폴더를 준다. 도커면 -v 로 붙인 자리다.\n"
                "  예) --out /out/%s" % (cwd, case.name))
        out = cwd / "07_케이스" / case.name
    try:
        out.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise SystemExit("결과 폴더를 못 만든다: %s\n  %s\n"
                         "--out 으로 쓸 수 있는 자리를 준다." % (out, e))
    if out.resolve() == case.resolve() or case.resolve() in out.resolve().parents:
        raise SystemExit("결과 폴더가 케이스 폴더 안이다. --out 으로 밖을 지정할 것")

    files = sorted(p for p in case.rglob("*") if p.is_file())
    if not files:
        raise SystemExit("파일이 없다: %s" % case)

    # ── 1. 종류 판정 ────────────────────────────────
    rows = []
    for p in files:
        kind, why, head = sniff(p)
        tk = text_kind(head) if kind == SAFE else None
        fake = lied(p, kind, tk)
        rel = p.relative_to(case).as_posix()
        hid = hidden_chars(rel)
        unsafe = win_unsafe(p.name)
        ads = streams(p)
        rows.append({"path": p, "rel": rel, "kind": kind,
                     "unsafe": unsafe, "ads": ads,
                     "astext": tk[0] if tk else "", "why": why,
                     "size": p.stat().st_size, "fake": fake, "hidden": hid,
                     "tool": TOOL.get(p.suffix.lower(), "")
                             if kind == SAFE and not fake and not hid else "",
                     "done": "", "note": ""})

    faked = [r for r in rows if r["fake"]]
    hidden = [r for r in rows if r["hidden"]]
    unsafe = [r for r in rows if r["unsafe"]]
    withads = [r for r in rows if r["ads"]]

    # 대소문자만 다른 이름. 리눅스에서는 둘인데 윈도우에서 하나가 덮인다.
    seen_low: dict = {}
    for r in rows:
        seen_low.setdefault(r["rel"].lower(), []).append(r["rel"])
    clash = [v for v in seen_low.values() if len(v) > 1]
    skipped_kind = [r for r in rows if r["kind"] not in (SAFE, "빈 파일")
                    and not r["fake"] and not r["hidden"]]

    # ── 2. 파일 목록을 tree_scan 에 태운다 ───────────
    listing = out / "_경로목록.txt"
    listing.write_text("\n".join(case.name + "/" + r["rel"] for r in rows) + "\n",
                       encoding="utf-8")
    tree_md = out / "트리.md"
    tree_ok, tree_msg = run("tree_scan", [str(listing), "--md", str(tree_md)])

    # ── 3. 텍스트만 도구에 태운다 ────────────────────
    for r in rows:
        if not r["tool"]:
            if r["hidden"]:
                r["note"] = "이름에 숨은 문자가 있다"
            elif r["fake"]:
                r["note"] = "이름을 속였다"
            elif r["kind"] == SAFE:
                r["note"] = "다루는 확장자가 아니다"
            elif r["kind"] == "빈 파일":
                r["note"] = "0 바이트"
            else:
                r["note"] = "건드리지 않았다"
            continue
        stem = r["rel"].replace("/", "_")
        if r["tool"] == "db_tree":
            md = out / ("구조_%s.md" % stem)
            ok, msg = run("db_tree", [str(r["path"]), "--md", str(md)])
        else:
            md = out / ("샘플_%s.md" % stem)
            a = [str(r["path"]), "--md", str(md)]
            if args.rows:
                a += ["--rows", str(args.rows)]
            ok, msg = run("sample_stats", a)
        r["done"] = md.name if ok else ""
        r["note"] = "" if ok else msg[:80]

    # ── 4. 요약 ─────────────────────────────────────
    total = sum(r["size"] for r in rows)
    L = []
    L.append("# 케이스 요약  %s" % case.name)
    L.append("")
    L.append("    폴더    %s" % case)
    L.append("    결과    %s" % out)
    L.append("")
    L.append("파일 %d개 · %s" % (len(rows), human(total)))
    L.append("")

    if withads:
        L.append("## 숨은 스트림이 붙은 파일 %d건" % len(withads))
        L.append("")
        L.append("| 파일 | 스트림 |")
        L.append("|---|---|")
        for r in withads:
            L.append("| %s | %s |" % (escape_hidden(r["rel"]), ", ".join(r["ads"])))
        L.append("")
        L.append("**본 스트림 뒤에 다른 내용이 붙어 있다.** 도구는 본 스트림만 읽었다.")
        L.append("`Zone.Identifier` 는 인터넷에서 받았다는 표시라 정상이다.")
        L.append("그 밖의 이름이면 사람이 먼저 본다.")
        L.append("")

    if clash:
        L.append("## 대소문자만 다른 이름 %d쌍" % len(clash))
        L.append("")
        for v in clash[:20]:
            L.append("- " + " · ".join(escape_hidden(x) for x in v))
        L.append("")
        L.append("**리눅스에서는 다른 파일이고 윈도우에서는 같은 파일이다.**")
        L.append("공유폴더로 옮길 때 하나가 조용히 덮인다. VM 안에서 이름을 갈라 놓는다.")
        L.append("")

    if unsafe:
        L.append("## 윈도우에서 문제가 되는 이름 %d건" % len(unsafe))
        L.append("")
        L.append("| 파일 | 무엇 |")
        L.append("|---|---|")
        for r in unsafe:
            L.append("| %s | %s |" % (escape_hidden(r["rel"]), ", ".join(r["unsafe"])))
        L.append("")
        L.append("**공유폴더로 옮기다 빠지거나 엉뚱한 자리로 간다.**")
        L.append("VM 안에서 이름을 바꾼 뒤 옮긴다. 원래 이름은 따로 적어 둔다.")
        L.append("")

    if hidden:
        L.append("## 이름에 숨은 문자 %d건" % len(hidden))
        L.append("")
        L.append("| 파일 | 문자 | 실제 종류 | 크기 |")
        L.append("|---|---|---|---|")
        for r in hidden:
            L.append("| %s | **%s** | %s | %s |"
                     % (escape_hidden(r["rel"]), ", ".join(r["hidden"]),
                        shown(r), human(r["size"])))
        L.append("")
        L.append("**화면에 보이는 확장자가 실제와 다를 수 있다. 도구에 안 태웠다.**")
        L.append("")
        L.append("RLO 같은 문자는 뒤의 글자를 거꾸로 그린다.")
        L.append("위 이름은 그 문자를 <U+xxxx> 로 바꿔 실었다.")
        L.append("원문 그대로 실으면 이 문서도 같이 속는다.")
        L.append("")
    else:
        L.append("## 이름에 숨은 문자 없음")
        L.append("")

    if faked:
        L.append("## 이름을 속인 파일 %d건" % len(faked))
        L.append("")
        L.append("| 파일 | 확장자 | 실제 종류 | 크기 |")
        L.append("|---|---|---|---|")
        for r in faked:
            L.append("| %s | %s | **%s** | %s |"
                     % (escape_hidden(r["rel"]), r["path"].suffix or "없음",
                        shown(r), human(r["size"])))
        L.append("")
        L.append("**확장자와 실제 종류가 어긋난다. 사람이 먼저 본다.**")
        L.append("")
    else:
        L.append("## 이름을 속인 파일 없음")
        L.append("")

    if skipped_kind:
        L.append("## 텍스트가 아니라 안 다룬 것 %d건" % len(skipped_kind))
        L.append("")
        L.append("| 파일 | 실제 종류 | 크기 |")
        L.append("|---|---|---|")
        for r in skipped_kind:
            L.append("| %s | %s | %s |"
                     % (escape_hidden(r["rel"]), shown(r), human(r["size"])))
        L.append("")
        L.append("이름과 종류는 맞다. 이 흐름에서 다루지 않을 뿐이다.")
        L.append("")

    L.append("## 파일별")
    L.append("")
    L.append("| 파일 | 실제 종류 | 크기 | 돌린 것 | 결과 |")
    L.append("|---|---|---|---|---|")
    for r in rows:
        L.append("| %s | %s | %s | %s | %s |"
                 % (escape_hidden(r["rel"]), shown(r), human(r["size"]),
                    r["tool"] or "-", r["done"] or r["note"] or "-"))
    L.append("")

    made = [r["done"] for r in rows if r["done"]]
    L.append("## 만든 것")
    L.append("")
    L.append("    트리.md            %s" % ("파일 구조 등급" if tree_ok else "실패. " + tree_msg))
    for m in made:
        L.append("    %s" % m)
    L.append("")

    L.append("## 다음")
    L.append("")
    L.append("- `트리.md` 에서 등급이 높은 경로부터 본다")
    L.append("- 구조 md 에서 개인정보 칸이 많은 표를 고른다")
    L.append("- 그 표를 `sample_stats <덤프> --table <표>` 로 따로 돌린다")
    if faked:
        L.append("- **이름을 속인 파일은 이 흐름에 넣지 않는다.** 별도로 다룬다")
    if hidden:
        L.append("- **이름에 숨은 문자가 있는 파일은 열지 않는다.** 실제 확장자를 먼저 확인한다")
    L.append("")

    (out / "00_요약.md").write_text("\n".join(L) + "\n", encoding="utf-8")

    print("케이스   %s" % case.name)
    print("파일     %d개 · %s" % (len(rows), human(total)))
    print("속인 것  %d건" % len(faked))
    print("숨은 문자 %d건" % len(hidden))
    print("숨은 스트림 %d건" % len(withads))
    print("이름 충돌  %d쌍" % len(clash))
    print("못 쓰는 이름 %d건" % len(unsafe))
    print("안 다룸  %d건" % len(skipped_kind))
    print("만든 것  %d개" % (len(made) + (1 if tree_ok else 0)))
    print("요약     %s" % (out / "00_요약.md"))


if __name__ == "__main__":
    main()
