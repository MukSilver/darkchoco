import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages"))
from dc_telegram import make_client

from local_config import load_local_env

BASE_DIR = Path(__file__).resolve().parent
SESSION_PATH = BASE_DIR / "telegram_session"

load_local_env()
client = make_client(SESSION_PATH)


async def main():
    await client.connect()

    try:
        if not await client.is_user_authorized():
            print("로그인된 세션이 없습니다. 먼저 test.py를 실행하세요.")
            return

        me = await client.get_me()
        print("로그인 확인 성공")
        print("사용자 ID:", me.id)
        print("사용자명:", me.username)
    finally:
        await client.disconnect()


asyncio.run(main())
