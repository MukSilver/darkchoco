"""굽기 원천을 Supabase 로 — 팀 Supabase(darkchoco-data)의 `core` 표를 노션 줄 꼴로 바꿔 준다.

    python tools/bake.py --source supabase --out src/data/map.json
    (또는 환경변수 MAP_SOURCE=supabase)

**굽기 규칙은 하나도 안 바뀐다.** `bake()` 는 노션 클라이언트의 `query_all()` 이 돌려주는 줄
(`{"id", "properties"}`)을 읽는다. 여기 `SupaSource.query_all()` 이 같은 꼴을 돌려주므로 허용 칸
목록(`ALLOWED_COLS` · `MATCH_ONLY_COLS` · `TME_ONLY_COLS`), DB 반영 · 검토 여부 관문, 반출 검사가 노션
굽기와 똑같이 걸린다 (2026-10-03 최현서 — 원천을 Supabase 로 옮긴다).

`core` 표는 정제 배치(darkchoco-data `refine.yml`)가 노션 DB 를 그대로 옮긴 것이다. 칸 이름만 영문이다.
노션 칸 → `core` 칸 짝은 그 저장소의 `src/fields.mjs` 와 같게 아래 `TABLES` 에 적는다. **굽기가 읽는
칸만 적는다** — 그래서 Supabase 에서도 그 칸만 받아 온다(`select=`). 샘플 · 주소 · 비고 같은 칸은
요청에 들어가지도 않는다. 조직명 · 대상 조직은 지금처럼 맞추기 전용으로만 읽는다.

**노션과 다른 곳**

  - 사건 번호는 숫자만 있다(`case_no` 198). 노션처럼 「LEAK-198」 로 붙여 준다(`uid` 의 접두어)
  - 관계(같은 사건 · 수집 줄)는 노션 페이지 id 목록이다. 줄 id(`notion_id`)와 같은 꼴이라 그대로 잇는다
  - 시각(`timestamptz`)은 UTC 로 온다. 노션 꼴(`2026-05-14T06:58:00.000+00:00`)로 맞춘다. 노션에 한국
    시각(+09:00)으로 적힌 값은 같은 순간이지만 글자가 UTC 로 바뀐다 — 비교 도구가 센다
  - 「운영 종료 날짜」 는 정제 배치가 아직 안 옮긴다. 없는 칸으로 읽혀 굽기 로그 「노션 줄에 없던 칸」 에 남는다

열쇠는 `supa.py` 가 읽는다(GET 만). 지도는 읽기 전용 역할 `map_reader` 열쇠를 쓴다.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import supa  # noqa: E402

#: 한 번에 받는 줄 수. PostgREST 기본 상한(1000) 아래
PAGE = 500

#: 노션 칸 이름 → (core 칸, 꼴). 꼴은 노션 줄을 만들 때 쓴다
#:   title · text   글 하나 (노션 제목 · 글 · 선택지가 다 글 하나로 읽힌다)
#:   list           글 여럿 (다중 선택)
#:   bool · number · date · datetime
#:   ids            관계 — 노션 페이지 id 목록
#:   uid:<접두어>   사건 번호 — 숫자만 오므로 접두어를 붙인다
TABLES: dict[str, dict] = {
    "collect": {
        "table": "sources",
        "cols": {
            "사건 ID": ("case_no", "uid:LEAK"),
            "게시 시각": ("posted_at", "datetime"),
            "관측 시각": ("observed_at", "datetime"),
            "수집일": ("collected_on", "date"),
            "게시처": ("venue", "text"),
            "게시 플랫폼": ("platform", "text"),
            "소스": ("source", "text"),
            "중복 관계": ("dup_relation", "text"),
            "규모 등급": ("size_grade", "text"),
            "주장 규모": ("claimed_size", "text"),
            "한국 관련": ("korea", "text"),
            "게시 성격": ("post_kind", "text"),
            "국가": ("country", "text"),
            "산업 분야": ("industry", "text"),
            "카운트다운 표기": ("countdown", "text"),
            "유출 항목": ("leaked_items", "list"),
            "공개된 파일 수": ("file_count", "number"),
            "같은 사건": ("same_as", "ids"),
            "같은 사건 (역방향)": ("same_as_back", "ids"),
            "검토 여부": ("reviewed", "text"),
            "상태": ("status", "text"),
            # 맞추기 전용 · t.me 만 뽑는 칸 — 굽기의 col_match · col_tme 가 읽는다
            "대상 조직": ("target_org", "text"),
            "게시자 핸들": ("poster", "text"),
            "원문 URL": ("source_url", "text"),
        },
    },
    "verify": {
        "table": "verifications",
        "cols": {
            "수집 줄": ("source_ids", "ids"),
            "진위 판정": ("truth", "text"),
            "즉시 악용 가능성": ("exploitable", "text"),
        },
    },
    "forum": {
        "table": "forums",
        "cols": {
            "포럼 이름": ("name", "title"),
            "상태": ("status", "text"),
            "이전 이름·별칭": ("aliases", "text"),
            "규모": ("size_note", "text"),
            "연결된 곳": ("links", "text"),
        },
    },
    "telegram": {
        "table": "telegram_channels",
        "cols": {
            "채널 이름": ("name", "title"),
            "상태": ("status", "text"),
            "이전 이름·별칭": ("aliases", "text"),
            "규모": ("size_note", "text"),
            "연결된 곳": ("links", "text"),
        },
    },
    "ransomware": {
        "table": "ransomware_groups",
        "cols": {
            "그룹 이름": ("name", "title"),
            "상태": ("status", "text"),
            "이전 이름·별칭": ("aliases", "text"),
            "규모": ("size_note", "text"),
            "연결된 곳": ("links", "text"),
        },
    },
    "actor": {
        "table": "actors",
        "cols": {
            "핸들": ("handle", "title"),
            "다른 이름": ("aliases", "text"),
            "역할": ("roles", "list"),
            "국가": ("countries", "list"),
            "처음 본 날": ("first_seen", "date"),
            "다루는 것": ("deals_in", "text"),
            "상태": ("status", "text"),
            "연결된 곳": ("links", "text"),
        },
    },
    "relations": {
        "table": "relations",
        "cols": {
            "관계 ID": ("relation_id", "title"),
            "출발 섬": ("from_island", "text"),
            "출발 영토": ("from_territory", "text"),
            "도착 섬": ("to_island", "text"),
            "도착 영토": ("to_territory", "text"),
            "관계 종류": ("type", "text"),
            "확실한 정도": ("confidence", "text"),
            "근거 사건 ID": ("evidence_events", "text"),
        },
    },
    "incident": {
        "table": "incidents",
        "cols": {
            "사건 ID": ("inc_no", "uid:INC"),
            "업종": ("industry", "text"),
            "국가": ("country", "text"),
            "사고 시점": ("happened_on", "date"),
            "공표 시점": ("announced_on", "date"),
            "유출 항목": ("leaked_items", "list"),
            "유출 규모": ("size_note", "text"),
            "외부 확인": ("confirmation", "text"),
            "출처": ("source", "text"),
            "조직명": ("org_name", "text"),
            "보도된 유출 위치": ("reported_location", "text"),
            "보도된 행위자": ("reported_actor", "text"),
        },
    },
    "address": {
        "table": "address_changes",
        "cols": {
            "대상 이름": ("name", "title"),
            "옛 주소": ("old_address", "text"),
            "새 주소": ("new_address", "text"),
        },
    },
}

#: 모든 표에 붙는 공개 스위치. 노션 「DB 반영」 이다 (스위치가 없는 DB 는 늘 참)
FLAG = ("DB 반영", "db_flag")

RE_TS = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d+))?(Z|[+-]\d{2}:\d{2})$")


def notion_ts(v: str) -> str:
    """`timestamptz` 글을 노션 날짜 꼴로 — 밀리초 셋째 자리까지, Z 는 +00:00."""
    m = RE_TS.match(v)
    if not m:
        return v
    base, frac, tz = m.groups()
    ms = ((frac or "") + "000")[:3]
    return f"{base}.{ms}{'+00:00' if tz == 'Z' else tz}"


def prop(kind: str, v) -> dict:
    """core 칸 값 하나 → 노션 칸 객체. `dc_notion.read_value` · `bake.rel_ids` · `bake.unique_id` 가 읽는 꼴이다."""
    if kind == "title":
        return {"type": "title", "title": [{"plain_text": str(v)}] if v not in (None, "") else []}
    if kind == "text":
        return {"type": "rich_text", "rich_text": [{"plain_text": str(v)}] if v not in (None, "") else []}
    if kind == "list":
        return {"type": "multi_select", "multi_select": [{"name": str(x)} for x in (v or []) if x not in (None, "")]}
    if kind == "bool":
        return {"type": "checkbox", "checkbox": bool(v)}
    if kind == "number":
        return {"type": "number", "number": v}
    if kind in ("date", "datetime"):
        if v in (None, ""):
            return {"type": "date", "date": None}
        return {"type": "date", "date": {"start": notion_ts(str(v)) if kind == "datetime" else str(v)}}
    if kind == "ids":
        return {"type": "relation", "relation": [{"id": str(x)} for x in (v or [])]}
    if kind.startswith("uid:"):
        return {"type": "unique_id", "unique_id": {"prefix": kind[4:] or None, "number": v}}
    raise ValueError(f"모르는 꼴: {kind}")


def to_page(row: dict, cols: dict[str, tuple[str, str]]) -> dict:
    """core 줄 하나 → 노션 줄 꼴(`{"id", "properties"}`)."""
    props = {name: prop(kind, row.get(dev)) for name, (dev, kind) in cols.items()}
    flag = row.get(FLAG[1])
    props[FLAG[0]] = prop("bool", True if flag is None else flag)
    return {"id": row["notion_id"], "properties": props}


class SupaSource:
    """노션 클라이언트 자리에 끼우는 것. `bake()` 가 부르는 `query_all(key)` 하나만 있다.

    key 는 `bake.load_sources()` 의 열쇠(collect · forum …)다. 표마다 한 번씩 차례로 받는다 —
    병렬로 안 보낸다. 받은 줄의 가장 늦은 동기화 시각(`synced_at`)을 `synced` 에 모아 로그에 남긴다
    """

    def __init__(self, get=supa.get):
        self._get = get
        self.synced: str | None = None

    def query_all(self, key: str) -> list[dict]:
        spec = TABLES.get(key)
        if spec is None:
            raise KeyError(f"Supabase 표 짝이 없는 원천: {key}")
        cols = spec["cols"]
        select = ",".join(dict.fromkeys(["notion_id", FLAG[1], "synced_at", *(dev for dev, _ in cols.values())]))
        out: list[dict] = []
        offset = 0
        while True:
            rows = self._get(
                f"/rest/v1/{spec['table']}?select={select}&order=notion_id.asc&limit={PAGE}&offset={offset}",
                profile="core",
            )
            for r in rows:
                s = r.get("synced_at")
                if isinstance(s, str) and (self.synced is None or s > self.synced):
                    self.synced = s
                out.append(to_page(r, cols))
            if len(rows) < PAGE:
                return out
            offset += PAGE
