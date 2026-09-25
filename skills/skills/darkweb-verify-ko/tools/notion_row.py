#!/usr/bin/env python3
"""⑨ 출력을 노션 DB 행으로 만든다.

**미리보기가 기본이다.** `--commit` 을 붙여야 실제로 쓴다.
기존 행을 고치지 않는다. 새 행만 만든다.

**예외가 하나 있다 (2026-09-25).** 행위자 DB 에 같은 핸들이 이미 있고 그 줄 비고에
「수집 DB 게시자 핸들에서」 가 있으면 기계가 만든 얇은 줄이다. 그때는 새 줄을 만들지 않고
**그 줄의 빈 칸만** 채운다. 사람이 만든 줄이면 지금처럼 건드리지 않고 멈춘다.

    python tools/notion_row.py 검증 out9.txt
    python tools/notion_row.py 검증 out9.txt --exclude "검증 자료,한계"
    python tools/notion_row.py 검증 out9.txt --set "검증자=이름"
    python tools/notion_row.py 검증 out9.txt --commit

입력 파일은 ⑨ 출력 그대로다. 한 줄에 `칸 이름: 값` 형식.
빈 값과 자동 생성 칸(생성일, 최근 1주 등)은 알아서 건너뛴다.

relation 칸은 사건 ID 로 준다. `같은 사건: LEAK-8` 처럼 쓰면 그 줄을 찾아 잇는다.
여럿이면 쉼표로 나눈다. 못 찾으면 잇지 않고 확인할 것에 적는다.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from notion import _call, search, title_of

READONLY = {"formula", "created_time", "last_edited_time", "unique_id",
            "created_by", "last_edited_by", "rollup"}
TRUE = {"예", "true", "True", "1", "O", "o", "체크"}


def find_db(name: str) -> tuple[str, str]:
    """이름으로 data_source 를 찾는다. 토큰마다 워크스페이스가 달라 ID를 박지 않는다."""
    hits = [r for r in search(name) if r.get("object") == "data_source"]
    if not hits:
        raise SystemExit(f"'{name}' 이름의 DB를 못 찾았다. notion.py search 로 확인할 것")
    if len(hits) > 1:
        # **정확히 같은 이름을 먼저 본다.** `search` 가 부분 일치라
        # `랜섬웨어 DB` 를 주면 `랜섬웨어 DB, 참고용` 이 함께 걸린다
        exact = [h for h in hits if title_of(h).strip() == name.strip()]
        if len(exact) != 1:
            names = ", ".join(title_of(h) for h in hits)
            raise SystemExit(f"같은 이름이 여럿이다: {names}. 정확한 이름을 줄 것")
        hits = exact
    return hits[0]["id"], title_of(hits[0])


# 페이지 본문으로 갈 항목. 칸이 아니라 블록이다.
BODY_MARK = "--- 아래는 페이지 본문에 붙인다. 칸이 아니다 ---"
BODY_KEYS = [("캡처", "paragraph"), ("연락처", "paragraph"),
             ("참고사항", "bulleted_list_item")]

# 이 칸이 비면 미리보기에서 알린다. 사람만 아는 값이라 물어봐야 채워진다.
# 여기 있는 DB 만 페이지 본문도 본다. 행위자·포럼 DB 는 칸만 쓴다.
#
# **`수집자` 를 2026-09-22 에 더했다.** 손 조사 결과를 올리는 길이 이 도구뿐인데,
# 팀원마다 쓰는 AI 가 달라 `--set "수집자=이름"` 을 빠뜨리면 그냥 빈칸으로 들어갔다.
# 실측으로 197줄 중 1줄이 이미 그렇게 비어 있었다. 여러 사람이 올리기 시작하면
# 그 비율이 커진다.
ASK_IF_EMPTY = {"수집": ["원문 URL", "게시 플랫폼", "수집자"]}


def _겹침규칙():
    """`push.py` 의 겹침 열쇠 두 함수를 빌려 온다. 못 찾으면 None.

    **여기서 규칙을 새로 쓰지 않는다.** 기계가 올리는 쪽(`push.py`)과 사람이
    올리는 쪽(이 도구)이 겹침을 다르게 보면, 같은 글이 두 줄로 들어온다.
    열쇠는 `UID` → `원문 URL` → `제목|게시 플랫폼` 차례다.

    이 스킬은 `cp -R` 한 번으로 떼어 갈 수 있어야 해서 `hub/` 가 없을 수도 있다.
    그때는 겹침 검사를 건너뛰고 미리보기에 그렇게 적는다. `_dcpath` 와 같은 태도다.
    """
    here = Path(__file__).resolve().parent
    for parent in [here, *here.parents]:
        if (parent / "hub" / "events" / "push.py").is_file():
            if str(parent) not in sys.path:
                sys.path.insert(0, str(parent))
            try:
                from hub.events.push import _노션줄의_열쇠, _열쇠  # noqa: E402
                return _열쇠, _노션줄의_열쇠
            except Exception:
                return None
    return None


def 겹치는가(ds_id: str, body: dict) -> tuple[bool, str]:
    """이미 있는 줄인지 본다. (겹치나, 사람에게 할 말).

    `body` 는 노션에 보낼 꼴이라 값을 도로 꺼내 열쇠를 만든다.
    """
    규칙 = _겹침규칙()
    if 규칙 is None:
        return False, "겹침 검사를 건너뛴다. `hub/events/push.py` 를 못 찾았다"
    _열쇠, _노션줄의_열쇠 = 규칙

    def 글(칸: str) -> str:
        v = body.get(칸) or {}
        if "rich_text" in v:
            return "".join(x.get("text", {}).get("content", "") for x in v["rich_text"])
        if "title" in v:
            return "".join(x.get("text", {}).get("content", "") for x in v["title"])
        return ""

    내uid = 글("UID").strip()
    내열쇠 = _열쇠(글("원문 URL"), 글("자료 제목"), 글("게시 플랫폼"))

    for r in _모든줄(ds_id):
        uid, k = _노션줄의_열쇠(r)
        if 내uid and uid and 내uid == uid:
            return True, "UID 가 같은 줄이 이미 있다: %s" % (r.get("url") or r["id"])
        if 내열쇠 and k == 내열쇠:
            return True, "열쇠가 같은 줄이 이미 있다 (%s): %s" % (
                "원문 URL" if 글("원문 URL").strip() else "제목|게시 플랫폼",
                r.get("url") or r["id"])
    return False, ""


# 행위자 DB 에서 기계가 만든 줄의 표지 (2026-09-25). `hub/events/actor.py` 가 수집 DB 를
# 훑어 판매 · 공개 핸들을 올리면서 비고에 이 말을 단다. 9/25 소급 줄도 같다.
# ⑨-3 은 이 줄을 만나면 빈 칸만 채운다. 검증하며 알아낸 별칭 · 국가 · 지갑이 들어갈 자리다.
자동표지 = "수집 DB 게시자 핸들에서"


def _키(s: str) -> str:
    """핸들 열쇠. **`hub/events/actor.py` 의 `키()` 와 같아야 한다.**

    이 스킬은 `cp -R` 로 떼어 갈 수 있어야 해서 가져오지 않고 옮겨 적는다.
    """
    return re.sub(r"[^a-z0-9가-힣]", "", (s or "").lower()).replace("0", "o")


def _조각(s: str) -> list[str]:
    """다른 이름을 이름 조각으로. **괄호 안(어디서 쓰는 닉인지)은 이름이 아니라 떼고 자른다.**

    괄호까지 세면 「(Signal)」 · 「(breached.st)」 가 별칭이 되어 남의 줄과 맞았다(2026-09-25 검토).
    `hub/events/actor.py` 의 `조각()` 과 같아야 한다.
    """
    s = re.sub(r"\([^)]*\)", " ", s or "")
    return [x.strip(" .'\"") for x in re.split(r"[,·/|;\n]|\s+또는\s+", s) if x.strip(" .'\"")]


def _보낼글(v: dict) -> str:
    """노션에 보낼 꼴의 title · rich_text 에서 글자를 꺼낸다."""
    for t in ("title", "rich_text"):
        if t in v:
            return "".join(x.get("text", {}).get("content", "") for x in v[t])
    return ""


def _읽은글(v: dict) -> str:
    """노션이 돌려준 꼴의 title · rich_text 에서 글자를 꺼낸다."""
    t = (v or {}).get("type")
    if t in ("title", "rich_text"):
        return "".join(x.get("plain_text", "") for x in v.get(t) or [])
    return ""


def _비었나(v: dict) -> bool:
    """이미 있는 줄의 칸이 비었나. 체크 칸은 끔도 값이라 빈 칸으로 안 본다."""
    t = (v or {}).get("type")
    if t is None or t == "checkbox":
        return t is None
    x = v.get(t)
    if t in ("title", "rich_text"):
        return not _읽은글(v).strip()
    return x in (None, "", [], {})


def 행위자_기존줄(ds_id: str, props: dict, body: dict) -> list[dict]:
    """행위자 DB 에서 같은 핸들(또는 다른 이름)을 가진 줄 **전부.** 없으면 빈 목록.

    첫 줄만 돌려주면 줄 차례에 따라 사람 줄에서 멈추기도 하고 기계 줄을 고치기도 했다
    (2026-09-25 검토). 여럿이면 부르는 쪽이 멈춘다.
    """
    제목 = next((k for k, v in props.items() if v["type"] == "title"), "")
    내것 = [_보낼글(body.get(제목) or {})] + _조각(_보낼글(body.get("다른 이름") or {}))
    내키 = {_키(x) for x in 내것 if _키(x)}
    if not 내키:
        return []
    맞음 = []
    for r in _모든줄(ds_id):
        pr = r.get("properties") or {}
        그쪽 = [_읽은글(pr.get(제목))] + _조각(_읽은글(pr.get("다른 이름")))
        if 내키 & {_키(x) for x in 그쪽 if _키(x)}:
            맞음.append(r)
    return 맞음


def 빈칸만(기존: dict, body: dict, 오늘: str) -> tuple[dict, list[str]]:
    """기계가 만든 줄에 쓸 칸. (쓸 것, 이미 차서 안 쓰는 칸). 비고 끝에 채운 날을 붙인다."""
    pr = 기존.get("properties") or {}
    쓸것 = {k: v for k, v in body.items() if k in pr and _비었나(pr[k])}
    안씀 = [k for k in body if k not in 쓸것]
    if 쓸것 and "비고" in pr:
        옛 = _읽은글(pr["비고"]).rstrip()
        덧 = "%s ⑨-3 에서 빈 칸 채움 (%s)" % (오늘, " · ".join(쓸것))
        쓸것["비고"] = {"rich_text": [{"text": {"content": (옛 + "\n" + 덧).strip()[:2000]}}]}
    return 쓸것, 안씀


def _모든줄(ds_id: str) -> list[dict]:
    """DB 전체를 읽는다. 100줄씩 끊어 온다."""
    out, cursor = [], None
    while True:
        body = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        r = _call(f"/data_sources/{ds_id}/query", "POST", body)
        out += r.get("results", [])
        if not r.get("has_more"):
            return out
        cursor = r.get("next_cursor")


def parse_body(text: str) -> list[tuple[str, str, str]]:
    """본문 표시줄 뒤에서 (제목, 블록종류, 내용) 을 순서대로 뽑는다.

    parse_output 은 같은 칸 이름이 여러 줄이면 마지막만 남긴다.
    참고사항은 여러 줄이 정상이라 따로 읽는다.
    """
    if BODY_MARK not in text:
        return []
    tail = text.split(BODY_MARK, 1)[1]
    out: list[tuple[str, str, str]] = []
    for name, kind in BODY_KEYS:
        for line in tail.split("\n"):
            line = line.strip()
            if not line.startswith(name + ":"):
                continue
            val = line.split(":", 1)[1].strip()
            if val:
                out.append((name, kind, val))
    return out


def body_blocks(items: list[tuple[str, str, str]]) -> list[dict]:
    """본문 항목을 노션 블록으로 바꾼다. 제목마다 heading_3 을 앞에 둔다."""
    def rt(s: str) -> list[dict]:
        return [{"type": "text", "text": {"content": s[:2000]}}]

    out: list[dict] = []
    seen: set[str] = set()
    for name, kind, val in items:
        if name not in seen:
            seen.add(name)
            out.append({"object": "block", "type": "heading_3",
                        "heading_3": {"rich_text": rt(name)}})
        out.append({"object": "block", "type": kind, kind: {"rich_text": rt(val)}})
    return out


def parse_output(text: str) -> dict[str, str]:
    """⑨ 출력에서 '칸: 값' 을 뽑는다.

    **4칸 이상 들여쓴 줄은 앞 칸의 값에 이어 붙인다.**
    검증 요약과 한계는 한 줄에 안 들어간다. 위험도 절만 다섯 줄이다.
    들여쓴 줄 안의 콜론을 새 칸으로 읽지 않는다.
    """
    out: dict[str, str] = {}
    cur = ""
    body = text.split(BODY_MARK, 1)[0]      # 본문 절은 여기서 안 읽는다
    for line in body.split("\n"):
        line = line.rstrip()
        if not line.strip():
            if cur:
                out[cur] += "\n"
            continue
        if line.lstrip().startswith(("#", "*", "[", "■", "```", "|")):
            cur = ""
            continue
        # 4칸 이상 들여쓴 줄은 앞 값의 이어짐이다
        if cur and re.match(r"^ {4,}\S", line):
            out[cur] += "\n" + line.strip()
            continue
        if line.lstrip().startswith("-"):
            cur = ""
            continue
        m = re.match(r"^ {0,3}([^:]{1,30}?)\s*:\s*(.*)$", line)
        if not m:
            cur = ""
            continue
        key, val = m.group(1).strip(), m.group(2).strip()
        # 주석성 꼬리표 제거
        val = re.sub(r"\s{2,}\(.*\)$", "", val)
        if not key:
            cur = ""
            continue
        out[key] = val
        cur = key
    return {k: v.strip() for k, v in out.items() if v.strip()}


_ROWS: dict[str, list[dict]] = {}


def _target_rows(ds_id: str) -> list[dict]:
    """상대 DB 의 줄을 한 번만 받아 둔다."""
    if ds_id not in _ROWS:
        out, cursor = [], None
        while True:
            body: dict = {"page_size": 100}
            if cursor:
                body["start_cursor"] = cursor
            d = _call(f"/data_sources/{ds_id}/query", "POST", body)
            out += d["results"]
            if not d.get("has_more"):
                break
            cursor = d["next_cursor"]
        _ROWS[ds_id] = out
    return _ROWS[ds_id]


def _row_labels(row: dict) -> set[str]:
    """이 줄을 부를 수 있는 이름들. 사건 ID 와 제목."""
    out: set[str] = set()
    for v in row.get("properties", {}).values():
        ty = v.get("type")
        if ty == "unique_id":
            u = v.get("unique_id") or {}
            pre, num = (u.get("prefix") or ""), u.get("number")
            if num is not None:
                out.add(f"{pre}-{num}".lower())
                out.add(f"{pre}{num}".lower())
                out.add(str(num))
        elif ty == "title":
            s = "".join(x.get("plain_text", "") for x in v.get("title", []))
            if s.strip():
                out.add(s.strip().lower())
    return out


def resolve_relation(ds_id: str, raw: str) -> tuple[list[str], list[str]]:
    """사건 ID 나 제목을 page id 로 바꾼다. (찾은 것, 못 찾은 것)"""
    want = [x.strip() for x in re.split(r"[,·/]", raw) if x.strip()]
    found, missing = [], []
    rows = _target_rows(ds_id)
    for w in want:
        key = w.lower()
        hit = next((r for r in rows if key in _row_labels(r)), None)
        if hit:
            if hit["id"] not in found:
                found.append(hit["id"])
        else:
            missing.append(w)
    return found, missing


def build(props: dict, values: dict[str, str]) -> tuple[dict, list[str], list[str]]:
    """노션 properties 를 만든다. 못 넣은 것과 경고를 함께 낸다."""
    body: dict = {}
    skipped: list[str] = []
    warn: list[str] = []

    known_body = {n for n, _ in BODY_KEYS}
    for key, raw in values.items():
        if key not in props:
            if key in known_body:
                continue          # 본문으로 간다. 따로 보고한다
            skipped.append(f"{key}  DB에 없는 칸")
            continue
        t = props[key]["type"]
        if t in READONLY:
            skipped.append(f"{key}  자동 생성 칸이라 입력 불가")
            continue

        if t == "title":
            body[key] = {"title": [{"text": {"content": raw[:2000]}}]}
        elif t == "rich_text":
            body[key] = {"rich_text": [{"text": {"content": raw[:2000]}}]}
        elif t == "number":
            num = re.sub(r"[^\d.\-]", "", raw)
            if not num:
                skipped.append(f"{key}  숫자로 못 읽음: {raw}")
                continue
            body[key] = {"number": float(num)}
        elif t == "checkbox":
            body[key] = {"checkbox": raw in TRUE}
        elif t == "date":
            m = re.search(r"\d{4}-\d{2}-\d{2}", raw)
            if not m:
                skipped.append(f"{key}  날짜로 못 읽음: {raw}")
                continue
            body[key] = {"date": {"start": m.group(0)}}
        elif t == "select":
            opts = [o["name"] for o in props[key]["select"]["options"]]
            if raw not in opts:
                warn.append(f"{key}  '{raw}' 는 없는 선택지다. 있는 것: {', '.join(opts)}")
                skipped.append(f"{key}  선택지에 없어 건너뜀")
                continue
            body[key] = {"select": {"name": raw}}
        elif t == "multi_select":
            opts = [o["name"] for o in props[key]["multi_select"]["options"]]
            # 선택지 이름 안에도 · 가 있다 (2차 기사·리스트업).
            # 쉼표와 빗금으로 먼저 자르고, 안 맞는 조각만 · 로 더 자른다.
            items = []
            for chunk in re.split(r"[,/]", raw):
                chunk = chunk.strip()
                if not chunk:
                    continue
                if chunk in opts or "·" not in chunk:
                    items.append(chunk)
                else:
                    items += [x.strip() for x in chunk.split("·") if x.strip()]
            bad = [x for x in items if x not in opts]
            if bad:
                warn.append(f"{key}  없는 선택지 {', '.join(bad)}. 있는 것: {', '.join(opts)}")
            ok = [x for x in items if x in opts]
            if not ok:
                skipped.append(f"{key}  넣을 선택지가 없어 건너뜀")
                continue
            body[key] = {"multi_select": [{"name": x} for x in ok]}
        elif t == "url":
            body[key] = {"url": raw}
        elif t == "relation":
            ds = props[key].get("relation", {}).get("data_source_id", "")
            if not ds:
                skipped.append(f"{key}  상대 DB를 못 찾음")
                continue
            ids, missing = resolve_relation(ds, raw)
            if missing:
                warn.append(f"{key}  못 찾은 줄: {', '.join(missing)}. 사건 ID 나 제목 그대로 줄 것")
            if not ids:
                skipped.append(f"{key}  이을 줄을 못 찾아 건너뜀")
                continue
            body[key] = {"relation": [{"id": i} for i in ids]}
        else:
            skipped.append(f"{key}  다루지 않는 칸 종류 {t}")
    return body, skipped, warn


def show(dbname: str, props: dict, body: dict, skipped: list[str],
         warn: list[str], excluded: list[str],
         blocks: list[dict] | None = None) -> None:
    blocks = blocks or []
    print(f"\n대상 DB   {dbname}")
    print(f"넣을 칸   {len(body)}개")
    print(f"본문 블록  {len(blocks)}개\n")
    print("| 칸 | 종류 | 값 |")
    print("|---|---|---|")
    for k, v in body.items():
        t = props[k]["type"]
        if t in ("title", "rich_text"):
            s = v[t][0]["text"]["content"]
        elif t == "select":
            s = v["select"]["name"]
        elif t == "multi_select":
            s = ", ".join(x["name"] for x in v["multi_select"])
        elif t == "date":
            s = v["date"]["start"]
        elif t == "checkbox":
            s = "체크" if v["checkbox"] else "해제"
        elif t == "relation":
            s = f"{len(v['relation'])}줄과 이음"
        else:
            s = str(v.get(t))
        s = s.replace("\n", " ")
        print(f"| {k} | {t} | {s[:70]}{'...' if len(s) > 70 else ''} |")

    if excluded:
        print("\n[사람이 뺀 칸]")
        for k in excluded:
            print(f"  {k}")
    if skipped:
        print("\n[못 넣은 칸]")
        for s in skipped:
            print(f"  {s}")
    if blocks:
        print("\n[페이지 본문]")
        for b in blocks:
            t = b["type"]
            s = b[t]["rich_text"][0]["text"]["content"].replace("\n", " ")
            head = "  " if t == "heading_3" else "    - "
            print(f"{head}{s[:76]}{'...' if len(s) > 76 else ''}")
    if warn:
        print("\n[확인할 것]")
        for w in warn:
            print(f"  {w}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("db", help="DB 이름. 예: 검증, 수집")
    ap.add_argument("infile", help="⑨ 출력 파일")
    ap.add_argument("--exclude", default="", help="뺄 칸. 쉼표 구분")
    ap.add_argument("--set", dest="sets", action="append", default=[],
                    help="칸=값 으로 고침. 여러 번 쓸 수 있다")
    ap.add_argument("--commit", action="store_true", help="실제로 행을 만든다")
    args = ap.parse_args()

    ds_id, dbname = find_db(args.db)
    props = _call(f"/data_sources/{ds_id}")["properties"]

    text = Path(args.infile).read_text(encoding="utf-8")
    values = parse_output(text)
    blocks = body_blocks(parse_body(text))

    excluded = [x.strip() for x in args.exclude.split(",") if x.strip()]
    for k in excluded:
        values.pop(k, None)
    for pair in args.sets:
        if "=" not in pair:
            raise SystemExit(f"--set 은 칸=값 형식이다: {pair}")
        k, v = pair.split("=", 1)
        values[k.strip()] = v.strip()

    body, skipped, warn = build(props, values)
    if not body:
        raise SystemExit("넣을 칸이 하나도 없다. 입력 형식을 확인할 것")

    # 사람만 아는 값이 비었으면 알린다. 물어보라는 뜻이다.
    for k in ASK_IF_EMPTY.get(args.db.strip(), []):
        if k in props and k not in body and k not in excluded:
            warn.append(f"{k} 이(가) 비었다. 캡처에 없으면 사람에게 묻는다. "
                        f"원문 URL 이 포럼을 정한다")
    if not blocks and args.db.strip() in ASK_IF_EMPTY:
        warn.append("페이지 본문이 없다. 캡처·연락처·참고사항을 안 냈는지 확인한다")

    # 겹침을 본다. 수집 DB 만이다 — 열쇠 규칙이 그 DB 를 전제로 만들어졌다.
    겹침, 겹침말 = (False, "")
    if args.db.strip() == "수집":
        겹침, 겹침말 = 겹치는가(ds_id, body)
        if 겹침:
            warn.append("**이미 있는 줄이다.** " + 겹침말)
        elif 겹침말:
            warn.append(겹침말)

    # 행위자 DB 는 같은 핸들이 있는지 본다. ⑨-3 을 돌리는 자리다 (2026-09-25).
    기존 = None
    if "행위자" in dbname or args.db.strip() == "행위자":
        맞음 = 행위자_기존줄(ds_id, props, body)
        사람줄 = [r for r in 맞음 if 자동표지 not in _읽은글((r.get("properties") or {}).get("비고"))]
        if 사람줄:
            show(dbname, props, body, skipped, warn, excluded, blocks)
            print("\n**사람이 만든 줄이 이미 있다.** ⑨-3 은 그 줄을 건드리지 않는다.")
            for r in 사람줄:
                print(r.get("url") or r["id"])
            raise SystemExit(1)
        if len(맞음) > 1:
            show(dbname, props, body, skipped, warn, excluded, blocks)
            print("\n**기계가 만든 줄이 여럿 맞는다.** 어느 줄에 채울지 사람이 정한다. 아무것도 안 쓴다.")
            for r in 맞음:
                print(r.get("url") or r["id"])
            raise SystemExit(1)
        기존 = 맞음[0] if 맞음 else None
        if 기존 is not None:
            오늘 = datetime.now(timezone(timedelta(hours=9))).date().isoformat()
            body, 안씀 = 빈칸만(기존, body, 오늘)
            warn.append("기계가 만든 줄이 이미 있다. **새 줄을 안 만들고 빈 칸만 채운다.** "
                        + (기존.get("url") or 기존["id"]))
            if 안씀:
                warn.append("이미 차 있어 안 쓰는 칸: " + ", ".join(안씀))

    show(dbname, props, body, skipped, warn, excluded, blocks)

    if 기존 is not None and not body:
        print("\n채울 빈 칸이 없다. 쓰지 않는다.")
        return

    if 겹침:
        print("\n겹치는 줄이 있어 멈춘다. " + 겹침말)
        print("**같은 글을 두 줄로 만들지 않는다.** 고칠 것이 있으면 노션에서 그 줄을 고친다.")
        print("정말 새 줄이 맞으면 원문 URL 을 채워 열쇠를 다르게 한다.")
        raise SystemExit(1)

    if not args.commit:
        print("\n미리보기다. 실제로 쓰지 않았다.")
        print("뺄 칸이 있으면  --exclude \"칸1,칸2\"")
        print("고칠 칸이 있으면 --set \"칸=값\"")
        print("그대로 올리려면 --commit")
        return

    if 기존 is not None:
        _call(f"/pages/{기존['id']}", "PATCH", {"properties": body})
        print(f"\n기계가 만든 줄의 빈 칸 {len(body)}개를 채웠다")
        print(기존.get("url") or 기존["id"])
        return

    page = _call("/pages", "POST",
                 {"parent": {"type": "data_source_id", "data_source_id": ds_id},
                  "properties": body})
    if blocks:
        # 노션은 한 번에 100 블록까지 받는다.
        for i in range(0, len(blocks), 100):
            _call(f"/blocks/{page['id']}/children", "PATCH",
                  {"children": blocks[i:i + 100]})
    print(f"\n행을 만들었다. 칸 {len(body)}개 · 본문 {len(blocks)}블록")
    print(page.get("url", page["id"]))


if __name__ == "__main__":
    main()
