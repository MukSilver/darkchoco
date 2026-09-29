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

**명부는 한 곳에 한 줄입니다** (2026-09-24 최현서 결정). 사람 값은 칸 갈래로
지킵니다. 갈래는 `place.py` 에 있습니다.

    빈칸만칸       사람이 쓴 칸은 안 건드린다
    합치는칸       사람 글은 두고 기계 줄만 갈아 끼운다
    이어붙이는칸   지우지 않고 새 주소를 맨 뒤에 붙인다
    주소           사이트가 스스로 옮겼을 때(리다이렉트)만 바꾼다. 그 밖에 기계가
                   본 주소가 다르면 「이전 주소」 에 이어 붙인다

그리고 **숫자가 같고 날짜만 다른 합치는 칸은 안 씁니다.** 기계 줄 끝의
「(날짜 기준)」 이 판마다 바뀌어서, 이것까지 치면 판마다 모든 줄을 고칩니다.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages"))

from dc_notion import Notion  # noqa: E402

from hub.places.place import (  # noqa: E402
    Place, 기계가_쓴_줄, 기계칸, 빈칸만칸, 사람판정_상태, 이어붙이는칸, 자동금지칸,
    합치는칸)

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
    금지칸: list = field(default_factory=list)     # 자동금지칸. 값이 와도 안 씀


자리표시자 = {"미확인", "미기입", "-", "—", "?", "unknown", "n/a", "none"}


def _사람이_쓴것(값: str) -> bool:
    """그 칸을 사람이 실제로 채웠는지.

    **자리표시자는 빈 칸으로 봅니다.** 노션 선택지에 「미기입」이 들어 있어서,
    그 값이 박힌 줄은 빈칸만칸 규칙에 걸려 기계가 영원히 못 채웁니다.
    세 DB 의 「유통 자리」와 「출처」가 실제로 그렇습니다.

    통합 전 저장소(Notion-DLS)의 mapping.json 이 placeholders 로 두고 있던
    규칙입니다. 옮겨 오면서 빠졌습니다. 2026-08-31 에 되살립니다.
    """
    v = (값 or "").strip()
    return bool(v) and v.lower() not in 자리표시자


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
        """명부를 읽습니다.

        **두드릴 주소(주소 · 어니언)는 `[.]` 를 점으로 읽습니다.** 사람이 주소를
        `abc[.]onion` 처럼 적어 둔 줄이 있습니다. 그대로 넘기면 urllib 이 대괄호를
        IPv6 로 읽다 ValueError 를 내고 그 줄을 못 봅니다(랜섬 2줄, 9/22 판부터).
        `현재` 는 노션 글자 그대로 둡니다 — 사람 값을 고쳐 쓰지 않습니다.
        """
        out = []
        for page in self.n.query_all(self.ds):
            props = page.get("properties", {})
            현재 = {칸: _글자(props.get(칸)) for 칸 in 기계칸 if 칸 in props}
            out.append(줄(
                page_id=page["id"],
                이름=_글자(props.get(self.제목칸)),
                주소=_점살리기(_글자(props.get("주소"))),
                어니언=_점살리기(_글자(props.get("어니언 주소"))),
                규모=_글자(props.get("규모")),
                상태=_글자(props.get("상태")),
                현재=현재,
            ))
        return out

    # ── 쓰기 ────────────────────────────────────────────────────────
    def 반영(self, 줄: 줄, p: Place, *, apply: bool = False,
            칸만: set | frozenset | None = None) -> 반영결과:
        """`칸만` 을 주면 그 칸만 씁니다 (2026-09-29, 깊은 판만 따로 돌 때 — deep.py).
        그때는 바뀔 것이 없으면 노션을 아예 안 부릅니다. 안 주면 예전과 같습니다."""
        r = 반영결과(이름=줄.이름 or p.이름)
        if (칸만 is None and 줄.현재.get("상태") in 사람판정_상태
                and p.상태 in ("online", "offline")):
            r.사람판정 = (f"사람이 「{줄.현재['상태']}」 으로 판정한 줄입니다. "
                      f"기계는 {p.상태} 로 봤지만 상태를 안 건드립니다")
        값 = p.노션값(줄.현재 or 줄.규모)
        if 칸만 is not None:
            값 = {k: v for k, v in 값.items() if k in 칸만}
        if not 값:
            r.안바뀜 = True
            return r

        # 0. **자동금지칸은 어느 조사기가 값을 채워 보내도 안 씁니다.**
        #    통합 전 저장소의 report_generator.FORBIDDEN_AUTO_FIELDS 가
        #    하던 일입니다. 노션에 닿기 직전 한 자리에서 봅니다 —
        #    조사기마다 지키게 하면 새 조사기가 붙을 때 빠집니다.
        #    지금은 노션값() 이 이 칸들을 안 내므로 걸릴 일이 없습니다.
        #    걸린다면 그것이 바로 알아야 하는 일이라 조용히 안 버립니다.
        막힌것 = sorted(set(값) & 자동금지칸)
        for 칸 in 막힌것:
            값.pop(칸, None)
        r.금지칸 = 막힌것

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
            if 칸 in 빈칸만칸 and _사람이_쓴것((줄.현재.get(칸) or "")):
                사람글.append(칸)
                continue
            찬것[칸] = v

        # 2-1. 이어붙이는칸은 지우지 않습니다. 새로 본 주소를 맨 뒤에 붙입니다.
        #      이미 있는 주소면 그대로라 아래 4 에서 「같다」 로 걸러집니다.
        for 칸 in [k for k in 찬것 if k in 이어붙이는칸]:
            찬것[칸] = _이어붙이기(줄.현재.get(칸) or "", 찬것[칸])

        # 2-2. 사람이 적은 주소는 사이트가 스스로 옮겼을 때만 바꿉니다.
        #      조사기가 주소를 새로 적는 것은 리다이렉트뿐이고 그때 명부에 적힌
        #      주소가 p.이전주소 로 옵니다. p.이전주소 는 「다른 미러」 에도
        #      쓰이므로, **명부의 주소와 같을 때만** 옮겨 간 것으로 봅니다.
        #      그 밖의 까닭(표기만 다른 것 등)으로 사람 값을 바꾸지 않습니다.
        #
        #      **기계가 본 주소가 사람 주소와 다르면 버리지 않고 「이전 주소」 에
        #      이어 붙입니다.** 그 칸은 원래 「리다이렉트 전 주소 · 다른 미러」
        #      를 적는 자리입니다(Place.이전주소). 랜섬은 집계 API 가 고른 대표
        #      유출 사이트 주소가 오는데, 사람이 적은 주소와 다를 수 있습니다.
        #      표기만 다른 같은 주소(http · 끝의 / · 대소문자)는 붙이지 않습니다.
        지금주소 = 줄.현재.get("주소") or 줄.주소 or ""
        옮겼나 = bool(p.이전주소) and _주소열쇠(p.이전주소) == _주소열쇠(지금주소)
        if "주소" in 찬것 and _사람이_쓴것(지금주소) and not 옮겼나:
            기계주소 = str(찬것.pop("주소") or "")
            사람글.append("주소")
            if (기계주소 and _주소열쇠(기계주소) != _주소열쇠(지금주소)
                    and "이전 주소" in self.스키마):
                바탕 = 찬것.get("이전 주소") or 줄.현재.get("이전 주소") or ""
                찬것["이전 주소"] = _이어붙이기(str(바탕), 기계주소)
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
            if 지금 is not None and _칸같나(칸, str(지금), v):
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
        if 칸만 is not None and not 달라진것:
            r.안바뀜 = True
            return r

        if not apply:
            return r
        try:
            self.n.update_page(줄.page_id, _속성으로(달라진것, self.스키마))
        except Exception as e:  # noqa: BLE001
            r.오류 = str(e).replace("\n", " ")[:200]
        return r


# ── 값 견주기 ──────────────────────────────────────────────────────
def _읽은꼴(v) -> str:
    """보낼 값을 `_글자()` 가 노션에서 읽어 오는 꼴로 바꿉니다."""
    if isinstance(v, bool):
        return "예" if v else "아니오"
    if isinstance(v, (list, tuple, set)):
        return " · ".join(str(x)[:100] for x in v)
    return str(v)


def _같나(지금: str, v) -> bool:
    """노션에서 읽은 글자 `지금` 과 보낼 값 `v` 가 같은가.

    **타입마다 읽은 꼴이 달라 맞춰서 봅니다.** 전에는 글자로만 견줘서 다중
    선택(목록)이 늘 다르게 나왔습니다. 빈칸만칸 규칙이 가려 드러나지 않았을
    뿐, 사람이 비워 둔 다중 선택 칸은 판마다 다시 썼습니다.
    """
    지금 = (지금 or "").strip()
    if isinstance(v, bool):
        return 지금 == _읽은꼴(v)
    if isinstance(v, (list, tuple, set)):
        return ({x.strip() for x in 지금.split(" · ") if x.strip()}
                == {str(x).strip()[:100] for x in v})
    if isinstance(v, (int, float)):
        try:
            return float(지금) == float(v)
        except ValueError:
            return False
    return 지금 == str(v).strip()


# 기계가 쓴 줄의 꼬리. `Place.규모줄()` 이 「… (YYYY-MM-DD 기준)」 으로 끝낸다
_기준꼬리 = re.compile(r"\s*\(\d{4}-\d{2}-\d{2} 기준\)\s*$")


def _기계줄숫자(줄: str) -> list[int]:
    """기계 줄에서 날짜 꼬리를 떼고 숫자만 뽑습니다. 「1,440」 은 1440 입니다."""
    몸 = _기준꼬리.sub("", 줄)
    return [int(x.replace(",", "")) for x in re.findall(r"\d[\d,]*", 몸)]


def _합친값_같나(지금: str, v: str) -> bool:
    """합치는 칸(규모 · 피해 대상 · 한국 관련 유출)을 견줍니다.

    **숫자가 같고 날짜만 다르면 같은 것으로 봅니다** (2026-09-24 최현서 결정).
    기계 줄은 「… (YYYY-MM-DD 기준)」 으로 끝나서 숫자가 그대로여도 판마다 날짜가
    바뀝니다. 이것까지 다르다고 치면 판마다 규모가 있는 줄을 전부 고칩니다.
    「확인일만 다른 것은 안 친다」 와 같은 논리입니다.

        사람 글         글자 그대로 견줍니다
        기계 줄         날짜를 떼고 숫자만 견줍니다. 여럿이면 전부 같아야 같습니다
        숫자 못 뽑음    글자 그대로 견줍니다

    **견주는 규칙만 바꿉니다.** 숫자가 바뀌어 쓸 때는 기계가 본 값을 날짜째 씁니다.
    """
    a = [l.strip() for l in (지금 or "").splitlines() if l.strip()]
    b = [l.strip() for l in (v or "").splitlines() if l.strip()]
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if x == y:
            continue
        if not (기계가_쓴_줄(x) and 기계가_쓴_줄(y)):
            return False
        nx, ny = _기계줄숫자(x), _기계줄숫자(y)
        if not nx or not ny or nx != ny:
            return False
    return True


def _칸같나(칸: str, 지금: str, v) -> bool:
    """칸에 맞는 규칙으로 견줍니다. 합치는 칸만 날짜를 빼고 봅니다."""
    if 칸 in 합치는칸 and isinstance(v, str):
        return _합친값_같나(지금, v)
    return _같나(지금, v)


# ── 이어 붙이기 ────────────────────────────────────────────────────
def _빈값(값: str) -> bool:
    """비었거나 자리표시자인가. 「— 미기입 —」 · 「— 없음 —」 도 빈 것입니다.

    `_사람이_쓴것()` 은 앞뒤 줄표가 붙은 꼴을 못 가립니다. 그 꼴이 든 칸 뒤에
    주소를 붙이면 조사기가 첫 조각 「—」 을 두드리려다 어니언 대체 경로를
    잃습니다.
    """
    s = (값 or "").strip().strip("-—– ").strip().lower()
    return not s or s in 자리표시자 or s == "없음"


def _점살리기(주소: str) -> str:
    """`abc[.]onion` 처럼 점을 대괄호로 감싼 주소를 점으로 되돌립니다."""
    return (주소 or "").replace("[.]", ".")


def _주소열쇠(조각: str) -> str:
    """같은 주소인지 가를 열쇠. 앞의 http:// · 뒤의 / · 대소문자를 뗍니다.

    `[.]` 도 점으로 봅니다. 사람이 `abc[.]onion` 으로 적은 주소와 기계가 본
    `abc.onion` 은 같은 주소입니다.
    """
    s = _점살리기((조각 or "").strip().lower())
    s = re.sub(r"^[a-z][a-z0-9+.-]*://", "", s)
    return s.rstrip("/")


# 칸 안의 주소 조각. 점이 들어 있고 글자가 섞인 것만 주소로 본다.
# 「(2026-07-30 확인)」 같은 꼬리와 괄호 · 따옴표는 주소가 아니다
_주소조각 = re.compile(r"[^\s,·()<>\"']+\.[^\s,·()<>\"']+")


def _주소조각들(s: str) -> list[str]:
    return [t for t in _주소조각.findall(s or "") if re.search(r"[a-z]", t, re.I)]


def _이어붙이기(기존: str, 새것) -> str:
    """기존 값은 그대로 두고, 없던 주소만 맨 뒤에 한 줄씩 붙입니다.

    **맨 뒤에 붙이는 까닭.** 조사기는 여러 줄 중 첫 주소만 두드립니다
    (`probe/forum.py` 의 `_어니언정리`). 사람이 먼저 적어 둔 주소가 계속
    먼저 두드려집니다.

    같은 주소인지는 `_주소열쇠()` 로 봅니다. 기존 줄에 「abc.onion (2026-07-30
    확인)」 처럼 꼬리가 붙어 있어도 주소 조각끼리 견줍니다.

    **새 줄도 주소마다 봅니다.** 랜섬 조사기는 미러 여럿을 「a · b · c」 한 줄로
    넘깁니다. 전에는 줄의 첫 주소만 보고 붙일지 정해서, 첫 주소가 새것이면
    이미 있던 b · c 까지 통째로 붙고(2026-09-24 첫 쓰기에서 랜섬 9줄), 첫 주소가
    있던 것이면 뒤의 새 미러를 놓쳤습니다. 이제 없던 주소만 골라 한 줄로 붙입니다.
    """
    새것 = str(새것 or "").strip()
    기존 = (기존 or "").strip()
    if not 새것:
        return 기존
    if _빈값(기존):
        return 새것
    있는것 = {_주소열쇠(t) for t in _주소조각들(기존)}
    붙일것 = []
    for 줄 in 새것.splitlines():
        새조각 = []
        for t in _주소조각들(줄):
            열쇠 = _주소열쇠(t)
            if 열쇠 and 열쇠 not in 있는것:
                새조각.append(t)
                있는것.add(열쇠)
        if 새조각:
            붙일것.append(" · ".join(새조각))
    return 기존 + "\n" + "\n".join(붙일것) if 붙일것 else 기존


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
    if t == "status":
        # 원본(Notion-DLS/notion.py read_value)에 있던 갈래입니다. 옮겨
        # 오면서 빠졌습니다. 이것이 없으면 status 타입 칸의 지금 값을 늘
        # "" 로 읽습니다. 「상태」가 status 타입이면 반영() 의
        # 사람판정_상태 검사와 노션값() 의 압수됨·인계됨 보호가
        # 한 번도 안 걸려, 사람이 판정해 둔 줄을 online 이 덮습니다.
        # 아래 _속성으로() 에 status 쓰기를 더하면서 같이 되살립니다.
        return (prop.get("status") or {}).get("name", "") or ""
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
            # 이름을 100자로 자릅니다. 노션 select·status 이름 상한이고,
            # 넘기면 그 줄이 400 으로 실패합니다. 원본
            # (Notion-DLS/notion.py build_value)이 [:100] 을 걸어 두었는데
            # 옮겨 오면서 빠졌습니다. 「어떤 곳인지」처럼 긴 글이 select 인
            # 칸이 하나라도 있으면 그 줄만 조용히 못 씁니다.
            out[칸] = {"select": {"name": str(v)[:100]}}
        elif t == "status":
            # status 는 select 와 **다른 타입**입니다. 이 갈래가 없어서
            # else 로 떨어져 rich_text 를 보내고 있었고, 노션은 그 줄에
            # 400 을 냅니다(반영() 의 update_page 가 r.오류 로 잡아 화면에만
            # 남고, 그 줄은 조용히 안 써집니다).
            # 읽는 쪽 _옵션읽기() 는 status 를 이미 보고 있었으니
            # 어긋남이었습니다.
            #
            # **status 는 옵션 자동 생성이 안 됩니다.** 스키마에 이미 있는
            # 이름이어야 하고, 그 검사는 반영() 3단계 선택지 검사가 합니다
            # (_옵션읽기() 가 status 옵션도 담아 둡니다).
            out[칸] = {"status": {"name": str(v)[:100]}}
        elif t == "multi_select":
            이름들 = v if isinstance(v, list) else [v]
            out[칸] = {"multi_select": [{"name": str(x)[:100]} for x in 이름들]}
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
        if r.금지칸:
            # 사람이 판단하는 칸에 기계 값이 왔습니다. 안 썼지만 알립니다.
            줄들.append(f"  {' ' * 폭}!! 사람 칸이라 안 쓴 값: {' · '.join(r.금지칸)}")
            문제 += 1
    줄들.append("")
    머리 = "썼습니다" if apply else "미리보기입니다. --apply 를 주면 씁니다"
    줄들.append(f"  {머리} — 바뀔 줄 {바뀜} · 그대로 {len(결과)-바뀜-문제} · 살펴볼 것 {문제}")
    return "\n".join(줄들)
