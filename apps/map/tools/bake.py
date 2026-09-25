#!/usr/bin/env python3
"""노션에서 지도 재료를 뽑아 `src/data/map.json` 한 장으로 굽는다.

    NOTION_TOKEN_FILE=~/.config/darkchoco/NOTION_TOKEN_산출물.txt \
      python tools/bake.py --out src/data/map.json

**화면이 노션을 직접 보지 않는다.** 배포 전에 한 번 굽고, 화면은 구운 파일만
읽는다. 화면에서 노션을 부르면 반출 관문이 사라지기 때문이다 (프젝 `DEV.md`).

반출을 네 겹으로 막는다.

  1. 줄 관문      「DB 반영」이 꺼졌거나 「검토 여부」가 미검토·사건 X 면 뺀다
  2. 읽는 칸      `ALLOWED_COLS` 에 없는 칸을 읽으려 하면 멈춘다. 원문 URL ·
                 자료 제목 · 대상 조직 · 다크웹 주소는 `DENY_COLS` 다
  3. 나가는 키    `TERRITORY_KEYS` · `EV_KEYS` · `RELATION_KEYS` 에 없는 키가
                 있으면 멈춘다
  4. 값 훑기      다 만든 뒤 JSON 에서 도메인 · `@` · 긴 숫자열을 찾는다

**셋째가 가장 세다.** 넷째는 값 모양만 보므로 피해 조직 이름처럼 점도 @도
없는 평범한 낱말은 그냥 통과한다. 키로 막으면 값이 무엇이든 걸린다.

첫 둘은 사람이 빠뜨릴 수 있고 실제로 두 번 뚫렸다
(`~/dcsite/apps/site/tools/build_data.py` 주석: 2026-09-03 목록 밖 TLD,
2026-09-07 검사 함수를 부르는 데가 없었음).

**DB id 를 이 파일에 박지 않는다.** 이 저장소는 공개될 수 있다. 환경변수나
`~/.config/darkchoco/map_sources.json` 에서 읽는다.

**영토는 명부 DB 셋과 게시자 핸들에서 만든다** (설계서 2.4 · 2.5).
포럼 · 텔레그램 · 랜섬웨어 DB 의 줄이 영토이고, 사건이 없어도 싣는다
(2026-09-23 최현서 결정). 사건은 게시처 · 게시 플랫폼으로 명부 줄에 맞춘다.

**행위자 섬은 수집 DB 「게시자 핸들」에서 만든다** (2026-09-25 최현서 결정).
관문을 지난 사건에 적힌 핸들 하나가 행위자 영토 하나다. 행위자 DB 는 지도가
안 읽는다 — 행위자 탭을 따로 만들게 되면 그때 쓴다.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── 부품 찾기 ───────────────────────────────────────────────────────────────


def _load_dc_notion():
    """팀 레포의 `dc_notion` 을 얹는다. 없으면 어디를 봤는지 알리고 멈춘다."""
    places = [
        Path(os.environ["DC_PACKAGES"]) if os.environ.get("DC_PACKAGES") else None,
        Path.home() / "darkchoco-team" / "packages",
    ]
    for p in places:
        if p and (p / "dc_notion" / "__init__.py").is_file():
            sys.path.insert(0, str(p))
            import dc_notion  # noqa: PLC0415

            return dc_notion
    looked = "\n".join(f"  {p}" for p in places if p)
    sys.exit(
        "dc_notion 을 못 찾았습니다. 아래를 봤습니다.\n"
        f"{looked}\n"
        "팀 레포를 받았다면 DC_PACKAGES 로 packages 폴더를 가리켜 주세요."
    )


# ── 어느 DB 를 읽는가 ───────────────────────────────────────────────────────

SOURCES_FILE = Path.home() / ".config" / "darkchoco" / "map_sources.json"


#: 꼭 있어야 하는 DB. 명부 셋(포럼 · 텔레그램 · 랜섬웨어)이 영토가 된다
#: (설계서 2.4 · 2.5, 2026-09-23 최현서 결정). 행위자 DB 는 안 읽는다 —
#: 행위자 섬은 수집 DB 게시자 핸들에서 만든다 (2026-09-25 최현서 결정)
REQUIRED_SOURCES = ("collect", "verify", "forum", "telegram", "ransomware")


def load_sources() -> dict[str, str]:
    """읽을 DB 의 data_source id 를 찾는다.

    **`database id` 와 `data_source id` 가 다르다.** `/data_sources/<database
    id>` 로 부르면 404 다. 설계서 5.1-10 이 「공유가 안 되어 404」로 적어 둔 것이
    실제로는 이 혼동이었다. 여기서 받는 것은 data_source id 다.

    환경변수 `DC_MAP_<KEY>_DS`(예: `DC_MAP_FORUM_DS`)가 파일보다 앞선다.
    관계선 DB(`relations`)는 없어도 굽는다. 없으면 관계선이 비고 로그에 남는다.
    """
    got: dict[str, str] = {}
    if SOURCES_FILE.is_file():
        got.update({k: v for k, v in json.loads(SOURCES_FILE.read_text(encoding="utf-8")).items()
                    if k != "_" and v})
    for key in (*REQUIRED_SOURCES, "relations"):
        env = os.environ.get(f"DC_MAP_{key.upper()}_DS")
        if env:
            got[key] = env
    missing = [k for k in REQUIRED_SOURCES if not got.get(k)]
    if missing:
        sys.exit(
            f"읽을 DB 를 못 정했습니다: {', '.join(missing)}\n"
            f"  {SOURCES_FILE} 에 적거나 DC_MAP_<KEY>_DS 로 알려 주세요.\n"
            "  값은 database id 가 아니라 data_source id 입니다."
        )
    return got


# ── 설계서 2.3 · 2.4 대응 ───────────────────────────────────────────────────

#: 수집 DB 「소스」 → 섬 코드. **빈 값은 지도에서 뺀다** (설계서 2.5).
#: 미분류 섬은 2026-09-23 에 없앴다 — 정본대로 소스 · 게시 플랫폼 · 게시 시각
#: 가운데 하나라도 비면 뺀다 (최현서 결정)
ISLAND_OF_SOURCE = {"포럼": "FORUM", "랜섬웨어": "RANSOMWARE", "텔레그램": "TELEGRAM"}

#: 명부 DB 마다 섬 코드와 이름 칸. 이름 칸이 곧 영토 이름이다
REGISTRY = {
    "forum": ("FORUM", "포럼 이름"),
    "ransomware": ("RANSOMWARE", "그룹 이름"),
    "telegram": ("TELEGRAM", "채널 이름"),
}

#: 섬 차례. 영토 목록도 이 차례로 싣는다 (정본 영토 탭과 같다)
ISLAND_ORDER = ("FORUM", "RANSOMWARE", "TELEGRAM", "ACTOR")

#: 검증 DB 「진위 판정」 → `Verdict` (`types.ts`)
VERDICT_OF = {
    "확인됨": "confirmed",
    "신뢰성 높음": "high",
    "미확인": "unknown",
    "신뢰성 낮음": "low",
    "허위": "false",
}

#: 검증 DB 에 줄이 없는 사건. 설계서 2.5 신뢰도 표에 이 줄이 빠져 있다
UNVERIFIED = "unverified"

#: 수집 DB 「규모 등급」 → `SizeGrade` (`types.ts`). 비어 있으면
#: 「주장 규모」 글에서 `size_grade()` 가 읽는다.
#:
#: **2026-09-22 에 노션에 생긴 칸이다.** 설계서 5.1 이 「이 칸이 없다」고
#: 미정으로 적어 두었던 것이 풀렸다. 선택지가 설계서 3.2 의 가중치 표와
#: 글자까지 같다. 아직 값이 채워지지 않아 실제로는 전부 모름으로 떨어진다.
SIZE_OF = {"큼": "large", "중간": "medium", "작음": "small", "모름": "unknown"}

#: 「중복 관계」가 이 값이면 재게시로 본다 (설계서 3.2 중복 가중치).
#: 「일부 조건이 다른 같은 케이스」는 팀이 정하기 전까지 처음 게시로 둔다
REPOST_VALUES = {"재게시", "아예 동일 케이스"}

#: 관계선 DB 「출발 섬」·「도착 섬」 → 섬 코드. 미분류는 관계선 DB 선택지에 없다
ISLAND_OF_NAME = {
    "포럼": "FORUM", "랜섬웨어": "RANSOMWARE", "텔레그램": "TELEGRAM", "행위자": "ACTOR",
}

#: 관계선 DB 「관계 종류」 → `RelationKind` (`types.ts`).
#: 「확인 필요」는 여기 없다 — 종류를 짐작해 채우지 않고 뺀다 (설계서 2.5)
KIND_OF = {
    "제휴자 모집": "affiliate",
    "공지·연락": "contact",
    "데이터 유출": "leak",
    "접근 공급": "access",
    "데이터 판매": "sale",
    "후속": "successor",
    "활동": "activity",
}

#: 관계선 DB 「확실한 정도」 → `Confidence` (`types.ts`)
CONF_OF = {"확인됨": "confirmed", "높은 신뢰": "high", "추정": "estimated"}

#: **노션에서 읽어도 되는 칸.** 여기 없는 칸을 읽으려 하면 굽기가 멈춘다.
#:
#: 반출을 막는 첫 겹이다. 굽기는 41칸 중 필요한 것만 읽는데, 그 「필요한 것」이
#: 코드 본문에 문자열로 흩어져 있으면 누가 한 줄 더 적어도 아무도 못 막는다.
#: 목록을 한자리에 모으고 `col()` 을 거치게 해서, 칸을 늘리려면 이 목록을
#: 고치게 만든다 — 고치는 순간 사람이 한 번 더 생각하게 된다.
ALLOWED_COLS = frozenset({
    "DB 반영",
    "진위 판정",
    "수집 줄",
    "검토 여부",
    "게시 시각",
    "게시처",
    "게시 플랫폼",
    "소스",
    "중복 관계",
    "사건 ID",
    "규모 등급",
    "주장 규모",
    # ↓ 관계선 DB. 「근거 사건 수」·「처음 본 날」·「마지막 본 날」은 안 읽는다 —
    #   화면이 기준일마다 사건에서 센다 (작업판 업데이트 탭 10단계).
    #   노션 값은 정본이 아니고 지금 25줄 모두 비어 있다
    "관계 ID",
    "출발 섬",
    "출발 영토",
    "도착 섬",
    "도착 영토",
    "관계 종류",
    "확실한 정도",
    "근거 사건 ID",
    # ↓ 수집 DB. 랜섬웨어 사건은 한국 관련이 「직접」이어야 든다 (정본 사건!N).
    #   게시 시각이 없으면 관측 시각, 그것도 없으면 수집일을 대신 넣는다 (업데이트 탭)
    "한국 관련",
    "관측 시각",
    "수집일",
    # ↓ 명부 DB 넷. 이름 칸이 영토 이름이 된다. 규모는 활동도 원자료다
    "포럼 이름",
    "채널 이름",
    "그룹 이름",
    "상태",
    "규모",
    "이전 이름·별칭",  # 사건을 영토에 맞추는 데만 쓴다. 밖에 안 낸다
    # ↓ 수집 DB. **행위자 영토 이름이 된다** (2026-09-25 최현서 결정). 전에는
    #   맞추기 전용이라 밖에 안 냈다. 관문을 지난 사건의 핸들만 쓰고, 값 훑기
    #   (`scan_strings`)가 @ · 주소 · 긴 숫자열을 한 번 더 막는다
    "게시자 핸들",
})

#: **맞추는 데만 쓰는 칸.** 값을 읽되 구운 파일에 절대 안 싣는다.
#:
#: 지금은 없다. 「게시자 핸들」이 여기 있었는데 2026-09-25 에 행위자 영토
#: 이름으로 내기로 해서 `ALLOWED_COLS` 로 옮겼다. 그때 핸들 모양을 셌다 —
#: 관문을 지난 사건(랜섬웨어 섬 제외)의 핸들 22개에 @ · 주소 · 긴 숫자 ·
#: 한글 · 빈칸 섞임이 하나도 없었다.
MATCH_ONLY_COLS: frozenset[str] = frozenset()

#: **절대 읽지 않는 칸.** 값에 개인정보나 피해 조직 이름이 들어 있다.
#:
#: 허용 목록만으로도 막히지만 이름을 적어 둔다. 왜 안 읽는지가 보여야
#: 나중에 누가 「이것도 필요한데」 하고 허용 목록에 옮기기 전에 멈춘다.
DENY_COLS = frozenset({
    "대상 조직",      # 피해 조직 이름 (2026-09-23 최현서 결정: 지도에 안 낸다)
    "자료 제목",      # 196줄 중 172줄에 대상 조직 표기가 들어 있다
    "원문 URL",
    # ↓ 명부 DB. 다크웹 주소와 접속 방법, 사람이 쓴 설명이다
    "주소",
    "어니언 주소",
    "이전 주소",
    "들어가는 법",
    "연락수단",
    "지갑 주소",
    "텔레그램",
    "어떤 곳인지",
    "추론 근거",
    "개인정보 유출",
    "한국 관련 유출",
    "피해 대상",
    "연결된 곳",
    "다루는 것",
    "한국 관련 근거",
    "관측 근거",
    "비고",
    "샘플",
    "UID",
    "수집자",
    "관측자",
    "검증자",
    "근거",          # 관계선 DB. 사람이 쓴 설명이라 무엇이 적혀 있을지 모른다
})


def col_prop(props: dict, name: str):
    """`col()` 과 같은데 값이 아니라 노션 prop 객체를 돌려준다.

    relation 과 unique_id 는 `read_value` 가 안 다뤄서 객체를 직접 봐야 한다.
    """
    col(lambda _p: None, props, name)  # 이름만 검사한다
    return props.get(name)


def col(read, props: dict, name: str):
    """노션 칸 하나를 읽는다. **허용 목록에 없으면 멈춘다.**"""
    if name in DENY_COLS:
        raise SystemExit(
            f"읽으면 안 되는 칸입니다: {name} — "
            "개인정보나 피해 조직 이름이 들어 있습니다. "
            "정말 필요하면 DENY_COLS 에서 빼기 전에 최현서에게 확인하세요."
        )
    if name in MATCH_ONLY_COLS:
        raise SystemExit(f"맞추기 전용 칸입니다: {name} — col_match() 로 읽으세요")
    if name not in ALLOWED_COLS:
        raise SystemExit(
            f"허용 목록에 없는 칸을 읽으려 했습니다: {name} — "
            "tools/bake.py 의 ALLOWED_COLS 에 더하세요. "
            "더하기 전에 그 칸 값이 밖에 나가도 되는지 보세요."
        )
    return read(props.get(name))


def col_match(read, props: dict, name: str) -> str | None:
    """맞추기 전용 칸을 읽는다. 돌려준 값은 비교에만 쓰고 어디에도 담지 않는다."""
    if name not in MATCH_ONLY_COLS:
        raise SystemExit(f"맞추기 전용 칸이 아닙니다: {name}")
    v = read(props.get(name))
    return v.strip() if isinstance(v, str) and v.strip() else None


#: **구운 파일에 나가도 되는 키.** 여기 없는 키가 있으면 굽기가 멈춘다.
#:
#: 반출을 막는 마지막 겹이고 이것이 가장 세다. 값 검사(`scan_strings`)는
#: 도메인 · `@` · 긴 숫자열만 보므로 **조직 이름처럼 평범한 낱말은 그냥 통과한다.**
#: 키로 막으면 값이 무엇이든 새 칸이면 무조건 걸린다.
#: **별칭(aliases)은 싣지 않는다.** 명부 「이전 이름·별칭」·「다른 이름」은 사람이
#: 쓰는 칸이라 자리표시 · 출처 메모 · 다른 핸들이 섞인다. 맞추는 데만 쓴다.
#: 이 목록에서 뺐으므로 별칭이 새면 검사가 걸린다 (2026-09-23 검토에서 찾음)
TERRITORY_KEYS = frozenset({
    "id", "name", "islandId", "web",
    # 활동도 원자료(숫자)와 처음 나온 날 (설계서 3.3, score.ts presentAt)
    "raw", "posts", "threads", "since",
})
EV_KEYS = frozenset({
    "id", "territoryId", "postedAt", "verdict", "size", "repost", "excluded",
    # 행위자 섬 영토 id(핸들 글자가 아니다)와 날짜를 대신 넣었다는 표시
    "actorTerritoryId", "dateSubstituted",
})
#: 관계선. 건수와 처음·마지막 본 날은 싣지 않는다 — 화면이 `evidence` 로 센다
RELATION_KEYS = frozenset({"id", "from", "to", "kind", "confidence", "evidence"})

#: 다크웹 섬 코드 (설계서 2.3). 미분류는 2026-09-23 에 없앴다.
#: `islands.ts` 의 `DARK_ISLANDS` 와 같아야 한다. 섬 이름과 색은 거기 있고
#: 굽기는 코드만 알면 된다 — 참조 검사에 쓴다
DARK_ISLAND_CODES = set(ISLAND_ORDER)



# ── 규모 등급 읽기 (설계서 3.2, 판 1.2) ─────────────────────────────────────

#: 등급 경계. 설계서 3.2 표 그대로다
BIG_ROWS, BIG_BYTES = 1_000_000, 100 * 1024**3
MID_ROWS, MID_BYTES = 100_000, 10 * 1024**3

#: 용량 단위 → 바이트
UNIT_BYTES = {"kb": 1024, "mb": 1024**2, "gb": 1024**3, "tb": 1024**4}

#: 한글 자릿수
UNIT_KO = {"만": 10_000, "억": 100_000_000}

#: 건수를 세는 낱말. 이것이 붙어야 「행 수」로 읽는다
COUNT_WORDS = "건|행|명|개|건수|files?|rows?|records?|entries|accounts?"

RE_BYTES = re.compile(
    r"([\d][\d,\. ]*)\s*(TB|GB|MB|KB)\b", re.IGNORECASE
)
RE_KO = re.compile(r"([\d][\d,\. ]*)\s*(만|억)")
RE_COUNT = re.compile(
    rf"([\d][\d,\. ]*)\s*(?:{COUNT_WORDS})", re.IGNORECASE
)
RE_SI = re.compile(r"([\d][\d,\. ]*)\s*([KMkm])\b")


def _num(s: str) -> float | None:
    """`1,156,455` · `9 000 000` · `46.6` 을 숫자로.

    **띄어 쓴 숫자를 받아야 한다** — 설계서 3.2 가 「"9 000 000"처럼 띄어 쓴
    숫자 포함」이라고 못박았다. 쉼표와 빈칸을 떼고 읽는다.
    """
    clean = s.replace(",", "").replace(" ", "").rstrip(".")
    try:
        return float(clean)
    except ValueError:
        return None


def size_grade(raw: str | None) -> str:
    """「주장 규모」 글에서 숫자와 단위를 읽어 등급을 매긴다.

    **등급 칸을 새로 만들지 않는다** (설계서 3.2, 판 1.2). 사람이 자유롭게
    적은 글에서 읽을 수 있을 때만 등급이 나오고, 못 읽으면 모름이다.

    한 줄에 여러 숫자가 있으면 **가장 큰 등급**을 쓴다. 「200만 행 · 7GB」처럼
    두 잣대가 같이 적힌 경우가 있는데, 둘 중 하나라도 큼이면 큰 유출이다.
    """
    if not raw:
        return "unknown"
    s = raw.strip()
    if not s:
        return "unknown"

    rows = 0.0
    byts = 0.0

    for num, unit in RE_BYTES.findall(s):
        v = _num(num)
        if v is not None:
            byts = max(byts, v * UNIT_BYTES[unit.lower()])

    for num, unit in RE_KO.findall(s):
        v = _num(num)
        if v is not None:
            rows = max(rows, v * UNIT_KO[unit])

    for num in RE_COUNT.findall(s):
        v = _num(num)
        if v is not None:
            rows = max(rows, v)

    for num, unit in RE_SI.findall(s):
        v = _num(num)
        if v is not None:
            rows = max(rows, v * (1_000 if unit.lower() == "k" else 1_000_000))

    if rows >= BIG_ROWS or byts >= BIG_BYTES:
        return "large"
    if rows >= MID_ROWS or byts >= MID_BYTES:
        return "medium"
    if rows > 0 or byts > 0:
        return "small"
    # 숫자가 아예 없거나 단위를 못 읽었다. 「샘플 11행을 공개함」처럼 규모가
    # 아닌 숫자만 있는 경우도 여기로 온다 — 세는 낱말이 없으면 안 읽는다
    return "unknown"


# ── 명부 규모 칸 읽기 (설계서 3.3) ─────────────────────────────────────────

#: 한글 자릿수와 K · M. 「멤버 32만 5천 655」 → 325655 (설계서 3.3 예)
UNIT_MULT = {"억": 100_000_000, "만": 10_000, "천": 1_000, "백": 100,
             "k": 1_000, "m": 1_000_000}
#: 날짜 · 시각. 「(2026-08-01 기준)」 「(09-10 기준)」의 숫자를 규모로 읽지 않게
#: 먼저 지운다. **점으로 끊은 날짜는 네 자리 연도가 있을 때만** 본다 —
#: 「12.5만」의 12.5 를 날짜로 지우면 안 된다
RE_DATEISH = re.compile(
    r"\d{4}[-./]\d{1,2}([-./]\d{1,2})?|\d{1,2}-\d{1,2}(?!\d)|\d{1,2}:\d{2}"
)
RE_KGROUP = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(억|만|천|백|[kKmM](?![A-Za-z]))?")

#: 명부 칸에 사람이 적는 자리표시 값. 이름이나 별칭으로 안 받는다
PLACEHOLDERS = frozenset({"미기입", "-", "—", "없음", "모름", "미확인", "해당 없음"})
#: 낱말 뒤 숫자가 끝나는 자리
RE_SEG_END = re.compile(r"[·(/)|\n]|\.\s")

#: 포럼 규모 칸의 낱말 → 원자료 칸.
#: 「전체 주제 N개」는 스레드로 안 읽는다 — 정본 엑셀이 BHF 의 그 값을 스레드
#: 칸에 넣지 않았다 (영토!N 빈칸)
FORUM_LABELS = {
    "raw": re.compile(r"(회원|멤버|이용자)"),
    "posts": re.compile(r"(게시물|게시글)"),
    "threads": re.compile(r"스레드"),
}


def korean_count(seg: str) -> float | None:
    """`1,637,135` · `32만 5천 655` · `9만 이상` · `약 300건` 을 숫자로.

    단위가 없는 숫자가 나오면 거기서 끝난다 — 「32만 5천 655」 의 655 가 마지막이다.
    """
    seg = RE_DATEISH.sub(" ", seg)
    total = 0.0
    found = False
    for num, unit in RE_KGROUP.findall(seg):
        try:
            v = float(num.replace(",", ""))
        except ValueError:
            continue
        total += v * UNIT_MULT.get(unit.lower() if unit in ("K", "M") else unit, 1)
        found = True
        if not unit:
            break
    return total if found else None


def registry_size(island: str, text: str | None) -> dict[str, float]:
    """명부 「규모」 칸의 **첫 줄**에서 활동도 원자료를 읽는다 (설계서 3.3).

    포럼은 회원 · 게시물 · 스레드를 낱말로 찾아 따로 읽는다. 나머지 섬은 첫
    숫자 하나다 — 설계서 3.3 「숫자가 둘이면 앞의 것」. 텔레그램은 구독자 수,
    랜섬웨어는 피해 기업 수다. 못 읽으면 빈 사전을 돌려주고, 그 영토는 원자료가
    없어 지도에서 빠진다 (2.5).
    """
    if not text:
        return {}
    first = text.strip().split("\n", 1)[0]
    if island == "FORUM":
        out: dict[str, float] = {}
        for key, label in FORUM_LABELS.items():
            m = label.search(first)
            if not m:
                continue
            rest = first[m.end():]
            end = RE_SEG_END.search(rest)
            v = korean_count(rest[: end.start()] if end else rest)
            if v is not None and v > 0:
                out[key] = v
        return out
    v = korean_count(RE_DATEISH.sub(" ", first))
    return {"raw": v} if v is not None and v > 0 else {}


# ── 영토 이름 ───────────────────────────────────────────────────────────────

#: 이름 끝에 붙은 도메인 꼬리. 「Leakforum.io」 → 「Leakforum」.
#: **`.onion` 은 안 뗀다.** 떼면 어니언 호스트가 점 없는 낱말이 되어 반출 검사를
#: 통과한다. 남겨 두면 검사가 걸려 굽기가 멈춘다 — 그쪽이 맞다
RE_TLD_TAIL = re.compile(r"\.(?!onion$)[A-Za-z]{2,24}$", re.IGNORECASE)


def display_name(raw: str) -> str:
    """명부 이름을 화면 이름으로. **도메인은 화면에 안 낸다.**

    괄호 안 표기(「BreachForums (bf.st)」의 bf.st)를 떼고, 이름 끝의 도메인
    꼬리(「NIFLHEIM.World」의 .World)를 뗀다. 그러고도 점이 남으면 반출
    검사가 잡는다 — 짐작해서 더 떼지 않는다.
    """
    name, _ = clean_name(raw)
    return RE_TLD_TAIL.sub("", name).strip() or name


FAR_FUTURE = datetime(9999, 12, 31, tzinfo=timezone.utc)


def when(s: str) -> datetime:
    """노션 날짜 글자를 견줄 수 있는 시각으로. 날짜만 있으면 그날 0시(UTC)다."""
    d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def number_duplicates(items: list[dict]) -> None:
    """같은 섬에 화면 이름이 겹치면 뒤에 번호를 붙인다.

    **도메인을 못 내서 생기는 일이다.** 「BreachForums (bf.st)」와
    「BreachForums (breached.su)」는 다른 포럼인데 괄호를 떼면 둘 다
    「BreachForums」가 된다. 첫 사건이 이른 곳부터 1, 2 를 붙인다. 사건이
    없으면 명부 차례를 따른다. 나중에 생긴 클론이 뒤 번호를 받으므로 앞
    번호가 바뀌지 않는다.
    """
    groups: dict[tuple[str, str], list[dict]] = {}
    for it in items:
        groups.setdefault((it["islandId"], it["name"].casefold()), []).append(it)
    for same in groups.values():
        if len(same) < 2:
            continue
        same.sort(key=lambda x: (when(x["_since"]) if x["_since"] else FAR_FUTURE, x["_order"]))
        for i, it in enumerate(same, 1):
            it["name"] = f"{it['name']} {i}"


# ── 반출 검사 ───────────────────────────────────────────────────────────────

RE_AT = re.compile(r"@")
RE_DIGITS = re.compile(r"\d{11,}")
#: 점을 낀 낱말. 아는 TLD 만 막으면 모르는 TLD 로 샌다 —
#: 2026-09-03 에 `.at` 도메인이 그렇게 빠져나갔다
RE_DOTTED = re.compile(r"[A-Za-z0-9가-힣_-]+\.[A-Za-z0-9가-힣_-]{2,}")


def scan_strings(node, path: str, bad: list[str]) -> None:
    """만든 JSON 을 재귀로 훑어 나가면 안 되는 모양을 찾는다."""
    if isinstance(node, dict):
        for k, v in node.items():
            scan_strings(v, f"{path}.{k}", bad)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            scan_strings(v, f"{path}[{i}]", bad)
    elif isinstance(node, str):
        # 게시 시각은 ISO 문자열이라 콜론과 숫자가 많다. 날짜는 건너뛴다
        if path.endswith((".postedAt", ".generatedAt", ".since")):
            return
        if RE_AT.search(node):
            bad.append(f"{path}: @ 가 들어 있습니다")
        if RE_DIGITS.search(node):
            bad.append(f"{path}: 숫자가 11자리 넘게 이어집니다")
        if RE_DOTTED.search(node):
            bad.append(f"{path}: 점을 낀 낱말이 있습니다 (도메인일 수 있습니다)")


def check(data: dict) -> list[str]:
    """반출 검사와 구조 검사. 걸린 것을 다 모아 돌려준다."""
    bad: list[str] = []
    scan_strings(data, "map", bad)

    # 섬 목록은 굽기가 안 싣는다 (이름과 색이 설계서 2.3 값이라 노션에 없다).
    # 대신 코드 집합으로 견준다
    terr = {t["id"] for t in data["territories"]}
    for t in data["territories"]:
        if t["islandId"] not in DARK_ISLAND_CODES:
            bad.append(f"영토 {t['id']} 의 섬 {t['islandId']} 가 설계서 2.3 에 없습니다")
    for e in data["events"]:
        if e["territoryId"] not in terr:
            bad.append(f"사건 {e['id']} 의 영토 {e['territoryId']} 가 목록에 없습니다")

    # **나가는 키를 화이트리스트로 본다.** 값 검사가 못 잡는 것을 여기서 잡는다 —
    # 조직 이름은 점도 @도 없는 평범한 낱말이라 `scan_strings` 를 그냥 통과한다
    for t in data["territories"]:
        extra = set(t) - TERRITORY_KEYS
        if extra:
            bad.append(f"영토에 허용 밖 칸이 있습니다: {sorted(extra)}")
    for e in data["events"]:
        extra = set(e) - EV_KEYS
        if extra:
            bad.append(f"사건에 허용 밖 칸이 있습니다: {sorted(extra)}")

    # 관계선은 양 끝이 목록 안 영토여야 하고, 근거는 목록 안 사건이어야 한다.
    # 목록 밖을 가리키면 굽기가 이름을 잘못 맞췄거나 어디선가 지어낸 것이다
    evs = {e["id"] for e in data["events"]}
    for r in data["relations"]:
        extra = set(r) - RELATION_KEYS
        if extra:
            bad.append(f"관계선에 허용 밖 칸이 있습니다: {sorted(extra)}")
        for end in ("from", "to"):
            if r.get(end) not in terr:
                bad.append(f"관계선 {r.get('id')} 의 {end} 영토가 목록에 없습니다")
        if r.get("from") == r.get("to"):
            bad.append(f"관계선 {r.get('id')} 가 같은 영토끼리 잇습니다")
        if r.get("kind") not in KIND_OF.values():
            bad.append(f"관계선 {r.get('id')} 의 종류가 설계서 2.3 에 없습니다")
        if r.get("confidence") not in CONF_OF.values():
            bad.append(f"관계선 {r.get('id')} 의 확실한 정도가 설계서 2.5 에 없습니다")
        for x in r.get("evidence", []):
            if x not in evs:
                bad.append(f"관계선 {r.get('id')} 의 근거 {x} 가 사건 목록에 없습니다")

    # 연결 관계 DB(오픈웹 ↔ 다크웹)는 노션에 없다 (설계서 5.1-5). 3D 보류와 함께
    # 비어 있는 것이 맞다. 값이 들어 있으면 어디선가 지어낸 것이다
    if data["links"]:
        bad.append("links 가 비어 있지 않습니다. 연결 관계 DB 가 아직 없습니다")
    return bad


# ── 값 다듬기 ───────────────────────────────────────────────────────────────

RE_PAREN = re.compile(r"\s*\([^)]*\)\s*$")


def clean_name(raw: str) -> tuple[str, str | None]:
    """영토 이름에서 괄호 안 표기를 떼어 별칭으로 내린다.

    「게시처」 선택지에 `BreachForums (bf.st)` 꼴이 있다. 괄호 안이 도메인이라
    그대로 두면 반출 검사에 걸린다. 떼고 나서도 점이 남으면 검사가 잡는다 —
    짐작해서 더 떼는 것보다 사람이 보는 편이 낫다.
    """
    m = RE_PAREN.search(raw)
    if not m:
        return raw.strip(), None
    return RE_PAREN.sub("", raw).strip(), m.group(0).strip(" ()")


def slug(name: str, seen: dict[str, str]) -> str:
    """영토 id. 이름이 그대로 보이지 않게 하되 같은 이름은 같은 id 가 되게 한다."""
    if name in seen:
        return seen[name]
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not base:
        base = "t"
    out = base
    n = 2
    while out in seen.values():
        out = f"{base}-{n}"
        n += 1
    seen[name] = out
    return out


def rel_ids(prop: dict | None) -> list[str]:
    """relation 칸의 상대 페이지 id 들. `read_value` 가 안 다루는 타입이다."""
    if not prop or prop.get("type") != "relation":
        return []
    return [r["id"] for r in prop.get("relation", [])]


def unique_id(prop: dict | None) -> str | None:
    """unique_id 칸을 `LEAK-197` 꼴로. 이것도 `read_value` 가 안 다룬다."""
    if not prop or prop.get("type") != "unique_id":
        return None
    u = prop.get("unique_id") or {}
    pre, num = u.get("prefix"), u.get("number")
    if num is None:
        return None
    return f"{pre}-{num}" if pre else str(num)


def split_evidence(raw: str | None) -> list[str]:
    """「근거 사건 ID」 한 칸을 사건 id 목록으로.

    **작업판 수식과 똑같이 끊는다.** 관계선후보 탭 「근거 사건 수」 칸이
    빈칸을 모두 지운 뒤 쉼표로 끊어 id 를 맞춘다 —
    `SEARCH(","&사건ID&",", ","&SUBSTITUTE(J," ","")&",")`.
    노션 칸도 같은 꼴(`LEAK-12, LEAK-40`)이고 끝에 쉼표가 붙은 줄이 있다.
    """
    if not raw:
        return []
    out: list[str] = []
    for tok in re.sub(r"\s+", "", raw).split(","):
        if tok and tok not in out:
            out.append(tok)
    return out


def bake_relations(n, ds: str, find_tid, events: list[dict],
                   read, log) -> list[dict]:
    """관계선 DB 를 읽어 지도 영토끼리 잇는 관계선만 남긴다.

    **영토는 섬과 이름을 같이 맞춘다.** 관계선 DB 는 영토를 명부 이름 글자로
    적는다. 이름만 맞추면 포럼 `Darkforums` 가 같은 이름의 텔레그램 채널
    `DarkForums` 와 붙어 제자리를 잇는 선이 된다 — 실제로 두 줄이 그랬다.
    `find_tid(섬 코드, 명부 이름)` 이 영토 id 를 찾는다 (`RegistryIndex`).

    건수와 처음·마지막 본 날은 여기서 안 센다. 기준일마다 값이 달라서
    화면이 `score.ts` 의 `relationCount` · `relationSpan` 으로 센다.
    """
    ev_ids = {e["id"] for e in events}

    def find(island_name: str | None, raw: str | None) -> str | None:
        island = ISLAND_OF_NAME.get(island_name or "")
        if not island or not raw:
            return None
        return find_tid(island, raw)

    rows = n.query_all(ds)
    dropped = {
        "DB 반영 꺼짐": 0, "종류 확인 필요": 0, "양 끝 영토가 지도에 없음": 0,
        "같은 영토끼리": 0, "근거가 모두 지도 밖": 0,
    }
    lost_evidence = 0
    out: list[dict] = []
    for i, row in enumerate(rows, 1):
        p = row.get("properties", {})
        if col(read, p, "DB 반영") is not True:
            dropped["DB 반영 꺼짐"] += 1
            continue
        kind = KIND_OF.get(col(read, p, "관계 종류") or "")
        if not kind:
            dropped["종류 확인 필요"] += 1
            continue
        a = find(col(read, p, "출발 섬"), col(read, p, "출발 영토"))
        b = find(col(read, p, "도착 섬"), col(read, p, "도착 영토"))
        if not a or not b:
            # 명부에서 걸러진 영토(offline · 규모 없음 · DB 반영 꺼짐)나 행위자
            # DB 에 없는 핸들을 가리키는 관계선이 여기로 온다
            dropped["양 끝 영토가 지도에 없음"] += 1
            continue
        if a == b:
            # 이름 괄호(도메인)를 떼면 두 클론이 한 영토가 된다.
            # BreachForums (bf.st) → BreachForums (breached.su) 가 그렇다
            dropped["같은 영토끼리"] += 1
            continue

        ev_all = split_evidence(col(read, p, "근거 사건 ID"))
        ev = [x for x in ev_all if x in ev_ids]
        lost_evidence += len(ev_all) - len(ev)
        # **근거가 있었는데 하나도 지도에 안 남으면 뺀다** (설계서 2.5
        # 「근거 사건이 모두 허위이거나 DB 반영이 꺼짐」). 근거가 처음부터 없는
        # 관계는 남긴다 — 「연결된 곳」 칸에서 만든 것이라 건수 1로 센다 (3.9)
        if ev_all and not ev:
            dropped["근거가 모두 지도 밖"] += 1
            continue

        out.append({
            "id": col(read, p, "관계 ID") or f"rel-{i}",
            "from": a,
            "to": b,
            "kind": kind,
            "confidence": CONF_OF.get(col(read, p, "확실한 정도") or "", "estimated"),
            "evidence": ev,
        })

    log(f"관계선 DB {len(rows)}줄 → {len(out)}줄")
    log("관계선에서 뺀 줄 — " + " · ".join(f"{k} {v}" for k, v in dropped.items()))
    if lost_evidence:
        log(f"  지도에 없는 근거 사건 id {lost_evidence}개는 뺐습니다")
    return out


# ── 굽기 ────────────────────────────────────────────────────────────────────


def read_registry(n, sources: dict[str, str], read, log) -> list[dict]:
    """명부 DB 넷을 읽어 영토 후보를 만든다. 거르기는 사건을 붙인 뒤에 한다.

    **이름이 똑같은 줄은 한 후보로 합친다.** 같은 곳을 어니언 주소 줄과 일반
    주소 줄로 두 번 적은 경우가 있다 (정본 확인필요 탭 7~13행). 이름이 조금이라도
    다르면 합치지 않는다 — 압수 뒤 새로 생긴 비슷한 이름의 포럼은 다른 곳이다.

    **DB 반영이 꺼진 줄은 켜진 줄에 아무것도 보태지 않는다.** 꺼진 줄의 별칭 ·
    규모 · 상태가 켜진 줄에 섞여 나가면 안 된다 (설계서 2.5 「켜진 줄만」).
    꺼진 줄도 후보로는 남긴다 — 그 줄의 사건이 비슷한 이름의 다른 영토에 잘못
    붙지 않고 「영토가 지도에서 빠진 곳」으로 빠지게 하려는 것이다.
    """
    out: list[dict] = []
    by_name: dict[tuple[str, str], dict] = {}
    merged = 0
    for key, (island, title_col) in REGISTRY.items():
        rows = n.query_all(sources[key])
        alias_col = "다른 이름" if island == "ACTOR" else "이전 이름·별칭"
        for i, row in enumerate(rows):
            p = row.get("properties", {})
            raw_name = (col(read, p, title_col) or "").strip()
            if not raw_name:
                continue
            aliases = [
                a.strip() for a in re.split(r"[,\n]", col(read, p, alias_col) or "")
                if a.strip() and a.strip() not in PLACEHOLDERS
            ]
            size = {} if island == "ACTOR" else registry_size(island, col(read, p, "규모"))
            on = col(read, p, "DB 반영") is True
            online = col(read, p, "상태") == "online"
            k = (island, raw_name.casefold())
            if k in by_name:
                c = by_name[k]
                merged += 1
                if not on:
                    continue  # 꺼진 줄은 보태지 않는다
                if not c["on"]:
                    # 먼저 들어온 꺼진 줄을 켜진 줄로 갈아 끼운다
                    c.update({"aliases": aliases, "on": True, "online": online})
                    for s in ("raw", "posts", "threads"):
                        c.pop(s, None)
                    c.update(size)
                    continue
                c["online"] = c["online"] or online
                for s, v in size.items():
                    c[s] = max(c.get(s) or 0, v)
                c["aliases"] += [a for a in aliases if a not in c["aliases"]]
                continue
            c = {
                "island": island, "rawName": raw_name, "aliases": aliases,
                "on": on, "online": online, "order": len(out), **size,
            }
            by_name[k] = c
            out.append(c)
        log(f"명부 {key} {len(rows)}줄")
    if merged:
        log(f"  이름이 같은 명부 줄 {merged}개를 합쳤습니다")
    return out


#: 핸들 자리에 적힌 자리표시. 이런 값은 사람이 아니다
HANDLE_PLACEHOLDERS = PLACEHOLDERS | {"unknown", "anonymous", "익명", "n/a"}


def clean_handle(raw) -> str | None:
    """게시자 핸들을 행위자 영토 이름으로 다듬는다. 자리표시와 빈칸은 None.

    앞의 `@` 는 뗀다 — 텔레그램식 표기다. 남기면 값 훑기(`scan_strings`)가
    이메일로 보고 굽기를 멈춘다.
    """
    if not isinstance(raw, str):
        return None
    h = raw.strip().lstrip("@").strip()
    if not h or h.casefold() in {x.casefold() for x in HANDLE_PLACEHOLDERS}:
        return None
    return h


class RegistryIndex:
    """사건의 게시처 · 게시 플랫폼 · 핸들을 명부 후보에 맞춘다.

    순서: 이름 전체 → 별칭 → 괄호를 뗀 이름. 괄호를 뗀 이름이 여러 후보에
    맞으면 괄호 안 표기로 가른다. 그래도 못 가르면 맞추지 않는다 — 짐작해서
    두 클론을 합치지 않는다. **괄호 안 표기가 양쪽에 다 있는데 서로 다르면**
    후보가 하나뿐이어도 안 붙인다 (「BreachForums (breached.st)」 사건이
    「BreachForums (bf.st)」 에 붙으면 안 된다).

    **행위자는 정확히 같은 이름만 맞춘다** (대소문자만 무시, 엑셀 MATCH 와 같다).
    괄호 떼기나 도메인 꼬리 떼기를 핸들에 걸면 등록 안 된 핸들이 비슷한 등록
    행위자에 붙는다.
    """

    def __init__(self, cands: list[dict]):
        self.full: dict[tuple[str, str], list[dict]] = {}
        self.alias: dict[tuple[str, str], list[dict]] = {}
        self.clean: dict[tuple[str, str], list[dict]] = {}
        for c in cands:
            isl = c["island"]
            self._add(self.full, (isl, c["rawName"].casefold()), c)
            for a in c["aliases"]:
                self._add(self.alias, (isl, a.casefold()), c)
                if isl != "ACTOR":
                    self._add(self.alias, (isl, clean_name(a)[0].casefold()), c)
            if isl == "ACTOR":
                continue
            self._add(self.clean, (isl, clean_name(c["rawName"])[0].casefold()), c)
            self._add(self.clean, (isl, display_name(c["rawName"]).casefold()), c)

    @staticmethod
    def _add(table, key, c):
        lst = table.setdefault(key, [])
        if c not in lst:
            lst.append(c)

    def find(self, island: str, name: str | None) -> dict | None:
        if not name or not name.strip():
            return None
        k = name.strip().casefold()
        for table in (self.full, self.alias):
            hit = table.get((island, k), [])
            if len(hit) == 1:
                return hit[0]
        if island == "ACTOR":
            return None
        nm, paren = clean_name(name)
        hit = self.clean.get((island, nm.casefold()), [])
        if len(hit) == 1:
            other = clean_name(hit[0]["rawName"])[1]
            if paren and other and paren.casefold() != other.casefold():
                return None  # 괄호 안 표기가 다른 클론이다
            return hit[0]
        if len(hit) > 1 and paren:
            p = paren.casefold()
            pick = [c for c in hit
                    if p in c["rawName"].casefold() or any(p in a.casefold() for a in c["aliases"])]
            if len(pick) == 1:
                return pick[0]
        return None


RE_TME = re.compile(r"t\.me/(?:s/)?([A-Za-z0-9_]{3,64})", re.IGNORECASE)


def bake(n, sources: dict[str, str], log) -> dict:
    dc = sys.modules["dc_notion"]
    read = dc.read_value

    # 1) 검증 DB 를 먼저 읽어 「수집 페이지 id → 판정」 표를 만든다.
    #    「수집 줄」 relation 이 채워져 있어 조인 키가 이미 있다
    verdict_of: dict[str, str] = {}
    vrows = n.query_all(sources["verify"])
    for row in vrows:
        p = row.get("properties", {})
        if col(read, p, "DB 반영") is not True:
            continue
        v = VERDICT_OF.get(col(read, p, "진위 판정") or "")
        if not v:
            continue
        for pid in rel_ids(col_prop(p, "수집 줄")):
            verdict_of[pid] = v
    log(f"검증 DB {len(vrows)}줄 → 판정 {len(verdict_of)}건")

    # 2) 명부 넷 — 영토 후보 (설계서 2.4)
    cands = read_registry(n, sources, read, log)
    index = RegistryIndex(cands)

    # 3) 수집 DB — 사건
    rows = n.query_all(sources["collect"])
    log(f"수집 DB {len(rows)}줄")

    gate = {"DB 반영 꺼짐": 0, "검토 여부": 0}
    why: dict[str, int] = {}
    raw_events: list[dict] = []

    for row in rows:
        p = row.get("properties", {})

        # ── 줄 관문 ────────────────────────────────────────────────────
        #
        # **「DB 반영」과 「검토 여부」를 둘 다 본다.** 2026-09-22 에 수집 196줄의
        # DB 반영을 한꺼번에 켜서 미검토 131줄도 켜져 있다. DB 반영 하나만 보면
        # 사람 손을 안 거친 줄이 지도에 오른다 (2026-09-23 최현서, 되돌린 결정).
        #
        # **`is not True` 로 본다.** 빈칸을 통과시키면 안 된다 — 노션 checkbox 는
        # 새 줄에서 꺼진 채로 들어오고, `push.py` 가 이 칸을 안 찍는다
        if col(read, p, "DB 반영") is not True:
            gate["DB 반영 꺼짐"] += 1
            continue
        # 빈칸은 자동 수집 이전에 사람이 올린 줄이라 사건 O 로 읽는다.
        # 소급해 채우지 않는다
        if col(read, p, "검토 여부") in ("미검토", "사건 X"):
            gate["검토 여부"] += 1
            continue

        # ── 지도에서 빼는 사건 (설계서 2.5) ──────────────────────────
        island = ISLAND_OF_SOURCE.get(col(read, p, "소스") or "")
        place = col(read, p, "게시처")
        plat = col(read, p, "게시 플랫폼")

        # 게시 시각이 없으면 관측 시각, 그것도 없으면 수집일을 대신 넣는다.
        # 점수와 칸에는 들고 창 · 상태 · 급상승에서는 빠진다 (정본 업데이트 탭)
        posted = col(read, p, "게시 시각")
        substituted = False
        if not posted:
            posted = col(read, p, "관측 시각") or col(read, p, "수집일")
            substituted = bool(posted)

        reason = None
        if not island:
            reason = "소스 없음"
        elif not (plat or "").strip():
            reason = "게시 플랫폼 없음"
        elif not posted:
            reason = "날짜 없음"
        elif island == "RANSOMWARE" and col(read, p, "한국 관련") != "직접":
            # 랜섬웨어 섬은 한국 관련이 정확히 「직접」인 사건만 든다 (정본 사건!N)
            reason = "한국 관련 아님"

        cand = None
        if not reason:
            if island == "TELEGRAM":
                # 텔레그램 재유포 사건의 채널 (설계서 3.3). t.me 주소가 게시 플랫폼에
                # 있으면 그 채널, 없으면 게시자 핸들이 채널 이름과 같을 때만.
                # 원문 URL 은 안 읽는다 (DENY_COLS) — 그래서 하나를 놓칠 수 있다
                m = RE_TME.search(plat or "")
                cand = index.find("TELEGRAM", m.group(1)) if m else None
                if not cand:
                    cand = index.find("TELEGRAM", col(read, p, "게시자 핸들"))
            else:
                cand = index.find(island, place) or index.find(island, plat)
            if not cand:
                reason = "영토를 정할 수 없음"

        # 행위자 — 게시자 핸들 (2026-09-25 최현서). 랜섬웨어 섬 사건의 핸들은
        # 그룹 이름이라 행위자로 안 본다 (설계서 2.4). 영토는 아래 4) 에서 만든다
        handle = None
        if not reason and island != "RANSOMWARE":
            handle = clean_handle(col(read, p, "게시자 핸들"))

        if reason:
            why[reason] = why.get(reason, 0) + 1
            continue

        raw_events.append({
            "id": unique_id(col_prop(p, "사건 ID")) or f"row-{len(raw_events) + 1}",
            "cand": cand,
            "handle": handle,
            "actor": None,
            "postedAt": posted,
            "verdict": verdict_of.get(row["id"], UNVERIFIED),
            # 「규모 등급」 칸이 채워져 있으면 그것을 쓰고, 비어 있으면
            # 「주장 규모」 글에서 읽는다 (설계서 3.2). 둘 다 못 읽으면 모름이다
            "size": (
                SIZE_OF.get(col(read, p, "규모 등급") or "")
                or size_grade(col(read, p, "주장 규모"))
            ),
            "repost": (col(read, p, "중복 관계") or "") in REPOST_VALUES,
            "substituted": substituted,
        })

    # 4) 영토 거르기 (설계서 2.5, 정본 영토 탭에서 되짚은 규칙)
    counted = {id(c): 0 for c in cands}
    for e in raw_events:
        if e["verdict"] != "false":
            counted[id(e["cand"])] += 1

    def keep_place(c: dict) -> bool:
        if not c["on"]:
            return False
        isl = c["island"]
        if isl == "FORUM":
            return c["online"] and any((c.get(k) or 0) > 0 for k in ("raw", "posts", "threads"))
        if isl == "TELEGRAM":
            return c["online"] and (c.get("raw") or 0) > 0
        # 랜섬웨어 — 한국 관련 사건이 있는 그룹은 offline 이거나 피해 기업 수가
        # 없어도 남긴다
        return (c["online"] and (c.get("raw") or 0) > 0) or counted[id(c)] > 0

    places = {id(c) for c in cands if c["island"] != "ACTOR" and keep_place(c)}

    # 행위자는 영토를 거른 뒤에 만든다 (2026-09-25 최현서). 지도에 남은 영토에
    # 올라온 사건의 게시자 핸들 하나가 행위자 영토 하나다. 허위도 센다 (정본에
    # 사건이 모두 허위인 행위자가 있다). 대소문자만 다른 핸들은 한 사람으로 본다.
    #
    # **랜섬웨어 그룹 이름과 같은 핸들은 뺀다.** 랜섬웨어 그룹은 행위자가 아니라
    # 영토다 (설계서 2.4 · 4.3.8 「랜섬웨어 그룹은 넣지 않음」)
    group_names = set()
    for c in cands:
        if c["island"] == "RANSOMWARE":
            group_names.add(c["rawName"].casefold())
            group_names.add(display_name(c["rawName"]).casefold())
    actor_of: dict[str, dict] = {}
    as_group = set()
    for e in raw_events:
        h = e["handle"]
        if not h or id(e["cand"]) not in places:
            continue
        k = h.casefold()
        if k in group_names:
            as_group.add(k)
            continue
        if k not in actor_of:
            actor_of[k] = {
                "island": "ACTOR", "rawName": h, "aliases": [], "on": True,
                "online": True, "order": len(actor_of),
            }
        e["actor"] = actor_of[k]
    actor_cands = list(actor_of.values())
    log(f"행위자 — 게시자 핸들에서 {len(actor_cands)}곳 · 랜섬 그룹 이름과 같아 뺀 핸들 {len(as_group)}개")

    kept = [c for c in cands if id(c) in places] + actor_cands
    kept_ids = places | {id(c) for c in actor_cands}

    events_out = []
    since: dict[int, str] = {}
    for e in raw_events:
        if id(e["cand"]) not in kept_ids:
            why["영토가 지도에서 빠진 곳"] = why.get("영토가 지도에서 빠진 곳", 0) + 1
            continue
        a = e["actor"] if e["actor"] is not None and id(e["actor"]) in kept_ids else None
        for c in (e["cand"], a):
            # 글자로 견주지 않고 날짜로 견준다. 노션 날짜는 날짜만 오기도 하고
            # 시각과 시간대가 붙어 오기도 한다
            if c is not None and (id(c) not in since or when(e["postedAt"]) < when(since[id(c)])):
                since[id(c)] = e["postedAt"]
        events_out.append((e, a))

    # 5) 영토 id · 이름
    items = []
    for c in kept:
        items.append({
            "_c": c, "_since": since.get(id(c)), "_order": c["order"],
            "islandId": c["island"], "name": display_name(c["rawName"]),
        })
    number_duplicates(items)
    items.sort(key=lambda it: (ISLAND_ORDER.index(it["islandId"]), it["name"].casefold()))
    seen_slug: dict[str, str] = {}
    tid_of: dict[int, str] = {}
    out_terr = []
    for it in items:
        c = it["_c"]
        tid = slug(f"{c['island'].lower()} {it['name']}", seen_slug)
        tid_of[id(c)] = tid
        # 별칭은 싣지 않는다 (TERRITORY_KEYS 주석). 맞추는 데만 썼다
        t = {"id": tid, "name": it["name"], "islandId": c["island"], "web": "dark"}
        for k in ("raw", "posts", "threads"):
            if c.get(k):
                t[k] = c[k]
        if it["_since"]:
            t["since"] = it["_since"]
        out_terr.append(t)

    events = []
    for e, a in events_out:
        ev = {
            "id": e["id"],
            "territoryId": tid_of[id(e["cand"])],
            "postedAt": e["postedAt"],
            "verdict": e["verdict"],
            "size": e["size"],
            "repost": e["repost"],
            "excluded": False,
        }
        if a is not None:
            ev["actorTerritoryId"] = tid_of[id(a)]
        if e["substituted"]:
            ev["dateSubstituted"] = True
        events.append(ev)

    log("관문에서 뺀 줄 — " + " · ".join(f"{k} {v}" for k, v in gate.items()))
    log("지도에서 뺀 사건 — " + (" · ".join(f"{k} {v}" for k, v in sorted(why.items())) or "없음"))
    by_island: dict[str, int] = {}
    for t in out_terr:
        by_island[t["islandId"]] = by_island.get(t["islandId"], 0) + 1
    log(f"영토 {len(out_terr)}곳 — " + " · ".join(f"{k} {by_island.get(k, 0)}" for k in ISLAND_ORDER))
    log(f"사건 {len(events)}건 · 행위자 영토에도 붙은 사건 "
        f"{sum(1 for e in events if 'actorTerritoryId' in e)}건 · "
        f"날짜를 대신 넣은 사건 {sum(1 for e in events if e.get('dateSubstituted'))}건")

    # 6) 관계선 — 명부 이름으로 영토를 찾는다
    relations: list[dict] = []
    if sources.get("relations"):
        # 걸러지기 전 명부 전체로 찾는다. 걸러진 클론을 가리키는 관계선이 남은
        # 클론에 붙지 않고 「양 끝 영토가 지도에 없음」으로 빠지게 하려는 것이다
        def find_tid(isl: str, nm: str | None) -> str | None:
            if isl == "ACTOR":
                # 행위자는 명부가 아니라 핸들에서 만들었다. 정확히 같은 핸들만 (대소문자 무시)
                h = clean_handle(nm)
                c = actor_of.get(h.casefold()) if h else None
            else:
                c = index.find(isl, nm)
            return tid_of.get(id(c)) if c else None

        relations = bake_relations(n, sources["relations"], find_tid, events, read, log)
    else:
        log("관계선 DB 를 안 알려 줘서 관계선을 비웁니다 "
            f"(DC_MAP_RELATIONS_DS 또는 {SOURCES_FILE.name} 의 relations)")

    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        # 섬 이름과 색은 설계서 2.3 값이라 노션에 없다. 화면이 제 상수를 쓴다
        "islands": [],
        "territories": out_terr,
        "events": events,
        "relations": relations,
        # 연결 관계 DB 가 노션에 없다 (설계서 5.1-5). 비어 있는 것이
        # 「연결이 없다」가 아니라 「적을 표가 아직 없다」는 뜻이다
        "links": [],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="노션에서 지도 재료를 굽습니다")
    ap.add_argument("--out", default="src/data/map.json", help="쓸 자리")
    ap.add_argument("--check-only", action="store_true",
                    help="굽지 않고 이미 있는 파일만 검사합니다")
    args = ap.parse_args()
    out = Path(args.out)

    def log(msg: str) -> None:
        # 값은 한 줄도 찍지 않는다. 로그가 곧 반출 경로다
        print(msg, flush=True)

    if args.check_only:
        if not out.is_file():
            sys.exit(f"{out} 가 없습니다")
        data = json.loads(out.read_text(encoding="utf-8"))
    else:
        dc = _load_dc_notion()
        sources = load_sources()
        n = dc.Notion(verbose=False)
        data = bake(n, sources, log)

    bad = check(data)
    if bad:
        print("\n반출 검사에 걸렸습니다. 파일을 쓰지 않습니다.", file=sys.stderr)
        for b in bad[:40]:
            print(f"  {b}", file=sys.stderr)
        if len(bad) > 40:
            print(f"  … 그 밖 {len(bad) - 40}건", file=sys.stderr)
        return 1

    if args.check_only:
        log("검사 통과")
        return 0

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    log(f"검사 통과 · {out} 에 썼습니다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
