"""디코 아침 브리핑 — 지난 하루 수집 DB 에 새로 들어온 사건을 웹후크로 한 번 올린다 (2026-10-01 · 꼴 10/02).

    python skills/collect/brief.py                    미리보기. 문안을 화면에 낸다 — **이 PC 에서만 쓴다(조직명이 나온다)**
    python skills/collect/brief.py --요약만            공개 로그용. 건수만 낸다
    python skills/collect/brief.py --확인              웹후크가 브리핑 채널을 가리키는지 본다(글은 안 올라감)
    python skills/collect/brief.py --보낸다            확인이 맞을 때만 한 번 보낸다

## 무엇을 싣나 — 최현서 10/02

수집 DB 에서 **지난 24시간 안에 만든 줄**을 한 줄에 하나씩 「LEAK-번호 · 조직명 · 행위자 · 한국 여부」 로 싣는다.

    조직명     「대상 조직」 칸 그대로. 브리핑 채널은 팀원만 본다(9/22 「디코에는 기업명이 나가도 된다」).
               지도 · 레포에는 여전히 안 낸다. **개인 이름으로 보이는 값은 가린다.** 이미 * 로 가린 값은 그대로 둔다
    행위자     게시자 핸들, 없으면 게시처(랜섬 그룹 · 포럼). 가해 쪽 이름만 — 알림을 전한 텔레그램 채널은 안 싣는다
    한국 여부  「한국 관련」 이 직접 · 간접일 때만 「한국 직접」 · 「한국 간접」. 미확인이면 칸째 뺀다

검토 상태는 안 싣는다(새로 들어온 줄은 늘 미검토). 사건 X 는 목록에서 뺀다. 디스코드 한 메시지 상한(2000자) 안에
들도록 앞쪽 줄만 싣고 「그 밖 N건은 대시보드에서」 로 줄인다. 디스코드 서식 글자(* _ ~ ` | >)는 무력화한다.

## 웹후크는 먼저 확인한다

9/22 에 받은 옛 웹후크는 브리핑 채널이 아니라 「알림」 채널을 가리켰다. 그래서 **보내기 전에 웹후크 주소를 GET 한다.**
디스코드는 웹후크 정보(channel_id 포함)를 돌려주고 글은 안 올라간다. 브리핑 채널과 다르면 보내지 않고 실패로 끝낸다.
우리 봇은 브리핑 채널을 못 본다(403). 그래서 웹후크로만 보낸다.

## 왜 skills/collect 에 두나

`hub/` 는 조사 대상에 요청을 보내지 못하게 지킨다(test_직접호출금지). 디스코드 웹후크는 조사 대상이 아니라 우리 채널이라
그 지킴과 상관이 없지만, 예외를 늘리지 않으려고 디스코드로 보내는 다른 도구(`notify.py`) 옆에 둔다.

## 값 · 문안은 로그에 찍지 않는다

웹후크 주소는 환경변수 `DISCORD_WEBHOOK`(Actions 비밀값) 또는 `~/.config/darkchoco/discord_webhook` 에서 읽는다.
**레포가 공개라 Actions 로그를 누구나 본다.** 로그에는 건수와 「맞음 / 틀림」 만 찍는다(`--요약만`). 보내기가 실패해도
상태 코드나 예외 이름만 찍고 보낸 내용은 안 찍는다. 보낼 때 멘션을 끈다(allowed_mentions).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
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
가림말 = "(개인 이름으로 보여 가림)"

# 핸들 자리에 적힌 「없음」 표시. hub/events/publisher.py 의 자리표시와 같다
자리표시 = frozenset({"-", "--", "?", "n/a", "na", "none", "null", "unknown", "없음", "미상", "해당 없음"})

# 조직으로 읽히는 말. 이 말이 있으면 사람 이름으로 안 본다. **모르면 가리는 쪽**이라 넓게 잡는다
_조직말 = re.compile(
    r"(?i)\b(inc|llc|llp|lp|ltd|ltda|limited|corp|corporation|co|company|companies|gmbh|kg|ohg|ag|se|sa|sas|sarl|srl|"
    r"spa|bv|nv|plc|pty|kk|oy|ab|as|aps|cv|group|holding|holdings|hospital|clinic|klinik|medical|medicine|health|"
    r"healthcare|dental|dentistry|pharmacy|pharma\w*|lab|labs|laboratory|laboratories|university|universidad|"
    r"universit\w+|college|school|schule|academy|institute|instituto|bank|banco|capital|finance|financial|insurance|"
    r"service|services|servicios|solutions|soluciones|systems|sistemas|tech|technology|technologies|technik|"
    r"software|data|digital|network|networks|industries|industry|industrial|manufacturing|foundation|stiftung|"
    r"association|verein|society|center|centre|centro|zentrum|partners|partner|law|legal|attorneys|lawyers|"
    r"rechtsanw\w+|logistics|logistik|transport\w*|shipping|freight|energy|power|electric|motors|automotive|auto|"
    r"international|global|worldwide|enterprises|enterprise|consulting|consultants|beratung|studio|agency|church|"
    r"city|county|state|department|ministry|government|council|municipality|gemeinde|club|hotel|hotels|restaurant|"
    r"store|stores|shop|market|supply|supplies|distribution|distributors|wholesale|retail|trading|construction|"
    r"builders|bau|engineering|architects|architekten|realty|properties|property|immobilien|estate|management|"
    r"media|press|publishing|verlag|marketing|design|security|science|sciences|research|biotech|bio|chemical|"
    r"chemicals|foods|food|farm|farms|agro|steel|metal|metals|plastics|textile|apparel|fashion|travel|tours|"
    r"airlines|air|marine|mining|oil|gas|water|telecom|communications|cpa|accounting|steuerberatung|praxis|pc|pa|"
    r"dds|md|psc)\b")
_한글조직말 = re.compile(
    r"(주식회사|\(주\)|㈜|유한|병원|의원|치과|한의원|약국|학교|대학|학원|회사|그룹|센터|협회|재단|은행|공사|공단|연구소|"
    r"연구원|법인|조합|상사|산업|전자|건설|무역|물산|교회|시청|구청|군청|보험|증권|카드|캐피탈|저축|신협|농협|수협|"
    r"몰|마트|스토어|쇼핑|미디어|방송|신문|엔터|테크|솔루션|시스템|네트웍스|소프트|코리아|월드|글로벌|인터내셔널)")
_사람토막 = re.compile(r"(?:Dr|Mr|Mrs|Ms|Prof)\.?|[A-Z][a-z]+(?:[-'][A-Z][a-z]+)*\.?|[A-Z]\.")
_서식 = re.compile(r"([\\*_~`|>])")


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


def 개인이름같나(값: str) -> bool:
    """대상 조직 칸 값이 개인 이름으로 보이나. **모르면 가리는 쪽이다.** 이미 * 로 가린 값은 그대로 둔다."""
    s = (값 or "").strip()
    if not s or "*" in s:
        return False
    if "@" in s:
        return True                                     # 메일 주소
    if re.search(r"\d", s) or re.search(r"[A-Za-z0-9-]\.[A-Za-z]{2,}\b", s):
        return False                                    # 숫자 · 도메인이 있으면 조직
    if re.fullmatch(r"[가-힣]{2,4}", s):
        return not _한글조직말.search(s)                  # 「홍길동」 꼴
    토막 = s.replace(",", " ").split()
    if 2 <= len(토막) <= 4 and not _조직말.search(s):
        return all(_사람토막.fullmatch(t) for t in 토막)  # 「John A. Smith」 꼴
    return False


def 무력화(s: str) -> str:
    """디스코드 서식 글자를 글자 그대로 보이게 한다. * 로 가린 이름이 굵은 글씨가 되지 않게."""
    return _서식.sub(r"\\\1", s)


def 행위자(p: dict) -> str:
    """게시자 핸들, 없으면 게시처. 텔레그램 주소 꼴은 알림을 전한 채널이라 안 싣는다."""
    for 칸 in ("게시자 핸들", "게시처"):
        v = 글자(p, 칸)
        낮춤 = v.lower()
        if not v or 낮춤 in 자리표시 or "t.me/" in 낮춤 or "telegram.me/" in 낮춤:
            continue
        return v
    return ""


def 한줄(p: dict) -> tuple[str, bool]:
    """(목록 한 줄, 개인 이름이라 가렸나)."""
    조직 = 글자(p, "대상 조직")
    가림 = 개인이름같나(조직)
    칸 = [글자(p, "사건 ID") or "번호 없음",
         가림말 if 가림 else 무력화(조직 or "조직명 빈칸"),
         무력화(행위자(p) or "행위자 모름")]
    한국 = 글자(p, "한국 관련")
    if 한국 in ("직접", "간접"):
        칸.append(f"한국 {한국}")
    return "· " + " · ".join(칸), 가림


def 문안(줄들: list[dict], 지금: datetime) -> tuple[str, dict]:
    """(디스코드에 올릴 글, 건수). 한 줄에 「LEAK-번호 · 조직명 · 행위자 · 한국 여부」. 건수에는 이름이 없다."""
    X = sum(1 for p in 줄들 if 글자(p, "검토 여부") == "사건 X")
    목록 = [p for p in 줄들 if 글자(p, "검토 여부") != "사건 X"]
    머리 = (f"**다크초코 아침 브리핑** · {지금.astimezone(KST):%m/%d %H:%M} KST 기준 · "
          f"지난 24시간 새로 들어온 사건 {len(목록)}건" + (f" (한국과 무관한 {X}건은 뺐습니다)" if X else ""))
    셈 = {"새 줄": len(줄들), "사건 X": X, "목록": len(목록), "실린 줄": 0, "가린 줄": 0}
    if not 목록:
        return 머리 + "\n새로 들어온 사건이 없습니다.", 셈
    줄글 = []
    for p in 목록:
        글, 가림 = 한줄(p)
        줄글.append(글)
        셈["가린 줄"] += int(가림)
    본문 = 머리 + "\n"
    for i, 줄 in enumerate(줄글):
        남은 = len(줄글) - i
        꼬리 = f"그 밖 {남은 - 1}건은 대시보드에서" if 남은 > 1 else ""
        if len(본문) + len(줄) + 1 + len(꼬리) > 상한:
            본문 += f"그 밖 {남은}건은 대시보드에서\n"
            break
        본문 += 줄 + "\n"
        셈["실린 줄"] += 1
    return 본문.rstrip("\n"), 셈


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
    except Exception as e:  # noqa: BLE001  예외 글에 주소가 섞일 수 있어 이름만 찍는다
        print(f"웹후크 확인 실패: {type(e).__name__}")
        return False
    맞음 = str(정보.get("channel_id") or "") == 브리핑채널
    print("웹후크 채널 확인: " + ("맞음" if 맞음 else "틀림"))
    return 맞음


def 보내기(주소: str, 글: str, opener=None) -> bool:
    """한 번 보낸다. **실패해도 보낸 내용과 디스코드가 돌려준 본문은 안 찍는다** — 상태 코드와 예외 이름만."""
    몸 = {"content": 글, "allowed_mentions": {"parse": []}}
    req = urllib.request.Request(주소, method="POST", data=json.dumps(몸).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "User-Agent": "darkchoco-brief"})
    try:
        with _열기(req, opener) as r:
            ok = 200 <= getattr(r, "status", 204) < 300
    except urllib.error.HTTPError as e:
        print(f"보내기 실패: HTTP {e.code}")
        return False
    except Exception as e:  # noqa: BLE001  예외 글에 보낸 내용이 섞일 수 있어 이름만 찍는다
        print(f"보내기 실패: {type(e).__name__}")
        return False
    print(f"보냄 · {len(글)}자" if ok else "보내기 실패")
    return ok


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="디코 아침 브리핑")
    ap.add_argument("--요약만", action="store_true", help="건수만 낸다. 공개 로그에서 쓴다")
    ap.add_argument("--확인", action="store_true", help="웹후크가 브리핑 채널을 가리키는지 본다. 틀리면 실패")
    ap.add_argument("--보낸다", action="store_true", help="확인이 맞을 때만 한 번 보낸다")
    a = ap.parse_args(argv)

    지금 = datetime.now(KST)
    줄들 = 새줄들(Notion(verbose=False), 지금)
    글, 셈 = 문안(줄들, 지금)
    if a.요약만:
        print("%s · 문안 %d자" % (" · ".join(f"{k} {v}" for k, v in 셈.items()), len(글)))
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
