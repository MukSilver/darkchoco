"""수집 DB 게시자 핸들 중 어디에도 없는 판매 · 공개 핸들을 행위자 DB 에 올린다 (2026-09-25 최현서 결정 D-3).

전에는 행위자 DB 가 검증 스킬 ⑨-3 을 돌릴 때만 채워졌다. 그 길 하나로는 DB 를 유지보수할 수 없다.
`push.py` 가 한 판 돌 때마다 **수집 DB 전체를 훑는다.** 방금 올린 줄만 보지 않는 까닭은 셋이다.

    대시보드(/api/forum-rows)로 들어온 줄     다음 수집 판(최대 6시간 뒤)에 잡힌다
    ⑨-1 로 손으로 올린 줄                  같다
    나중에 사람이 게시자 핸들을 채운 줄        같다

줄을 만드는 길마다 코드를 붙이면 붙이지 않은 길이 샌다. 한 자리에서 훑으면 새는 길이 없다.

## 무엇을 올리나

**DB 판매 · DB 무료 공개 글이 하나라도 있는 핸들만** 올린다. 랜섬웨어 유출 글만 있는 핸들은
그룹이라 행위자가 아니다(그쪽 「명부 없음」 은 `publisher.py` 가 켠다). 9/25 소급(D-2)과 같은
규칙이다.

맞추는 열쇠는 소문자 · 영숫자 · 한글만 남기고 0 을 o 로 바꾼 글자다. 행위자 DB 는 핸들 ·
다른 이름, 명부 셋은 이름 · 이전 이름·별칭과 견준다. **이미 있는 줄은 고치지 않는다.** 자동으로
만든 줄도 그렇다 — 빈 칸을 채우는 것은 ⑨-3 의 몫이다.

## 줄 모양은 ⑨-3 이다

관찰한 것만 넣는다. 다른 이름 · 국가 · 지갑 · 텔레그램은 근거가 없어 비운다.

    핸들          게시자 핸들 (같은 열쇠가 여럿이면 가장 많이 쓰인 표기)
    연결된 곳      그 핸들 사건들의 게시처
    처음 본 날     가장 이른 게시 시각. 없으면 비운다
    출처           사건의 소스
    역할           DB 판매 글이 있으면 판매자, 그 밖은 미확인
    한국 관련 유출  「YYYY-MM 한국 N건」. **피해 조직명은 안 쓴다**
    비고           「YYYY-MM-DD 수집 DB 게시자 핸들에서 자동 등록」
    DB 반영        켬

**비고의 「수집 DB 게시자 핸들에서」 가 표지다.** ⑨-3 은 이 표지가 있는 줄만 빈 칸을 채운다
(`skills/.../references/stage9-db.md`). 9/25 소급 줄도 같은 표지를 달고 있다.

**로그에는 핸들을 안 찍는다.** 레포가 공개라 Actions 로그도 누구나 본다. 건수만 낸다.

**자동 줄을 지우지 말고 「DB 반영」 을 끈다.** 노션 조회는 지운 줄을 안 돌려줘서, 지우면 그 핸들의
판매 글이 수집 DB 에 남아 있는 한 다음 판에 같은 줄이 다시 생긴다(2026-09-25 검토).
"""
from __future__ import annotations

import collections
import re
from datetime import date, datetime, timedelta, timezone

행위자DS = "58571d39-209a-4787-a0f5-2d9b735920be"
수집DS = "5160ce53-7ce2-4271-879e-06f3ad9957cf"
# (데이터베이스 id, 제목 칸). publisher.명부 와 같은 셋이다
명부 = (("5a3ddb6320c54ec09083396d8bd4088d", "그룹 이름"),
        ("8b274ac9f558463c98f84fbde5e21020", "포럼 이름"),
        ("df4c98250f7e4b4f938c10fe3851618b", "채널 이름"))

표지 = "수집 DB 게시자 핸들에서"
판매성격 = frozenset({"DB 판매", "DB 무료 공개"})
출처맞춤 = {"포럼": "포럼", "텔레그램": "텔레그램", "X": "트위터", "랜섬웨어": "랜섬웨어 유출 사이트"}
# 한 판에 이보다 많이 나오면 규칙이 샌 것이다. 쓰지 않고 알린다. 9/25 소급이 8줄이었다
상한 = 30
KST = timezone(timedelta(hours=9))


def 키(s: str) -> str:
    """대소문자 · 공백 · 기호 · 0/o 를 견디는 열쇠. 한글은 남긴다."""
    return re.sub(r"[^a-z0-9가-힣]", "", (s or "").lower()).replace("0", "o")


def 조각(s: str) -> list[str]:
    """다른 이름 · 별칭 칸을 이름 조각으로 자른다. **괄호 안은 이름이 아니다.**

    「Max98 (breached.st) · Max (Signal)」 의 괄호는 어디서 쓰는 닉인지 적은 것이다(⑨-3 형식).
    괄호 안까지 조각으로 세면 signal · breachedst 같은 플랫폼 이름이 별칭이 되어 남의 줄과
    맞았다(2026-09-25 검토). 괄호를 먼저 떼고 자른다. notion_find.split_aliases 와 같은 규칙이다.
    """
    s = re.sub(r"\([^)]*\)", " ", s or "")
    return [x.strip(" .'\"") for x in re.split(r"[,·/|;\n]|\s+또는\s+", s) if x.strip(" .'\"")]


def 글(p: dict, k: str) -> str:
    v = (p.get("properties") or {}).get(k) or {}
    t = v.get("type")
    if t in ("title", "rich_text"):
        return "".join(x.get("plain_text", "") for x in v.get(t) or [])
    if t in ("select", "status"):
        return (v.get(t) or {}).get("name") or ""
    if t == "date":
        return (v.get("date") or {}).get("start") or ""
    return ""


def 있는키(행위자줄: list[dict], 명부줄들: list[tuple[str, list[dict]]]) -> set[str]:
    """이미 어딘가에 있는 이름의 열쇠. `명부줄들` 은 (제목 칸, 노션 줄 목록) 들이다."""
    s = set()
    for p in 행위자줄:
        for c in [글(p, "핸들")] + 조각(글(p, "다른 이름")):
            if 키(c):
                s.add(키(c))
    for 제목, 줄들 in 명부줄들:
        for p in 줄들:
            for c in [글(p, 제목)] + 조각(글(p, "이전 이름·별칭")):
                if 키(c):
                    s.add(키(c))
    return s


def 후보(수집줄: list[dict], 있음: set[str]) -> tuple[dict[str, tuple[str, list[dict]]], collections.Counter]:
    """{열쇠: (표기, 그 핸들의 수집 줄들)} 과 세어 둔 것."""
    무리 = collections.defaultdict(list)
    표기셈 = collections.defaultdict(collections.Counter)
    for p in 수집줄:
        h = 글(p, "게시자 핸들").strip()
        if h and 키(h):
            무리[키(h)].append(p)
            표기셈[키(h)][h] += 1
    셈 = collections.Counter()
    out = {}
    for k, 줄들 in 무리.items():
        if k in 있음:
            셈["이미 있음"] += 1
        elif {글(p, "게시 성격") for p in 줄들} & 판매성격:
            out[k] = (표기셈[k].most_common(1)[0][0], 줄들)
        else:
            셈["판매·공개 글 없음"] += 1
    return out, 셈


def _한국줄(p: dict) -> bool:
    return 글(p, "국가") == "한국" or 글(p, "한국 관련") in ("직접", "공급망")


def _kst날(s: str) -> str:
    """시각을 KST 날짜로. 텔레그램 · 집계처 시각은 UTC 라 그대로 자르면 15시 이후가 하루 앞선다.

    push.py 의 _발견일 · skills/collect/stats.py 의 _kst 와 같은 까닭이다(2026-09-25 검토).
    """
    s = (s or "").strip()
    if len(s) <= 10:
        return s
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return s[:10]
    return (d.astimezone(KST) if d.tzinfo else d).date().isoformat()


def _날(p: dict) -> str:
    return _kst날(글(p, "게시 시각") or 글(p, "발견일"))


def 속성(표기: str, 줄들: list[dict], 오늘: str, 까닭: str = "자동 등록") -> dict:
    """행위자 DB 새 줄의 속성. 피해 조직 이름이 들어갈 칸이 없다."""
    곳 = sorted({글(p, "게시처") for p in 줄들 if 글(p, "게시처")})
    처음 = sorted(x for x in (_kst날(글(p, "게시 시각")) for p in 줄들) if x)
    출처 = sorted({출처맞춤[글(p, "소스")] for p in 줄들 if 글(p, "소스") in 출처맞춤})
    역할 = "판매자" if any(글(p, "게시 성격") == "DB 판매" for p in 줄들) else "미확인"
    달셈 = collections.Counter(_날(p)[:7] for p in 줄들 if _한국줄(p) and _날(p))
    한국 = " · ".join("%s 한국 %d건" % (m, c) for m, c in sorted(달셈.items()))
    p = {
        "핸들": {"title": [{"text": {"content": 표기[:200]}}]},
        "확인일": {"date": {"start": 오늘}},
        "역할": {"multi_select": [{"name": 역할}]},
        "조사 단계": {"select": {"name": "시작 전"}},
        "비고": {"rich_text": [{"text": {"content": "%s %s %s" % (오늘, 표지, 까닭)}}]},
        "DB 반영": {"checkbox": True},
    }
    if 곳:
        p["연결된 곳"] = {"rich_text": [{"text": {"content": " · ".join(곳)[:2000]}}]}
    if 처음:
        p["처음 본 날"] = {"date": {"start": 처음[0]}}
    if 출처:
        p["출처"] = {"multi_select": [{"name": x} for x in 출처]}
    if 한국:
        p["한국 관련 유출"] = {"rich_text": [{"text": {"content": 한국[:2000]}}]}
    return p


def 훑기(n, *, apply: bool, 오늘: date | None = None) -> collections.Counter:
    """수집 DB 를 훑어 없는 판매 · 공개 핸들을 행위자 DB 에 올린다. 센 것을 돌려준다."""
    오늘 = (오늘 or datetime.now(KST).date()).isoformat()
    명부줄들 = [(제목, n.query_all(n.data_sources(db)[0]["id"])) for db, 제목 in 명부]
    있음 = 있는키(n.query_all(행위자DS), 명부줄들)
    새것, 셈 = 후보(n.query_all(수집DS), 있음)
    셈["새로"] = len(새것)
    if not apply or not 새것:
        return 셈
    if len(새것) > 상한:
        셈["상한 넘어 안 씀"] = len(새것)
        return 셈
    for 표기, 줄들 in 새것.values():
        try:
            n.request("POST", "/pages", {
                "parent": {"type": "data_source_id", "data_source_id": 행위자DS},
                "properties": 속성(표기, 줄들, 오늘)})
            셈["만듦"] += 1
        except Exception:  # noqa: BLE001  한 줄이 죽어도 나머지를 올린다
            셈["못 만듦"] += 1
    return 셈


def 요약(셈: collections.Counter, apply: bool) -> str:
    """로그 한 줄. 핸들은 안 찍는다."""
    s = "  행위자 — 없는 판매·공개 핸들 %d · 이미 있음 %d · 판매·공개 글 없음 %d" % (
        셈["새로"], 셈["이미 있음"], 셈["판매·공개 글 없음"])
    if 셈["상한 넘어 안 씀"]:
        return s + "\n  !! 한 판에 %d줄은 %d 을 넘습니다. 규칙이 샜을 수 있어 안 씁니다" % (
            셈["상한 넘어 안 씀"], 상한)
    if apply:
        s += " → 만듦 %d · 못 만듦 %d" % (셈["만듦"], 셈["못 만듦"])
    elif 셈["새로"]:
        s += " (미리보기. --apply 면 행위자 DB 에 새 줄)"
    return s
