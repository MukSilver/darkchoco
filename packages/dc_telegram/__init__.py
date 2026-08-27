"""dc_telegram — 텔레그램 접속과 수집의 공용 부품.

두 앱(tg-notion-report, tg-korea-alert)이 같은 코드를 복사해 쓰다가
서로 갈라진 것을 한 벌로 되돌린 것입니다.

각 앱이 붙였던 기능은 둘 다 살렸습니다.
  · tg-notion-report — 증분 수집, 원자적 쓰기, 채널 메타데이터
  · tg-korea-alert   — 날짜 범위 필터, 타임존

이 패키지는 apps 를 import 하지 않습니다.
"""

from .client import SESSION_PATH, make_client, parse_channel
from .collect import collect_messages
from .meta import channel_metadata, forward_metadata, reaction_count, sender_metadata
from .store import load_payload, merge_records, validate_same_channel, write_json_atomic
from .timeutil import get_timezone, isoformat, parse_day

__all__ = [
    "SESSION_PATH", "make_client", "parse_channel",
    "collect_messages",
    "channel_metadata", "sender_metadata", "forward_metadata", "reaction_count",
    "load_payload", "merge_records", "validate_same_channel", "write_json_atomic",
    "get_timezone", "isoformat", "parse_day",
]
