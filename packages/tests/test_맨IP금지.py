"""Tor 없이 밖으로 나가지 않는지 봅니다.

다크웹 쪽을 여는 일은 저쪽 로그에 우리 주소를 남기는 일입니다. 남는
주소가 한국이면 우리가 누구인지 좁혀집니다.

이 검사가 지키는 것 둘입니다.

  1. 조사기 안에서 urllib 을 직접 부르지 않습니다. 부르면 _나가기.py 의
     프록시를 건너뜁니다. 한 군데만 새도 그 갈래는 맨 IP 로 나갑니다
  2. Tor 가 없으면 요청을 아예 안 보냅니다. 빈손으로 돌아오지, 맨
     연결로 채워 오지 않습니다

옛날에 이런 식으로 샜습니다 — 어니언 주소만 프록시를 쓰고 평범한
도메인은 맨 연결이었습니다. 규칙이 대상마다 다르면 반드시 빠뜨립니다.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packages"))

PROBE = ROOT / "hub" / "crawler" / "probe"


def _토르없이():
    """이 안에서는 TOR_SOCKS_PROXY 도 맨연결 허락도 없습니다."""
    class 지움:
        def __enter__(self):
            self.옛 = {k: os.environ.pop(k, None)
                      for k in ("TOR_SOCKS_PROXY", "DARKCHOCO_ALLOW_DIRECT")}
        def __exit__(self, *a):
            for k, v in self.옛.items():
                if v is not None:
                    os.environ[k] = v
    return 지움()


def test_조사기는_urlopen_을_직접_안_부른다():
    """urlopen 은 프록시를 안 거칩니다. opener.open 을 써야 합니다."""
    샌곳 = []
    for f in sorted(PROBE.glob("*.py")):
        if f.name == "_나가기.py":
            continue                      # 나가는 길 자신입니다
        for i, 줄 in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"urllib\.request\.urlopen\s*\(", 줄):
                샌곳.append(f"{f.name}:{i}")
    assert not 샌곳, f"프록시를 건너뛰는 곳: {' · '.join(샌곳)}"


def test_조사기는_build_opener_를_직접_안_만든다():
    """직접 만들면 프록시 없는 오프너가 됩니다."""
    샌곳 = []
    for f in sorted(PROBE.glob("*.py")):
        if f.name == "_나가기.py":
            continue
        for i, 줄 in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if "build_opener" in 줄:
                샌곳.append(f"{f.name}:{i}")
    assert not 샌곳, f"프록시 없는 오프너를 만드는 곳: {' · '.join(샌곳)}"


def test_토르가_없으면_오프너를_안_준다():
    from hub.crawler.probe._나가기 import 보호없음, 오프너
    with _토르없이():
        try:
            오프너()
        except 보호없음:
            return
        raise AssertionError("Tor 없이 오프너를 내줬다")


def test_socks_주소는_받지_않는다():
    """표준 라이브러리는 SOCKS 를 못 탑니다. 조용히 맨 연결이 되면 안 됩니다."""
    from hub.crawler.probe._나가기 import 보호없음, 오프너
    try:
        오프너("socks5://127.0.0.1:9050")
    except 보호없음 as e:
        assert "HTTPTunnelPort" in str(e)
        return
    raise AssertionError("SOCKS 주소를 받아들였다")


def test_세_갈래가_토르_없이는_안_나간다():
    from hub.crawler.probe import forum, ransom, telegram
    with _토르없이():
        것들 = {
            "forum": forum.한곳("https://example.invalid/", "F", [0.0]),
            "telegram": telegram.한곳("https://t.me/nope", [0.0]),
            "ransom": next(iter(ransom.조사())),
        }
    for 갈래, p in 것들.items():
        assert "Tor 가 없어" in p.못본이유, f"{갈래}: {p.못본이유!r}"
        # 안 나갔으면 노션에도 안 씁니다. 두드리지 못한 것입니다.
        assert p.노션값() == {}, f"{갈래} 가 안 나가고도 쓰려 한다"


def test_맨연결은_일부러_켜야_된다():
    from hub.crawler.probe._나가기 import 오프너
    with _토르없이():
        os.environ["DARKCHOCO_ALLOW_DIRECT"] = "1"
        try:
            assert 오프너() is not None
        finally:
            os.environ.pop("DARKCHOCO_ALLOW_DIRECT", None)


def test_갈래를_빼면_그_갈래만_맨연결이_된다():
    """끄는 사람이 무엇을 끄는지 알고 끄는 것입니다. 조용히 새는 것과 다릅니다."""
    from hub.crawler.probe._나가기 import 보호없음, 오프너
    with _토르없이():
        os.environ["DARKCHOCO_TOR_SKIP"] = "telegram"
        try:
            assert 오프너(갈래="telegram") is not None
            for 갈래 in ("forum", "ransom"):
                try:
                    오프너(갈래=갈래)
                except 보호없음:
                    continue
                raise AssertionError(f"{갈래} 가 Tor 없이 나가려 한다")
        finally:
            os.environ.pop("DARKCHOCO_TOR_SKIP", None)


def test_연결_실패를_offline_로_안_적는다():
    """백신·Tor·망 문제를 「사이트가 죽었다」로 적으면 안 됩니다.

    V3 가 실제로 prologic.su · leaky.pro 접근을 막았습니다. 그것을
    offline 으로 적으면 사람이 조사해 둔 값을 우리 쪽 사정으로 덮습니다.
    """
    from hub.crawler.probe import forum

    class 막힘:
        def open(self, req, timeout=0):
            raise OSError("[WinError 10054] 현재 연결은 원격 호스트에 의해 "
                          "강제로 끊겼습니다 (connection reset)")
    옛 = forum.오프너
    forum.오프너 = lambda 프록시=None, 갈래="": 막힘()
    try:
        p = forum.한곳("https://prologic.su/", "prologic", [0.0])
    finally:
        forum.오프너 = 옛
    assert p.상태 != "offline", p.상태
    assert p.노션값() == {}, p.노션값()
    assert "백신" in p.못본이유, p.못본이유


def test_안내문서와_코드가_안_어긋난다():
    """문서에 적은 환경 변수와 주기가 코드와 같은지 봅니다.

    문서만 고치고 코드를 안 고치거나 그 반대면, 문서를 따라 한 사람이
    보호 없이 돌게 됩니다.
    """
    문서 = (ROOT / "docs" / "안전하게-돌리기.md").read_text(encoding="utf-8")
    for 낱말 in ("TOR_SOCKS_PROXY", "DARKCHOCO_TOR_SKIP",
                "DARKCHOCO_ALLOW_DIRECT", "HTTPTunnelPort 9080",
                "ExcludeExitNodes {kr}", "StrictNodes 1"):
        assert 낱말 in 문서, f"문서에 {낱말} 이 없습니다"

    from hub.crawler.probe import _나가기
    for 낱말 in ("TOR_SOCKS_PROXY", "DARKCHOCO_TOR_SKIP",
                "DARKCHOCO_ALLOW_DIRECT"):
        assert 낱말 in (ROOT / "hub/crawler/probe/_나가기.py")            .read_text(encoding="utf-8"), f"코드에 {낱말} 이 없습니다"

    from hub.crawler.run import 주기
    for 갈래, 분 in 주기.items():
        assert re.search(rf"{갈래}\s+{분}\s*분", 문서),             f"문서의 {갈래} 주기가 코드({분}분)와 다릅니다"


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_"):
            v(); print(f"  OK  {k}"); n += 1
    print(f"\n{n}개 통과")
