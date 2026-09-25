import argparse
import getpass
from pathlib import Path

from local_config import normalize_discord_webhook


BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"


def parse_args():
    parser = argparse.ArgumentParser(description="Save local API settings to a .env file.")
    parser.add_argument(
        "--hidden",
        action="store_true",
        help="Hide entered values instead of showing them in the terminal",
    )
    return parser.parse_args()


def prompt_value(label, hidden=False):
    while True:
        prompt = f"{label}: "
        value = (getpass.getpass(prompt) if hidden else input(prompt)).strip()
        if value:
            return value
        print("값을 입력해야 합니다.")


def main(args):
    if ENV_PATH.exists():
        answer = input(".env 파일이 이미 있습니다. 덮어쓸까요? [y/N]: ").strip().lower()
        if answer != "y":
            print("설정을 변경하지 않았습니다.")
            return

    if args.hidden:
        print("숨김 입력 모드입니다. 입력 중에는 문자나 별표가 표시되지 않습니다.")

    api_id = prompt_value("TELEGRAM_API_ID", args.hidden)
    if not api_id.isdigit():
        raise ValueError("TELEGRAM_API_ID는 숫자여야 합니다.")
    api_hash = prompt_value("TELEGRAM_API_HASH", args.hidden)
    webhook_url = normalize_discord_webhook(prompt_value("DISCORD_WEBHOOK_URL", args.hidden))
    dart_api_key = prompt_value("DART_API_KEY", args.hidden)
    gemini_api_key = prompt_value("GEMINI_API_KEY", args.hidden)

    ENV_PATH.write_text(
        "\n".join(
            [
                f"TELEGRAM_API_ID={api_id}",
                f"TELEGRAM_API_HASH={api_hash}",
                f"DISCORD_WEBHOOK_URL={webhook_url}",
                f"DART_API_KEY={dart_api_key}",
                f"GEMINI_API_KEY={gemini_api_key}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"설정을 저장했습니다: {ENV_PATH}")


if __name__ == "__main__":
    main(parse_args())
