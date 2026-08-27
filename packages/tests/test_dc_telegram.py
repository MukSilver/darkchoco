"""dc_telegram 로직 테스트. telethon 없이도 돕니다.

    python -m pytest packages/tests/ -q
    python packages/tests/test_dc_telegram.py
"""
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# telethon 을 안 깔아도 순수 로직은 검증할 수 있게 최소 스텁을 끼웁니다.
if "telethon" not in sys.modules:
    t = types.ModuleType("telethon"); t.TelegramClient = object
    u = types.ModuleType("telethon.utils")
    u.get_display_name = lambda s: getattr(s, "name", None)
    u.get_peer_id = lambda p: getattr(p, "id", 0)
    ch = types.ModuleType("telethon.tl.functions.channels")
    ch.GetFullChannelRequest = lambda e: None
    for n, m in [("telethon", t), ("telethon.utils", u),
                 ("telethon.tl", types.ModuleType("telethon.tl")),
                 ("telethon.tl.functions", types.ModuleType("telethon.tl.functions")),
                 ("telethon.tl.functions.channels", ch)]:
        sys.modules[n] = m

import dc_telegram as dc  # noqa: E402


def test_parse_channel():
    assert dc.parse_channel("https://t.me/LEAKBASE4/") == "LEAKBASE4"
    assert dc.parse_channel("t.me/foo") == "foo"
    assert dc.parse_channel("@bar") == "bar"
    assert dc.parse_channel(" baz/ ") == "baz"


def test_merge_records_새것이_이기고_내림차순():
    old = [{"id": 3, "text": "old3"}, {"id": 1, "text": "old1"}]
    new = [{"id": 4, "text": "new4"}, {"id": 3, "text": "new3"}]
    m = dc.merge_records(old, new)
    assert [r["id"] for r in m] == [4, 3, 1]
    assert m[1]["text"] == "new3"


def test_validate_same_channel_다른채널_차단():
    dc.validate_same_channel({"channel": {"id": 111}}, {"id": 111})
    try:
        dc.validate_same_channel({"channel": {"id": 111}}, {"id": 222})
    except ValueError:
        return
    raise AssertionError("다른 채널인데 통과했습니다")


def test_write_json_atomic_임시파일_안남김():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "sub" / "out.json"
        dc.write_json_atomic(p, {"channel": {"id": 1}, "messages": [{"id": 9}]})
        assert dc.load_payload(p)["messages"][0]["id"] == 9
        assert not [f for f in p.parent.iterdir() if f.name.startswith(".")]


def test_timeutil():
    assert dc.get_timezone("Asia/Seoul") is not None
    assert str(dc.parse_day("2026-08-27")) == "2026-08-27"
    try:
        dc.parse_day("2026/08/27")
    except Exception:
        return
    raise AssertionError("잘못된 날짜 형식이 통과했습니다")


if __name__ == "__main__":
    ok = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print(f"  OK  {name}"); ok += 1
    print(f"\n{ok}개 통과")
