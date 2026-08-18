import argparse
import asyncio
import json
import os
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from telethon import TelegramClient


BASE_DIR = Path(__file__).resolve().parent
SESSION_PATH = BASE_DIR / "telegram_session"
DEFAULT_OUTPUT = BASE_DIR / "output" / "channel_messages.json"


def parse_channel(value: str):
    value = value.strip().rstrip("/")
    if value.lstrip("-").isdigit():
        return int(value)
    return value.removeprefix("https://t.me/").removeprefix("@")


def parse_day(value: str):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("날짜는 YYYY-MM-DD 형식이어야 합니다.") from exc


def parse_args():
    parser = argparse.ArgumentParser(description="Telegram 채널·그룹의 대화를 JSON으로 수집합니다.")
    parser.add_argument("channel", type=parse_channel, help="username, t.me URL 또는 채널/그룹 ID")
    parser.add_argument("--limit", type=int, default=1000, help="최대 메시지 수 (기본: 1000)")
    parser.add_argument("--from-date", type=parse_day, help="수집 시작일 (YYYY-MM-DD, 포함)")
    parser.add_argument("--to-date", type=parse_day, help="수집 종료일 (YYYY-MM-DD, 포함)")
    parser.add_argument("--timezone", default="Asia/Seoul", help="날짜 판정 시간대 (기본: Asia/Seoul)")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="저장할 JSON 경로")
    return parser.parse_args()


def get_timezone(name: str):
    try:
        return ZoneInfo(name)
    except Exception:
        if name == "Asia/Seoul":
            return timezone(timedelta(hours=9), name)
        if name in {"UTC", "Etc/UTC"}:
            return timezone.utc
        raise ValueError(f"시간대 '{name}'을 불러올 수 없습니다. tzdata를 설치하거나 Asia/Seoul 또는 UTC를 사용하세요.")


def sender_label(sender):
    if sender is None:
        return None
    title = getattr(sender, "title", None)
    name = " ".join(
        part for part in (getattr(sender, "first_name", None), getattr(sender, "last_name", None)) if part
    )
    return title or name or getattr(sender, "username", None)


async def collect(channel, limit: int, output: Path, from_date=None, to_date=None, timezone_name="Asia/Seoul"):
    if limit < 1:
        raise ValueError("--limit은 1 이상이어야 합니다.")
    if from_date and to_date and from_date > to_date:
        raise ValueError("--from-date는 --to-date보다 늦을 수 없습니다.")

    local_tz = get_timezone(timezone_name)
    min_utc = datetime.combine(from_date, time.min, local_tz).astimezone(timezone.utc) if from_date else None
    max_utc = datetime.combine(to_date, time.max, local_tz).astimezone(timezone.utc) if to_date else None
    api_id = int(os.environ["TELEGRAM_API_ID"])
    api_hash = os.environ["TELEGRAM_API_HASH"]
    client = TelegramClient(str(SESSION_PATH), api_id, api_hash)

    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("로그인된 세션이 없습니다. 먼저 test.py를 실행하세요.")

        entity = await client.get_entity(channel)
        channel_name = getattr(entity, "title", None) or getattr(entity, "username", None)
        records = []

        async for message in client.iter_messages(entity, limit=None):
            message_date = message.date
            if message_date and max_utc and message_date > max_utc:
                continue
            if message_date and min_utc and message_date < min_utc:
                break
            if len(records) >= limit:
                break

            sender = await message.get_sender()
            reply_to_id = message.reply_to.reply_to_msg_id if message.reply_to else None
            records.append({
                "id": message.id,
                "date": message_date.isoformat() if message_date else None,
                "text": message.raw_text or "",
                "views": message.views or 0,
                "forwards": message.forwards or 0,
                "reply_count": message.replies.replies if message.replies else 0,
                "reply_to_id": reply_to_id,
                "has_media": message.media is not None,
                "grouped_id": message.grouped_id,
                "sender_id": message.sender_id,
                "sender_name": sender_label(sender),
                "sender_username": getattr(sender, "username", None) if sender else None,
            })

        records.sort(key=lambda item: item.get("date") or "")
        payload = {
            "channel": {"id": entity.id, "title": channel_name, "username": getattr(entity, "username", None)},
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "timezone": timezone_name,
            "date_range": {
                "from": from_date.isoformat() if from_date else None,
                "to": to_date.isoformat() if to_date else None,
            },
            "requested_limit": limit,
            "message_count": len(records),
            "messages": records,
        }
        output = output.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"대상: {channel_name}")
        print(f"수집 메시지: {len(records)}개")
        print(f"저장 위치: {output}")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(collect(args.channel, args.limit, args.output, args.from_date, args.to_date, args.timezone))
