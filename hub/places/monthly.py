"""랜섬 그룹 × 달 피해 건수를 노션 「랜섬 그룹 월별 피해」 DB 에 쌓습니다 (2026-09-25 인계 B).

    python -m hub.places.monthly --소급 24            지난 24달을 받아 무엇이 쓰일지 셉니다 (미리보기)
    python -m hub.places.monthly --소급 24 --apply    실제로 씁니다

## 왜

명부 조사기는 판마다 최근 일곱 달 피해 목록을 받아 **메모리에서 센 뒤 숫자만 명부에 쓰고
버렸습니다.** 로컬 `places.db` 의 규모 표는 예약 실행에서 사라지고, 합계 스냅숏이라 달별로
되돌릴 수도 없었습니다. 랜섬 그룹의 과거(타임라인)를 보려면 달별 숫자가 남아 있어야 합니다.

## 무엇을 쌓나

그룹 · 연월마다 한 줄입니다. 피해 건수 · 한국 건수 · 업종별 건수 · 받은 때 · 달 마감(그 달이
끝났나)입니다. 명부의 그룹 줄과 관계로 잇습니다. **피해 조직 이름은 안 담습니다.** 그룹과
건수뿐입니다(SECURITY.md 의 「건수만」). 명부(다크웹 DB 셋)에는 칸을 안 늘립니다.

## 언제 쓰나

    판마다   조사기가 받은 달 중 **이번 달과 지난달만** 고칩니다. 끝난 달은 거의 안 바뀝니다
    소급     지난 N달(기본 24)을 한 번에 받아 채웁니다. 집계처가 분당 1회라 24분쯤 걸리고
             Tor 가 필요해 GitHub Actions(`ransom-months.yml`)에서 돕니다

**값이 같으면 안 씁니다.** 받은 때만 다른 것은 같은 것으로 봅니다.

## 이름을 안 찍습니다

레포가 공개라 Actions 로그도 누구나 봅니다. 그룹 이름은 명부에서 오는 우리 관찰 목록이라
`--요약만` 과 같은 까닭으로 찍지 않습니다. 건수만 냅니다.

Supabase 2단계가 열리면(김무근) 같은 표를 옮깁니다. 지도 세션과 칸 이름을 맞춥니다.
"""
from __future__ import annotations

import argparse
import collections
import os
import sys
import urllib.error
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages"))
sys.path.insert(0, str(ROOT))

# 「랜섬 그룹 월별 피해」. 2026-09-25 에 「다크웹」 페이지 아래에 만들었다
# (프젝 06_도구/월별피해DB_20260925). 비밀이 아니라 코드에 둡니다
월별DS = "7b49e29b-b054-4351-86a7-563acc4409a2"
KST = timezone(timedelta(hours=9))

__all__ = ["월별DS", "월별표", "속성", "판마다", "이번과지난", "요약"]


def _글(v: str) -> dict:
    return {"rich_text": [{"text": {"content": (v or "")[:2000]}}]} if v else {"rich_text": []}


def 업종글(c) -> str:
    """「Manufacturing 3 · Healthcare 1」. 많은 것부터 열 개까지."""
    return " · ".join(f"{k} {v}" for k, v in collections.Counter(c).most_common(10))


def 속성(그룹: str, 연월: str, d: dict, 그룹쪽: str, 마감: bool, 받은때: str) -> dict:
    p = {
        "이름": {"title": [{"text": {"content": f"{그룹} · {연월}"[:2000]}}]},
        "그룹 이름": _글(그룹),
        "연월": {"date": {"start": f"{연월}-01"}},
        "피해 건수": {"number": int(d.get("건수", 0))},
        "한국 건수": {"number": int(d.get("한국", 0))},
        "업종별 건수": _글(업종글(d.get("업종") or {})),
        "받은 때": {"date": {"start": 받은때}},
        "달 마감": {"checkbox": bool(마감)},
    }
    if 그룹쪽:
        p["그룹"] = {"relation": [{"id": 그룹쪽}]}
    return p


def _견줄값(p: dict) -> tuple:
    """같은 줄인지 볼 값. **받은 때는 안 봅니다** — 판마다 다릅니다."""
    글 = lambda k: "".join(x.get("text", {}).get("content", "") or x.get("plain_text", "")
                          for x in (p.get(k) or {}).get("rich_text") or [])
    관계 = tuple(sorted(x.get("id", "").replace("-", "") for x in (p.get("그룹") or {}).get("relation") or []))
    return ((p.get("피해 건수") or {}).get("number"), (p.get("한국 건수") or {}).get("number"),
            글("업종별 건수"), bool((p.get("달 마감") or {}).get("checkbox")), 관계)


class 월별표:
    """노션 월별 DB 의 지금 값. (그룹 소문자, 연월) → (page id, 견줄 값)."""

    def __init__(self, n):
        self.n = n
        self.있는것: dict[tuple[str, str], tuple[str, tuple]] = {}
        for r in n.query_all(월별DS):
            pr = r.get("properties") or {}
            그룹 = "".join(x.get("plain_text", "") for x in (pr.get("그룹 이름") or {}).get("rich_text") or [])
            연월 = ((pr.get("연월") or {}).get("date") or {}).get("start", "")[:7]
            if 그룹 and 연월:
                self.있는것[(그룹.lower(), 연월)] = (r["id"], _견줄값(pr))

    def 반영(self, 달별: dict[str, dict[str, dict]], 그룹쪽: dict[str, str], *,
           오늘: date, apply: bool) -> collections.Counter:
        받은때 = datetime.now(KST).isoformat(timespec="seconds")
        이번달 = f"{오늘.year}-{오늘.month:02d}"
        셈 = collections.Counter()
        for 연월, 그룹들 in sorted(달별.items()):
            for 그룹, d in sorted(그룹들.items()):
                p = 속성(그룹, 연월, d, 그룹쪽.get(그룹.lower(), ""), 연월 < 이번달, 받은때)
                k = (그룹.lower(), 연월)
                있음 = self.있는것.get(k)
                if 있음 and 있음[1] == _견줄값(p):
                    셈["그대로"] += 1
                    continue
                셈["고침" if 있음 else "새로"] += 1
                if not apply:
                    continue
                try:
                    if 있음:
                        self.n.update_page(있음[0], p)
                    else:
                        r = self.n.request("POST", "/pages", {
                            "parent": {"type": "data_source_id", "data_source_id": 월별DS},
                            "properties": p}) or {}
                        있음 = (r.get("id", ""), None)
                    self.있는것[k] = (있음[0], _견줄값(p))
                except Exception:  # noqa: BLE001  한 줄이 실패해도 나머지는 씁니다
                    셈["실패"] += 1
        return 셈


def 이번과지난(달별: dict, 오늘: date) -> dict:
    """판마다 쓰는 것은 이번 달과 지난달뿐입니다. 끝난 달은 소급이 채웁니다."""
    지난 = (오늘.replace(day=1) - timedelta(days=1))
    고를것 = {f"{오늘.year}-{오늘.month:02d}", f"{지난.year}-{지난.month:02d}"}
    return {k: v for k, v in 달별.items() if k in 고를것}


def 그룹쪽표(줄들) -> dict[str, str]:
    """명부 그룹 이름(소문자) → 명부 줄 page id. 조사기가 명부와 짝을 짓는 규칙과 같습니다."""
    밖 = {}
    for r in 줄들:
        이름 = (getattr(r, "이름", "") or "").strip().lower()
        if 이름 and 이름 not in 밖 and getattr(r, "page_id", ""):
            밖[이름] = r.page_id
    return 밖


def 요약(셈: collections.Counter, 무엇: str) -> str:
    """건수만 냅니다. 대시보드 로그 요약이 이 줄을 집습니다(worker.js 요약무늬)."""
    s = f"  월별 피해 ({무엇}) — 새로 {셈['새로']} · 고침 {셈['고침']} · 그대로 {셈['그대로']}"
    return s + (f" · 실패 {셈['실패']}" if 셈["실패"] else "")


def 판마다(n, 달별: dict, 줄들, *, 오늘: date, apply: bool) -> collections.Counter:
    """명부 조사 한 판 뒤에 부릅니다. 이번 달과 지난달만 씁니다."""
    고른것 = 이번과지난(달별, 오늘)
    if not 고른것:
        return collections.Counter()
    return 월별표(n).반영(고른것, 그룹쪽표(줄들), 오늘=오늘, apply=apply)


def 소급(달수: int, *, apply: bool, 프록시: str | None) -> int:
    """지난 `달수` 달을 받아 채웁니다. **Tor 가 필요합니다.** 요청 사이 62초."""
    from dc_notion import Notion
    from dc_ransomfeed import rl_victims
    from hub.places.egress import 오프너
    from hub.places.probe import ransom
    from hub.places.write import 명부

    op = 오프너(프록시, 갈래="ransom")         # Tor 가 없으면 여기서 보호없음 이 납니다
    오늘 = ransom._오늘()
    달들 = ransom._달들(달수)
    print(f"    집계처에서 피해 {len(달들)}달치를 받습니다 "
          f"(요청 사이 {ransom.간격:.0f}초라 {len(달들) * ransom.간격 / 60:.0f}분쯤 걸립니다)", flush=True)
    달별, 못본, 마지막 = {}, [], [0.0]
    for i, (년, 월) in enumerate(달들, 1):
        try:
            건들 = ransom._받기(rl_victims(년, 월), 마지막, op)
        except (urllib.error.URLError, OSError, ValueError) as e:
            못본.append(f"{년}-{월:02d}({type(e).__name__})")
            continue
        if not isinstance(건들, list):
            못본.append(f"{년}-{월:02d}(꼴이 바뀜)")
            continue
        달별[f"{년}-{월:02d}"] = ransom.달별세기(건들)
        print(f"      {i}/{len(달들)}  {년}-{월:02d}  {len(건들)}건", flush=True)

    m = 명부("ransom")
    셈 = 월별표(m.n).반영(달별, 그룹쪽표(m.줄들()), 오늘=오늘, apply=apply)
    print(요약(셈, f"소급 {len(달별)}달"), flush=True)
    if 못본:
        print(f"  못 받은 달 {len(못본)} — {' · '.join(못본[:6])}", flush=True)
    print("  " + ("썼습니다" if apply else "미리보기입니다. --apply 를 주면 씁니다"), flush=True)
    return 1 if 셈["실패"] else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="랜섬 그룹 월별 피해를 소급해 채웁니다")
    ap.add_argument("--소급", type=int, default=24, help="지난 몇 달을 받을지 (기본 24)")
    ap.add_argument("--apply", action="store_true", help="실제로 노션에 씁니다. 없으면 미리보기")
    a = ap.parse_args(argv)
    if not 1 <= a.소급 <= 60:
        print("  1 ~ 60 달만 받습니다")
        return 2
    return 소급(a.소급, apply=a.apply, 프록시=os.environ.get("TOR_SOCKS_PROXY"))


if __name__ == "__main__":
    raise SystemExit(main())
