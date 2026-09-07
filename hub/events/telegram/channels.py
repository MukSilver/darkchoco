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
            # 이 폴더에는 test.py 가 없습니다. 세션을 만드는 것은
            # apps/tg-korea-alert/test.py 이고, 세션 파일은 그 앱 폴더에
            # 생깁니다. 여기서 보는 자리는 SESSION_PATH 입니다.
            raise RuntimeError(
                f"로그인된 세션이 없습니다. 이 스크립트가 보는 세션 파일은 "
                f"{SESSION_PATH} 입니다. 세션을 만드는 스크립트는 "
                f"apps/tg-korea-alert/test.py 이고 세션을 그 앱 폴더에 만듭니다.")

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
