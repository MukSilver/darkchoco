"""명부를 노션에 반영합니다.

안유빈 님이 dls_fill.py 에 만든 방식을 그대로 씁니다.

  1. 노션 스키마를 실제로 읽습니다. 칸 이름과 타입을 받아옵니다
  2. 스키마에 없는 칸은 걸러냅니다. 틀린 칸에 쓰다 조용히 건너뛰는 일이
     없게 하려는 것입니다
  3. 기본은 미리보기입니다. --apply 를 줘야 실제로 씁니다
  4. 기계가 쓰는 칸 밖은 안 건드립니다

**노션 칸을 늘리지 않습니다.** 다크웹 DB 스키마가 LLM 다크웹 RAG 의
근간이라 바꾸면 그쪽이 흔들립니다.

**못 넣은 칸이 하나라도 있으면 알립니다.** 칸 이름이 틀리면 노션은
오류를 내지 않고 그 칸만 건너뜁니다. 조용히 틀리는 것이 제일 위험합니다.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages"))

from dc_notion import Notion  # noqa: E402

from hub.crawler.place import (  # noqa: E402
    Place, 기계칸, 빈칸만칸, 사람판정_상태)

__all__ = ["명부", "반영결과", "갈래별_DB"]

# 다크웹 DB 세 개. 비밀이 아니라 코드에 둡니다.
갈래별_DB = {
    "telegram": ("텔레그램 DB", "df4c98250f7e4b4f938c10fe3851618b", "채널 이름"),
    "forum":    ("포럼 DB",     "8b274ac9f558463c98f84fbde5e21020", "포럼 이름"),
    "ransom":   ("랜섬웨어 DB",  "5a3ddb6320c54ec09083396d8bd4088d", "그룹 이름"),
}


@dataclass
class 줄:
    """명부의 한 줄. 조사 전에 읽어 둡니다."""

    page_id: str
    이름: str
    주소: str = ""
    어니언: str = ""      # 이음 사전이 이것을 씁니다. 없으면 어니언 관계를 못 봅니다
    규모: str = ""
    상태: str = ""
    현재: dict = field(default_factory=dict)   # 기계칸의 지금 값


@dataclass
class 반영결과:
    이름: str
    바뀐칸: dict = field(default_factory=dict)
    건너뛴칸: list = field(default_factory=list)   # 스키마에 없는 칸
    안바뀜: bool = False
    오류: str = ""
    없는옵션: list = field(default_factory=list)   # 스키마 선택지에 없음
    사람글: list = field(default_factory=list)     # 사람이 이미 써 둔 칸
    사람판정: str = ""                             # 압수됨·인계됨. 안 건드림


class 명부:
    """노션 명부 하나를 읽고 씁니다."""

    def __init__(self, 갈래: str, *, verbose: bool = False):
        if 갈래 not in 갈래별_DB:
            raise ValueError(f"모르는 갈래입니다: {갈래}")
        self.갈래 = 갈래
        self.이름, self.db, self.제목칸 = 갈래별_DB[갈래]
        self.n = Notion(verbose=verbose)
        ds = self.n.data_sources(self.db)
        if not ds:
            raise RuntimeError(f"{self.이름} 에 데이터 소스가 없습니다")
        self.ds = ds[0]["id"]
        self.스키마 = self.n.schema(self.ds)
        self.옵션 = self._옵션읽기()

    def _옵션읽기(self) -> dict[str, set]:
        """select · multi_select 가 받는 값 목록입니다.

        갈래마다 다릅니다. 랜섬에만 「압수됨」과 「ransomware.live」가 있고
        포럼·텔레그램에는 없습니다. 없는 값을 보내면 노션이 400 을 냅니다.
        """
        raw = self.n.request("GET", f"/data_sources/{self.ds}")
        out = {}
        for 칸, v in (raw.get("properties") or {}).items():
            t = v.get("type")
            if t in ("select", "multi_select", "status"):
                out[칸] = {o["name"] for o in (v[t].get("options") or [])}
        return out

    # ── 읽기 ────────────────────────────────────────────────────────
    def 줄들(self) -> list[줄]:
        out = []
        for page in self.n.query_all(self.ds):
            props = page.get("properties", {})
            현재 = {칸: _글자(props.get(칸)) for 칸 in 기계칸 if 칸 in props}
            out.append(줄(
                page_id=page["id"],
                이름=_글자(props.get(self.제목칸)),
                주소=_글자(props.get("주소")),
                어니언=_글자(props.get("어니언 주소")),
                규모=_글자(props.get("규모")),
                상태=_글자(props.get("상태")),
                현재=현재,
            ))
        return out

    # ── 쓰기 ────────────────────────────────────────────────────────
    def 반영(self, 줄: 줄, p: Place, *, apply: bool = False) -> 반영결과:
        r = 반영결과(이름=줄.이름 or p.이름)
        if 줄.현재.get("상태") in 사람판정_상태 and p.상태 in ("online", "offline"):
            r.사람판정 = (f"사람이 「{줄.현재['상태']}」 으로 판정한 줄입니다. "
                      f"기계는 {p.상태} 로 봤지만 상태를 안 건드립니다")
        값 = p.노션값(줄.현재 or 줄.규모)
        if not 값:
            r.안바뀜 = True
            return r

        # 1. 스키마에 없는 칸은 걸러냅니다. 여기서 안 거르면 노션이 조용히
        #    건너뛰고, 우리는 썼다고 믿습니다.
        쓸것, 없는칸 = {}, []
        for 칸, v in 값.items():
            if 칸 in self.스키마:
                쓸것[칸] = v
            else:
                없는칸.append(칸)
        r.건너뛴칸 = 없는칸

        # 2. 사람이 이미 쓴 칸은 안 건드립니다. 비어 있을 때만 채웁니다.
        #    선택지 검사보다 먼저 합니다. 어차피 안 쓸 값을 두고
        #    「선택지에 없다」고 알릴 이유가 없습니다.
        찬것, 사람글 = {}, []
        for 칸, v in 쓸것.items():
            if 칸 in 빈칸만칸 and (줄.현재.get(칸) or "").strip():
                사람글.append(칸)
                continue
            찬것[칸] = v
        r.사람글 = 사람글

        # 3. 선택지에 없는 값을 거릅니다. 갈래마다 선택지가 다릅니다.
        #    포럼 DB 에는 「직접 확인」 출처도, 「압수됨」 상태도 없습니다.
        골라낸것, 없는옵션 = {}, []
        for 칸, v in 찬것.items():
            받는값 = self.옵션.get(칸)
            if 받는값 is None:
                골라낸것[칸] = v
                continue
            if isinstance(v, list):
                남 = [x for x in v if x in 받는값]
                없는옵션 += [f"{칸}={x}" for x in v if x not in 받는값]
                if 남:
                    골라낸것[칸] = 남
            elif v in 받는값:
                골라낸것[칸] = v
            else:
                없는옵션.append(f"{칸}={v}")
        r.없는옵션 = 없는옵션

        # 4. 지금 값과 같으면 안 씁니다. 확인일만 바꾸려고 쓰지 않습니다.
        달라진것 = {}
        for 칸, v in 골라낸것.items():
            지금 = 줄.현재.get(칸, {"규모": 줄.규모, "상태": 줄.상태,
                                 "주소": 줄.주소}.get(칸))
            if 지금 is not None and str(지금).strip() == str(v).strip():
                continue
            달라진것[칸] = v
        # 확인일만 바뀌는 줄도 **두드린 것이면** 씁니다.
        #
        # 403 · 404 · 429 로 막힌 줄은 상태가 계속 미확인이라, 「우리가
        # 오늘 이 줄을 두드렸다」 는 사실이 아예 안 남았습니다. 40줄쯤이
        # 그렇습니다. 언제 마지막으로 확인했는지는 명부의 값입니다.
        #
        # 두드리지도 못한 줄은 위에서 이미 걸러졌습니다.
        if set(달라진것) <= {"확인일"} and not p.두드림:
            r.안바뀜 = True
            return r
        r.바뀐칸 = 달라진것

        if not apply:
            return r
        try:
            self.n.update_page(줄.page_id, _속성으로(달라진것, self.스키마))
        except Exception as e:  # noqa: BLE001
            r.오류 = str(e).replace("\n", " ")[:200]
        return r


# ── 값 만들기 ──────────────────────────────────────────────────────
def _글자(prop) -> str:
    """노션 속성에서 사람이 읽을 글자를 뽑습니다."""
    if not isinstance(prop, dict):
        return ""
    t = prop.get("type")
    if t in ("title", "rich_text"):
        return "".join(x.get("plain_text", "") for x in prop.get(t) or [])
    if t == "select":
        return (prop.get("select") or {}).get("name", "") or ""
    if t == "url":
        return prop.get("url") or ""
    if t == "date":
        return (prop.get("date") or {}).get("start", "") or ""
    if t == "multi_select":
        return " · ".join(x.get("name", "") for x in prop.get("multi_select") or [])
    if t == "number":
        v = prop.get("number")
        return "" if v is None else str(v)
    if t == "checkbox":
        return "예" if prop.get("checkbox") else "아니오"
    return ""


def _속성으로(값: dict, 스키마: dict) -> dict:
    """스키마의 타입에 맞는 모양으로 바꿉니다."""
    out = {}
    for 칸, v in 값.items():
        t = 스키마.get(칸)
        if t == "select":
            out[칸] = {"select": {"name": str(v)}}
        elif t == "multi_select":
            이름들 = v if isinstance(v, list) else [v]
            out[칸] = {"multi_select": [{"name": str(x)} for x in 이름들]}
        elif t == "date":
            out[칸] = {"date": {"start": str(v)}}
        elif t == "url":
            out[칸] = {"url": str(v) or None}
        elif t == "number":
            try:
                out[칸] = {"number": float(v)}
            except (TypeError, ValueError):
                continue
        elif t == "checkbox":
            out[칸] = {"checkbox": bool(v)}
        elif t == "title":
            out[칸] = {"title": [{"text": {"content": str(v)[:2000]}}]}
        else:
            out[칸] = {"rich_text": [{"text": {"content": str(v)[:2000]}}]}
    return out


def 표로(결과: list[반영결과], *, apply: bool) -> str:
    """사람이 읽을 요약."""
    if not 결과:
        return "  바뀔 것이 없습니다."
    # 선택지에 없는 값은 줄마다가 아니라 한 번만 알립니다. 스키마 문제라
    # 줄 수만큼 반복해 봐야 같은 말입니다.
    없는옵션 = sorted({x for r in 결과 for x in r.없는옵션})
    폭 = min(24, max(len(r.이름) for r in 결과) + 2)
    줄들 = []
    if 없는옵션:
        줄들.append(f"  !! 노션 선택지에 없어 안 쓴 값: {' · '.join(없는옵션)}")
    바뀜 = 문제 = 0
    for r in 결과:
        if r.오류:
            줄들.append(f"  {r.이름[:폭-2].ljust(폭)}실패 — {r.오류[:60]}")
            문제 += 1
        elif r.안바뀜:
            줄들.append(f"  {r.이름[:폭-2].ljust(폭)}그대로")
        else:
            무엇 = " · ".join(f"{k}={str(v)[:32]}" for k, v in r.바뀐칸.items())
            줄들.append(f"  {r.이름[:폭-2].ljust(폭)}{무엇}")
            바뀜 += 1
        if r.건너뛴칸:
            줄들.append(f"  {' ' * 폭}!! 스키마에 없는 칸: {' · '.join(r.건너뛴칸)}")

            문제 += 1
    줄들.append("")
    머리 = "썼습니다" if apply else "미리보기입니다. --apply 를 주면 씁니다"
    줄들.append(f"  {머리} — 바뀔 줄 {바뀜} · 그대로 {len(결과)-바뀜-문제} · 살펴볼 것 {문제}")
    return "\n".join(줄들)
