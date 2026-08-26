import argparse
import asyncio
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import RPCError
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.types import Channel
from telethon.utils import get_display_name, get_peer_id


BASE_DIR = Path(__file__).resolve().parent
SESSION_PATH = BASE_DIR / "telegram_session"
DEFAULT_OUTPUT = BASE_DIR / "output" / "channel_messages.json"


def parse_channel(value: str):
    value = value.strip()
    if value.lstrip("-").isdigit():
        return int(value)
    return value.removeprefix("https://t.me/").removeprefix("@")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Telegram 채널의 정보와 메시지를 JSON 파일로 수집합니다."
    )
    parser.add_argument(
        "channel",
        type=parse_channel,
        help="채널 username, t.me URL 또는 list_channels.py에서 확인한 ID",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1000,
        help="가져올 최대 메시지 수(기본값: 1000)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="저장할 JSON 경로",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="기존 JSON이 있으면 마지막 메시지 이후의 신규 메시지만 수집해 합침",
    )
    return parser.parse_args()


def isoformat(value):
    return value.isoformat() if value else None


def safe_peer_id(peer):
    if peer is None:
        return None
    try:
        return get_peer_id(peer)
    except (TypeError, ValueError):
        return None


def sender_metadata(message):
    sender = getattr(message, "sender", None)
    return {
        "sender_id": message.sender_id,
        "sender_username": getattr(sender, "username", None),
        "sender_display_name": get_display_name(sender) if sender else None,
        "post_author": getattr(message, "post_author", None),
        "via_bot_id": getattr(message, "via_bot_id", None),
    }


def forward_metadata(message):
    forward = getattr(message, "forward", None)
    if not forward:
        return {
            "is_forwarded": False,
            "forward_from_id": None,
            "forward_from_name": None,
            "forward_channel_post": None,
            "forward_date": None,
        }
    return {
        "is_forwarded": True,
        "forward_from_id": safe_peer_id(getattr(forward, "from_id", None)),
        "forward_from_name": getattr(forward, "from_name", None),
        "forward_channel_post": getattr(forward, "channel_post", None),
        "forward_date": isoformat(getattr(forward, "date", None)),
    }


def reaction_count(message):
    reactions = getattr(getattr(message, "reactions", None), "results", None) or []
    return sum(getattr(reaction, "count", 0) or 0 for reaction in reactions)


def load_existing_payload(output: Path):
    resolved = output.expanduser().resolve()
    if not resolved.exists():
        return None
    payload = json.loads(resolved.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict) or not isinstance(payload.get("messages"), list):
        raise ValueError(f"기존 JSON 구조가 올바르지 않습니다: {resolved}")
    return payload


def validate_same_channel(existing, current):
    old = existing.get("channel") or {}
    old_id, new_id = old.get("id"), current.get("id")
    old_username = str(old.get("username") or "").lower()
    new_username = str(current.get("username") or "").lower()
    if old_id and new_id and int(old_id) != int(new_id):
        raise ValueError("기존 JSON과 현재 수집 대상의 Telegram 채널 ID가 다릅니다.")
    if not old_id and old_username and new_username and old_username != new_username:
        raise ValueError("기존 JSON과 현재 수집 대상의 username이 다릅니다.")


def merge_records(existing_records, new_records):
    merged = {}
    for record in list(existing_records) + list(new_records):
        if not isinstance(record, dict) or record.get("id") is None:
            continue
        merged[int(record["id"])] = record
    return [merged[message_id] for message_id in sorted(merged, reverse=True)]


def write_json_atomic(output: Path, payload):
    output = output.expanduser().resolve()
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


async def get_channel_metadata(client, entity):
    metadata = {
        "id": entity.id,
        "peer_id": safe_peer_id(entity),
        "title": getattr(entity, "title", None) or getattr(entity, "username", None),
        "username": getattr(entity, "username", None),
        "url": (
            f"https://t.me/{entity.username}"
            if getattr(entity, "username", None)
            else None
        ),
        # Channel.date는 계정·엔티티 상태에 따라 채널 생성일로 단정하기 어려워
        # 원시 메타데이터 날짜로만 보관하고 보고서의 생성 시점에는 사용하지 않는다.
        "created_at": None,
        "entity_date": isoformat(getattr(entity, "date", None)),
        "channel_type": (
            "supergroup" if getattr(entity, "megagroup", False)
            else "channel" if getattr(entity, "broadcast", False)
            else "group"
        ),
        "is_public": bool(getattr(entity, "username", None)),
        "is_joined": not bool(getattr(entity, "left", False)),
        "verified": bool(getattr(entity, "verified", False)),
        "scam": bool(getattr(entity, "scam", False)),
        "fake": bool(getattr(entity, "fake", False)),
        "restricted": bool(getattr(entity, "restricted", False)),
        "participants_count": getattr(entity, "participants_count", None),
        "about": None,
        "linked_chat_id": None,
        "api_access_status": "accessible",
    }

    if isinstance(entity, Channel):
        try:
            full = await client(GetFullChannelRequest(entity))
            full_chat = full.full_chat
            metadata["participants_count"] = (
                getattr(full_chat, "participants_count", None)
                or metadata["participants_count"]
            )
            metadata["about"] = getattr(full_chat, "about", None)
            metadata["linked_chat_id"] = getattr(full_chat, "linked_chat_id", None)
        except RPCError as error:
            metadata["full_info_error"] = type(error).__name__

    return metadata


async def collect(channel, limit: int, output: Path, incremental: bool = False):
    if limit < 1:
        raise ValueError("--limit은 1 이상이어야 합니다.")

    api_id = int(os.environ["TELEGRAM_API_ID"])
    api_hash = os.environ["TELEGRAM_API_HASH"]
    client = TelegramClient(str(SESSION_PATH), api_id, api_hash)

    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("로그인된 세션이 없습니다. 먼저 test.py를 실행하세요.")

        entity = await client.get_entity(channel)
        channel_info = await get_channel_metadata(client, entity)
        # 일부 공개 t.me 주소는 Telegram API 응답에서 username이 비어 있을 수 있다.
        # 이 경우 실제로 조회에 성공한 입력 username을 비교용 주소로 보존한다.
        if not channel_info.get("username") and isinstance(channel, str):
            requested_username = channel.strip().strip("/@ ")
            if re.fullmatch(r"[A-Za-z0-9_]{4,}", requested_username):
                channel_info["username"] = requested_username
                channel_info["url"] = f"https://t.me/{requested_username}"
                channel_info["is_public"] = True
                channel_info["address_source"] = "requested_input"
        else:
            channel_info["address_source"] = "telegram_api"
        existing = load_existing_payload(output) if incremental else None
        existing_records = (existing or {}).get("messages") or []
        if existing:
            validate_same_channel(existing, channel_info)
        last_message_id = max(
            (int(item["id"]) for item in existing_records if isinstance(item, dict) and item.get("id") is not None),
            default=0,
        )
        records = []

        async for message in client.iter_messages(
            entity,
            limit=limit,
            min_id=last_message_id if incremental and last_message_id else 0,
        ):
            record = {
                "id": message.id,
                "date": isoformat(message.date),
                "edit_date": isoformat(message.edit_date),
                "text": message.raw_text or "",
                "views": message.views or 0,
                "forwards": message.forwards or 0,
                "reply_count": message.replies.replies if message.replies else 0,
                "reaction_count": reaction_count(message),
                "has_media": message.media is not None,
                "grouped_id": message.grouped_id,
                "reply_to_message_id": message.reply_to_msg_id,
                "service_action": (
                    type(message.action).__name__ if message.action else None
                ),
                "message_url": (
                    f"{channel_info['url']}/{message.id}"
                    if channel_info.get("url") else None
                ),
            }
            record.update(sender_metadata(message))
            record.update(forward_metadata(message))
            records.append(record)

        combined_records = (
            merge_records(existing_records, records) if incremental else records
        )

        payload = {
            "schema_version": 2,
            "channel": channel_info,
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "requested_limit": limit,
            "collection_mode": "incremental" if incremental else "full",
            "previous_message_count": len(existing_records) if incremental else 0,
            "new_message_count": len(records),
            "last_message_id_before": last_message_id or None,
            "message_count": len(combined_records),
            "messages": combined_records,
        }

        output = output.expanduser().resolve()
        write_json_atomic(output, payload)

        print(f"채널: {channel_info.get('title') or '미확인'}")
        print(f"구독자·참가자 수: {channel_info.get('participants_count') or '미확인'}")
        if incremental:
            print(f"기존 메시지: {len(existing_records)}개")
            print(f"신규 메시지: {len(records)}개")
            print(f"병합 후 전체: {len(combined_records)}개")
        else:
            print(f"수집 메시지: {len(records)}개")
        print(f"저장 위치: {output}")
        print("주의: JSON에는 메시지 원문이 포함될 수 있습니다. 내부 분석용으로만 보관하고 Notion·보고서·외부 공유에 사용하지 마세요.")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(collect(args.channel, args.limit, args.output, args.incremental))
