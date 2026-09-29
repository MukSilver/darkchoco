"""수집 DB 「게시처」 를 정한다. 명부 셋이 정본이다 (2026-09-25 최현서 결정).

「게시처」(select)는 9/22 에 한 번만 돌린 채우기로 채운 칸이었다. 매일 도는 수집(`push.py`)과
대시보드 포럼 사건(`/api/forum-rows`)은 「게시 플랫폼」(글자)에만 써서 그 뒤 들어온 줄이
비었다. 이제 줄을 만들 때 같이 쓴다. 규칙은 여기 한 곳에 둔다.

## 소스마다 무엇으로 맞추나

    텔레그램   게시자 핸들로만.  CTI 채널이 옮긴 랜섬 피해 알림이라 핸들이 곧 그룹이다.
               게시 플랫폼은 채널(t.me/…)이거나 피해 조직 도메인이라 게시처가 아니다
    포럼       주소 → 표기 이름.  핸들은 글쓴이라 게시처가 아니다. 못 맞추면 비운다
    랜섬웨어   주소 → 표기 이름 → 핸들
    X          **안 채운다**(2026-09-29, DEV 9/26 X 절). 여러 곳의 글을 옮기는 집계 계정이다.
               전에는 랜섬 갈래로 떨어져 핸들에 「명부 없음」 까지 켰다

**`t.me` 는 주소 열쇠에서 뺀다.** `t.me/osint_cti` 에서 호스트는 `t.me` 하나라, 열쇠로 쓰면
CTI 채널 줄이 전부 명부의 첫 텔레그램 채널에 붙는다. 9/22 도구가 그 함정을 갖고 있었다.

**핸들은 정확히 같을 때만 명부 이름으로 바꾼다.** 대소문자 · 공백 · 기호 · 0/o 를 견디는
열쇠(`Cl0p` = `clop`)와 명부의 별칭을 쓴다. 명부에 없으면 핸들을 그대로 쓰고 「명부 없음」 을 켠다.

**이미 있는 선택지를 먼저 쓴다.** 열쇠가 같은데 글자만 다른 이름(`Emperador` · `emperador`)을
쓰면 노션이 선택지를 하나 더 만들어 같은 그룹이 둘로 갈린다.

**배포 대시보드(`apps/dash/deploy/worker.js`)에 포럼 쪽 규칙이 JS 로 한 벌 더 있다.**
`packages/tests/test_게시처.py` 가 둘을 맞춰 본다.
"""
from __future__ import annotations

import re

칸, 없음칸 = "게시처", "명부 없음"

# 핸들로 찾을 때 먼저 볼 명부. 랜섬 그룹이 먼저다. (갈래, 데이터베이스 id, 제목 칸)
명부 = (("랜섬", "5a3ddb6320c54ec09083396d8bd4088d", "그룹 이름"),
      ("포럼", "8b274ac9f558463c98f84fbde5e21020", "포럼 이름"),
      ("텔레", "df4c98250f7e4b4f938c10fe3851618b", "채널 이름"))
주소칸 = ("주소", "이전 주소", "어니언 주소")

# **re.A 로 \b 를 ASCII 에 맞춘다.** worker.js 의 같은 꼴(u 플래그 없음)이 그렇다. 없으면 파이썬은
# 한글을 낱말 글자로 봐서 「examplefor.st로 이전」 에서 주소를 못 뽑고, JS 는 뽑아 두 벌이 갈렸다
HOST = re.compile(r"\b[a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)+\b", re.I | re.A)
안쓰는호스트 = frozenset({"t.me", "telegram.me", "ransomware.live", "wordpress.com"})
# 핸들 자리에 적힌 「없음」 표시. 게시처 선택지로 만들지 않는다
자리표시 = frozenset({"-", "--", "?", "n/a", "na", "none", "null", "unknown", "없음", "미상", "해당 없음"})


def 글자(p: dict, 이름: str) -> str:
    v = (p.get("properties") or {}).get(이름) or {}
    t = v.get("type")
    if t in ("title", "rich_text"):
        return "".join(x.get("plain_text", "") for x in v.get(t) or [])
    if t in ("select", "status"):
        return (v.get(t) or {}).get("name", "") or ""
    if t == "url":
        return v.get("url") or ""
    return ""


def 호스트들(s: str) -> list[str]:
    out = []
    # 사람이 명부에 `abc[.]onion` 처럼 적은 주소가 있다. 명부 조사기(write.py)처럼 점으로 읽는다
    for m in HOST.finditer((s or "").replace("[.]", ".")):
        h = m.group(0).lower().removeprefix("www.")
        if "." in h and h not in 안쓰는호스트 and h not in out:
            out.append(h)
    return out


def 민키(s: str) -> str:
    """대소문자 · 공백 · 기호 · 0/o 를 견디는 열쇠."""
    return re.sub(r"[^a-z0-9]", "", (s or "").lower()).replace("0", "o")


class 명부표:
    """명부 줄들에서 만든 찾기 표. `줄들` 은 (갈래, 제목 칸, 노션 줄 목록) 들이다."""

    def __init__(self, 줄들: list[tuple[str, str, list[dict]]]):
        self.주소: dict[str, str] = {}
        self.이름: dict[str, str] = {}
        self.민: dict[str, str] = {}
        for _, 제목, 페이지들 in 줄들:
            for p in 페이지들:
                이름 = 글자(p, 제목).strip()
                if not 이름 or 글자(p, "담당자") == "자동":
                    continue
                self.이름.setdefault(이름.lower(), 이름)
                for c in [이름] + [x.strip() for x in re.split(r"[/·,]", 글자(p, "이전 이름·별칭"))]:
                    k = 민키(c)
                    if len(k) >= 4:
                        self.민.setdefault(k, 이름)
                for c in 주소칸:
                    for h in 호스트들(글자(p, c)):
                        self.주소.setdefault(h, 이름)

    @classmethod
    def 노션에서(cls, n, 갈래들=("랜섬", "포럼", "텔레")) -> "명부표":
        줄들 = []
        for 갈래, db, 제목 in 명부:
            if 갈래 in 갈래들:
                줄들.append((갈래, 제목, n.query_all(n.data_sources(db)[0]["id"])))
        return cls(줄들)

    def 핸들로(self, 핸들: str) -> tuple[str, str]:
        k = 민키(핸들)
        if k in self.민:
            return self.민[k], "핸들"
        민 = re.sub(r"\s*ransomware\s*$|\d+$", "", (핸들 or "").strip(), flags=re.I).strip()
        if 민 and 민 != (핸들 or "").strip() and 민키(민) in self.민:
            return self.민[민키(민)], "핸들(꼬리 뗌)"
        return "", ""

    def 표기로(self, 표기: str) -> tuple[str, str]:
        for h in 호스트들(표기):
            if h in self.주소:
                return self.주소[h], "주소"
        t = (표기 or "").strip()
        if t.lower() in self.이름:
            return self.이름[t.lower()], "표기 이름"
        k = 민키(re.sub(r"\(.*?\)", " ", t))
        if k in self.민:
            return self.민[k], "표기 이름"
        return "", ""


def 고르기(표: 명부표, 소스: str, 표기: str, 핸들: str) -> tuple[str, str, bool]:
    """(게시처, 어떻게, 명부에 있나). 못 고르면 ("", 까닭, True)."""
    표기, 핸들 = (표기 or "").strip(), (핸들 or "").strip()
    if 핸들.lower() in 자리표시:
        핸들 = ""
    if 소스 == "X":
        # 집계 계정 글이다. 게시처를 비워 둔다(모듈 머리말). 「명부 없음」 도 안 켠다
        return "", "X 는 게시처를 안 채움", True
    if 소스 == "텔레그램":
        if not 핸들:
            return "", "핸들 없음", True
        이름, 어떻게 = 표.핸들로(핸들)
        return (이름, 어떻게, True) if 이름 else (핸들, "핸들(명부에 없음)", False)
    if 소스 == "포럼":
        이름, 어떻게 = 표.표기로(표기)
        return (이름, 어떻게, True) if 이름 else ("", "포럼 표기 못 맞춤", True)
    이름, 어떻게 = 표.표기로(표기)
    if not 이름 and 핸들:
        이름, 어떻게 = 표.핸들로(핸들)
        if not 이름:
            return 핸들, "핸들(명부에 없음)", False
    return (이름, 어떻게, True) if 이름 else ("", "못 맞춤", True)


def 선택지맞춤(이름: str, 선택지: list[str]) -> str:
    """이미 있는 선택지 중 열쇠가 같은 것이 있으면 그 이름을 쓴다.

    **열쇠가 네 글자보다 짧으면 대소문자만 무시하고 통째로 견준다.** 민키는 한글 · 키릴을
    지워서 한글 이름끼리 열쇠가 모두 빈 글자가 되고, 아무 한글 선택지에나 붙었다
    (2026-09-25 검토). 명부 찾기 표의 네 글자 문턱과 같다.
    """
    if not 이름 or 이름 in 선택지:
        return 이름
    k = 민키(이름)
    if len(k) < 4:
        낮춤 = 이름.strip().lower()
        return next((o for o in 선택지 if o.strip().lower() == 낮춤), 이름)
    for o in 선택지:
        if 민키(o) == k:
            return o
    return 이름


def 선택지글(s: str) -> str:
    """노션 선택지 이름에는 쉼표가 못 들어간다. 넣으면 줄을 만드는 요청 전체가 거부된다.

    핸들 「GroupA, GroupB」 가 그대로 가서 그 수집 줄이 판마다 못 올라갔다(2026-09-25 검토).
    """
    return re.sub(r"\s*,\s*", " · ", s or "").strip()


def 속성(표: 명부표, 선택지: list[str], 소스: str, 표기: str, 핸들: str) -> dict:
    """노션에 더할 속성. 못 고르면 빈 dict — 칸을 비워 둔다."""
    이름, _, 있나 = 고르기(표, 소스, 표기, 핸들)
    이름 = 선택지맞춤(선택지글(이름), 선택지)[:100]
    if not 이름:
        return {}
    p = {칸: {"select": {"name": 이름}}}
    if not 있나:
        p[없음칸] = {"checkbox": True}
    return p


def 선택지읽기(n, ds: str) -> list[str]:
    raw = n.request("GET", "/data_sources/" + ds) or {}
    v = ((raw.get("properties") or {}).get(칸) or {}).get("select") or {}
    return [o["name"] for o in v.get("options") or []]
