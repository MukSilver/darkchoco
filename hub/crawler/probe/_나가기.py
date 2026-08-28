"""밖으로 나가는 길. 조사기 셋이 모두 여기를 지납니다.

**우리 IP 로 나가지 않습니다.** 다크웹 포럼과 랜섬 그룹의 쪽을 여는 일은
저쪽 로그에 우리 주소를 남기는 일입니다. 남는 것이 학교 망이든 집이든
한국 주소이면 우리가 누구인지 좁혀집니다.

그래서 기본값이 **보호가 없으면 안 나갑니다** 입니다. 빠뜨려서 맨
연결이 되는 일이 없게, 못 나가는 쪽이 기본입니다.

    TOR_SOCKS_PROXY   Tor 의 HTTPTunnelPort 주소. 이것이 있어야 나갑니다
    DARKCHOCO_TOR_SKIP
                      Tor 를 안 거칠 갈래. 쉼표로 나눕니다 (telegram 등)
    DARKCHOCO_ALLOW_DIRECT=1
                      맨 연결을 일부러 허락합니다. 평소에 쓰지 마십시오

갈래마다 사정이 다릅니다.

    forum    반드시 Tor. 저쪽이 다크웹 포럼입니다
    ransom   반드시 Tor. 어느 그룹을 보는지가 남을 이유가 없습니다
    telegram t.me 는 텔레그램 서버라 다크웹은 아닙니다. 다만 어느 채널을
             언제 보는지가 우리 주소와 함께 남습니다. 한편 Tor 출구는
             t.me 에서 캡차나 차단을 자주 만납니다. 그래서 켜 두되 끌 수
             있게 했습니다

    export DARKCHOCO_TOR_SKIP=telegram

**끄면 그 갈래는 우리 IP 로 나갑니다.** 끌 때는 그것을 알고 끄는
것입니다. 아무 말 없이 새는 것과 다릅니다.

Tor 를 어떻게 켜나 — torrc 에 두 줄을 넣고 tor 를 띄웁니다.

    HTTPTunnelPort 9080
    ExcludeExitNodes {kr}
    StrictNodes 1

SOCKS 가 아니라 HTTPTunnelPort 를 씁니다. 표준 라이브러리는 SOCKS 를
못 탑니다. socks 라이브러리를 받으면 되지만, 받을 것을 늘리면 팀원이
그것을 안 깔고 돌렸을 때 조용히 맨 연결로 새는 길이 생깁니다.

`ExcludeExitNodes {kr}` 은 한국 출구를 아예 안 쓰게 합니다. Tor 에도
한국 출구가 있어서, 안 막으면 우리 IP 는 아니어도 한국 주소가 남습니다.

    export TOR_SOCKS_PROXY=http://127.0.0.1:9080

표준 라이브러리만 씁니다.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

__all__ = ["보호없음", "오프너", "프록시주소", "출구확인", "안내",
           "뺀갈래", "맨연결_허락"]

확인주소 = "https://check.torproject.org/api/ip"

안내 = (
    "밖으로 나가려면 Tor 가 있어야 합니다. 우리 IP 를 남기지 않으려는 것입니다.\n"
    "  1. torrc 에 넣으십시오\n"
    "       HTTPTunnelPort 9080\n"
    "       ExcludeExitNodes {kr}\n"
    "       StrictNodes 1\n"
    "  2. tor 를 띄우고\n"
    "       export TOR_SOCKS_PROXY=http://127.0.0.1:9080\n"
    "  확인은  python dc.py doctor  로 합니다."
)


class 보호없음(RuntimeError):
    """Tor 가 없어 안 나갑니다. 맨 IP 로 나가느니 안 하는 편이 낫습니다."""


def 프록시주소() -> str:
    """쓸 프록시. 없으면 빈 글자입니다."""
    return (os.environ.get("TOR_SOCKS_PROXY") or "").strip()


def 맨연결_허락() -> bool:
    return (os.environ.get("DARKCHOCO_ALLOW_DIRECT") or "").strip() == "1"


_맨연결_허락 = 맨연결_허락        # 옛 이름


def 뺀갈래() -> set[str]:
    """Tor 를 안 거칠 갈래들. 비어 있는 것이 기본입니다."""
    값 = (os.environ.get("DARKCHOCO_TOR_SKIP") or "").strip()
    return {x.strip().lower() for x in 값.split(",") if x.strip()}


def 오프너(프록시: str | None = None, *, 갈래: str = ""):
    """요청을 보낼 오프너. 보호가 없으면 예외를 냅니다.

    **여기서 예외를 내는 것이 이 파일의 요점입니다.** 없으면 그냥 열어
    주는 쪽으로 두면, 환경 변수를 안 넣은 사람이 돌렸을 때 아무 말 없이
    맨 IP 로 나갑니다. 그것을 나중에 알아채는 방법이 없습니다.

    갈래 를 주면 DARKCHOCO_TOR_SKIP 에 든 갈래는 맨 연결을 허락합니다.
    끄는 사람이 무엇을 끄는지 알고 끄는 것입니다.
    """
    프록시 = (프록시 or 프록시주소()).strip()

    if 갈래 and 갈래.lower() in 뺀갈래():
        # 일부러 뺀 갈래입니다. 프록시가 있으면 그래도 씁니다.
        if not 프록시:
            return urllib.request.build_opener()

    if not 프록시:
        if 맨연결_허락():
            return urllib.request.build_opener()
        raise 보호없음(안내)

    if 프록시.startswith("socks"):
        raise 보호없음(
            "SOCKS 는 표준 라이브러리로 못 탑니다. tor 의 HTTPTunnelPort "
            "주소를 주십시오 (예: http://127.0.0.1:9080).\n" + 안내)

    # 프록시를 지정한 핸들러만 답니다. 환경 변수에서 프록시를 주워 오는
    # 기본 동작을 끄려는 것입니다. 그쪽이 비어 있으면 맨 연결이 됩니다.
    return urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": 프록시, "https": 프록시}))


def 출구확인(프록시: str | None = None, *, timeout: int = 30) -> dict:
    """무엇으로 나가고 있는지 물어봅니다.

    돌려주는 것 — {"tor": bool, "ip": str, "된다": bool, "말": str}

    Tor 를 타고 있으면 그 IP 는 출구 노드 것이지 우리 것이 아닙니다.
    그것만으로 「우리 것으로 안 남는다」가 보장됩니다. 한국인지는 여기서
    못 가립니다. torrc 의 ExcludeExitNodes {kr} 로 막습니다.
    """
    프록시 = (프록시 or 프록시주소()).strip()
    if not 프록시:
        허락 = _맨연결_허락()
        return {"tor": False, "ip": "", "된다": 허락,
                "말": ("맨 연결을 일부러 허락한 상태입니다 "
                      "(DARKCHOCO_ALLOW_DIRECT=1). 우리 IP 가 남습니다."
                      if 허락 else "Tor 가 없습니다. 안 나갑니다.")}
    try:
        op = 오프너(프록시)
    except 보호없음 as e:
        return {"tor": False, "ip": "", "된다": False, "말": str(e)}

    req = urllib.request.Request(확인주소, headers={
        "User-Agent": "darkchoco-research/1.0", "Accept": "application/json"})
    try:
        with op.open(req, timeout=timeout) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, OSError, ValueError) as e:
        return {"tor": False, "ip": "", "된다": False,
                "말": f"프록시로 확인 주소를 못 열었습니다: {e}. "
                     f"tor 가 떠 있는지 보십시오."}

    tor = bool(d.get("IsTor"))
    ip = str(d.get("IP") or "")
    return {"tor": tor, "ip": ip, "된다": tor,
            "말": (f"Tor 를 타고 있습니다. 밖에 남는 주소는 {ip} 입니다."
                  if tor else
                  f"프록시는 열렸는데 Tor 가 아닙니다. 남는 주소는 {ip} 입니다. "
                  f"이대로면 우리 IP 일 수 있습니다.")}
