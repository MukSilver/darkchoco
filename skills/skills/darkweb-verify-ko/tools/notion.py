"""노션 API 얇은 래퍼.

토큰은 저장소 밖 파일에서 읽는다. 값을 출력하거나 로그에 남기지 않는다.

찾는 순서는 넷이다. 먼저 걸리는 것을 쓴다.

    1. NOTION_TOKEN_FILE 환경변수가 가리키는 파일
    2. /run/secrets/notion_token          도커 관례
    3. ~/.config/darkchoco/notion_token   사람마다 하나
    4. ./.notion_token.txt                지금 폴더

찾는 자리와 재시도는 packages/dc_notion 에 있다.

**토큰 값을 환경변수로 받지 않는다.** 값을 넣으면 `docker inspect` 와
셸 히스토리에 남는다. 파일을 마운트하고 그 경로를 준다.

**DB id 는 환경변수로 받을 수 있다 (2026-09-25).** id 는 비밀이 아니다. `NOTION_VERIFY_DB` 에
검증 DB 의 id(또는 노션 주소)를 넣어 두면 이름 검색을 건너뛴다. 없으면 지금처럼 이름으로 찾는다.
`db_from_env()` 를 본다.

    python tools/notion.py search 검증
    python tools/notion.py blocks <page_id>
    python tools/notion.py md <page_id> out/page.md
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

# 경로·재시도·토큰 탐색은 packages/dc_notion 이 맡습니다.
# 환경변수로 토큰을 받지 않는 방침은 그대로입니다(allow_env_token=False).
#
# 이 스킬은 cp -R 로 떼어 갈 수 있어야 하므로, 저장소 밖에서도 부품을 찾게
# _dcpath 에 맡깁니다. 못 찾아도 import 는 되어야 합니다. 노션을 안 쓰는
# 절(③④⑤⑥)이 그대로 돌아야 하기 때문입니다.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _dcpath import ensure_packages, missing_message, use_utf8  # noqa: E402

use_utf8()

if ensure_packages():
    from dc_notion import API, VERSION, Notion, NotionError  # noqa: E402
else:
    API = "https://api.notion.com/v1"
    VERSION = ""

    class NotionError(RuntimeError):
        pass

    class Notion:                                        # noqa: D101
        def __init__(self, *a, **k):
            raise SystemExit(missing_message())

_client: Notion | None = None


def _notion() -> Notion:
    """처음 부를 때만 만든다. 토큰이 없어도 import 는 되어야 한다.

    이 스킬은 노션 없이도 ③④⑤⑥ 절이 돌기 때문이다.
    """
    global _client
    if _client is None:
        try:
            _client = Notion(verbose=False, allow_env_token=False)
        except RuntimeError as e:
            raise SystemExit(
                str(e) + "\n노션 없이도 ③④⑤⑥ 은 돈다. 그 절을 안 봄 으로 적고 진행하면 된다."
            ) from e
    return _client


def _call(path: str, method: str = "GET", body: dict | None = None) -> dict:
    """노션에 요청한다. 실패하면 예전처럼 메시지를 남기고 끝낸다."""
    try:
        return _notion()._request(method, path, body)
    except NotionError as e:
        raise SystemExit(str(e)) from e


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


# 이름 검색을 건너뛸 DB 와 그 환경변수 (2026-09-25 최현서 결정).
#
# 이름 검색은 같은 이름이 여럿이면 멈춘다. 「랜섬웨어 DB, 참고용」 에 걸려 멈춘 적이 있다.
# 검증 DB 는 코드 어디에도 id 가 없어 늘 이름으로 찾았다. **id 를 코드에 적지 않는다.**
# 이 스킬은 떼어 가 다른 워크스페이스에서도 돌아야 한다. 환경변수가 없으면 검색으로 물러난다.
DB_ENV = {"검증": "NOTION_VERIFY_DB", "검증 DB": "NOTION_VERIFY_DB"}

_ID = re.compile(r"[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}", re.I)


def db_from_env(name: str) -> tuple[str, str] | None:
    """환경변수에 적힌 DB 의 (data_source id, 이름). 변수가 없으면 None.

    값은 data_source id · database id · 노션 주소 어느 것이든 받는다. 주소면 처음 나오는
    id 를 쓴다(뒤의 `?v=` 는 보기 id 다). database id 면 첫 data_source 로 옮겨 간다.
    **변수가 있는데 못 열면 검색으로 물러나지 않고 멈춘다.** 잘못 적은 값을 조용히 넘기면
    엉뚱한 DB 를 검색으로 집을 수 있다.
    """
    env = DB_ENV.get((name or "").strip())
    raw = (os.environ.get(env) or "").strip() if env else ""
    if not raw:
        return None
    m = _ID.search(raw)
    if not m:
        raise SystemExit(f"{env} 에서 노션 id 를 못 읽었다. id 나 노션 주소를 넣는다. 비우면 이름으로 찾는다")
    ident = m.group(0)
    까닭 = ""
    for path in (f"/data_sources/{ident}", f"/databases/{ident}"):
        try:
            d = _call(path)
        except (Exception, SystemExit) as e:  # noqa: BLE001  _call 은 실패를 SystemExit 로 던진다
            까닭 = str(e)
            continue
        if d.get("object") == "database":
            dss = d.get("data_sources") or []
            if not dss:
                까닭 = "database 에 data_source 가 없다"
                continue
            return dss[0]["id"], title_of(d)
        return d.get("id") or ident, title_of(d)
    raise SystemExit(f"{env} 가 가리키는 DB 를 못 열었다: {ident}\n{까닭}\n"
                     f"값을 확인하거나 {env} 를 비우면 이름으로 찾는다")


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
