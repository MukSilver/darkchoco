"""시간 처리. 날짜 범위와 타임존은 tg-korea-alert 쪽에서 온 것입니다."""

from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:                                  # 3.8 이하
    ZoneInfo = None                                  # type: ignore


def isoformat(value):
    """datetime 을 ISO 문자열로. None 이면 None 을 그대로 돌려줍니다."""
    return value.isoformat() if value else None


def parse_day(value: str) -> date:
    """YYYY-MM-DD 만 받습니다. argparse type 으로 바로 쓸 수 있습니다."""
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError("날짜는 YYYY-MM-DD 형식이어야 합니다.") from exc


def get_timezone(name: str = "Asia/Seoul"):
    """tzdata 가 없는 환경(주로 Windows)에서도 서울과 UTC 는 되게 합니다."""
    if ZoneInfo is not None:
        try:
            return ZoneInfo(name)
        except Exception:
            pass
    if name == "Asia/Seoul":
        return timezone(timedelta(hours=9), name)
    if name in {"UTC", "Etc/UTC"}:
        return timezone.utc
    raise ValueError(
        f"시간대 '{name}' 을 불러올 수 없습니다. "
        "tzdata 를 설치하거나 Asia/Seoul 또는 UTC 를 쓰십시오."
    )


def day_bounds(from_day: date | None, to_day: date | None, tz):
    """날짜(달력 기준)를 그 타임존의 하루 경계 datetime 으로 바꿉니다."""
    start = datetime.combine(from_day, datetime.min.time(), tz) if from_day else None
    end = datetime.combine(to_day, datetime.max.time(), tz) if to_day else None
    return start, end
