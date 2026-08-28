"""명부 한 줄.

다크웹 DB 세 개(포럼·텔레그램·랜섬웨어)가 24칸을 공유합니다. 대상이
포럼이든 채널이든 랜섬 그룹이든, 알아내야 하는 것이 같습니다.

    어디가 있나 · 지금 살아있나 · 얼마나 큰가

그래서 조사 방법만 갈래마다 다르고, 내놓는 것은 이 한 가지입니다.

지키는 것 셋입니다.

  1. **노션 칸을 늘리지 않습니다.** 다크웹 DB 스키마가 LLM 다크웹 RAG 의
     근간이라 바꾸면 그쪽이 흔들립니다. 기존 칸만 씁니다.
  2. **사람이 쓴 것을 안 지웁니다.** `규모` 칸에 사람이 적은 조사 결과가
     섞여 있습니다. 그 자체가 결과라 지우면 안 됩니다.
  3. **못 본 것을 없음으로 적지 않습니다.** 못 봤으면 왜인지 남깁니다.
     빈칸으로 두면 나중에 실제로 빈 것으로 읽힙니다.

숫자는 우리 쪽 SQLite 에 시계열로 쌓고, 노션에는 사람이 읽을 한 줄만
넣습니다. 그래야 언제부터 죽었는지, 구독자가 줄고 있는지를 볼 수 있습니다.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

__all__ = ["Place", "기계칸", "지금", "규모합치기", "기계가_쓴_줄"]


def 지금() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


# 기계가 채워도 되는 노션 칸입니다. 전부 기존 칸입니다.
# 이 목록 밖을 쓰면 사람이 조사한 것을 지웁니다.
기계칸 = {"상태", "규모", "확인일", "주소", "어니언 주소", "최근 활동"}

# 기계가 쓴 줄을 알아보는 꼴입니다. 사람 글과 갈라내려는 것입니다.
#   구독자 8,145 (2026-08-28 기준)
#   회원 349,000 · 게시물 821,000 (2026-08-28 기준)
_기계줄 = re.compile(
    r"^\s*(?:구독자|회원|게시물|피해 기업)[\s\d,·]*"
    r"(?:구독자|회원|게시물|피해 기업)?[\s\d,·]*"
    r"(?:\s*안팎)?\s*\(\d{4}-\d{2}-\d{2} 기준\)\s*$")


# 숫자만 있는 줄. 이수빈 님이 8/26 에 넣은 "646" 같은 것입니다.
# 새 줄이 같은 것을 더 자세히 말하므로 갈아 끼웁니다.
_숫자만 = re.compile(r"^\s*[\d,\.\s]{1,15}\s*$")


def 기계가_쓴_줄(줄: str) -> bool:
    """새 줄로 갈아 끼워도 되는 줄인가.

    사람이 문장으로 적은 것은 아닙니다. 그것은 조사 결과라 남깁니다.
        구독자 1,440명 (2026.08.04 13:32 GMT+9 기준)   남깁니다
        멤버 수·게시물 수 못 셈 …                        남깁니다
        646                                          갈아 끼웁니다
        구독자 8,145 (2026-08-28 기준)                  갈아 끼웁니다
    """
    줄 = (줄 or "").strip()
    if not 줄:
        return False
    return bool(_기계줄.match(줄)) or bool(_숫자만.match(줄))


def 규모합치기(기존: str, 새줄: str) -> str:
    """기존 값에 새 줄을 얹습니다. 사람 글은 남깁니다.

        빈칸이면            그냥 씁니다
        기계 줄이 있으면    그 줄만 갈아 끼웁니다
        사람 글이 있으면    남기고 맨 앞에 붙입니다

    같은 줄이 이미 있으면 아무것도 안 합니다.
    """
    새줄 = (새줄 or "").strip()
    기존 = (기존 or "").strip()
    if not 새줄:
        return 기존
    if not 기존:
        return 새줄

    줄들 = [l.rstrip() for l in 기존.splitlines()]
    if any(l.strip() == 새줄 for l in 줄들):
        return 기존                       # 이미 같은 줄이 있습니다

    바꿈 = False
    나온것 = []
    for l in 줄들:
        if not 바꿈 and 기계가_쓴_줄(l):
            나온것.append(새줄)           # 옛 기계 줄을 갈아 끼웁니다
            바꿈 = True
        else:
            나온것.append(l)
    if not 바꿈:
        나온것.insert(0, 새줄)            # 사람 글 위에 붙입니다
    return "\n".join(나온것).strip()


@dataclass
class Place:
    """명부 한 줄. 세 갈래가 같은 모양을 씁니다."""

    갈래: str                       # forum · telegram · ransom
    이름: str
    주소: str = ""
    어니언: str = ""

    # ── 기계가 봅니다
    상태: str = "미확인"            # online · offline · 미확인 · 압수됨 · 인계됨
    확인일: str = field(default_factory=지금)
    회원수: int | None = None
    게시물수: int | None = None
    구독자수: int | None = None
    피해기업수: int | None = None
    어림수: bool = False            # t.me 가 8.12K 처럼 줄여 준 값인가
    주소이상: bool = False          # 명부의 주소가 이 갈래 것이 아닙니다
    최근활동: str = ""

    # ── 갈래별 (노션 기존 칸)
    형식: str = ""                  # 랜섬. RaaS · IAB · DLS · 카딩 …
    종류: str = ""                  # 랜섬. group · market

    # ── 어떻게 알았나
    출처: list[str] = field(default_factory=list)
    못본이유: str = ""              # 못 봤으면 왜인지. 빈칸으로 두지 않습니다
    받은곳: str = ""

    def 봤나(self) -> bool:
        return not self.못본이유

    def 규모줄(self) -> str:
        """기계가 쓸 한 줄. 꼴을 하나로 맞춥니다.

        지금 노션에는 사람마다 다른 꼴이 섞여 있어 RAG 가 읽기 어렵습니다.
        기계가 쓰는 줄만이라도 하나로 맞춥니다.
        """
        조각 = []
        if self.구독자수 is not None:
            조각.append(f"구독자 {self.구독자수:,}")
        if self.회원수 is not None:
            조각.append(f"회원 {self.회원수:,}")
        if self.게시물수 is not None:
            조각.append(f"게시물 {self.게시물수:,}")
        if self.피해기업수 is not None:
            조각.append(f"피해 기업 {self.피해기업수:,}")
        if not 조각:
            return ""
        꼬리 = " 안팎" if self.어림수 else ""
        return " · ".join(조각) + 꼬리 + f" ({self.확인일[:10]} 기준)"

    def 노션값(self, 기존규모: str = "") -> dict:
        """노션에 넣을 값. **기존 칸만** 씁니다.

        기존규모 를 주면 사람 글을 남기고 합칩니다.
        못 봤으면 상태와 확인일도 안 건드립니다. 틀린 값을 남기느니
        옛 값을 두는 편이 낫습니다.
        """
        out: dict[str, object] = {"확인일": self.확인일[:10], "상태": self.상태}

        # 명부의 주소가 이 갈래 것이 아니면 조사를 못 했습니다. 그래도
        # 상태는 미확인으로 남깁니다. online 이라고 적혀 있는 것이 근거
        # 없는 값이기 때문입니다. 주소와 규모는 안 건드립니다.
        if self.주소이상:
            return out

        # 못 봤으면 상태와 확인일까지만 남깁니다. 언제 봤는데 못 봤는지가
        # 그 자체로 정보입니다. 규모는 안 건드립니다.
        if not self.봤나():
            return out

        새줄 = self.규모줄()
        if 새줄:
            out["규모"] = 규모합치기(기존규모, 새줄)

        if self.주소:
            out["주소"] = self.주소
        if self.어니언 and self.갈래 == "forum":
            out["어니언 주소"] = self.어니언
        if self.갈래 == "ransom":
            if self.형식:
                out["형식"] = self.형식
            if self.종류:
                out["종류"] = self.종류
            if self.최근활동:
                out["최근 활동"] = self.최근활동[:10]
        return out

    def 숫자들(self) -> dict:
        """우리 쪽 SQLite 에 시계열로 쌓을 값."""
        return {k: v for k, v in {
            "회원수": self.회원수, "게시물수": self.게시물수,
            "구독자수": self.구독자수, "피해기업수": self.피해기업수,
        }.items() if v is not None}

    def dict(self) -> dict:
        return asdict(self)
