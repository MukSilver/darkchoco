"""dc_telegram — 텔레그램 접속과 수집의 공용 부품.

두 앱(tg-notion-report, tg-korea-alert)이 같은 코드를 복사해 쓰다가
서로 갈라진 것을 한 벌로 되돌린 것입니다.

각 앱이 붙였던 기능은 둘 다 살렸습니다.
  · tg-notion-report — 증분 수집, 원자적 쓰기, 채널 메타데이터
  · tg-korea-alert   — 날짜 범위 필터, 타임존

이 패키지는 apps 를 import 하지 않습니다.
"""

# store 와 timeutil 은 표준 라이브러리만 씁니다. 바로 부릅니다.
from .store import load_payload, merge_records, validate_same_channel, write_json_atomic
from .timeutil import day_bounds, get_timezone, isoformat, parse_day

# client · collect · meta 는 telethon 을 씁니다. 순수 로직만 쓰는 곳까지
# telethon 을 받게 하지 않으려고 늦게 부릅니다. dc_safety 와
# dc_ransomfeed 가 이미 같은 방식입니다.
# 2026-08-31. 전에는 여기서 .client 를 바로 불러, parse_day 하나만
# 쓰려 해도 telethon 이 있어야 했습니다.
_TELETHON = {
    "SESSION_PATH": "client", "make_client": "client", "parse_channel": "client",
    "collect_messages": "collect",
    "channel_metadata": "meta", "forward_metadata": "meta",
    "reaction_count": "meta", "safe_peer_id": "meta",
    "sender_label": "meta", "sender_metadata": "meta",
}


def __getattr__(name):
    모듈 = _TELETHON.get(name)
    if 모듈:
        from importlib import import_module
        return getattr(import_module("." + 모듈, __name__), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "SESSION_PATH", "make_client", "parse_channel",
    "collect_messages",
    "channel_metadata", "sender_metadata", "forward_metadata", "reaction_count",
    "safe_peer_id", "sender_label",
    "load_payload", "merge_records", "validate_same_channel", "write_json_atomic",
    "get_timezone", "isoformat", "parse_day", "day_bounds",
]
