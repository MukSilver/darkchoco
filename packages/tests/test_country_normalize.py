"""`dc_kr.normalize_country` 와 그것을 쓰는 판정기 둘을 시험합니다. 밖에 안 나갑니다.

    python packages/tests/test_country_normalize.py

2026-09-18 에 더했습니다. 소스마다 국가를 다르게 적어 보내는데 받는 쪽이 `KR`
하나만 알고 있었습니다. 랜섬웨어 집계처는 `KR` 로 주고 CTI 텔레그램 채널은
`Korea` 로 줍니다. 그날 CTI 채널 유출 알림 12줄이 전부 「외국」 으로 빠졌습니다.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages"))

from dc_kr import KrClassifier, normalize_country  # noqa: E402
from dc_kr import SupplyClassifier  # noqa: E402


class 재료:
    """판정기가 보는 다섯 칸."""

    def __init__(self, victim="", website="", description="", country="", sector=""):
        self.victim = victim
        self.website = website
        self.description = description
        self.country = country
        self.sector = sector


# ── normalize_country 자체 ────────────────────────────────────────────


def test_남한_이름은_KR_로_모인다():
    for 값 in ("KR", "kr", " kr ", "kor", "Korea", "korea", "KOREA",
               "South Korea", "south korea", "Korea, South", "Korea (South)",
               "Republic of Korea", "한국", "대한민국"):
        assert normalize_country(값) == "KR", 값


def test_북한_이름은_KP_로_가고_남한과_안_섞인다():
    for 값 in ("KP", "DPRK", "North Korea", "Korea, North", "북한"):
        assert normalize_country(값) == "KP", 값
    # `North Korea` 가 `Korea` 규칙에 먼저 걸리면 북한 건이 한국으로 샌다.
    assert normalize_country("North Korea") != "KR"


def test_모르는_이름은_안_바꾸고_대문자로만_돌려준다():
    """빈 문자열로 만들면 「안 적어 보냈다」 와 「못 알아봤다」 가 안 갈린다."""
    assert normalize_country("Turkey") == "TURKEY"
    assert normalize_country("Argentina") == "ARGENTINA"
    assert normalize_country("USA") == "USA"


def test_빈_값은_빈_문자열이다():
    assert normalize_country("") == ""
    assert normalize_country("   ") == ""
    assert normalize_country(None) == ""


def test_앞뒤_공백과_마침표를_뗀다():
    assert normalize_country("  Korea.  ") == "KR"
    assert normalize_country("South   Korea") == "KR"


# ── KrClassifier ──────────────────────────────────────────────────────


def test_국가가_이름이어도_confirmed_가_나온다():
    등급, _점수, 근거 = KrClassifier({}).classify(재료(victim="Foo Corp", country="Korea"))
    assert 등급 == "confirmed", (등급, 근거)
    assert any("country=KR" in x for x in 근거)


def test_북한은_이름으로_적혀_와도_뺀다():
    등급, _점수, _근거 = KrClassifier({}).classify(
        재료(victim="Foo Corp", country="North Korea"))
    assert 등급 == "none"


def test_국가를_몰라도_kr_도메인이면_잡는다():
    """고치기 전에도 되던 것입니다. 안 깨졌는지 봅니다."""
    등급, _점수, 근거 = KrClassifier({}).classify(
        재료(victim="lookpin.co.kr", website="lookpin.co.kr", country="Korea"))
    assert 등급 in ("confirmed", "strong"), (등급, 근거)


# ── SupplyClassifier ──────────────────────────────────────────────────


def test_국가가_Korea_면_해외기업_갈래로_안_샌다():
    """3번 갈래는 country 가 KR 이 아닌 것만 봅니다.

    `Korea` 가 `KOREA` 로 남던 때는 한국 기업이 「해외(KOREA) 기업이지만 사명에
    Korea 포함」 으로 적혔습니다.
    """
    _등급, _점수, 근거 = SupplyClassifier({}).classify(
        재료(victim="Korea Foo Systems", website="foo.com", country="Korea"))
    assert not any("해외(KOREA)" in x for x in 근거), 근거


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
