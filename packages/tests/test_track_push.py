"""track_push.py 가 Actions 로그에 피해 조직을 안 찍는지 시험합니다. 노션과 집계처에 붙지 않습니다.

    python packages/tests/test_track_push.py

track.yml 이 하루 한 번 돌립니다. **레포를 공개로 돌리면 Actions 로그를 90일 동안 누구나 봅니다.**
대상 조직은 피해 조직 이름이라 로그에 찍으면 안 됩니다. 어느 줄인지는 UID 로 가립니다.
"""
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from hub.events import track_push  # noqa: E402

_가짜조직 = "가짜조직-QZX-시험용"


def _글(v: str) -> dict:
    return {"type": "rich_text", "rich_text": [{"plain_text": v}]}


def _고름(v: str) -> dict:
    return {"type": "select", "select": {"name": v} if v else None}


class _가짜노션:
    """track_push 가 쓰는 셋(_call · search · title_of)만 흉내 냅니다. 랜섬 줄 하나가 있습니다."""

    @staticmethod
    def search(_q):
        return [{"object": "data_source", "id": "ds-1", "last_edited_time": "2026-09-26"}]

    @staticmethod
    def title_of(_r):
        return "수집 DB"

    @staticmethod
    def _call(path, method="GET", body=None):
        if path == "/data_sources/ds-1":
            return {"properties": {c: {} for c in ("관측 시각", "게시 상태", "관측자", "관측 근거")}}
        if path == "/data_sources/ds-1/query":
            return {"has_more": False, "results": [{
                "id": "page-1",
                "properties": {
                    "소스": _고름("랜섬웨어"),
                    "UID": _글("u-track-1"),
                    "대상 조직": _글(_가짜조직),
                    "게시 상태": _고름("게시 중"),
                    "관측자": _고름("집계처"),
                },
            }]}
        raise AssertionError("미리보기에서 쓰면 안 됩니다: %s %s" % (method, path))


def test_바뀐_줄_로그에_대상_조직이_안_나간다():
    원래 = track_push._노션, track_push.집계처판, sys.argv
    track_push._노션 = lambda: _가짜노션
    # 이 줄은 이번 판에 안 보였습니다. 「게시 중」 → 「안 보임」 으로 바뀝니다
    track_push.집계처판 = lambda dry=False: {"다른-uid"}
    sys.argv = ["track_push.py"]
    버퍼 = io.StringIO()
    try:
        with contextlib.redirect_stdout(버퍼):
            rc = track_push.main()
    finally:
        track_push._노션, track_push.집계처판, sys.argv = 원래
    글 = 버퍼.getvalue()
    assert rc == 0, 글
    assert "바뀐 줄 1" in 글, 글
    # 어느 줄인지는 UID 로 보입니다
    assert "u-track-1" in 글, 글
    assert _가짜조직 not in 글, 글


if __name__ == "__main__":
    시험 = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    실패 = 0
    for 이름, f in 시험:
        try:
            f()
            print("  통과  %s" % 이름)
        except AssertionError as e:  # noqa: PERF203
            실패 += 1
            print("  실패  %s  %s" % (이름, e))
        except Exception as e:  # noqa: BLE001
            실패 += 1
            print("  오류  %s  %s: %s" % (이름, type(e).__name__, e))
    print("%d개 중 %d개 실패" % (len(시험), 실패))
    raise SystemExit(1 if 실패 else 0)
