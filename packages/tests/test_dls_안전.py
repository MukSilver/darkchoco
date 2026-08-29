"""dls_fill 이 노션을 망가뜨리지 않는지 봅니다.

이 도구는 안유빈 님 것입니다. 여기서는 **hub 크롤러와 같은 규칙을
지키는지**만 봅니다. 두 도구가 같은 514줄을 쓰는데 규칙이 다르면
한쪽이 다른 쪽을 지웁니다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages"))

from dc_console import use_utf8  # noqa: E402

use_utf8()

앱 = ROOT / "apps" / "dls-observatory"


def _글():
    return (앱 / "dls_fill.py").read_text(encoding="utf-8")


def test_한국_관련_유출에_이름을_안_쓴다():
    """SECURITY.md — 나가는 것은 항목 이름과 건수입니다.

    예전에는 post_title(피해 기관 이름)을 그대로 적었습니다. 같은 칸에
    hub 크롤러는 건수만 씁니다. 한쪽만 이름을 적으면 규칙이 깨집니다.
    """
    글 = _글()
    자리 = 글[글.index("group_kr_victims(canonical)"):]
    자리 = 자리[:자리.index("# ---------- ransomlook")]
    # 주석은 빼고 실제로 도는 줄만 봅니다.
    코드 = " ".join(l for l in 자리.splitlines()
                  if not l.strip().startswith("#"))
    # korea_leaks 에 실제로 넣는 값만 봅니다.
    넣는줄 = [l for l in 자리.splitlines()
            if 'out["korea_leaks"]' in l and not l.strip().startswith("#")]
    assert 넣는줄, "korea_leaks 를 안 씁니다"
    한줄 = 넣는줄[0]
    for 금지 in ("post_title", "names", "victim"):
        assert 금지 not in 한줄, f"{금지} 이 값에 들어갑니다: {한줄.strip()}"
    assert "len(kr)" in 한줄 and "건" in 한줄, 한줄.strip()


def test_압수됨_인계됨_을_안_덮는다():
    """hub/places/place.py 의 사람판정_상태 와 같은 규칙입니다."""
    글 = _글()
    assert '("압수됨", "인계됨")' in 글, "사람 판정 보호가 없습니다"
    from hub.places.place import 사람판정_상태
    for v in 사람판정_상태:
        assert f'"{v}"' in 글, f"{v} 를 안 지킵니다"


def test_선택지에_없는_값을_안_보낸다():
    """infer.py 는 노션에 없는 값을 낼 수 있습니다."""
    글 = _글()
    assert "옵션 = {" in 글 and "안쓴값" in 글, "선택지 검사가 없습니다"
    # 조용히 버리면 안 됩니다. 끝에 알려야 합니다.
    assert "선택지에 없어 안 쓴 값" in 글, "버린 값을 안 알립니다"


def test_국가_칸을_안_쓴다():
    """infer 가 내는 값 중 여럿이 노션 선택지에 없습니다."""
    m = json.loads((앱 / "mapping.json").read_text(encoding="utf-8"))
    assert m["columns"].get("country") == "", "국가 칸이 아직 켜져 있습니다"
    assert "국가" not in (m.get("append_columns") or [])


def test_노션에_없는_선택지를_짚어_둔다():
    """왜 껐는지가 스키마에서 확인되어야 합니다."""
    스키마 = json.loads((HERE / "노션스키마.json").read_text(encoding="utf-8"))
    있는것 = set(스키마["ransom"]["선택지"]["국가"])
    for 없어야할것 in ("추정: 이란", "추정: 베트남", "추정: 한국", "추정: 일본"):
        assert 없어야할것 not in 있는것, (
            f"{없어야할것} 이 생겼습니다. 국가 칸을 다시 켤 수 있는지 보십시오")
    형식 = set(스키마["ransom"]["선택지"]["형식"])
    assert "추정: 스틸러/로그" not in 형식
    assert "추정: 사기 도구" not in 형식


def test_dls_fill_도_Tor_를_탄다():
    """hub 크롤러는 Tor 없이는 아예 안 나갑니다.

    같은 ransomware.live 를 두 도구가 치는데 한쪽만 맨 IP 로 나가면
    규칙이 도구마다 갈립니다. 그러면 반드시 빠뜨립니다.

    여기서는 막지 않고 **어느 길로 나갔는지를 매 줄에 적습니다.**
    이 앱은 사람이 손으로도 돌리는 것이라, 막으면 Tor 없는 자리에서
    아무것도 못 합니다. 대신 로그를 보면 압니다.
    """
    글 = (앱 / "sources.py").read_text(encoding="utf-8")
    assert "urllib.request.urlopen(req" not in 글, (
        "프록시를 건너뛰는 urlopen 이 남아 있습니다")
    assert "TOR_SOCKS_PROXY" in 글, "프록시를 안 봅니다"
    assert "_나가는길" in 글

    import os
    import sys as _sys
    _sys.path.insert(0, str(앱))
    import sources                                   # noqa: PLC0415

    옛 = os.environ.pop("TOR_SOCKS_PROXY", None)
    try:
        sources._오프너캐시.clear()
        assert "맨 연결" in sources._나가는길()[1]
        os.environ["TOR_SOCKS_PROXY"] = "http://127.0.0.1:9080"
        sources._오프너캐시.clear()
        오프너, 어떻게 = sources._나가는길()
        assert 어떻게 == "Tor", 어떻게
        # https 만 프록시로 보냅니다. http 는 CONNECT 를 안 써서 Tor 가 끊습니다.
        import urllib.request
        핸들러 = [h for h in 오프너.handlers
                if isinstance(h, urllib.request.ProxyHandler)]
        assert 핸들러 and set(핸들러[0].proxies) == {"https"}, (
            핸들러[0].proxies if 핸들러 else "ProxyHandler 없음")
    finally:
        sources._오프너캐시.clear()
        os.environ.pop("TOR_SOCKS_PROXY", None)
        if 옛 is not None:
            os.environ["TOR_SOCKS_PROXY"] = 옛


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_"):
            v()
            print(f"  OK  {k}")
            n += 1
    print(f"\n{n}개 통과")
