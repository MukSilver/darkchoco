import asyncio
import getpass
import os
from pathlib import Path

import qrcode
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

from local_config import load_local_env


BASE_DIR = Path(__file__).resolve().parent
SESSION_PATH = BASE_DIR / "telegram_session"
QR_PATH = BASE_DIR / "telegram_login_qr.png"

load_local_env()
api_id = int(os.environ["TELEGRAM_API_ID"])
api_hash = os.environ["TELEGRAM_API_HASH"]

client = TelegramClient(str(SESSION_PATH), api_id, api_hash)


async def main():
    await client.connect()

    try:
        if not await client.is_user_authorized():
            qr_login = await client.qr_login()

            while True:
                qrcode.make(qr_login.url).save(QR_PATH)
                print(f"QR 이미지를 열어 스캔하세요: {QR_PATH}")

                try:
                    await qr_login.wait(timeout=30)
                    break
                except asyncio.TimeoutError:
                    print("QR이 만료되어 새 QR을 생성합니다.")
                    await qr_login.recreate()
                except SessionPasswordNeededError:
                    password = getpass.getpass("텔레그램 2단계 인증 비밀번호: ")
                    await client.sign_in(password=password)
                    break

        me = await client.get_me()
        print("로그인 성공")
        print("사용자 ID:", me.id)
        print("사용자명:", me.username)
    finally:
        await client.disconnect()


asyncio.run(main())
