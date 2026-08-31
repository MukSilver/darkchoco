import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "packages"))
from dc_telegram import make_client



BASE_DIR = Path(__file__).resolve().parent
SESSION_PATH = BASE_DIR / "telegram_session"


async def main():
    # 클라이언트를 모듈 바깥에서 만들면 import 만 해도 세션 파일이 열리고,
    # 환경변수가 없으면 그 자리에서 RuntimeError 가 납니다. channels.py 와
    # 같이 main() 안에서 만듭니다.
    client = make_client(SESSION_PATH)

    await client.connect()

    try:
        if not await client.is_user_authorized():
            # 이 폴더에는 test.py 가 없습니다. 세션을 만드는 것은
            # apps/tg-korea-alert/test.py 이고, 세션 파일은 그 앱 폴더에
            # 생깁니다. 여기서 보는 자리는 SESSION_PATH 입니다.
            print("로그인된 세션이 없습니다.")
            print(f"이 스크립트가 보는 세션 파일: {SESSION_PATH}")
            print("세션을 만드는 스크립트: apps/tg-korea-alert/test.py"
                  " (세션을 그 앱 폴더에 만듭니다)")
            return

        me = await client.get_me()
        print("로그인 확인 성공")
        print("사용자 ID:", me.id)
        print("사용자명:", me.username)
    finally:
        await client.disconnect()


# import 만 해도 텔레그램에 붙던 자리입니다. 목록을 보려고 건드리기만 해도
# 접속이 일어났습니다. 다른 파일과 같이 __main__ 가드를 답니다.
if __name__ == "__main__":
    asyncio.run(main())
