"""메시지·채널 메타데이터 추출. tg-notion-report 쪽에서 온 것입니다."""

from __future__ import annotations

from telethon.utils import get_display_name, get_peer_id

from .timeutil import isoformat


def safe_peer_id(peer):
    """peer 를 정수 ID 로. 실패하면 None 을 돌려주고 예외를 올리지 않습니다."""
    if peer is None:
        return None
    try:
        return get_peer_id(peer)
    except (TypeError, ValueError):
        return None


def sender_metadata(message) -> dict:
    sender = getattr(message, "sender", None)
    return {
        "sender_id": message.sender_id,
        "sender_username": getattr(sender, "username", None),
        "sender_display_name": get_display_name(sender) if sender else None,
        "post_author": getattr(message, "post_author", None),
        "via_bot_id": getattr(message, "via_bot_id", None),
    }


def forward_metadata(message) -> dict:
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


def reaction_count(message) -> int:
    reactions = getattr(getattr(message, "reactions", None), "results", None) or []
    return sum(getattr(reaction, "count", 0) or 0 for reaction in reactions)


def sender_label(sender) -> str:
    """사람이 읽을 이름 한 줄. tg-korea-alert 의 알림 문구에 쓰입니다.

    수집 JSON 의 sender_name 과는 형태가 다르다. 그쪽은 이름만 넣고 없으면
    null 이므로 apps/tg-korea-alert/collect_messages.py 에 따로 둔다.
    """
    if sender is None:
        return "알 수 없음"
    name = get_display_name(sender)
    username = getattr(sender, "username", None)
    if name and username:
        return f"{name} (@{username})"
    return name or (f"@{username}" if username else "알 수 없음")


async def channel_metadata(client, entity) -> dict:
    """채널 자체의 정보. 참여자 수처럼 권한이 필요한 값은 없으면 None 입니다."""
    from telethon.tl.functions.channels import GetFullChannelRequest

    meta = {
        "channel_id": safe_peer_id(entity),
        "title": getattr(entity, "title", None),
        "username": getattr(entity, "username", None),
        "is_broadcast": getattr(entity, "broadcast", None),
        "is_megagroup": getattr(entity, "megagroup", None),
        "created_at": isoformat(getattr(entity, "date", None)),
        "participants_count": None,
        "about": None,
    }
    try:
        full = await client(GetFullChannelRequest(entity))
        chat = getattr(full, "full_chat", None)
        if chat is not None:
            meta["participants_count"] = getattr(chat, "participants_count", None)
            meta["about"] = getattr(chat, "about", None)
    except Exception:
        # 권한이 없거나 채널 종류가 달라 실패할 수 있습니다. 값 없이 진행합니다.
        pass
    return meta
