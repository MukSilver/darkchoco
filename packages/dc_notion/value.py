"""노션 속성 값 읽기·쓰기. dls-observatory 에서 왔습니다.

노션은 속성 종류마다 JSON 모양이 달라서, 읽을 때와 쓸 때 변환이 필요합니다.
그 변환을 한곳에 모았습니다.
"""

from __future__ import annotations

from typing import Any


def plain_text(rich) -> str:
    if isinstance(rich, str):
        return rich
    return "".join(x.get("plain_text", "") for x in (rich or []))


# --------------------------------------------------------------------------
# 프로퍼티 값 읽기 / 쓰기
# --------------------------------------------------------------------------
def read_value(prop: dict | None) -> Any:
    """Notion 프로퍼티 → 파이썬 값 (비어 있으면 None / [] / '')."""
    if not prop:
        return None
    t = prop.get("type")
    if t == "title":
        return "".join(x.get("plain_text", "") for x in prop["title"]) or None
    if t == "rich_text":
        return "".join(x.get("plain_text", "") for x in prop["rich_text"]) or None
    if t == "select":
        return (prop["select"] or {}).get("name")
    if t == "status":
        return (prop["status"] or {}).get("name")
    if t == "multi_select":
        return [o["name"] for o in prop["multi_select"]]
    if t == "date":
        return (prop["date"] or {}).get("start")
    if t == "checkbox":
        return prop["checkbox"]
    if t == "number":
        return prop["number"]
    if t == "url":
        return prop["url"]
    if t == "people":
        return [p.get("id") for p in prop.get("people", [])]
    if t == "email":
        return prop["email"]
    if t == "phone_number":
        return prop["phone_number"]
    return None


def is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def build_value(prop_type: str, value: Any) -> dict | None:
    """파이썬 값 → Notion 프로퍼티 payload. 타입이 안 맞으면 None."""
    if value is None or value == "":
        return None

    if prop_type == "rich_text":
        text = str(value)[:1990]
        return {"rich_text": [{"type": "text", "text": {"content": text}}]}
    if prop_type == "title":
        return {"title": [{"type": "text", "text": {"content": str(value)[:1990]}}]}
    if prop_type == "select":
        return {"select": {"name": str(value)[:100]}}
    if prop_type == "status":
        # status 타입은 옵션 자동 생성이 안 되므로 기존 옵션 이름이어야 함
        return {"status": {"name": str(value)[:100]}}
    if prop_type == "multi_select":
        items = value if isinstance(value, (list, tuple, set)) else [value]
        return {"multi_select": [{"name": str(v)[:100]} for v in items if v]}
    if prop_type == "date":
        return {"date": {"start": str(value)}}
    if prop_type == "url":
        return {"url": str(value)}
    if prop_type == "number":
        try:
            return {"number": float(value)}
        except (TypeError, ValueError):
            return None
    if prop_type == "checkbox":
        return {"checkbox": bool(value)}
    if prop_type in ("email", "phone_number"):
        return {prop_type: str(value)}
    return None
