"""수집 결과 저장. 증분 병합과 원자적 쓰기는 tg-notion-report 쪽에서 온 것입니다.

원자적으로 쓰는 이유는, 수집 도중 중단되어도 기존 파일이 깨지지 않게 하기
위해서입니다. 임시 파일에 다 쓴 뒤 한 번에 바꿔치웁니다.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def load_payload(output: Path):
    """기존 결과를 읽습니다. 없으면 None, 구조가 틀리면 예외입니다."""
    resolved = Path(output).expanduser().resolve()
    if not resolved.exists():
        return None
    payload = json.loads(resolved.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict) or not isinstance(payload.get("messages"), list):
        raise ValueError(f"기존 JSON 구조가 올바르지 않습니다: {resolved}")
    return payload


def validate_same_channel(existing, current) -> None:
    """다른 채널 결과에 덮어쓰는 사고를 막습니다.

    ID 가 양쪽에 있으면 ID 로, 없으면 username 으로 봅니다.
    """
    old = existing.get("channel") or {}
    old_id, new_id = old.get("id") or old.get("channel_id"), current.get("id") or current.get("channel_id")
    old_username = str(old.get("username") or "").lower()
    new_username = str(current.get("username") or "").lower()
    if old_id and new_id and int(old_id) != int(new_id):
        raise ValueError("기존 JSON 과 현재 수집 대상의 채널 ID 가 다릅니다.")
    if not old_id and old_username and new_username and old_username != new_username:
        raise ValueError("기존 JSON 과 현재 수집 대상의 username 이 다릅니다.")


def merge_records(existing_records, new_records) -> list:
    """메시지 ID 를 키로 합칩니다. 같은 ID 는 새 것이 이깁니다."""
    merged = {}
    for record in list(existing_records) + list(new_records):
        if not isinstance(record, dict) or record.get("id") is None:
            continue
        merged[int(record["id"])] = record
    return [merged[mid] for mid in sorted(merged, reverse=True)]


def write_json_atomic(output: Path, payload) -> None:
    """임시 파일에 쓰고 한 번에 바꿉니다. 중단되어도 기존 파일이 남습니다."""
    output = Path(output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(
        prefix=f".{output.stem}_", suffix=".tmp", dir=output.parent
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, output)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise
