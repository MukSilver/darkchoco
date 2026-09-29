"""게시처 깊은 판만 따로 돕니다 (2026-09-29 최현서, 인계 H-4).

    python -m hub.places.deep                          포럼 · 랜섬. 미리보기라 노션에 안 씁니다
    python -m hub.places.deep --only forum --limit 5   포럼 다섯 줄만
    python -m hub.places.deep --apply                  씁니다

`TOR_SOCKS_PROXY` 가 있어야 돕니다. 브라우저는 Tor 없이 안 띄웁니다(fetch.py 브라우저세션).
Actions 에서는 `.github/workflows/places-deep.yml` 이 부릅니다.

## 왜 따로 도나

얕은 판(`places.yml` 의 crawl-tor)이 한 판 48~53분이고 잡 제한이 120분입니다. 깊은 판은 갈래마다
상한 90분이라(run.py 깊은판_상한초) 같은 잡에 넣으면 넘칩니다. 전에는 러너에 playwright 가 없어
늘 건너뛰었고, VM 은 9/22 부터 꺼져 있어 깊은 판 값이 게시처 DB 에 닿은 적이 없었습니다.

## 무엇을 보나

노션 명부에서 **상태가 online 이고 주소가 http 인 줄**만 봅니다. 얕은 판이 같은 날 먼저 돌아
상태를 정해 둡니다. 한 판 안에서 얕은 판 결과를 넘겨받던 `run.한갈래` 와 고르는 기준이 같습니다.
브라우저는 막힌 곳을 뚫는 도구가 아니라 연 곳을 더 깊게 보는 도구입니다(run.py 깊게볼갈래 주석).

## 무엇을 쓰나

**빈칸만 채우는 칸과 이어 붙이는 칸만 씁니다**(`깊은판칸`). 상태 · 확인일 · 규모 · 주소는 얕은 판
몫이라 안 씁니다 — 브라우저가 403 을 받아도 그 곳이 죽은 것은 아닙니다. 사람이 채운 칸은
`명부.반영` 이 안 건드립니다(빈칸만칸). 「사람 값 덮어쓰기」 셈은 그것을 한 번 더 세는 숫자라
늘 0 이어야 합니다. 챌린지로 중단된 줄은 값을 버립니다(모으기.py).

## 로그에 이름을 안 찍습니다

레포가 공개라 Actions 로그를 누구나 봅니다. 건수만 찍습니다.
"""
from __future__ import annotations

import argparse
import dataclasses
import os
import sys
import time
from collections import Counter
from dataclasses import dataclass, field

from hub.places.place import 빈칸만칸, 이어붙이는칸

깊은판칸 = frozenset(빈칸만칸 | 이어붙이는칸)


@dataclass
class 깊은판결과:
    갈래: str
    대상: int = 0            # online · http 인 줄
    봄: int = 0              # 브라우저가 열고 수집기를 다 돈 줄
    챌린지: int = 0          # 열었지만 챌린지로 중단돼 값을 버린 줄
    못엶: int = 0            # 브라우저가 못 연 줄 · 예외 · 상한에서 끊긴 뒤 줄
    끊김: bool = False       # 깊은 판 상한(90분)에서 끊겼나
    초: float = 0.0
    칸별: Counter = field(default_factory=Counter)   # 채울(채운) 칸마다 줄 수
    바뀐줄: int = 0
    덮어쓰기: int = 0        # 사람이 채운 칸을 바꾸려 한 수. 0 이어야 한다
    사람값이라_안씀: int = 0   # 사람이 채워 둬서 안 쓴 칸 수(빈칸만칸 규칙이 막은 것)
    오류: int = 0
    읽기오류: str = ""


def 고르기(줄들) -> list:
    """깊게 볼 줄. 상태가 online 이고 주소가 http 인 줄."""
    return [x for x in 줄들
            if (x.상태 or "").strip() == "online" and (x.주소 or "").strip().startswith("http")]


def 한갈래(갈래: str, *, apply: bool, tor: str | None, limit: int = 0,
         명부=None, 깊게=None) -> 깊은판결과:
    """한 갈래의 깊은 판. 예외를 밖으로 안 냅니다(한 갈래가 죽어도 다음 갈래는 돕니다)."""
    from hub.places import write                      # noqa: PLC0415

    r = 깊은판결과(갈래=갈래)
    t0 = time.time()
    try:
        m = 명부 or write.명부(갈래)
        볼것 = 고르기(m.줄들())
    except Exception as e:  # noqa: BLE001
        r.읽기오류 = f"{type(e).__name__}: {e}"[:160]
        return r
    if limit:
        볼것 = 볼것[:limit]
    r.대상 = len(볼것)
    if 깊게 is None:
        from hub.places.run import 깊게 as 깊게                # noqa: PLC0415
        from hub.places.run import 깊은판_상한초               # noqa: PLC0415
    else:
        깊은판_상한초 = 0

    나온것 = 0
    for 줄, q in 깊게(갈래, 볼것, {"tor": tor}):
        나온것 += 1
        if not q.봤나():
            # 모으기.py 가 챌린지로 중단된 줄은 두드림을 끄고 못본이유를 남긴다. 값은 버린다
            r.챌린지 += 1
            continue
        r.봄 += 1
        # 깊게() 는 상태를 미확인 · 두드림 꺼짐으로 내놓는다(상태는 http 가 정한다).
        # 그대로면 노션값() 이 아무것도 안 낸다. 지금 상태를 두고 깊은판칸만 쓰게 한다
        q2 = dataclasses.replace(q, 상태=줄.상태 or "online", 두드림=True)
        try:
            res = m.반영(줄, q2, apply=apply, 칸만=깊은판칸)
        except Exception:  # noqa: BLE001  한 줄이 죽어도 나머지는 돕니다
            r.오류 += 1
            continue
        if res.오류:
            r.오류 += 1
        r.사람값이라_안씀 += len(res.사람글)
        if res.바뀐칸:
            r.바뀐줄 += 1
            for 칸 in res.바뀐칸:
                r.칸별[칸] += 1
                if 칸 not in 이어붙이는칸 and write._사람이_쓴것(줄.현재.get(칸) or ""):
                    r.덮어쓰기 += 1
    r.못엶 = r.대상 - 나온것
    r.초 = time.time() - t0
    r.끊김 = bool(깊은판_상한초) and r.초 >= 깊은판_상한초
    return r


def 요약(r: 깊은판결과) -> str:
    """로그 몇 줄. **건수만** 냅니다. 게시처 이름을 안 찍습니다."""
    if r.읽기오류:
        return f"  {r.갈래}: 명부를 못 읽었습니다 — {r.읽기오류}"
    줄들 = [f"  {r.갈래}: 깊게 볼 줄 {r.대상} · 연 줄 {r.봄} · 챌린지로 중단 {r.챌린지} · "
          f"못 연 줄 {r.못엶} · {r.초 / 60:.0f}분" + (" · **상한(90분)에서 끊김**" if r.끊김 else "")]
    if r.칸별:
        줄들.append("    채울 칸: " + " · ".join(f"{k} {v}" for k, v in r.칸별.most_common()))
    else:
        줄들.append("    채울 칸: 없음")
    줄들.append(f"    바뀔 줄 {r.바뀐줄} · 사람 값 덮어쓰기 {r.덮어쓰기} · "
              f"사람이 채워 둬서 안 쓴 칸 {r.사람값이라_안씀} · 오류 {r.오류}")
    return "\n".join(줄들)


def 괜찮나(결과: list[깊은판결과], *, 잡제한분: int) -> tuple[bool, list[str]]:
    """예약에 넣어도 되나(최현서 9/29 기준): 잡 제한 안 · 사람 값 덮어쓰기 0 · 실패로 안 멈춤."""
    까닭 = []
    총분 = sum(r.초 for r in 결과) / 60
    if 총분 >= 잡제한분:
        까닭.append(f"잡 제한 {잡제한분}분을 넘었다({총분:.0f}분)")
    if any(r.덮어쓰기 for r in 결과):
        까닭.append("사람 값 덮어쓰기가 0 이 아니다")
    if any(r.읽기오류 for r in 결과):
        까닭.append("명부를 못 읽은 갈래가 있다")
    if any(r.대상 and not (r.봄 or r.챌린지) for r in 결과):
        까닭.append("연 줄이 하나도 없는 갈래가 있다(브라우저 · Tor 를 볼 것)")
    return not 까닭, 까닭


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="게시처 깊은 판만 따로 돕니다")
    ap.add_argument("--only", default="forum,ransom", help="forum · ransom 중 쉼표로")
    ap.add_argument("--apply", action="store_true", help="노션에 씁니다. 없으면 미리보기")
    ap.add_argument("--limit", type=int, default=0, help="갈래마다 최대 몇 줄. 0 은 전부")
    ap.add_argument("--잡제한분", type=int, default=0, help="괜찮나를 볼 잡 제한(분). 0 이면 안 본다")
    a = ap.parse_args(argv)

    tor = (os.environ.get("TOR_SOCKS_PROXY") or "").strip()
    if not tor:
        print("  TOR_SOCKS_PROXY 가 없습니다. 깊은 판은 Tor 없이 안 돕니다")
        return 1
    갈래들 = [g.strip() for g in a.only.split(",") if g.strip() in ("forum", "ransom")]
    print("  깊은 판만 — " + ("씁니다" if a.apply else "미리보기입니다. --apply 를 주면 씁니다"), flush=True)
    결과 = []
    for g in 갈래들:
        r = 한갈래(g, apply=a.apply, tor=tor, limit=a.limit)
        결과.append(r)
        print(요약(r), flush=True)
    if a.잡제한분:
        좋다, 까닭 = 괜찮나(결과, 잡제한분=a.잡제한분)
        print("  예약에 넣어도 되나: " + ("예" if 좋다 else "아니오 — " + " · ".join(까닭)))
    return 0 if all(not r.읽기오류 for r in 결과) else 1


if __name__ == "__main__":
    sys.path[:0] = ["packages", "."]
    raise SystemExit(main())
