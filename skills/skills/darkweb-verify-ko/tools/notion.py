"""노션 API 얇은 래퍼.

토큰은 저장소 밖 파일에서 읽는다. 값을 출력하거나 로그에 남기지 않는다.

찾는 순서는 넷이다. 먼저 걸리는 것을 쓴다.

    1. NOTION_TOKEN_FILE 환경변수가 가리키는 파일
    2. /run/secrets/notion_token          도커 관례
    3. ~/.config/darkchoco/notion_token   사람마다 하나
    4. ./.notion_token.txt                지금 폴더

**토큰 값을 환경변수로 받지 않는다.** 값을 넣으면 `docker inspect` 와
셸 히스토리에 남는다. 파일을 마운트하고 그 경로를 준다.

    python tools/notion.py search 검증
    python tools/notion.py blocks <page_id>
    python tools/notion.py md <page_id> out/page.md
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.notion.com/v1"
VERSION = "2025-09-03"
# 토큰을 찾는 자리. 위에서부터 본다.
TOKEN_PLACES = [
    Path("/run/secrets/notion_token"),
    Path.home() / ".config" / "darkchoco" / "notion_token",
    Path.home() / ".config" / "darkchoco" / "notion_token.txt",
    Path.cwd() / ".notion_token.txt",
]
TIMEOUT = 30
RETRY = 3


def _token_file() -> Path:
    """토큰 파일을 찾는다. 못 찾으면 어디를 봤는지 전부 알린다."""
    env = os.environ.get("NOTION_TOKEN_FILE")
    places = ([Path(env)] if env else []) + TOKEN_PLACES
    for p in places:
        try:
            if p.is_file():
                return p
        except OSError:
            continue
    raise SystemExit(
        "토큰 파일을 못 찾았다. 아래를 봤다.\n  "
        + "\n  ".join(str(p) for p in places)
        + "\n\n하나를 만들거나 NOTION_TOKEN_FILE 로 경로를 준다.\n"
          "도커면 -v <토큰파일>:/run/secrets/notion_token:ro 로 붙인다.\n"
          "노션 없이도 ③④⑤⑥ 은 돈다. 그 절을 안 봄 으로 적고 진행하면 된다.")


def _token() -> str:
    p = _token_file()
    t = p.read_text(encoding="utf-8").strip()
    if not t:
        raise SystemExit(f"토큰 파일이 비어 있다: {p}")
    return t


def _call(path: str, method: str = "GET", body: dict | None = None) -> dict:
    url = path if path.startswith("http") else API + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": "Bearer " + _token(),
            "Notion-Version": VERSION,
            "Content-Type": "application/json",
        },
    )
    last = None
    for i in range(RETRY):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503):
                last = e
                time.sleep(1.5 * (i + 1))
                continue
            raise SystemExit(f"{e.code} {e.reason} — {path}")
        except urllib.error.URLError as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise SystemExit(f"재시도 {RETRY}회 실패 — {path} ({last})")


def title_of(obj: dict) -> str:
    if obj.get("object") == "page":
        for v in obj.get("properties", {}).values():
            if v.get("type") == "title":
                return "".join(x["plain_text"] for x in v["title"])
    return "".join(x["plain_text"] for x in obj.get("title", []))


def search(query: str = "", page_size: int = 100) -> list[dict]:
    body = {"page_size": page_size}
    if query:
        body["query"] = query
    return _call("/search", "POST", body)["results"]


def latest(query: str) -> dict | None:
    """같은 이름 페이지가 여럿일 때 최근 수정본을 고른다."""
    hits = [r for r in search(query) if title_of(r)]
    if not hits:
        return None
    return max(hits, key=lambda r: r.get("last_edited_time", ""))


def children(block_id: str) -> list[dict]:
    out, cursor = [], None
    while True:
        u = f"/blocks/{block_id}/children?page_size=100"
        if cursor:
            u += "&start_cursor=" + cursor
        d = _call(u)
        out += d["results"]
        if not d.get("has_more"):
            return out
        cursor = d["next_cursor"]
        time.sleep(0.15)


def _rt(v: dict) -> str:
    return "".join(r.get("plain_text", "") for r in v.get("rich_text", []))


def to_markdown(block_id: str, depth: int = 0, acc: list[str] | None = None) -> str:
    if acc is None:
        acc = []
    for b in children(block_id):
        t = b["type"]
        v = b.get(t, {})
        pad = "  " * depth
        if t == "heading_1":
            acc.append("\n# " + _rt(v))
        elif t == "heading_2":
            acc.append("\n## " + _rt(v))
        elif t == "heading_3":
            acc.append("\n### " + _rt(v))
        elif t == "bulleted_list_item":
            acc.append(pad + "- " + _rt(v))
        elif t == "numbered_list_item":
            acc.append(pad + "1. " + _rt(v))
        elif t in ("callout", "quote"):
            acc.append("> " + _rt(v).replace("\n", "\n> "))
        elif t == "code":
            acc.append("```")
            acc.append(_rt(v))
            acc.append("```")
        elif t == "divider":
            acc.append("\n---\n")
        elif t == "table":
            rows = children(b["id"])
            for i, r in enumerate(rows):
                cs = r["table_row"]["cells"]
                acc.append("| " + " | ".join("".join(x["plain_text"] for x in c) for c in cs) + " |")
                if i == 0 and v.get("has_column_header"):
                    acc.append("|" + "---|" * len(cs))
            continue
        elif t == "table_of_contents":
            continue
        else:
            s = _rt(v) if isinstance(v, dict) else ""
            if s.strip():
                acc.append(s)
        if b.get("has_children") and t != "table":
            to_markdown(b["id"], depth + 1, acc)
    return "\n".join(acc)


def _main(argv: list[str]) -> None:
    if len(argv) < 2:
        raise SystemExit(__doc__)
    cmd = argv[1]
    if cmd == "search":
        q = argv[2] if len(argv) > 2 else ""
        for r in search(q):
            kind = "DB " if r["object"] == "data_source" else "page"
            print(f"{kind} {r['id']}  {r.get('last_edited_time','')[:16]}  {title_of(r)[:60]}")
    elif cmd == "blocks":
        print(json.dumps(children(argv[2]), ensure_ascii=False, indent=2))
    elif cmd == "md":
        text = to_markdown(argv[2])
        if len(argv) > 3:
            p = Path(argv[3])
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text + "\n", encoding="utf-8")
            print(f"{p}  {len(text)}자")
        else:
            print(text)
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    _main(sys.argv)
