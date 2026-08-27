import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"


def normalize_discord_webhook(value):
    url = urlsplit(value.strip())
    if url.scheme != "https" or url.hostname not in {"discord.com", "discordapp.com"}:
        raise ValueError("Discord 웹훅은 discord.com 또는 discordapp.com의 HTTPS URL이어야 합니다.")

    parts = [part for part in url.path.split("/") if part]
    if len(parts) != 4 or parts[:2] != ["api", "webhooks"] or not all(parts[2:]):
        raise ValueError("Discord 웹훅 URL 형식이 올바르지 않습니다.")

    return urlunsplit(("https", "discord.com", url.path, url.query, ""))


def load_local_env(path=ENV_PATH):
    """Load simple KEY=VALUE entries without overriding existing environment variables."""
    if not path.exists():
        return

    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Invalid .env entry at line {line_number}")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(key, value)
