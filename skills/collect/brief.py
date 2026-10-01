"""디코 아침 브리핑 — 지난 하루 수집 DB 에 새로 들어온 사건을 웹후크로 한 번 올린다 (2026-10-01).

    python skills/collect/brief.py                    미리보기. 문안을 화면에 낸다 — 이 PC 에서만 쓴다
    python skills/collect/brief.py --요약만            공개 로그용. 건수만 낸다
    python skills/collect/brief.py --확인              웹후크가 브리핑 채널을 가리키는지 본다(글은 안 올라감)
    python skills/collect/brief.py --보낸다            확인이 맞을 때만 한 번 보낸다
    python skills/collect/brief.py --꼴 집계           대안 꼴. 줄마다 적지 않고 차 있는 칸으로 묶어 센다

## 무엇을 싣나

수집 DB 에서 **지난 24시간 안에 만든 줄**이다. 줄마다 사건 ID · 산업 분야 · 국가 · 주장 규모만 싣는다.
**조직명 · 자료 제목 · 게시자 핸들 · 주소는 안 싣는다.** 사건 X(한국과 무관)는 건수에만 넣고 목록에서 뺀다.
디스코드 한 메시지 상한(2000자) 안에 들도록 목록을 자르고 「외 N건」 을 붙인다.

## 웹후크는 먼저 확인한다

9/22 에 받은 옛 웹후크는 브리핑 채널이 아니라 「알림」 채널을 가리켰다. 그래서 **보내기 전에 웹후크 주소를 GET 한다.**
디스코드는 웹후크 정보(channel_id 포함)를 돌려주고 글은 안 올라간다. 브리핑 채널과 다르면 보내지 않고 실패로 끝낸다.
우리 봇은 브리핑 채널을 못 본다(403). 그래서 웹후크로만 보낸다.

## 왜 skills/collect 에 두나

`hub/` 는 조사 대상에 요청을 보내지 못하게 지킨다(test_직접호출금지). 디스코드 웹후크는 조사 대상이 아니라 우리 채널이라
그 지킴과 상관이 없지만, 예외를 늘리지 않으려고 디스코드로 보내는 다른 도구(`notify.py`) 옆에 둔다.

## 값은 어디에도 찍지 않는다

웹후크 주소는 환경변수 `DISCORD_WEBHOOK`(Actions 비밀값) 또는 `~/.config/darkchoco/discord_webhook` 에서 읽는다.
**레포가 공개라 Actions 로그를 누구나 본다.** 로그에는 건수와 「맞음 / 틀림」 만 찍는다(`--요약만`).
보낼 때 멘션을 끈다(allowed_mentions). 노션 칸 글에 `@everyone` 이 있어도 아무도 안 불린다.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages"))
sys.path.insert(0, str(ROOT))

from dc_notion import Notion  # noqa: E402

수집DS = "5160ce53-7ce2-4271-879e-06f3ad9957cf"
브리핑채널 = "1554544235011776565"
KST = timezone(timedelta(hours=9))
상한 = 1900                    # 디스코드 한 메시지 2000자. 여유를 둔다
TIMEOUT = 15
웹후크파일 = Path.home() / ".config" / "darkchoco" / "discord_webhook"


def 글자(p: dict, 칸: str) -> str:
    v = (p.get("properties") or {}).get(칸) or {}
    t = v.get("type")
    if t in ("title", "rich_text"):
        return "".join(x.get("plain_text", "") for x in v.get(t) or []).strip()
    if t in ("select", "status"):
        return ((v.get(t) or {}).get("name") or "").strip()
    if t == "multi_select":
        return " · ".join(o.get("name", "") for o in v.get(t) or [])
    if t == "unique_id":
        u = v.get("unique_id") or {}
        return f"{u.get('prefix') or ''}-{u.get('number')}" if u.get("number") is not None else ""
    return ""


def 새줄들(n: Notion, 지금: datetime, 시간: int = 24) -> list[dict]:
    """지난 `시간` 안에 만든 수집 DB 줄. 만든 때 오래된 것부터."""
    부터 = (지금 - timedelta(hours=시간)).astimezone(timezone.utc).isoformat(timespec="seconds")
    out, cursor = [], None
    while True:
        body = {"page_size": 100,
                "filter": {"timestamp": "created_time", "created_time": {"on_or_after": 부터}},
                "sorts": [{"timestamp": "created_time", "direction": "ascending"}]}
        if cursor:
            body["start_cursor"] = cursor
        res = n.request("POST", f"/data_sources/{수집DS}/query", body) or {}
        out.extend(res.get("results") or [])
        if not res.get("has_more"):
            return out
        cursor = res.get("next_cursor")


def 문안(줄들: list[dict], 지금: datetime) -> tuple[str, dict]:
    """(디스코드에 올릴 글, 건수). **조직명 · 제목 · 핸들 · 주소는 안 싣는다.**"""
    셈 = Counter(글자(p, "검토 여부") or "빈칸" for p in 줄들)
    목록 = [p for p in 줄들 if 글자(p, "검토 여부") != "사건 X"]
    머리 = (f"**다크초코 아침 브리핑** · {지금.astimezone(KST):%m/%d %H:%M} KST 기준 · 지난 24시간\n"
          f"새로 들어온 사건 {len(줄들)}건 — "
          + " · ".join(f"{k} {v}" for k, v in sorted(셈.items(), key=lambda kv: (-kv[1], kv[0]))))
    if not 줄들:
        return 머리 + "\n새로 들어온 사건이 없습니다.", dict(셈)
    꼬리말 = "\n(사건 X 는 목록에서 뺐습니다. 조직명은 대시보드에서 봅니다)"
    줄글 = []
    for p in 목록:
        칸 = [글자(p, "사건 ID") or "번호 없음", 글자(p, "산업 분야") or "업종 —",
             글자(p, "국가") or "국가 —", (글자(p, "주장 규모") or "규모 —")[:40]]
        줄글.append("· " + " · ".join(칸))
    본문 = 머리 + "\n"
    실린 = 0
    for i, 줄 in enumerate(줄글):
        남은 = len(줄글) - i
        뒤 = f"\n외 {남은 - 1}건" if 남은 > 1 else ""
        if len(본문) + len(줄) + 1 + len(뒤) + len(꼬리말) > 상한:
            본문 += f"외 {남은}건\n"
            break
        본문 += 줄 + "\n"
        실린 += 1
    return 본문.rstrip("\n") + 꼬리말, dict(셈) | {"목록": len(줄글), "실린 줄": 실린}


def 번호범위(번호들: list[str]) -> str:
    """LEAK-344 ~ LEAK-370 (27건) 꼴. 번호를 못 읽으면 앞의 몇 개만."""
    수 = sorted(int(x.split("-")[-1]) for x in 번호들 if x.split("-")[-1].isdigit())
    if not 수:
        return "—"
    머리 = 번호들[0].rsplit("-", 1)[0] if "-" in 번호들[0] else "LEAK"
    if len(수) == 1:
        return f"{머리}-{수[0]}"
    빈 = (수[-1] - 수[0] + 1) - len(수)
    return f"{머리}-{수[0]} ~ {머리}-{수[-1]}" + (f" 사이 {len(수)}건(빈 번호 {빈})" if 빈 else f" ({len(수)}건)")


def 집계문안(줄들: list[dict], 지금: datetime, 위: int = 5) -> tuple[str, dict]:
    """대안 꼴. 줄마다 적지 않고 차 있는 칸으로 묶어 센다. 게시처는 가해 쪽(랜섬 그룹 · 포럼) 이름이다."""
    셈 = Counter(글자(p, "검토 여부") or "빈칸" for p in 줄들)
    머리 = (f"**다크초코 아침 브리핑** · {지금.astimezone(KST):%m/%d %H:%M} KST 기준 · 지난 24시간\n"
          f"새로 들어온 사건 {len(줄들)}건 — "
          + " · ".join(f"{k} {v}" for k, v in sorted(셈.items(), key=lambda kv: (-kv[1], kv[0]))))
    if not 줄들:
        return 머리 + "\n새로 들어온 사건이 없습니다.", dict(셈)

    def 줄(이름, c: Counter) -> str:
        항목 = c.most_common()
        글 = " · ".join(f"{k} {v}" for k, v in 항목[:위])
        return f"{이름}  {글}" + (f" · 그 밖 {sum(v for _, v in 항목[위:])}" if len(항목) > 위 else "")

    찬 = sum(1 for p in 줄들 if 글자(p, "산업 분야") or 글자(p, "국가") or 글자(p, "주장 규모"))
    글 = "\n".join([
        머리,
        "사건 번호  " + 번호범위([글자(p, "사건 ID") for p in 줄들 if 글자(p, "사건 ID")]),
        줄("한국 관련", Counter(글자(p, "한국 관련") or "빈칸" for p in 줄들)),
        줄("들어온 길", Counter(글자(p, "소스") or "빈칸" for p in 줄들)),
        줄("게시처", Counter(글자(p, "게시처") or "빈칸" for p in 줄들)),
        f"업종 · 국가 · 규모가 찬 줄  {찬} / {len(줄들)}",
        "(조직명은 대시보드에서 봅니다)",
    ])
    return 글[:상한], dict(셈)


def 웹후크() -> str:
    v = (os.environ.get("DISCORD_WEBHOOK") or "").strip()
    if not v and 웹후크파일.exists():
        v = 웹후크파일.read_text(encoding="utf-8").strip()
    if not v:
        raise SystemExit("웹후크가 없습니다(DISCORD_WEBHOOK 또는 ~/.config/darkchoco/discord_webhook)")
    if not v.startswith(("https://discord.com/api/webhooks/", "https://discordapp.com/api/webhooks/")):
        raise SystemExit("웹후크 꼴이 아닙니다(주소는 찍지 않습니다)")
    return v


def _열기(req, opener=None):
    return (opener or urllib.request.urlopen)(req, timeout=TIMEOUT)


def 채널확인(주소: str, opener=None) -> bool:
    """웹후크가 브리핑 채널을 가리키나. GET 이라 글은 안 올라간다. **주소 · 채널 번호를 찍지 않는다.**"""
    req = urllib.request.Request(주소, method="GET", headers={"User-Agent": "darkchoco-brief"})
    try:
        with _열기(req, opener) as r:
            정보 = json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        print(f"웹후크 확인 실패: HTTP {e.code}")
        return False
    except (urllib.error.URLError, OSError, ValueError) as e:
        print(f"웹후크 확인 실패: {type(e).__name__}")
        return False
    맞음 = str(정보.get("channel_id") or "") == 브리핑채널
    print("웹후크 채널 확인: " + ("맞음" if 맞음 else "틀림"))
    return 맞음


def 보내기(주소: str, 글: str, opener=None) -> bool:
    몸 = {"content": 글, "allowed_mentions": {"parse": []}}
    req = urllib.request.Request(주소, method="POST", data=json.dumps(몸).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "User-Agent": "darkchoco-brief"})
    try:
        with _열기(req, opener) as r:
            ok = 200 <= getattr(r, "status", 204) < 300
    except urllib.error.HTTPError as e:
        print(f"보내기 실패: HTTP {e.code}")
        return False
    except (urllib.error.URLError, OSError) as e:
        print(f"보내기 실패: {type(e).__name__}")
        return False
    print(f"보냄 · {len(글)}자" if ok else "보내기 실패")
    return ok


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="디코 아침 브리핑")
    ap.add_argument("--요약만", action="store_true", help="건수만 낸다. 공개 로그에서 쓴다")
    ap.add_argument("--확인", action="store_true", help="웹후크가 브리핑 채널을 가리키는지 본다. 틀리면 실패")
    ap.add_argument("--보낸다", action="store_true", help="확인이 맞을 때만 한 번 보낸다")
    ap.add_argument("--꼴", choices=("목록", "집계"), default="목록",
                    help="목록: 줄마다 번호 · 업종 · 국가 · 규모(기본안). 집계: 차 있는 칸으로 묶어 센다(대안)")
    a = ap.parse_args(argv)

    지금 = datetime.now(KST)
    줄들 = 새줄들(Notion(verbose=False), 지금)
    글, 셈 = (집계문안 if a.꼴 == "집계" else 문안)(줄들, 지금)
    if a.요약만:
        print("새로 들어온 줄 %d · %s · 문안 %d자" % (
            len(줄들), " · ".join(f"{k} {v}" for k, v in 셈.items()), len(글)))
    else:
        print(글)
    if not (a.확인 or a.보낸다):
        return 0
    주소 = 웹후크()
    if not 채널확인(주소):
        print("브리핑 채널이 아니어서 보내지 않습니다")
        return 1
    if a.보낸다:
        return 0 if 보내기(주소, 글) else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
