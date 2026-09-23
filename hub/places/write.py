"""명부를 노션에 반영합니다.

안유빈 님이 dls_fill.py 에 만든 방식을 그대로 씁니다.

  1. 노션 스키마를 실제로 읽습니다. 칸 이름과 타입을 받아옵니다
  2. 스키마에 없는 칸은 걸러냅니다. 틀린 칸에 쓰다 조용히 건너뛰는 일이
     없게 하려는 것입니다
  3. 기본은 미리보기입니다. --apply 를 줘야 실제로 씁니다
  4. 기계가 쓰는 칸 밖은 안 건드립니다

## 사람 줄에는 쓰지 않습니다. 다르면 「자동 줄」 을 새로 만듭니다 (2026-09-23)

전에는 조사한 값을 명부의 그 줄에 바로 썼습니다. 상태·확인일·주소·어니언 주소·
최근 활동은 덮고, 빈 칸은 채웠습니다. 예약 실행 두 판이 사람 승인 없이 595줄에
그렇게 썼고, 최현서가 방식을 바꿨습니다.

    사람 줄     한 글자도 안 씁니다
    자동 줄     기계가 본 값이 사람 줄과 다를 때만 새로 만듭니다.
                담당자 = 「자동」 · DB 반영 = 끔 · 이름은 사람 줄과 같습니다
                비고에 짝이 되는 사람 줄의 page id 를 적습니다
    그 뒤       자동 줄이 있으면 판마다 그 줄만 고칩니다. 기계 것이라 덮어도 됩니다

「다르다」 의 뜻은 **예전 방식이었으면 사람 줄을 고쳤을 것인가**입니다. 확인일만
다른 것은 안 칩니다 — 판마다 다르므로 그것까지 치면 모든 줄에 자동 줄이 생깁니다.
**규모 같은 합치는 칸도 숫자가 같고 날짜만 다르면 안 칩니다** (`_합친값_같나`).
기계 줄 끝의 「(날짜 기준)」 이 판마다 바뀌기 때문입니다.

사람 줄과 자동 줄을 합치는 것은 나중에 사람이나 LLM 이 합니다. 합친 뒤 자동 줄을
지우면, 다음 판에 다시 다를 때만 새로 생깁니다.

**자동 줄은 조사 대상이 아닙니다.** 줄들() 이 둘을 가르고, 조사기는 사람 줄만
두드립니다. 자동 줄을 두드리면 자동 줄의 자동 줄이 생깁니다.

**노션 칸을 늘리지 않습니다.** 다크웹 DB 스키마가 LLM 다크웹 RAG 의
근간이라 바꾸면 그쪽이 흔들립니다. 자동 줄 표시도 있는 칸(담당자)의 선택지로 합니다.

**못 넣은 칸이 하나라도 있으면 알립니다.** 칸 이름이 틀리면 노션은
오류를 내지 않고 그 칸만 건너뜁니다. 조용히 틀리는 것이 제일 위험합니다.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages"))

from dc_notion import Notion  # noqa: E402

from hub.places.place import (  # noqa: E402
    Place, 기계가_쓴_줄, 기계칸, 빈칸만칸, 사람판정_상태, 자동금지칸, 합치는칸)

__all__ = ["명부", "반영결과", "갈래별_DB", "자동표시"]

# 자동 줄의 담당자 선택지. 세 명부에 사람이 만들어 두었습니다 (2026-09-23)
자동표시 = "자동"

# 자동 줄 비고의 첫 줄. 짝이 되는 사람 줄을 이것으로 찾습니다.
# **이름으로 짝을 찾지 않습니다.** 명부에는 이름이 같은 줄이 있습니다.
짝머리 = "자동 줄 · 사람 줄 "
_짝꼴 = re.compile(re.escape(짝머리) + r"([0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?"
                  r"[0-9a-f]{4}-?[0-9a-f]{12})")
짝설명 = ("조사기가 본 값이 사람 줄과 달라 따로 적은 줄입니다. 사람 줄은 안 건드렸습니다. "
        "맞는 값을 사람 줄로 옮긴 뒤 이 줄을 지우면 됩니다.")


def _짝찾기(비고: str) -> str:
    m = _짝꼴.search(비고 or "")
    return m.group(1).replace("-", "") if m else ""


def _아이디(page_id: str) -> str:
    return (page_id or "").replace("-", "")


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
    자동: bool = False     # 담당자가 「자동」 인 줄. 조사 대상이 아닙니다
    짝: str = ""           # 자동 줄이면 짝이 되는 사람 줄의 page id (하이픈 없이)


@dataclass
class 반영결과:
    이름: str
    바뀐칸: dict = field(default_factory=dict)     # 사람 줄과 다른 칸. 사람 줄에는 안 씁니다
    자동줄: str = ""                               # 새로 · 고침 · 그대로 · "" (자동 줄 없음)
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
        # 사람 줄 page id(하이픈 없이) → 그 짝인 자동 줄. 줄들() 이 채웁니다
        self.자동짝: dict[str, 줄] = {}
        # **「자동」 선택지가 없으면 자동 줄을 안 만듭니다.** 없는 값을 보내면 노션이
        # 선택지를 멋대로 새로 만들거나 400 을 냅니다. 어느 쪽이든 조용히 틀립니다
        self.자동못씀 = ("" if 자동표시 in self.옵션.get("담당자", set()) else
                      f"{self.이름} 담당자 칸에 「{자동표시}」 선택지가 없어 자동 줄을 못 만듭니다")

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
        """명부의 모든 줄. 자동 줄도 들어 있습니다 — `사람줄()` 로 거릅니다."""
        out = []
        self.자동짝 = {}
        for page in self.n.query_all(self.ds):
            props = page.get("properties", {})
            현재 = {칸: _글자(props.get(칸)) for 칸 in 기계칸 if 칸 in props}
            자동 = _글자(props.get("담당자")) == 자동표시
            x = 줄(
                page_id=page["id"],
                이름=_글자(props.get(self.제목칸)),
                주소=_글자(props.get("주소")),
                어니언=_글자(props.get("어니언 주소")),
                규모=_글자(props.get("규모")),
                상태=_글자(props.get("상태")),
                현재=현재,
                자동=자동,
                짝=_짝찾기(_글자(props.get("비고"))) if 자동 else "",
            )
            # 같은 사람 줄에 자동 줄이 둘이면 먼저 읽힌 것 하나만 고칩니다.
            # 나머지는 사람이 합칠 때 같이 봅니다
            if 자동 and x.짝 and x.짝 not in self.자동짝:
                self.자동짝[x.짝] = x
            out.append(x)
        return out

    @staticmethod
    def 사람줄(줄들: list[줄]) -> list[줄]:
        """조사 대상. 자동 줄을 뺍니다."""
        return [x for x in 줄들 if not x.자동]

    # ── 쓰기 ────────────────────────────────────────────────────────
    def 반영(self, 줄: 줄, p: Place, *, apply: bool = False) -> 반영결과:
        """사람 줄 `줄` 을 조사한 결과 `p` 를 반영합니다. **사람 줄에는 안 씁니다.**

        기계가 본 값이 사람 줄과 다르면 자동 줄을 새로 만들고, 이미 있으면 그 줄을
        고칩니다. 머리말의 「사람 줄에는 쓰지 않습니다」 를 봅니다.
        """
        if 줄.자동:
            # 조사기는 사람줄() 만 넘깁니다. 여기 오면 부르는 쪽이 틀렸습니다.
            # 조용히 넘기면 자동 줄의 자동 줄이 생깁니다
            raise ValueError(f"자동 줄은 조사 대상이 아닙니다: {줄.이름}")
        r = 반영결과(이름=줄.이름 or p.이름)
        if 줄.현재.get("상태") in 사람판정_상태 and p.상태 in ("online", "offline"):
            r.사람판정 = (f"사람이 「{줄.현재['상태']}」 으로 판정한 줄입니다. "
                      f"기계는 {p.상태} 로 봤지만 상태를 안 건드립니다")
        값 = p.노션값(줄.현재 or 줄.규모)
        if not 값:
            r.안바뀜 = True
            return r

        # 0. **자동금지칸은 어느 조사기가 값을 채워 보내도 안 씁니다.**
        #    통합 전 저장소의 report_generator.FORBIDDEN_AUTO_FIELDS 가
        #    하던 일입니다. 노션에 닿기 직전 한 자리에서 봅니다 —
        #    조사기마다 지키게 하면 새 조사기가 붙을 때 빠집니다.
        #    지금은 노션값() 이 이 칸들을 안 내므로 걸릴 일이 없습니다.
        #    걸린다면 그것이 바로 알아야 하는 일이라 조용히 안 버립니다.
        #
        #    자동 줄을 만들 때 담당자 · 비고 · DB 반영은 여기를 안 지나고
        #    _자동줄만들기() 가 따로 넣습니다. 조사 값이 아니라 표시입니다.
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

        # 2. 선택지에 없는 값을 거릅니다. 갈래마다 선택지가 다릅니다.
        #    포럼 DB 에는 「직접 확인」 출처도, 「압수됨」 상태도 없습니다.
        #
        #    **사람이 이미 쓴 칸의 값도 여기서는 남깁니다.** 자동 줄은 기계가 본
        #    것을 다 적는 자리라, 사람 값과 나란히 놓고 볼 수 있어야 합니다.
        기계값, 없는옵션 = {}, []
        for 칸, v in 쓸것.items():
            받는값 = self.옵션.get(칸)
            if 받는값 is None:
                기계값[칸] = v
                continue
            if isinstance(v, list):
                남 = [x for x in v if x in 받는값]
                없는옵션 += [f"{칸}={x}" for x in v if x not in 받는값]
                if 남:
                    기계값[칸] = 남
            elif v in 받는값:
                기계값[칸] = v
            else:
                없는옵션.append(f"{칸}={v}")
        r.없는옵션 = 없는옵션

        # 3. 사람 줄과 견줍니다. **예전이면 사람 줄을 고쳤을 칸**이 「다른 칸」 입니다.
        #    빈칸만칸은 사람이 이미 쓴 것이면 안 쳤습니다. 그 규칙을 그대로 둡니다 —
        #    사람이 「영어」 라 쓴 것을 기계가 「English」 로 봤다고 자동 줄을 만들면
        #    거의 모든 줄에 자동 줄이 생깁니다.
        r.사람글 = [칸 for 칸 in 기계값
                  if 칸 in 빈칸만칸 and _사람이_쓴것(줄.현재.get(칸) or "")]
        다른칸 = {}
        for 칸, v in 기계값.items():
            if 칸 in r.사람글 or 칸 == "확인일":
                # 확인일은 판마다 다릅니다. 이것까지 치면 모든 줄에 자동 줄이 생깁니다
                continue
            지금 = 줄.현재.get(칸, {"규모": 줄.규모, "상태": 줄.상태,
                                 "주소": 줄.주소}.get(칸))
            if 지금 is not None and _칸같나(칸, 지금, v):
                continue
            다른칸[칸] = v
        r.바뀐칸 = 다른칸

        짝 = self.자동짝.get(_아이디(줄.page_id))
        if 짝 is None:
            if not 다른칸:
                r.안바뀜 = True
                return r
            r.자동줄 = "새로"
            if not apply:
                return r
            if self.자동못씀:
                r.오류 = self.자동못씀
                return r
            try:
                self.자동짝[_아이디(줄.page_id)] = self._자동줄만들기(줄, 기계값)
            except Exception as e:  # noqa: BLE001
                r.오류 = str(e).replace("\n", " ")[:200]
            return r

        # 4. 자동 줄이 이미 있습니다. 기계 것이라 판마다 그 줄을 고칩니다.
        #    사람 줄과 같아졌어도 고칩니다 — 그 줄은 기계가 마지막으로 본 값을 적는
        #    자리입니다. 지울지는 합치는 사람이 정합니다.
        #
        #    확인일만 바뀌는 것도 **두드린 것이면** 씁니다. 403 · 404 · 429 로 막힌
        #    줄은 상태가 계속 미확인이라, 「우리가 오늘 이 줄을 두드렸다」 는 사실이
        #    아예 안 남았습니다. 두드리지도 못한 줄은 노션값() 이 이미 걸렀습니다.
        자동바꿀것 = {칸: v for 칸, v in 기계값.items()
                  if not _칸같나(칸, 짝.현재.get(칸, ""), v)}
        if not 자동바꿀것 or (set(자동바꿀것) <= {"확인일"} and not p.두드림):
            r.자동줄 = "그대로"
            r.안바뀜 = not 다른칸
            return r
        r.자동줄 = "고침"
        if not apply:
            return r
        try:
            self.n.update_page(짝.page_id, _속성으로(자동바꿀것, self.스키마))
            짝.현재.update({칸: _읽은꼴(v) for 칸, v in 자동바꿀것.items()})
        except Exception as e:  # noqa: BLE001
            r.오류 = str(e).replace("\n", " ")[:200]
        return r

    def _자동줄만들기(self, 사람: 줄, 기계값: dict) -> 줄:
        """사람 줄 `사람` 의 짝인 자동 줄을 새로 만듭니다.

        이름은 사람 줄과 같게 둡니다. 합칠 때 이름으로 나란히 놓고 봅니다.
        짝은 이름이 아니라 비고의 page id 로 찾습니다.
        """
        props = _속성으로(기계값, self.스키마)
        props[self.제목칸] = {"title": [{"text": {"content": (사람.이름 or "")[:2000]}}]}
        표시 = {"담당자": 자동표시, "비고": 짝머리 + 사람.page_id + "\n" + 짝설명}
        props.update(_속성으로({k: v for k, v in 표시.items() if k in self.스키마},
                             self.스키마))
        if "DB 반영" in self.스키마:
            # **자동 줄은 공개하지 않습니다.** DB 반영은 지도 · RAG · 가이드가 같이
            # 보는 공개 스위치입니다. 사람이 합친 사람 줄이 공개됩니다
            props["DB 반영"] = {"checkbox": False}
        res = self.n.request("POST", "/pages", {
            "parent": {"type": "data_source_id", "data_source_id": self.ds},
            "properties": props,
        }) or {}
        return 줄(page_id=res.get("id", ""), 이름=사람.이름,
                 현재={칸: _읽은꼴(v) for 칸, v in 기계값.items()},
                 자동=True, 짝=_아이디(사람.page_id))


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
    선택(목록)이 늘 다르게 나왔습니다. 사람 줄에 쓸 때는 빈칸만칸 규칙이 가려
    드러나지 않았는데, 자동 줄은 판마다 견주므로 그대로 두면 판마다 고칩니다.
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
    바뀝니다. 이것까지 다르다고 치면 규모를 적어 둔 사람 줄마다 자동 짝 줄이
    생겨 명부가 두 배가 됩니다. 「확인일만 다른 것은 안 친다」 와 같은 논리입니다.
    첫 미리보기에서 텔레그램 자동 줄 12개가 전부 이 까닭이었습니다.

        사람 글         글자 그대로 견줍니다
        기계 줄         날짜를 떼고 숫자만 견줍니다. 여럿이면 전부 같아야 같습니다
        숫자 못 뽑음    글자 그대로 견줍니다

    **견주는 규칙만 바꿉니다.** 자동 줄에 쓸 때는 기계가 본 값을 날짜째 씁니다.
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
    새로 = 고침 = 문제 = 0
    for r in 결과:
        if r.오류:
            줄들.append(f"  {r.이름[:폭-2].ljust(폭)}실패 — {r.오류[:60]}")
            문제 += 1
        elif r.안바뀜:
            줄들.append(f"  {r.이름[:폭-2].ljust(폭)}그대로")
        else:
            무엇 = " · ".join(f"{k}={str(v)[:32]}" for k, v in r.바뀐칸.items())
            줄들.append(f"  {r.이름[:폭-2].ljust(폭)}자동 줄 {r.자동줄} · {무엇 or '확인일'}")
            새로 += r.자동줄 == "새로"
            고침 += r.자동줄 == "고침"
        if r.건너뛴칸:
            줄들.append(f"  {' ' * 폭}!! 스키마에 없는 칸: {' · '.join(r.건너뛴칸)}")

            문제 += 1
        if r.금지칸:
            # 사람이 판단하는 칸에 기계 값이 왔습니다. 안 썼지만 알립니다.
            줄들.append(f"  {' ' * 폭}!! 사람 칸이라 안 쓴 값: {' · '.join(r.금지칸)}")
            문제 += 1
    줄들.append("")
    머리 = "썼습니다" if apply else "미리보기입니다. --apply 를 주면 씁니다"
    줄들.append(f"  {머리} — 자동 줄 새로 {새로} · 고침 {고침} · 살펴볼 것 {문제}"
               f" · 사람 줄은 안 건드립니다")
    return "\n".join(줄들)
