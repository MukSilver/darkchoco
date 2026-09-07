"""두 랜섬 어댑터가 같은 사건을 같은 줄로 만드는지 본다. 밖에 요청을 안 보낸다.

    python packages/tests/test_열쇠맞춤.py

2026-09-07. 어댑터가 둘인데 표에서 서로 다른 줄로 쌓이고 있었다. uid 는 KEY 여섯을
이어 만드는데 그중 셋(src_id · venue · title)이 달랐다. 여기서 그것을 못박는다.

**앱이 만든 해시를 열쇠로 쓰면 안 된다.** 피해자를 도메인으로만 가려서 같은 회사가
여러 번 털리면 한 줄로 뭉친다. 알림은 그것이 맞지만 우리 표는 게시물 하나가 사건 하나다.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps" / "kr-leak-alarm"))
sys.path.insert(0, str(ROOT / "skills"))

from collector.sources.base import LeakRecord  # noqa: E402
from dc_store import KEY  # noqa: E402
from hub.events.sources.ransom_kr import _항목으로  # noqa: E402

from collect.sources import ransomlive  # noqa: E402


def _집계처응답(**바꿈) -> dict:
    """ransomware.live v2 응답 한 줄. 필드 이름은 그 API 문서 그대로다."""
    d = {
        "post_title": "Acme Corp", "victim": "Acme Corp", "group_name": "lockbit",
        "country": "KR", "website": "acme.co.kr", "activity": "Construction",
        "description": "Acme is a builder.", "published": "2026-08-17 10:00:00",
        "discovered": "2026-08-18 02:00:00",
        "post_url": "http://someonion.onion/post/1",
        "data_size": "50GB", "ransom": "100000",
    }
    d.update(바꿈)
    return d


def _우리줄(응답: dict):
    """우리 어댑터가 만드는 줄. `kr` 엔드포인트 이름표를 그대로 쓴다."""
    return ransomlive.to_item(응답, ransomlive.FEEDS["kr"], "kr")


def _팀줄(응답: dict):
    r = LeakRecord(
        victim=응답["post_title"], group=응답["group_name"], country=응답["country"],
        sector=응답["activity"], website=응답["website"],
        description=응답["description"], published=응답["published"],
        discovered=응답["discovered"], post_url=응답["post_url"],
        source="ransomware.live",
        data_size=응답["data_size"], ransom=응답["ransom"],
    ).finalize()
    return _항목으로(r)


def test_같은_사건이면_uid_가_같다():
    응답 = _집계처응답()
    우리, 팀 = _우리줄(응답), _팀줄(응답)
    assert 우리.uid() == 팀.uid(), (
        "열쇠가 갈렸다. 다른 칸: %s"
        % [k for k in KEY if str(getattr(우리, k, "")) != str(getattr(팀, k, ""))])


def test_열쇠_칸_여섯이_글자까지_같다():
    응답 = _집계처응답()
    우리, 팀 = _우리줄(응답), _팀줄(응답)
    for k in KEY:
        assert str(getattr(우리, k, "")) == str(getattr(팀, k, "")), k


def test_같은_회사의_다른_게시물은_안_뭉친다():
    """앱 해시를 열쇠로 쓰면 여기서 뭉쳤다. 게시물 하나가 사건 하나다."""
    첫 = _팀줄(_집계처응답(published="2025-09-15 00:00:00",
                        post_url="http://someonion.onion/post/1"))
    둘 = _팀줄(_집계처응답(published="2026-02-28 00:00:00",
                        post_url="http://someonion.onion/post/2"))
    assert 첫.uid() != 둘.uid()


def test_버려지던_규모와_가격이_들어온다():
    팀 = _팀줄(_집계처응답())
    assert 팀.claimed_size == "50GB"
    assert 팀.price == "100000"


def test_빈_규모는_출처를_안_옴으로_적는다():
    """빈 값이 「주장 없음」 이 아니다. 집계처가 안 긁은 것일 수 있다."""
    있음 = _팀줄(_집계처응답())
    없음 = _팀줄(_집계처응답(data_size=""))
    assert 있음.raw["규모 출처"] == "집계처 API"
    assert "안 옴" in 없음.raw["규모 출처"]


def test_노션_선택지에_있는_게시_성격을_쓴다():
    """「유출 게시」 는 노션 선택지에 없어 3번 관문에서 버려졌다."""
    assert _팀줄(_집계처응답()).kind == "랜섬웨어 유출"


def test_앱_해시와_판정_결과는_raw_에_남는다():
    raw = _팀줄(_집계처응답()).raw
    for k in ("앱 uid", "victim_key", "group_key", "산업 분야", "발견일"):
        assert k in raw, k


def test_원문이_없으면_집계처_이름이_자리가_된다():
    팀 = _팀줄(_집계처응답(post_url=""))
    assert 팀.venue == "ransomware.live"
    assert 팀.venue_kind == "그밖"


if __name__ == "__main__":
    시험 = [(k, v) for k, v in sorted(globals().items())
            if k.startswith("test_") and callable(v)]
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
