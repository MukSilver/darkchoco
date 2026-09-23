#!/usr/bin/env python3
"""Supabase `core` · `map` 의 표와 칸 이름·타입만 뽑는다. **줄 값은 안 읽는다.**

    python tools/supa_schema.py --out <저장소 밖 자리>/supa_schema.json

열쇠를 어디서 읽는지는 `supa.py` 머리말에 있다.

데이터 API 의 OpenAPI 설명(`GET /rest/v1/`)을 읽는다. 여기에는 표 이름과
칸 이름 · 타입 · 기본키 · 외래키 · 칸 주석만 있고 줄 값이 없다.

**연결 1단계다** (2026-09-23 최현서 결정). 굽기(`bake.py`)의 원천을
Supabase 로 바꾸는 것은 이 보고를 보고 최현서가 정한 뒤에 한다.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import supa  # noqa: E402

SCHEMAS = ("core", "map")

RE_FK = re.compile(r"<fk table='([^']+)' column='([^']+)'/>")


def columns(defn: dict) -> list[dict]:
    """OpenAPI 정의 하나 → 칸 목록."""
    required = set(defn.get("required", []))
    out = []
    for name, p in (defn.get("properties") or {}).items():
        desc = p.get("description") or ""
        fk = RE_FK.search(desc)
        # PostgREST 는 칸 주석 뒤에 「Note:」 로 키 정보를 붙인다. 주석만 남긴다
        comment = desc.split("\n\nNote:")[0].split("Note:\n")[0].strip()
        out.append({
            "name": name,
            "type": p.get("format") or p.get("type") or "",
            "required": name in required,
            "pk": "<pk/>" in desc,
            "fk": f"{fk.group(1)}.{fk.group(2)}" if fk else None,
            "comment": comment[:200],
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Supabase 스키마의 칸 목록을 뽑습니다")
    ap.add_argument("--out", help="JSON 으로 쓸 자리. 저장소 밖에 둡니다")
    args = ap.parse_args()

    result: dict[str, dict] = {}
    closed: list[str] = []
    for schema in SCHEMAS:  # 차례대로 한 번씩. 병렬로 안 보낸다
        try:
            spec = supa.get("/rest/v1/", profile=schema, accept="application/openapi+json")
        except supa.SupaError as e:
            if e.code == "PGRST106":
                closed.append(schema)
                print(f"[{schema}] API 에 열려 있지 않습니다 (Exposed schemas 에 없음)")
                continue
            print(f"[{schema}] 실패 — HTTP {e.status} {e.code}: {e}", file=sys.stderr)
            return 1
        tables = {name: columns(d) for name, d in (spec.get("definitions") or {}).items()}
        result[schema] = tables
        print(f"[{schema}] 표 {len(tables)}개")
        for name, cols in tables.items():
            print(f"  {name} — {len(cols)}칸")
            for c in cols:
                key = " PK" if c["pk"] else ""
                key += f" → {c['fk']}" if c["fk"] else ""
                note = f"  # {c['comment']}" if c["comment"] else ""
                print(f"    {c['name']}: {c['type']}{key}{note}")

    if args.out:
        out = Path(args.out).expanduser().resolve()
        if supa.REPO in out.parents:
            print("저장소 안에는 쓰지 않습니다. 저장소 밖 자리를 주세요.", file=sys.stderr)
            return 1
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
        print(f"썼습니다: {out.name}")

    if closed:
        print(f"\n열어야 할 스키마: {', '.join(closed)}. 김무근에게 Exposed schemas 에 "
              "더해 달라고 해야 합니다.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
