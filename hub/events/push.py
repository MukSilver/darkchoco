"""사건 수집 표(items)를 노션 수집 DB 로 올립니다.

    python hub/events/push.py                  미리보기. 노션에 안 씁니다
    python hub/events/push.py --kr             한국 건만
    python hub/events/push.py --limit 20 --apply   스무 줄만 실제로 씁니다
    python hub/events/push.py --db ~/data/darkchoco.db --kr   다른 표(최현서 랜섬 표)를 읽습니다

**여기까지가 끊겨 있었습니다.** 어댑터가 받아 온 것이 SQLite 에서 끝나고
사람 눈까지 안 갔습니다. 기사에 쓰려면 그것을 봐야 하는데 지금은
SQLite 를 직접 열어야만 보였습니다.

## 무엇을 올리나

**대상 조직이 있는 줄만 올립니다.** 수집 DB 는 유출 사건 하나가 한 줄인데,
items 표에는 채널 공지와 광고도 같이 들어 있습니다. 피해자가 없으면
사건이 아닙니다. 표에는 그대로 두고 노션에만 안 올립니다.

## 안 보내는 것

items 29칸 중 열일곱만 보냅니다. **본문은 안 보냅니다.**

    body    411줄 (91%)   게시글 본문
    raw     448줄          원본 응답. 「발견일」 과 「규모 출처」 두 키만 꺼내 씁니다
    clues   448줄

수집 DB 에 본문 칸이 아예 없습니다. 그 설계를 그대로 따릅니다.
CLAUDE.md 의 「나가는 것은 필드명, 패턴, 건수뿐이다」와도 맞습니다.

## 자동으로 올라간 줄은 「미검토」 입니다

2026-09-06 부터 수집 DB 에 「검토 여부」 칸이 있습니다. 여기서 올린 줄은 전부
미검토이고 수집자는 「자동」 입니다. 지도 · 통계 · 검증 큐는 미검토 줄을 안 봅니다.
사람이 노션에서 사건 O / X 를 고르면 그때 사건이 됩니다.

같이 올리는 칸 여덟: 검토 여부 · 수집자 · 소스 · UID · 주장 규모 · 규모 출처 ·
발견일 · 한국 관련(+근거).

**게시처(+명부 없음)도 같이 씁니다** (2026-09-25). 명부 셋으로 맞추고 규칙은
`hub/events/publisher.py` 에 있습니다. 명부를 못 읽으면 그 칸만 비우고 줄은 올립니다.

**판 끝에 행위자 DB 도 채웁니다** (2026-09-25). 수집 DB 전체를 훑어 행위자 DB · 명부 셋 어디에도
없는 판매 · 공개 핸들을 올립니다. 올릴 줄이 없는 판에도 돕니다. 규칙은 `hub/events/actor.py` 에
있고, 실패해도 수집은 그대로입니다.

**빈 규모는 「없음」 이 아니라 모르는 것입니다.** 칸을 아예 안 보냅니다. `-` 나 `n/a` 처럼
없다는 표시로 온 것도 같이 봅니다. 발견일은 UTC 를 KST 로 옮긴 뒤에 자릅니다.

## 겹치는 것을 어떻게 거르나

**UID 가 먼저입니다.** items.uid 가 노션 UID 칸에 있으면 같은 글입니다.
UID 가 없는 옛 줄은 원문 URL 로, URL 도 없으면 자료 제목과 게시 플랫폼을 묶어 봅니다.
**사람이 쓴 줄을 안 덮습니다.** 새로 만들기만 하고 있는 줄은 건드리지 않습니다.
사람이 「사건 X」 로 닫은 줄도 UID 가 막아 다시 안 들어옵니다.

**텔레그램 줄의 원문 URL 은 그 글을 전한 메시지 주소입니다** (2026-09-28). 수집 표의
post_url(원래 링크)은 그대로 두고 올릴 때만 바꿉니다. 까닭은 `_원문()` 에 있습니다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages"))
sys.path.insert(0, str(ROOT))

from dc_kr import KrClassifier, normalize_country  # noqa: E402
from dc_notion import Notion  # noqa: E402
from hub.events import actor, publisher  # noqa: E402

_clf: KrClassifier | None = None


def _분류기(확인된조직: list[str] | None = None) -> KrClassifier:
    """처음 부를 때만 만듭니다. 키워드 파일을 읽는 값이 있습니다.

    문턱을 `review` 로 둡니다. 알림은 `likely` 위만 보내지만 여기는 노션에 올리는
    자리라, 사람이 봐야 할 것도 목록에 올려 놓고 검토에서 가르는 편이 낫습니다.

    **`확인된조직` 을 주면 새로 만듭니다** (2026-09-23). 수집 DB 에서 사람이 사건 O 로
    확정한 한국 조직 이름입니다. 판정기의 기업 목록은 대기업 백여 곳뿐이라, 한 번 털린
    중소 사이트가 다시 팔리는 글을 못 알아봤습니다. 이름은 노션에서 그때그때 읽고
    **레포에 적지 않습니다.** 레포가 공개라 피해 조직 목록이 파일로 남습니다.
    """
    global _clf
    if 확인된조직 is not None:
        _clf = KrClassifier({"min_tier_to_report": "review",
                             "extra_keywords": 확인된조직})
    elif _clf is None:
        _clf = KrClassifier({"min_tier_to_report": "review"})
    return _clf


# 판정기에 더하면 안 되는 이름. 짧거나 흔한 낱말은 남의 글에도 걸립니다
_흔한이름 = {"korea", "korean", "seoul", "test", "shop", "mall", "bank", "news", "data"}


def 확인된_조직들(노션줄들: list[dict]) -> list[str]:
    """수집 DB 에서 사건 O 인 줄의 대상 조직 이름. **네 글자 미만과 흔한 낱말은 뺍니다.**"""
    out = set()
    for r in 노션줄들:
        p = r.get("properties") or {}
        if ((p.get("검토 여부") or {}).get("select") or {}).get("name") != "사건 O":
            continue
        v = "".join(x.get("plain_text", "")
                    for x in ((p.get("대상 조직") or {}).get("rich_text") or [])).strip().lower()
        if len(v) >= 4 and v not in _흔한이름 and not v.isdigit():
            out.add(v)
    return sorted(out)

# 수집 DB 의 data_source id. **`NOTION_COLLECT_DB` 가 있으면 그것을 쓴다** (2026-09-29).
#
# 전에는 이 파일 · 대시보드 `apps/dash/dbs.json` · `deploy/worker.js` 세 곳에 손으로 적혀, 한쪽이 바뀌면
# 다른 쪽이 조용히 틀렸다. 이제 worker.js 는 dbs.json 을 읽고, 이 기본값은 dbs.json 「수집」 과 같아야 한다
# (시험 `test_수집DB_기본값은_대시보드_레지스트리와_같다`). 환경변수는 다른 워크스페이스에서 코드를 안 고치고
# 돌리려는 것이다. id 는 비밀이 아니다. **data_source id 를 넣는다** — 노션 주소의 id 는 database id 라 다르다.
_수집DB_기본 = "5160ce53-7ce2-4271-879e-06f3ad9957cf"
_노션id = re.compile(r"[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}", re.I)


def 수집DB_읽기(환경=None) -> str:
    """`NOTION_COLLECT_DB` 를 읽어 하이픈 꼴 id 로. 비었으면 기본값. **id 꼴이 아니면 멈춘다** —
    이름이나 주소를 조용히 받으면 엉뚱한 DB 에 쓸 수 있다."""
    값 = ((환경 if 환경 is not None else os.environ).get("NOTION_COLLECT_DB") or "").strip()
    if not 값:
        return _수집DB_기본
    if not _노션id.fullmatch(값):
        raise SystemExit("NOTION_COLLECT_DB 에 수집 DB 의 data_source id 를 넣는다(32자리 16진수, 하이픈은 있어도 된다). "
                         "비우면 기본값을 쓴다")
    h = 값.replace("-", "").lower()
    return "%s-%s-%s-%s-%s" % (h[:8], h[8:12], h[12:16], h[16:20], h[20:])


수집DB = 수집DB_읽기()
기본표 = ROOT / "hub" / "data" / "darkchoco.db"

# **items 의 country 가 ISO 두 글자라고 가정하면 안 됩니다.** 랜섬웨어 집계처는
# 두 글자로 주지만 CTI 텔레그램 채널은 `Korea` 처럼 이름으로 줍니다. 그래서 찾기
# 전에 `normalize_country` 로 맞춥니다. 노션 선택지는 한글 이름이라 그대로 보내면
# 3번 관문에서 버려집니다. 선택지에 있는 것만 옮깁니다.
나라 = {
    "KR": "한국", "US": "미국", "JP": "일본", "CN": "중국", "RU": "러시아",
    "TR": "터키", "IN": "인도", "BR": "브라질", "GB": "영국", "DE": "독일",
    "FR": "프랑스", "VN": "베트남", "ID": "인도네시아", "TW": "대만",
}

# items 의 kind 는 지금 「유출 게시」 하나뿐이라 노션 선택지와 안 맞습니다.
# venue_kind 가 실제로 갈리는 값이라 그것을 씁니다.
게시성격 = {
    "dls": "랜섬웨어 유출",
    "telegram": "확인 못 함",     # 채널 글은 무엇인지 사람이 봐야 갈립니다
    "forum": "확인 못 함",
    "x": "확인 못 함",            # X 집계 계정 글도 같습니다 (2026-09-26)
}
# 최현서 표의 kind 는 노션 선택지 글자 그대로 들어 있습니다 (랜섬웨어 유출 · 확인 못 함).
# 그 글자가 선택지에 있으면 그것을 쓰고, 비어 있으면 venue_kind 로 물러납니다.
게시성격_선택지 = {"랜섬웨어 유출", "DB 판매", "DB 무료 공개", "접근 권한 판매",
             "사기 의심", "기타", "확인 못 함"}

# items.source → 노션 「소스」. 어느 수집기가 가져왔나. [사건] 화면의 탭입니다.
# X 는 2026-09-26 에 더했습니다(최현서 결정, skills/collect/sources/x_jina.py). 노션 선택지는 이미 있었습니다.
소스 = {"ransom": "랜섬웨어", "ransomlive": "랜섬웨어",
      "telegram": "텔레그램", "forum": "포럼", "kit": "포럼", "x": "X"}

# **값이 아니라 「없다」는 표시입니다.** 집계처가 규모 칸에 이런 것을 넣어 보냅니다.
# skills/collect/sources/ransomlive.py 의 DASH 와 같게 봅니다. 그쪽은 세는 자리에만
# 있었고 올리는 자리에는 없어서, 대시뿐인 줄이 노션에 규모 `-` 로 들어갈 뻔했습니다.
DASH = {"-", "--", "---", "—", "–", "n/a", "N/A", "na", "unknown", "Unknown", "?"}

KST = timezone(timedelta(hours=9))

보낼칸 = 17


def _글(v: str) -> dict:
    return {"rich_text": [{"text": {"content": (v or "")[:2000]}}]}


def _날(v: str) -> dict | None:
    """노션 date 는 ISO 를 받습니다. 꼴이 아니면 안 보냅니다."""
    v = (v or "").strip()
    if not v:
        return None
    if len(v) >= 10 and v[4] == "-" and v[7] == "-":
        return {"date": {"start": v[:10] if len(v) == 10 else v}}
    return None


def _값(줄, 칸: str) -> str:
    """칸이 없는 표(옛 스키마)에서도 죽지 않게 읽습니다. 없거나 비면 빈 문자열입니다."""
    try:
        v = 줄[칸] if 칸 in 줄.keys() else None
    except Exception:  # noqa: BLE001
        v = None
    if v is None:
        return ""
    return v if isinstance(v, str) else str(v)


def _raw(raw: str) -> dict:
    """raw(원본 응답 JSON)를 dict 로. 깨졌거나 dict 가 아니면 빈 dict 입니다."""
    if not raw:
        return {}
    try:
        d = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return d if isinstance(d, dict) else {}


def _발견일(raw: str) -> dict | None:
    """집계처가 처음 본 날. 두 어댑터가 이름을 달리 붙여서 둘 다 봅니다.

        ransomlive.py (최현서 랜섬 표)    raw["발견일"]
        ransom_kr.py  (팀 hub 표)        raw["discovered"]

    **UTC 를 KST 로 옮긴 뒤에 자릅니다.** 집계처 시각은 UTC 인데 그냥 열 글자를 자르면
    15시 이후에 발견된 건이 하루 앞선 날로 박힙니다. 실측으로 기본표 315건 중 152건이
    그 구간이다. 게시일과의 차이가 게시 지연을 재는 유일한 신호라 하루가 어긋나면 못 쓴다.
    `collect/stats.py` 의 `_kst()` 와 같은 규칙을 쓴다. 두 도구가 다른 날을 말하면 안 된다.
    """
    d = _raw(raw)
    v = str(d.get("발견일") or d.get("discovered") or "").strip()
    if not v:
        return None
    if len(v) == 10:                      # 날짜만 온 것은 시간대를 따질 것이 없다
        return _날(v)
    try:
        t = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        return _날(v[:10])
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return _날(t.astimezone(KST).strftime("%Y-%m-%d"))


def _규모출처(raw: str, src: str | None) -> str:
    """규모를 어디서 봤나. **raw 에 적힌 것이 먼저입니다.**

    `ransomlive.py` 가 집계처 응답을 보고 raw["규모 출처"] 에 이미 적어 둡니다. 실측 두 건이
    집계처 API 에는 없고 웹 UI 와 원 출처에만 있었고, 이 칸은 바로 그 구분을 남기려고 만들었습니다.
    수집기 이름으로 되짚으면, 사람이 원 출처에서 본 규모를 넣었을 때 「집계처 API」 로 도장이 찍힙니다.
    어느 수집기인지도 모르면 출처를 모르는 것이므로 칸을 안 보냅니다.
    """
    적힘 = str(_raw(raw).get("규모 출처") or "").strip()
    if 적힘:
        return "집계처 API" if 적힘.startswith("집계처") else "원 출처"
    if not src:
        return ""
    return "집계처 API" if src == "랜섬웨어" else "원 출처"


class _판정재료:
    """`dc_kr` 이 보는 다섯 칸. **어느 칸을 넣을지가 소스마다 다릅니다.**

    판정기는 피해자 이름과 주소에서 걸리면 등급을 높게 주고, 설명문에서만 걸리면
    「사람이 봐야 함」(review) 으로 낮춥니다. 랜섬 줄은 피해자와 도메인이 차 있어
    높은 등급이 나오지만, 텔레그램·포럼 글은 그 칸이 비어 있고 글만 있어서
    **아무리 잘 걸려도 review 가 천장입니다.** 그래서 review 도 받습니다.
    """

    def __init__(self, 줄):
        본문 = (_값(줄, "title") + " " + _값(줄, "body"))[:4000]
        self.victim = _값(줄, "target_org")
        self.website = _값(줄, "target_domain") or _값(줄, "venue")
        self.description = 본문
        self.country = _값(줄, "country")
        self.sector = str(_raw(_값(줄, "raw")).get("산업 분야") or "")


집계처국가만 = "집계처 국가만 — 도메인·이름·한글 신호 없음"


def _한국관련(줄) -> tuple[str, str]:
    """(한국 관련, 근거). 판정은 `dc_kr` 한 곳에서 합니다.

    부품이 내는 등급 다섯을 노션 선택지 셋으로 접습니다.

        confirmed · strong · likely   →   직접
        review                        →   미확인.  **근거는 남깁니다**
        none                          →   미확인

    포럼 줄은 판정이 안 나와도 근거를 적습니다. 킷은 자동으로 안 돌고 사람이 골라
    돌린 글이라, 「신호가 없다」 가 「한국과 무관하다」 는 뜻이 아니기 때문입니다.
    """
    등급, _점수, 근거 = _분류기().classify(_판정재료(줄))
    if 등급 in ("confirmed", "strong", "likely"):
        # **집계처 국가 칸 하나로만 직접이 된 줄은 그렇게 적는다** (2026-09-29 최현서, 인계 H-5).
        # 「직접」 은 두고 근거 맨 앞에 붙인다. 도메인 · 이름 · 한글 신호가 하나도 없으면 사람이
        # 그것을 알고 보게 한다. 「제외어 … country=KR 이므로 유지」 는 신호가 아니라 안내라 안 센다
        신호 = [g for g in 근거 if not g.startswith("제외어 ")]
        if 신호 == ["소스 country=KR"]:
            근거 = [집계처국가만] + 근거
        return "직접", " · ".join(근거)[:2000]
    if 소스.get(_값(줄, "source").strip()) == "포럼":
        따로 = 근거 + ["사람이 고른 글. 대상 조직은 검토하면서 채운다"]
        return "미확인", " · ".join(따로)[:2000]
    return "미확인", " · ".join(근거)[:2000]


def 사건인가(줄) -> tuple[bool, str]:
    """노션에 올릴 자격이 있나. (올릴 것인가, 왜 올리나)

    **피해자가 없으면 사건이 아닙니다.** items 표에는 채널 공지와 광고도 같이 있습니다.
    다만 포럼은 다릅니다. 킷은 자동으로 안 돕니다 — 사람이 브라우저에서 글을 열고
    눌러야 돕니다. 그 줄은 이미 한 번 걸러진 글이고, 대상 조직이 빈 것은 피해자가
    없어서가 아니라 포럼 글에서는 회사 이름이 칸이 아니라 문장으로만 있어서입니다.
    텔레그램도 한국 신호가 있으면 올립니다. 아래 본문에 까닭이 있습니다.
    """
    소스이름 = 소스.get(_값(줄, "source").strip())
    if 소스이름 == "포럼":
        return True, "사람이 킷을 돌린 글"
    if _값(줄, "target_org").strip():
        return True, ""
    # **X 도 텔레그램과 같은 갈래입니다** (2026-09-26). 둘 다 집계하는 곳의 글이라 칸 이름 없이
    # 글로만 써서 대상 조직을 자주 못 읽습니다. 한국 신호가 있을 때만 미검토로 올립니다
    if 소스이름 not in ("텔레그램", "X"):
        return False, ""
    # **텔레그램은 대상 조직을 못 읽어도 한국 신호가 있으면 올립니다** (2026-09-23, 관문 「나」).
    #
    # 채널 글 대부분이 칸 이름 없이 글로만 써서 대상 조직을 못 읽습니다. 한 판 193건 중
    # 176건이 그랬고 전부 여기서 빠졌습니다. 버리지 않고 「미검토」 로 올려 대시보드에서
    # 사람이 O/X 를 찍게 합니다. 다만 **한국 신호가 없는 글까지 올리면 외국 판매 글과
    # 광고가 판마다 쏟아집니다.** 그래서 판정기가 review 이상을 낸 글만 올립니다.
    #
    # CVE 알림과 악성코드 시그니처는 유출 글이 아닙니다. 판정 전에 뺍니다.
    if _raw(_값(줄, "raw")).get("우리 대상") is False:
        return False, "유출 글이 아닙니다"
    등급, _점수, 근거 = _분류기().classify(_판정재료(줄))
    if 등급 != "none":
        return True, "대상 조직을 못 읽었지만 한국 신호가 있습니다: " + " · ".join(근거)
    return False, ""


def 외국인가(줄) -> bool:
    """`--kr` 이 뺄 줄. **명백히 외국인 것만 뺍니다.**

    전에는 country=='KR' 인 줄만 통과시켰습니다. 그러면 국가를 모르는 텔레그램·포럼은
    영원히 0줄입니다. 놓친 것은 눈에 안 보이고 섞인 것은 검토에서 걸러지므로,
    모르는 것은 올리고 사람이 사건 O / X 로 가릅니다.

    **한국인가를 두 번 묻습니다. 국가 칸과 판정기입니다.**

        국가 칸    `Korea` 도 `KR` 로 맞춰서 봅니다. 아는 이름만 바꾸므로
                   `Turkey` 같은 것은 그대로 외국입니다
        판정기     국가 칸이 틀려도 `.kr` 도메인이나 한국 기업명이 잡히면 남깁니다

    둘을 같이 보는 이유는 서로 다른 실패를 막기 때문입니다. 2026-09-18 에 CTI 채널
    유출 알림 12줄이 전부 이 자리에서 빠졌는데, 그중 한 줄은 국가 칸이 `Korea` 인
    한국 건이었고 판정기는 그것을 `한국 도메인(.kr)` 으로 이미 맞히고 있었습니다.
    맞히는 쪽이 있는데 못 맞히는 쪽이 앞에 서 있었습니다.

    **판정기가 「직접」 이라고 한 것만 남깁니다.** 「미확인」 까지 남기면 설명문에
    `korea` 가 한 번 나온 외국 건이 전부 들어옵니다. 같은 날 아르헨티나 건이
    그랬습니다.
    """
    c = normalize_country(_값(줄, "country"))
    if not c or c in ("KR", "UNKNOWN", "N/A", "-"):
        return False
    return _한국관련(줄)[0] != "직접"


def 게시처칸(표, 선택지: list[str], 줄) -> dict:
    """「게시처」 · 「명부 없음」 (2026-09-25). 규칙은 `publisher.py` 한 곳에 있습니다.

    전에는 이 칸을 9/22 에 한 번 채운 뒤로 아무도 안 써서, 그 뒤 들어온 45줄이 비어
    있었습니다. 명부를 못 읽었으면(`표` 가 None) 칸을 비워 둡니다.
    """
    if 표 is None:
        return {}
    return publisher.속성(표, 선택지, 소스.get(_값(줄, "source").strip()) or "",
                        _값(줄, "venue"), _값(줄, "actor"))


def 만들기(줄) -> dict:
    """items 한 줄을 노션 속성으로 옮깁니다. 빈 값은 아예 안 보냅니다.

    sqlite3.Row 를 받지만 r["칸"] 과 r.keys() 만 쓰므로 dict 도 됩니다 (시험용).
    """
    p: dict = {
        "자료 제목": {"title": [{"text": {"content": (줄["title"] or "제목 없음")[:2000]}}]},
        # 자동으로 올라온 줄입니다. 사람이 노션에서 사건 O / X 를 고르기 전에는
        # 지도 · 통계 · 검증 큐가 안 봅니다 (프젝 DEV.md 4-9).
        "수집자": {"select": {"name": "자동"}},
        "검토 여부": {"select": {"name": "미검토"}},
    }
    if 줄["target_org"]:
        p["대상 조직"] = _글(줄["target_org"])
    if 줄["actor"]:
        p["게시자 핸들"] = _글(줄["actor"])
    if 줄["venue"]:
        p["게시 플랫폼"] = _글(줄["venue"])
    원문 = _원문(줄)
    if 원문:
        p["원문 URL"] = _글(원문)

    d = _날(줄["posted_at"])
    if d:
        p["게시 시각"] = d
    d = _날(줄["first_seen"])
    if d:
        p["수집일"] = d

    이름 = 나라.get(normalize_country(줄["country"]))
    if 이름:
        p["국가"] = {"select": {"name": 이름}}

    kind = _값(줄, "kind").strip()
    성격 = kind if kind in 게시성격_선택지 else 게시성격.get(_값(줄, "venue_kind"))
    if 성격:
        p["게시 성격"] = {"select": {"name": 성격}}

    # ── 2026-09-06 에 더한 칸 ──
    src = 소스.get(_값(줄, "source").strip())
    if src:
        p["소스"] = {"select": {"name": src}}

    uid = _값(줄, "uid").strip()
    if uid:
        p["UID"] = _글(uid)

    규모 = _값(줄, "claimed_size").strip()
    if 규모 and 규모.strip() not in DASH:
        p["주장 규모"] = _글(규모)
        출처 = _규모출처(_값(줄, "raw"), src)
        if 출처:
            p["규모 출처"] = {"select": {"name": 출처}}

    발견 = _발견일(_값(줄, "raw"))
    if 발견:
        p["발견일"] = 발견

    관련, 근거 = _한국관련(줄)
    p["한국 관련"] = {"select": {"name": 관련}}
    if 근거:
        p["한국 관련 근거"] = _글(근거)

    return p


def _열쇠(url: str, 제목: str, 곳: str) -> str:
    """겹침을 보는 열쇠. URL 이 있으면 그것이 먼저입니다."""
    u = (url or "").strip()
    return u if u else "%s|%s" % ((제목 or "").strip(), (곳 or "").strip())


# 텔레그램 메시지 주소 꼴. `https://t.me/<채널>/<번호>` 만 받습니다
_메시지주소 = re.compile(r"https://t\.me/[A-Za-z0-9_]{3,64}/\d+")


def _원문(줄) -> str:
    """노션 「원문 URL」 에 넣을 값. **텔레그램 줄은 그 글을 전한 메시지 주소입니다** (2026-09-28).

    설계서 「텔레그램 재유포 사건의 채널 정하는 방법」 대로 텔레그램 소스 사건은 원래 게시처가
    따로 있어도 전한 채널의 사건입니다. 지도는 원문 URL 의 t.me 로 채널을 찾습니다. 원래 게시처는
    게시 플랫폼 칸에 남습니다. 2026-09-28 에 텔레그램 93줄 중 44줄이 원래 링크만 갖고 있어서
    어느 채널이 전했는지 알 수 없었습니다.

    **수집 표의 post_url 은 그대로 원래 링크입니다.** UID 재료(dc_store KEY)라서 수집기에서 바꾸면
    모든 텔레그램 글의 UID 가 바뀌고, 이미 올린 글(사람이 사건 X 로 닫은 줄 포함)이 새 줄로 또
    올라갑니다. 검증 도구도 post_url 을 「원 출처」 로 읽습니다. 그래서 노션에 올릴 때만 바꿉니다.

    메시지 주소는 수집기가 raw 「집계 채널 글 주소」 에 남깁니다(tg_post.py). 없으면 글 번호
    (`채널/번호`)로 만들고, 그것도 아니면 옛날처럼 원래 링크를 둡니다."""
    원래 = _값(줄, "post_url").strip()
    if _값(줄, "source").strip() != "telegram":
        return 원래
    주소 = str(_raw(_값(줄, "raw")).get("집계 채널 글 주소") or "").strip()
    if _메시지주소.fullmatch(주소):
        return 주소
    글번호 = _값(줄, "src_id").strip()
    if _글번호.fullmatch(글번호):
        return "https://t.me/" + 글번호
    return 원래


def _열쇠들(줄) -> tuple[str, str]:
    """(uid, 열쇠). uid 가 비면 첫 값은 빈 문자열입니다.

    **열쇠의 URL 은 노션에 올라가는 원문 URL 과 같아야 합니다.** 다음 판에는 노션에서 읽은
    원문 URL 로 열쇠를 만들어 견주기 때문입니다. 그래서 텔레그램 줄은 메시지 주소가 열쇠입니다.
    같은 링크를 붙인 서로 다른 메시지는 따로 올라갑니다 — 메시지 하나가 사건 하나입니다."""
    return _값(줄, "uid").strip(), _열쇠(_원문(줄), _값(줄, "title"), _값(줄, "venue"))


# 글 번호 꼴. 텔레그램 `채널/번호` 와 포럼 킷 `포럼/번호` 가 이렇습니다
_글번호 = re.compile(r"[A-Za-z0-9_.\-]+/\d+")


def _자취(줄) -> str:
    """줄을 로그에 남길 때 쓸 표시. **값이 아니라 표시입니다.**

    UID 와 글 번호뿐이라 개인정보 규칙에 안 걸립니다. 제목이나 본문은 안 넣습니다.

    **글 번호를 같이 넣는 이유가 있습니다.** UID 는 우리가 만든 해시라서, items
    표가 사라지면 그것만으로는 무엇이었는지 되짚을 길이 없습니다. CI 는 실행마다
    표를 지웁니다 (`collect.yml`). `breachdetect/1270060` 이면 채널과 글이 그대로
    남아 90일치 실행 로그에서 원문을 다시 볼 수 있습니다.

    **글 번호 꼴일 때만 붙입니다** (2026-09-26). 랜섬 줄의 src_id 는 `그룹|피해 조직`
    이고, 포럼 킷은 글 번호를 못 뽑으면 주소를 통째로 씁니다. 둘 다 붙이면 피해 조직
    이름이 Actions 로그에 그대로 나갑니다.
    """
    uid = _값(줄, "uid").strip() or "uid없음"
    src = _값(줄, "src_id").strip()
    return "%s %s" % (uid, src) if _글번호.fullmatch(src) else uid


def _가린오류(e: Exception, 줄) -> str:
    """못 올린 까닭. **노션이 받은 값을 되읊으면 제목과 대상 조직을 가립니다.**

    노션 검증 오류는 `instead was ...` 처럼 보낸 값을 돌려줄 때가 있습니다. 칸 이름과
    까닭은 있어야 고치므로 오류를 통째로 버리지 않고 값만 가립니다. 자르기 전에
    가립니다. 자른 뒤에 가리면 잘린 이름 조각이 남습니다.
    """
    m = str(e)
    for v in sorted({_값(줄, "title").strip(), _값(줄, "target_org").strip()},
                    key=len, reverse=True):
        if v:
            m = m.replace(v, "(가림)")
    return m[:120]


def _뺀줄찍기(뺀: list, 한줄에: int = 3) -> None:
    """뺀 줄의 자취를 찍습니다. 세 개씩 끊어 로그가 옆으로 안 흐르게 합니다.

    2026-09-13~18 에 무엇이 버려졌는지 어디에도 안 남았습니다. 건수만 찍었고
    표는 CI 가 지웠기 때문입니다. 그 엿새를 되짚을 수 없어서 이 자리를 뒀습니다.
    """
    for i in range(0, len(뺀), 한줄에):
        print("      " + " · ".join(뺀[i:i + 한줄에]))


def _겹치나(줄, 본uid: set[str], 본열쇠: set[str]) -> bool:
    """uid 나 열쇠 어느 하나라도 본 것이면 겹칩니다. uid 가 없는 줄은 열쇠로만 봅니다."""
    uid, k = _열쇠들(줄)
    return (bool(uid) and uid in 본uid) or k in 본열쇠


def _노션줄의_열쇠(r: dict) -> tuple[str, str]:
    """노션 한 줄에서 (UID, 열쇠). UID 칸이 없던 옛 줄은 UID 가 빈 문자열입니다."""
    p = r.get("properties") or {}

    def 글(칸: str) -> str:
        v = (p.get(칸) or {}).get("rich_text") or []
        return "".join(x.get("plain_text", "") for x in v)

    제목 = "".join(x.get("plain_text", "")
                 for x in ((p.get("자료 제목") or {}).get("title") or []))
    return 글("UID").strip(), _열쇠(글("원문 URL"), 제목, 글("게시 플랫폼"))


def 이미있는것(n: Notion, 줄들: list[dict] | None = None) -> tuple[set[str], set[str]]:
    """노션에 이미 있는 줄의 (UID 들, 열쇠들). 사람이 쓴 것도 여기 들어갑니다.

    이미 읽어 둔 `줄들` 을 주면 노션을 다시 안 읽습니다."""
    본uid, 본것 = set(), set()
    for r in (줄들 if 줄들 is not None else n.query_all(수집DB)):
        uid, k = _노션줄의_열쇠(r)
        if uid:
            본uid.add(uid)
        본것.add(k)
    return 본uid, 본것


def 행위자훑기(n: Notion, apply: bool) -> None:
    """판 끝에 행위자 DB 를 채웁니다. **여기서 죽어도 수집은 성공입니다.** 규칙은 `actor.py`."""
    try:
        print(actor.요약(actor.훑기(n, apply=apply), apply))
    except Exception as e:  # noqa: BLE001
        print("  행위자 DB 를 못 채웠습니다 (%s). 다음 판에 다시 봅니다" % type(e).__name__)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="사건 수집 표를 노션 수집 DB 로 올립니다")
    ap.add_argument("--apply", action="store_true",
                    help="실제로 노션에 씁니다. 없으면 미리보기입니다")
    ap.add_argument("--kr", action="store_true", help="국가가 KR 인 것만")
    ap.add_argument("--new", action="store_true", help="아직 안 본 것만")
    ap.add_argument("--limit", type=int, default=0, help="최대 몇 줄까지")
    ap.add_argument("--모두", action="store_true",
                    help="대상 조직이 없는 줄도 올립니다. 채널 공지까지 다 갑니다")
    ap.add_argument("--db", default=str(기본표), help="읽을 SQLite 파일")
    a = ap.parse_args(argv)

    f = Path(a.db)
    if not f.exists():
        print("  표가 없습니다: %s" % f)
        return 1

    c = sqlite3.connect(f)
    c.row_factory = sqlite3.Row
    # **대상 조직이 있어야 올립니다.** 수집 DB 는 유출 사건 하나가 한 줄인데,
    # items 표에는 채널 공지·광고·안내도 같이 들어 있습니다. 2026-09-02 에
    # 실제로 보니 텔레그램 133줄이 전부 그런 것이었습니다 — 「DarkForums
    # pinned a photo」 같은 것들이고 대상 조직이 하나도 안 채워져 있습니다.
    #
    # 피해자가 없으면 사건이 아닙니다. 그것이 가르는 가장 단순한 기준입니다.
    # 표에는 그대로 두고 노션에만 안 올립니다. 나중에 어댑터가 유출 글을
    # 가려내게 되면 그때 올라갑니다.
    #
    # 예외가 둘입니다 — 포럼 킷 줄, 그리고 **한국 신호가 있는 텔레그램 글**
    # (2026-09-23). 까닭은 사건인가() 에 있습니다.
    # **관문을 SQL 에 두지 않습니다.** 소스마다 자격이 다른데 조건문에 넣으면
    # 조건이 계속 자라고 시험을 못 씁니다. 넓게 뽑아 파이썬에서 가릅니다.
    조건, 값 = ["forgotten = 0"], []
    if a.new:
        조건.append("is_new = 1")
    q = "select * from items where " + " and ".join(조건) + " order by first_seen desc"
    전부 = list(c.execute(q, 값))

    # **노션을 먼저 읽습니다.** 겹침을 보려고 어차피 읽는데, 사람이 사건 O 로 확정한
    # 조직 이름을 판정기에 먼저 넣어야 관문(사건인가)이 그 이름을 알아봅니다.
    n = Notion()
    print("  노션에 이미 있는 것을 봅니다...", flush=True)
    노션줄들 = n.query_all(수집DB)
    확인된것 = 확인된_조직들(노션줄들)
    _분류기(확인된것)
    print("  판정기에 사람이 확정한 한국 조직 %d곳을 더했습니다" % len(확인된것))

    # **--limit 은 거른 뒤에 겁니다.** SQL 에 걸면 스무 줄을 뽑아 거기서 또 빼므로
    # 실제로 올라가는 것이 몇 줄일지 미리 알 수 없습니다.
    줄들, 외국 = [], []
    유출아님 = 신호없음 = 신호로올림 = 0
    for r in 전부:
        if not a.모두:
            올림, 왜 = 사건인가(r)
            if not 올림:
                if 왜 == "유출 글이 아닙니다":
                    유출아님 += 1
                else:
                    신호없음 += 1
                continue
            신호로올림 += 왜.startswith("대상 조직을 못 읽었지만")
        if a.kr and 외국인가(r):
            외국.append(_자취(r))
            continue
        줄들.append(r)
        if a.limit and len(줄들) >= a.limit:
            break

    print()
    print("  items 표 %d줄 중 %d줄을 골랐습니다" % (len(전부), len(줄들)))
    if 유출아님 or 신호없음:
        print("    대상 조직이 없는 %d줄은 뺐습니다. 유출 사건이 아닙니다" % (유출아님 + 신호없음))
        print("      CVE · 악성코드 %d줄 · 대상 조직도 한국 신호도 없는 %d줄" % (유출아님, 신호없음))
        print("      (포럼 줄은 사람이 킷을 돌린 글이라 대상 조직이 비어도 올립니다)")
        # **여기는 자취를 안 찍습니다.** 매 실행마다 130줄 넘게 나오고 대부분
        # 같은 채널 공지가 되풀이됩니다. 로그를 그만큼 불려도 되짚을 것이 없습니다.
    if 신호로올림:
        print("    대상 조직은 못 읽었지만 한국 신호가 있어 미검토로 올리는 텔레그램 %d줄" % 신호로올림)
    if 외국:
        print("    국가가 한국이 아닌 %d줄은 뺐습니다. 모르는 것은 올립니다" % len(외국))
        _뺀줄찍기(외국)
    if not 줄들:
        행위자훑기(n, a.apply)
        return 0

    본uid, 본것 = 이미있는것(n, 노션줄들)
    print("  노션에 %d줄이 있습니다 (UID 가 찬 줄 %d)" % (len(본것), len(본uid)))

    # **표 안에서도 겹칩니다.** URL 이 없는 줄은 제목과 곳으로만 가리는데,
    # 같은 글이 여러 채널에 퍼지면 열쇠가 같아집니다. 448줄이 열쇠로는
    # 414개입니다. 그대로 밀면 노션에 34줄이 중복으로 생깁니다.
    # UID 가 먼저고, 그 다음이 열쇠입니다. 어느 하나라도 본 것이면 뺍니다.
    새것 = []
    for r in 줄들:
        if _겹치나(r, 본uid, 본것):
            continue
        uid, k = _열쇠들(r)
        if uid:
            본uid.add(uid)
        본것.add(k)
        새것.append(r)
    겹침 = len(줄들) - len(새것)
    print("  겹치는 %d줄을 뺐습니다. 올릴 것은 %d줄입니다" % (겹침, len(새것)))
    print()

    # 게시처를 정할 명부 셋. **못 읽으면 게시처만 비워 두고 나머지는 올립니다.** 게시처는
    # 나중에 채울 수 있지만 올리지 못한 줄은 다음 판까지 안 보입니다
    표, 선택지 = None, []
    if 새것:
        try:
            표 = publisher.명부표.노션에서(n)
            선택지 = publisher.선택지읽기(n, 수집DB)
        except Exception as e:  # noqa: BLE001
            print("  명부를 못 읽어 게시처는 비워 둡니다 (%s)" % type(e).__name__)
        정함 = [게시처칸(표, 선택지, r) for r in 새것]
        print("  게시처 — 명부 이름 %d · 명부에 없어 핸들 그대로 %d · 못 정함 %d" % (
            sum(1 for x in 정함 if x and publisher.없음칸 not in x),
            sum(1 for x in 정함 if publisher.없음칸 in x),
            sum(1 for x in 정함 if not x)))

    if not a.apply:
        print("  미리보기입니다. 노션에 안 씁니다. --apply 를 주면 씁니다.")
        print()
        print("  올라갈 칸 %d개" % 보낼칸)
        print("    자료 제목 · 대상 조직 · 게시자 핸들 · 게시 플랫폼 · 원문 URL")
        print("    게시 시각 · 수집일 · 국가 · 게시 성격")
        print("    검토 여부(미검토) · 수집자(자동) · 소스 · UID · 주장 규모 · 규모 출처 · 발견일 · 한국 관련(+근거)")
        print("    게시처(+명부 없음) — 명부 셋으로 맞춥니다. 칸 수에는 안 셉니다")
        print()
        print("  안 올라가는 것")
        print("    body · raw · clues · sample_path — 수집 DB 에 그 칸이 없습니다")
        print()
        # **제목을 안 찍습니다.** 제목이 곧 피해 조직 이름이고, 레포를 공개로
        # 돌리면 Actions 로그를 누구나 봅니다. 어느 줄인지는 자취(UID · 글 번호)로 가립니다.
        for r in 새것[:5]:
            p = 만들기(r)
            print("    %-40s %s · %s · 한국 관련 %s" % (
                _자취(r),
                (p.get("소스") or {}).get("select", {}).get("name", "-"),
                r["country"] or "-",
                p["한국 관련"]["select"]["name"]))
        if len(새것) > 5:
            print("    ... 그리고 %d줄 더" % (len(새것) - 5))
        행위자훑기(n, False)
        return 0

    쓴것, 못쓴것 = 0, []
    for i, r in enumerate(새것, 1):
        try:
            n.request("POST", "/pages", {
                "parent": {"type": "data_source_id", "data_source_id": 수집DB},
                "properties": {**만들기(r), **게시처칸(표, 선택지, r)},
            })
            쓴것 += 1
        except Exception as e:  # noqa: BLE001
            못쓴것.append("%s: %s" % (_자취(r), _가린오류(e, r)))
        if i % 25 == 0:
            print("    %d/%d" % (i, len(새것)), flush=True)

    print()
    print("  %d줄을 올렸습니다" % 쓴것)
    if 못쓴것:
        print("  못 올린 것 %d줄" % len(못쓴것))
        for m in 못쓴것[:5]:
            print("    " + m)
    # 방금 올린 줄까지 보도록 올린 뒤에 훑습니다
    행위자훑기(n, True)
    return 1 if 못쓴것 else 0


if __name__ == "__main__":
    raise SystemExit(main())
