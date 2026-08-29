#!/usr/bin/env python3
"""수집한 것을 넣는 한 표. 랜섬·텔레그램·포럼이 여기로 모인다.

    from dc_store import Store, Item
    s = Store(Path("data/darkchoco.db"))
    s.put(Item(source="ransom", venue="titanblog.org", ...))

`skills/darkweb-verify-ko/tools/feed_parse.py` 가 이 표를 읽어 ③ 입력 14칸으로 바꾼다.

## 다른 수집기를 보고 정한 것

2026-08-26 에 팀원의 Kr-Leak-alarm 을 읽고 물린 자리 넷을 여기서 막는다.

| 물린 자리 | 여기서 |
|---|---|
| 내보낼 때 URL 을 무력화해 같은 글 판별이 깨졌다 | **URL 을 손대지 않는다.** 무력화는 보여줄 때만 한다 |
| `description` 이 게시글 본문인 줄 알았는데 회사 소개였다 | `body_kind` 로 **본문이 어디서 왔는지** 적는다 |
| 요약 사이트 셋을 독립 출처로 셀 뻔했다 | `post_url`(원 출처)과 `via`(어디서 알았나)를 나눈다 |
| 삭제 경로가 하나도 없어 본문이 무기한 남았다 | `forget()` 이 있다. 케이스가 끝나면 지운다 |

## 개인정보를 어디에 두나

**샘플 값을 이 표에 넣지 않는다.** `sample_path` 에 파일 경로만 둔다.
값은 그 파일에 있고, 케이스가 끝나면 파일과 함께 지운다.

`body` 는 게시글 본문이라 값이 섞일 수 있다. 그래서 `forget()` 이 본문도 지운다.
나가는 것은 필드명, 패턴, 건수뿐이라는 규칙은 산출물에 적용된다.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field, asdict
from datetime import date
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    uid           TEXT PRIMARY KEY,   -- venue + 원문키 해시. 다시 봐도 같은 줄
    src_id        TEXT DEFAULT '',    -- 소스 쪽 고유 번호. 있으면 이것 하나로 갈린다
    source        TEXT NOT NULL,      -- ransom | telegram | forum
    venue         TEXT NOT NULL,      -- 도메인까지. 포럼명만 적지 않는다
    venue_kind    TEXT DEFAULT '',    -- dls | forum | telegram | 그밖
    actor         TEXT DEFAULT '',    -- 행위자 핸들 또는 그룹명
    target_org    TEXT DEFAULT '',
    target_domain TEXT DEFAULT '',
    title         TEXT DEFAULT '',
    body          TEXT DEFAULT '',    -- 게시글 본문. 없으면 빈칸
    body_kind     TEXT DEFAULT '없음', -- 게시글 본문 | 회사 소개 | 요약 | 없음
    body_via      TEXT DEFAULT '',    -- api | kit | rss
    posted_at     TEXT DEFAULT '',    -- 원문 표기 그대로. 바꾸지 않는다
    seen_at       TEXT NOT NULL,      -- 우리가 본 날. 확인일이다
    post_url      TEXT DEFAULT '',    -- 원 출처. 무력화하지 않는다
    via           TEXT DEFAULT '[]',  -- 어디서 알았나. JSON 배열. 독립 출처가 아니다
    claimed_size  TEXT DEFAULT '',    -- 주장 규모. 숫자로 바꾸지 않는다
    price         TEXT DEFAULT '',
    currency      TEXT DEFAULT '',
    kind          TEXT DEFAULT '',    -- 게시 성격. 노션 수집 DB 와 같은 값
    country       TEXT DEFAULT '',
    sample_path   TEXT DEFAULT '',    -- 파일 경로만. 값은 안 넣는다
    clues         TEXT DEFAULT '{}',  -- JSON. onion/telegram/wallet/host 개수와 값
    raw           TEXT DEFAULT '{}',  -- JSON. 못 알아본 것 전부. 버리지 않는다
    got_by        TEXT DEFAULT '',    -- 어느 도구 몇 판이 가져왔나
    first_seen    TEXT NOT NULL,
    last_seen     TEXT NOT NULL,
    is_new        INTEGER NOT NULL DEFAULT 1,
    forgotten     INTEGER NOT NULL DEFAULT 0   -- 본문과 샘플을 지웠으면 1
);
CREATE INDEX IF NOT EXISTS ix_items_new    ON items(is_new);
CREATE INDEX IF NOT EXISTS ix_items_source ON items(source);
CREATE INDEX IF NOT EXISTS ix_items_seen   ON items(first_seen DESC);
CREATE INDEX IF NOT EXISTS ix_items_org    ON items(target_org);

CREATE TABLE IF NOT EXISTS runs (
    started  TEXT NOT NULL,
    source   TEXT NOT NULL,
    got      INTEGER DEFAULT 0,
    fresh    INTEGER DEFAULT 0,
    note     TEXT DEFAULT ''
);
"""

# 다시 봐도 같은 줄이 되게 하는 열쇠. 여기 있는 것만으로 uid 를 만든다.
#
# `src_id` 가 맨 앞이다. 소스 쪽 고유 번호가 있으면 그것 하나로 갈린다.
# 2026-08-27. 처음에는 이것이 없어서 CVE 알림 스무 건 중 셋이 한 줄로 뭉쳤다.
# 원 출처도 행위자도 대상 조직도 비어 있어 나머지 열쇠가 다 같았다.
# **줄이 뭉치면 조용히 사라진다.** 넣은 수와 나온 수를 늘 대조할 것.
KEY = ("src_id", "venue", "post_url", "actor", "target_org", "title")


@dataclass
class Item:
    source: str
    venue: str
    src_id: str = ""
    venue_kind: str = ""
    actor: str = ""
    target_org: str = ""
    target_domain: str = ""
    title: str = ""
    body: str = ""
    body_kind: str = "없음"
    body_via: str = ""
    posted_at: str = ""
    post_url: str = ""
    via: list = field(default_factory=list)
    claimed_size: str = ""
    price: str = ""
    currency: str = ""
    kind: str = ""
    country: str = ""
    sample_path: str = ""
    clues: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)
    got_by: str = ""

    def uid(self) -> str:
        d = asdict(self)
        s = "|".join(str(d.get(k, "")).strip().lower() for k in KEY)
        return hashlib.sha1(s.encode("utf-8")).hexdigest()[:16]


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(self.path)
        self.con.row_factory = sqlite3.Row
        self.con.executescript(SCHEMA)
        self.con.commit()

    def close(self) -> None:
        self.con.close()

    # ── 넣기 ────────────────────────────────────
    def put(self, it: Item, today: str | None = None) -> bool:
        """넣거나 갱신한다. 처음 보는 줄이면 참을 돌려준다.

        **이미 있는 값을 빈 값으로 덮지 않는다.** 소스마다 채우는 칸이 달라서,
        나중 소스가 빈칸을 들고 오면 앞서 채운 것이 지워진다."""
        day = today or date.today().isoformat()
        uid = it.uid()
        cur = self.con.execute("SELECT * FROM items WHERE uid=?", (uid,)).fetchone()
        d = asdict(it)
        d["via"] = json.dumps(it.via, ensure_ascii=False)
        d["clues"] = json.dumps(it.clues, ensure_ascii=False)
        d["raw"] = json.dumps(it.raw, ensure_ascii=False)

        if cur is None:
            d.update(uid=uid, seen_at=day, first_seen=day, last_seen=day,
                     is_new=1, forgotten=0)
            cols = ",".join(d)
            self.con.execute("INSERT INTO items (%s) VALUES (%s)"
                             % (cols, ",".join("?" * len(d))), list(d.values()))
            self.con.commit()
            return True

        keep = {}
        # 본문 셋은 같이 움직인다. 따로 두면 본문과 그 출처가 어긋난다.
        # 실제로 body 만 바뀌고 body_kind 가 "회사 소개" 로 남는 일을 겪었다
        본문셋 = ("body", "body_kind", "body_via")
        진짜본문이_왔다 = (it.body and it.body_kind == "게시글 본문"
                     and cur["body_kind"] != "게시글 본문")
        본문이_처음이다 = it.body and not cur["body"]
        if 진짜본문이_왔다 or 본문이_처음이다:
            for k in 본문셋:
                keep[k] = d[k]

        for k, v in d.items():
            if k in 본문셋:
                continue
            old = cur[k] if k in cur.keys() else ""
            if k == "via":                       # 어디서 알았나는 합친다
                merged = sorted(set(json.loads(old or "[]")) | set(it.via))
                keep[k] = json.dumps(merged, ensure_ascii=False)
            elif v in ("", "{}", "[]", "없음", None):
                continue                          # 빈 값으로 덮지 않는다
            elif not old or old in ("{}", "[]", "없음"):
                keep[k] = v
        keep["last_seen"] = day
        self.con.execute("UPDATE items SET %s WHERE uid=?"
                         % ",".join("%s=?" % k for k in keep),
                         list(keep.values()) + [uid])
        self.con.commit()
        return False

    # ── 읽기 ────────────────────────────────────
    def rows(self, only_new: bool = False, source: str = "",
             since: str = "") -> list[sqlite3.Row]:
        q, arg, where = "SELECT * FROM items", [], []
        if only_new:
            where.append("is_new = 1")
        if source:
            where.append("source = ?")
            arg.append(source)
        if since:
            where.append("first_seen >= ?")
            arg.append(since)
        if where:
            q += " WHERE " + " AND ".join(where)
        return self.con.execute(q + " ORDER BY first_seen DESC", arg).fetchall()

    def seen(self, uid: str) -> bool:
        return self.con.execute("SELECT 1 FROM items WHERE uid=?",
                                (uid,)).fetchone() is not None

    # ── 다시 읽기 ───────────────────────────────
    def replace(self, old_uid: str, it: Item) -> str:
        """줄 하나를 다시 읽은 것으로 갈아 끼운다. 새 uid 를 돌려준다.

        파서를 고치면 열쇠 칸(`venue`·`post_url`·`target_org`·`title`)이 바뀐다.
        그러면 `put` 은 옛 줄을 놔둔 채 새 줄을 하나 더 만든다. 그래서 갈아 끼우는
        자리를 따로 둔다.

        **관측된 사실은 지킨다.** 처음 본 날, 마지막으로 본 날, 사람이 봤다는 표시는
        다시 읽는다고 달라지지 않는다. 바뀌는 것은 해석뿐이다.

        다시 읽은 결과가 이미 있는 다른 줄과 같은 열쇠가 되면, 옛 줄을 지우고
        그쪽에 합친다. 같은 글이 두 줄로 남는 것보다 낫다."""
        cur = self.con.execute("SELECT * FROM items WHERE uid=?",
                               (old_uid,)).fetchone()
        if cur is None:
            raise KeyError(old_uid)
        new = it.uid()
        if new != old_uid and self.seen(new):
            with self.con:
                self.con.execute("DELETE FROM items WHERE uid=?", (old_uid,))
            self.put(it, cur["last_seen"])
            return new

        d = asdict(it)
        d["via"] = json.dumps(it.via, ensure_ascii=False)
        d["clues"] = json.dumps(it.clues, ensure_ascii=False)
        d["raw"] = json.dumps(it.raw, ensure_ascii=False)
        d.update(uid=new, seen_at=cur["seen_at"], first_seen=cur["first_seen"],
                 last_seen=cur["last_seen"], is_new=cur["is_new"],
                 forgotten=cur["forgotten"])
        with self.con:
            self.con.execute("DELETE FROM items WHERE uid=?", (old_uid,))
            self.con.execute("INSERT INTO items (%s) VALUES (%s)"
                             % (",".join(d), ",".join("?" * len(d))),
                             list(d.values()))
        return new

    # ── 표시와 지우기 ───────────────────────────
    def ack(self, uid: str) -> None:
        """사람이 봤다고 표시한다. 줄은 안 지운다."""
        self.con.execute("UPDATE items SET is_new=0 WHERE uid=?", (uid,))
        self.con.commit()

    def forget(self, uid: str) -> bool:
        """본문과 샘플 경로를 지운다. 케이스가 끝나면 부른다.

        **줄 자체는 남긴다.** 지우면 같은 건이 새 건으로 다시 들어온다.
        남는 것은 조직명, 행위자, 시각, 주소처럼 값이 아닌 것들이다."""
        n = self.con.execute(
            "UPDATE items SET body='', body_kind='지움', sample_path='',"
            " clues='{}', forgotten=1 WHERE uid=? AND forgotten=0", (uid,)).rowcount
        self.con.commit()
        return bool(n)

    def forget_older(self, day: str) -> int:
        """이 날짜보다 오래된 줄의 본문을 다 지운다. 보존기한이다."""
        n = self.con.execute(
            "UPDATE items SET body='', body_kind='지움', sample_path='',"
            " clues='{}', forgotten=1 WHERE last_seen < ? AND forgotten=0",
            (day,)).rowcount
        self.con.commit()
        return n

    # ── 실행 기록 ───────────────────────────────
    def log_run(self, started: str, source: str, got: int, fresh: int,
                note: str = "") -> None:
        self.con.execute("INSERT INTO runs VALUES (?,?,?,?,?)",
                         (started, source, got, fresh, note[:2000]))
        self.con.commit()

    def counts(self) -> dict:
        out = {}
        for r in self.con.execute(
                "SELECT source, COUNT(*) n, SUM(is_new) new FROM items GROUP BY source"):
            out[r["source"]] = {"전체": r["n"], "새 것": r["new"] or 0}
        return out
