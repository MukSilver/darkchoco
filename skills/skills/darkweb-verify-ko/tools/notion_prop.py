#!/usr/bin/env python3
"""노션 DB 에 선택 칸을 더하거나 그 칸의 값을 채운다.

    python tools/notion_prop.py show <db_id>
    python tools/notion_prop.py add <db_id> <칸이름> <값1> <값2> ...
    python tools/notion_prop.py set <page_id> <칸이름> <값>
    python tools/notion_prop.py --dry ...

읽기 전용인 `notion.py` 는 건드리지 않고 그쪽 인증과 호출만 빌려 쓴다.

**있는 칸을 덮어쓰지 않는다.** 같은 이름이 이미 있으면 멈추고 알린다.
칸을 지우는 기능은 넣지 않았다. 손으로 지우는 편이 안전하다.

`add` 는 기존 선택지를 지우지 않는다. 없는 것만 더한다.
노션 API 로는 칸 순서를 못 바꾼다. 새 칸은 맨 뒤에 붙고 사람이 끌어 옮긴다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import notion  # noqa: E402

# 노션이 받는 색 이름. 그 밖은 default 로 보낸다.
COLORS = ["default", "gray", "brown", "orange", "yellow",
          "green", "blue", "purple", "pink", "red"]


def res(db_id: str) -> str:
    """DB 를 가리키는 경로를 찾는다.

    Notion-Version 2025-09-03 부터 DB 가 database 와 data_source 로 갈렸다.
    칸 정보는 data_source 쪽에 있고, search 가 돌려주는 id 도 그쪽이다.
    옛 워크스페이스는 아직 databases 로만 열리므로 둘 다 본다.

    **`SystemExit` 도 잡는다.** `notion._call` 은 노션 오류를 `SystemExit` 로 바꿔 던진다.
    `except Exception` 만 두면 첫 경로가 404 일 때 둘째 경로를 안 보고 끝났다.
    둘 다 실패하면 마지막 까닭을 같이 낸다. 토큰이 없을 때도 그 말이 보인다."""
    까닭 = ""
    for path in ("/data_sources/" + db_id, "/databases/" + db_id):
        try:
            notion._call(path)
            return path
        except (Exception, SystemExit) as e:  # noqa: BLE001
            까닭 = str(e)
            continue
    raise SystemExit("DB 를 찾지 못했다: %s\n%s" % (db_id, 까닭))


def db(db_id: str) -> dict:
    return notion._call(res(db_id))


def props_of(d: dict) -> dict:
    return d.get("properties", {})


def cmd_show(db_id: str) -> int:
    d = db(db_id)
    print("DB  %s" % notion.title_of(d))
    print("칸 %d개\n" % len(props_of(d)))
    for name, p in props_of(d).items():
        t = p.get("type", "?")
        line = "  %-22s %s" % (name, t)
        if t in ("select", "multi_select", "status"):
            opts = (p.get(t) or {}).get("options", [])
            line += "  [" + ", ".join(o.get("name", "") for o in opts) + "]"
        print(line)
    return 0


def cmd_add(db_id: str, name: str, values: list[str], multi: bool, dry: bool) -> int:
    d = db(db_id)
    cur = props_of(d)
    kind = "multi_select" if multi else "select"

    have = cur.get(name)
    if have and have.get("type") not in (kind,):
        print("이미 %s 칸이 있고 종류가 다르다 (%s). 손으로 정리할 것"
              % (name, have.get("type")), file=sys.stderr)
        return 1

    old = [o.get("name") for o in ((have or {}).get(kind) or {}).get("options", [])] if have else []
    add = [v for v in values if v not in old]
    if have and not add:
        print("%s 칸이 이미 있고 더할 선택지가 없다" % name)
        return 0

    opts = []
    for o in ((have or {}).get(kind) or {}).get("options", []):
        opts.append({"name": o["name"], "color": o.get("color", "default")})
    for i, v in enumerate(add):
        opts.append({"name": v, "color": COLORS[(i % (len(COLORS) - 1)) + 1]})

    body = {"properties": {name: {kind: {"options": opts}}}}
    print("DB   %s" % notion.title_of(d))
    print("칸   %s (%s)" % (name, kind))
    print("더함 %s" % (", ".join(add) if add else "(없음)"))
    if old:
        print("기존 %s" % ", ".join(old))
    if dry:
        print("\ndry run. 요청을 보내지 않았다.")
        return 0
    notion._call(res(db_id), "PATCH", body)
    print("\n반영했다. **칸 순서는 API 로 못 바꾼다.** 맨 뒤에 붙으니 사람이 끌어 옮긴다")
    return 0


def cmd_set(page_id: str, name: str, value: str, dry: bool) -> int:
    body = {"properties": {name: {"select": {"name": value}}}}
    print("줄   %s" % page_id)
    print("칸   %s = %s" % (name, value))
    if dry:
        print("dry run. 요청을 보내지 않았다.")
        return 0
    notion._call("/pages/" + page_id, "PATCH", body)
    print("반영했다")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="노션 DB 에 선택 칸을 더하거나 값을 채운다")
    ap.add_argument("cmd", choices=["show", "add", "set"])
    ap.add_argument("target", help="show/add 는 db_id, set 은 page_id")
    ap.add_argument("rest", nargs="*", help="add: <칸이름> <값...> · set: <칸이름> <값>")
    ap.add_argument("--multi", action="store_true", help="add: 여러 개 고르는 칸으로")
    ap.add_argument("--dry", action="store_true", help="요청을 보내지 않고 무엇을 할지만 낸다")
    a = ap.parse_args()

    if a.cmd == "show":
        return cmd_show(a.target)
    if not a.rest:
        print("칸 이름이 필요하다", file=sys.stderr)
        return 2
    if a.cmd == "add":
        return cmd_add(a.target, a.rest[0], a.rest[1:], a.multi, a.dry)
    if len(a.rest) < 2:
        print("set 은 <칸이름> <값> 이 필요하다", file=sys.stderr)
        return 2
    return cmd_set(a.target, a.rest[0], a.rest[1], a.dry)


if __name__ == "__main__":
    raise SystemExit(main())
