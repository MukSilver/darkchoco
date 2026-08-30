import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "packages"))
from dc_telegram import make_client

from telethon.tl.types import Channel


BASE_DIR = Path(__file__).resolve().parent
SESSION_PATH = BASE_DIR / "telegram_session"


async def main():
    client = make_client(SESSION_PATH)

    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise RuntimeError("로그인된 세션이 없습니다. 먼저 test.py를 실행하세요.")

        print(f"{'ID':>16}  {'종류':<10}  {'username':<32}  이름")
        print("-" * 90)

        count = 0
        async for dialog in client.iter_dialogs():
            if not isinstance(dialog.entity, Channel):
                continue

            entity = dialog.entity
            channel_type = "그룹" if getattr(entity, "megagroup", False) else "채널"
            username = getattr(entity, "username", None) or "-"
            print(f"{dialog.id:>16}  {channel_type:<10}  {username:<32}  {dialog.name}")
            count += 1

        print(f"\n총 {count}개 채널/슈퍼그룹을 찾았습니다.")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
