import argparse
import asyncio
import json
import os
import sqlite3
from datetime import timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


from company_country_classifier import CompanyCountryClassifier
from local_config import load_local_env, normalize_discord_webhook


BASE_DIR = Path(__file__).resolve().parent
SESSION_PATH = BASE_DIR / "telegram_session"
DEFAULT_DB_PATH = BASE_DIR / "alert_monitor.db"
DEFAULT_CHANNELS = ["breachdetect", "osint_cti"]
KST = timezone(timedelta(hours=9), "KST")
BURST_SETTLE_SECONDS = 1.0

def parse_args():
    parser = argparse.ArgumentParser(
        description="Monitor selected Telegram channels and forward Korea-related posts to Discord."
    )
    parser.add_argument(
        "--channels",
        nargs="+",
        default=DEFAULT_CHANNELS,
        help="Telegram channel usernames, IDs, URLs, or exact display titles",
    )
    parser.add_argument("--database", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument(
        "--test-alert",
        action="store_true",
        help="Send one sample alert to Discord and exit without connecting to Telegram",
    )
    return parser.parse_args()


def parse_channel(value):
    value = value.strip().rstrip("/")
    if value.lstrip("-").isdigit():
        return int(value)
    return value.removeprefix("https://t.me/").removeprefix("@")


def open_database(path):
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS channel_state (
            channel_id INTEGER PRIMARY KEY,
            channel_title TEXT NOT NULL,
            username TEXT,
            last_message_id INTEGER NOT NULL,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS forwarded_alerts (
            channel_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            forwarded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (channel_id, message_id)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS processed_messages (
            channel_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            outcome TEXT NOT NULL,
            classification_source TEXT NOT NULL,
            processed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (channel_id, message_id)
        )
        """
    )
    connection.commit()
    return connection


async def resolve_channel(client, value):
    from telethon.tl.types import Channel   # 설치 전에도 --help 가 뜨게 한다
    parsed = parse_channel(value)
    try:
        return await client.get_entity(parsed)
    except (ValueError, TypeError):
        if not isinstance(parsed, str):
            raise

    target = parsed.casefold()
    async for dialog in client.iter_dialogs():
        if not isinstance(dialog.entity, Channel):
            continue
        title = (dialog.name or "").casefold()
        username = (getattr(dialog.entity, "username", None) or "").casefold()
        if target in {title, username}:
            return dialog.entity
    raise ValueError(f"Telegram channel not found: {value}")


def channel_link(entity, message_id):
    username = getattr(entity, "username", None)
    if username:
        return f"https://t.me/{username}/{message_id}"
    internal_id = str(entity.id)
    return f"https://t.me/c/{internal_id}/{message_id}"


def post_discord(webhook_url, content):
    if len(content) > 2000:
        content = content[: 1997] + "..."

    request = Request(
        webhook_url,
        data=json.dumps({"content": content}, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "telegram-korea-alert/1.0"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            if response.status not in {200, 204}:
                raise RuntimeError(f"Discord returned HTTP {response.status}")
    except (HTTPError, URLError) as exc:
        raise RuntimeError(f"Discord webhook request failed: {exc}") from exc


def send_discord(webhook_url, entity, message, classification):
    title = getattr(entity, "title", None) or getattr(entity, "username", None) or str(entity.id)
    posted_at = message.date.astimezone(KST).strftime("%Y-%m-%d %H:%M:%S KST")
    link = channel_link(entity, message.id)
    text = message.raw_text or "(textless post)"
    details = [
        f"Source: {classification.source}",
        f"Confidence: {classification.confidence:.0%}",
    ]
    if classification.company_name:
        details.append(f"Company: {classification.company_name}")
    if classification.evidence:
        details.append(f"Evidence: {classification.evidence}")
    detail_text = "\n".join(details)
    header = (
        f"**[{title}] Korea-related alert**\n"
        f"Posted: {posted_at}\n"
        f"Original: {link}\n"
        f"{detail_text}\n\n"
    )
    post_discord(webhook_url, header + text)


def send_test_alert(webhook_url):
    content = (
        "**[TEST] Korea-related alert**\n"
        "탐지 근거: South Korea, .kr\n\n"
        "이 메시지가 보이면 Discord 웹훅 전송이 정상적으로 작동합니다.\n"
        "실제 Telegram 게시물에서 한국 관련 표현이 탐지되면 같은 채널로 알림이 전송됩니다."
    )
    post_discord(webhook_url, content)


class AlertMonitor:
    def __init__(self, client, database, webhook_url, entities, classifier):
        from telethon import utils          # 설치 전에도 --help 가 뜨게 한다
        self.client = client
        self.database = database
        self.webhook_url = webhook_url
        self.entities = {entity.id: entity for entity in entities}
        self.entities_by_peer_id = {utils.get_peer_id(entity): entity for entity in entities}
        self.classifier = classifier
        self.lock = asyncio.Lock()

    def last_message_id(self, channel_id):
        row = self.database.execute(
            "SELECT last_message_id FROM channel_state WHERE channel_id = ?", (channel_id,)
        ).fetchone()
        return row[0] if row else None

    def update_state(self, entity, message_id):
        self.database.execute(
            """
            INSERT INTO channel_state (channel_id, channel_title, username, last_message_id)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(channel_id) DO UPDATE SET
                channel_title = excluded.channel_title,
                username = excluded.username,
                last_message_id = MAX(channel_state.last_message_id, excluded.last_message_id),
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                entity.id,
                getattr(entity, "title", None) or str(entity.id),
                getattr(entity, "username", None),
                message_id,
            ),
        )
        self.database.commit()

    async def process_message(self, entity, message):
        if not message:
            return

        already_processed = self.database.execute(
            "SELECT 1 FROM processed_messages WHERE channel_id = ? AND message_id = ?",
            (entity.id, message.id),
        ).fetchone()
        if already_processed:
            self.update_state(entity, message.id)
            return

        text = message.raw_text or ""
        classification = await self.classifier.classify(text)
        outcome = "ignored"
        if classification.is_korean:
            already_sent = self.database.execute(
                "SELECT 1 FROM forwarded_alerts WHERE channel_id = ? AND message_id = ?",
                (entity.id, message.id),
            ).fetchone()
            if not already_sent:
                await asyncio.to_thread(
                    send_discord, self.webhook_url, entity, message, classification
                )
                self.database.execute(
                    "INSERT INTO forwarded_alerts (channel_id, message_id) VALUES (?, ?)",
                    (entity.id, message.id),
                )
                print(f"[forwarded] {getattr(entity, 'title', entity.id)} #{message.id}")
            outcome = "forwarded"

        if not classification.is_korean:
            print(
                f"[ignored]   {getattr(entity, 'title', entity.id)} #{message.id} "
                f"({classification.source}, {classification.confidence:.0%})"
            )

        self.database.execute(
            """
            INSERT INTO processed_messages
                (channel_id, message_id, outcome, classification_source)
            VALUES (?, ?, ?, ?)
            """,
            (entity.id, message.id, outcome, classification.source),
        )
        self.database.commit()
        self.update_state(entity, message.id)

    async def catch_up(self, entity):
        last_id = self.last_message_id(entity.id) or 0
        messages = [
            message
            async for message in self.client.iter_messages(
                entity,
                min_id=last_id,
                reverse=True,
            )
        ]
        if len(messages) > 1:
            print(
                f"[batch]     {getattr(entity, 'title', entity.id)} "
                f"processing {len(messages)} posts in ID order"
            )
        for message in messages:
            await self.process_message(entity, message)

    async def initialize(self):
        async with self.lock:
            for entity in self.entities.values():
                last_id = self.last_message_id(entity.id)
                if last_id is None:
                    latest = await self.client.get_messages(entity, limit=1)
                    latest_id = latest[0].id if latest else 0
                    self.update_state(entity, latest_id)
                    print(
                        f"[initialized] {getattr(entity, 'title', entity.id)} "
                        f"at #{latest_id}; old posts skipped"
                    )
                    continue

                await self.catch_up(entity)

    async def on_new_message(self, event):
        entity = self.entities_by_peer_id.get(event.chat_id)
        if entity is None:
            return
        async with self.lock:
            await asyncio.sleep(BURST_SETTLE_SECONDS)
            await self.catch_up(entity)
            # If this event arrived late after a higher ID advanced channel_state,
            # process the event itself as a final safeguard. The per-message table
            # makes this a no-op when catch_up already handled it.
            await self.process_message(entity, event.message)


async def main(args):
    from telethon import TelegramClient, events   # 설치 전에도 --help 가 뜨게 한다
    load_local_env()
    webhook_url = normalize_discord_webhook(os.environ["DISCORD_WEBHOOK_URL"])
    if args.test_alert:
        await asyncio.to_thread(send_test_alert, webhook_url)
        print("Discord test alert sent successfully.")
        return

    api_id = int(os.environ["TELEGRAM_API_ID"])
    api_hash = os.environ["TELEGRAM_API_HASH"]
    # DART 와 Gemini 는 보조 판별기다. 판별기 자체가 DART 실패와 Gemini 한도 소진을
    # 견디게 짜여 있는데, 여기서 os.environ[...] 로 읽는 바람에 키가 없으면
    # 판별기를 만들기도 전에 KeyError 로 통째로 죽었다. 없으면 없는 채로 간다.
    dart_api_key = os.environ.get("DART_API_KEY", "")
    gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
    if not dart_api_key:
        print("[dart] DART_API_KEY 가 없습니다 — DART 조회를 건너뜁니다 (규칙·캐시로만 판별).")
    if not gemini_api_key:
        print("[gemini] GEMINI_API_KEY 가 없습니다 — Gemini 판별을 건너뜁니다 (규칙·캐시·DART 로만 판별).")
    database = open_database(args.database)
    client = TelegramClient(str(SESSION_PATH), api_id, api_hash)

    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("No authorized Telegram session. Run test.py first.")

        entities = [await resolve_channel(client, channel) for channel in args.channels]
        classifier = CompanyCountryClassifier(database, dart_api_key, gemini_api_key)
        await classifier.initialize()
        monitor = AlertMonitor(client, database, webhook_url, entities, classifier)
        client.add_event_handler(
            monitor.on_new_message,
            events.NewMessage(chats=entities),
        )
        await monitor.initialize()
        print("Monitoring started. Press Ctrl+C to stop.")
        await client.run_until_disconnected()
    finally:
        database.close()
        await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main(parse_args()))
    except KeyboardInterrupt:
        print("Monitoring stopped.")
