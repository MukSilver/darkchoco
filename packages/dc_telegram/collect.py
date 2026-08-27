"""메시지 수집 본체.

두 앱이 각자 붙였던 기능을 모두 옵션으로 받습니다.
  · incremental=True          이미 받은 것 다음부터 (tg-notion-report)
  · from_day / to_day         날짜 범위 (tg-korea-alert)
  · with_meta=True            발신자·포워드·리액션 (tg-notion-report)

기본값은 둘 다 끈 상태라, 어느 앱에서 불러도 예전 동작을 해치지 않습니다.
"""

from __future__ import annotations

from pathlib import Path

from .client import make_client, parse_channel
from .meta import channel_metadata, forward_metadata, reaction_count, sender_metadata
from .store import load_payload, merge_records, validate_same_channel, write_json_atomic
from .timeutil import day_bounds, get_timezone, isoformat


def _record(message, tz, with_meta: bool) -> dict:
    at = message.date.astimezone(tz) if (tz and message.date) else message.date
    rec = {
        "id": message.id,
        "date": isoformat(at),
        "text": message.message or "",
        "views": getattr(message, "views", None),
        "forwards": getattr(message, "forwards", None),
    }
    if with_meta:
        rec.update(sender_metadata(message))
        rec.update(forward_metadata(message))
        rec["reactions"] = reaction_count(message)
    return rec


async def collect_messages(
    channel: str,
    output: Path,
    limit: int | None = None,
    *,
    incremental: bool = False,
    from_day=None,
    to_day=None,
    timezone_name: str = "Asia/Seoul",
    with_meta: bool = True,
    session: Path | str | None = None,
    client=None,
) -> dict:
    """채널 메시지를 받아 JSON 으로 저장하고 payload 를 돌려줍니다."""
    name = parse_channel(channel)
    tz = get_timezone(timezone_name)
    start, end = day_bounds(from_day, to_day, tz)

    owns_client = client is None
    client = client or make_client(session)
    if owns_client:
        await client.start()

    try:
        entity = await client.get_entity(name)
        meta = await channel_metadata(client, entity)

        # 증분이면 이미 받은 마지막 ID 다음부터만 받습니다.
        existing, min_id = None, 0
        if incremental:
            existing = load_payload(output)
            if existing:
                validate_same_channel(existing, meta)
                ids = [r["id"] for r in existing["messages"] if r.get("id") is not None]
                min_id = max(ids) if ids else 0

        records = []
        kwargs = {"limit": limit}
        if min_id:
            kwargs["min_id"] = min_id
        if end:
            kwargs["offset_date"] = end

        async for message in client.iter_messages(entity, **kwargs):
            at = message.date.astimezone(tz) if message.date else None
            if start and at and at < start:
                break                       # 시간 역순이라 더 볼 필요가 없습니다
            if end and at and at > end:
                continue
            records.append(_record(message, tz, with_meta))

        if existing:
            records = merge_records(existing["messages"], records)

        payload = {"channel": meta, "messages": records, "count": len(records)}
        write_json_atomic(output, payload)
        return payload
    finally:
        if owns_client:
            await client.disconnect()
