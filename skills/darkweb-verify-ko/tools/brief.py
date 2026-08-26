#!/usr/bin/env python3
"""큐를 한 장으로 요약한다. 아침에 사람이 무엇을 볼지 정하는 화면이다.

    python tools/brief.py 07_케이스/_큐
    python tools/brief.py 07_케이스/_큐 --since 2026-08-26
    python tools/brief.py 07_케이스/_큐 --out 07_케이스/_큐/브리핑_20260827.md

**추리지 않고 나눈다.** 버리는 건이 없다.
급한 순서로 묶어 보이기만 하고, 무엇을 볼지는 사람이 정한다.

    1  막힌 것        사람이 손대야 다음으로 간다
    2  이미 아는 건    도구가 기존 줄과 이었다. 새 조사를 시작하지 않는다
    3  열어야 할 것    게시글을 열고 포럼 킷을 눌러야 ④ 로 간다
    4  돌릴 수 있는 것  재료가 다 들어왔다
    5  끝난 것        ⑥ 판정 근거까지 나왔다

**도구가 낸 분류는 확정이 아니다.** 2번 묶음도 사람이 확인하고 정한다.
개인정보 값을 담지 않는다. 조직명, 행위자, 건수만 낸다.
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

MISS = "못 봄"

# 도구가 이미 아는 줄과 이었다고 본 분류들. 사람이 확정하기 전까지는 참고다.
KNOWN = ("아예 동일 케이스", "재게시", "일부 조건이 다른 같은 케이스")


def load(q: Path, since: str | None) -> list[tuple[str, dict]]:
    out = []
    for d in sorted(q.iterdir()):
        sf = d / "상태.json"
        if not d.is_dir() or not sf.exists():
            continue
        try:
            st = json.loads(sf.read_text(encoding="utf-8"))
        except ValueError:
            st = {"칸": {}, "막힌 것": ["상태.json 을 못 읽는다"]}
        if since and str(st.get("칸", {}).get("탐지 시각", ""))[:10] < since:
            continue
        out.append((d.name, st))
    return out


def val(st: dict, k: str) -> str:
    v = str(st.get("칸", {}).get(k, "") or "")
    return "" if v.startswith(MISS) else v


def bucket(st: dict, case: Path) -> str:
    if st.get("막힌 것"):
        return "막힌 것"
    if "⑥" in st.get("끝낸 단계", []):
        return "끝난 것"
    cls = st.get("도구 분류") or {}
    if any(cls.get(k) for k in KNOWN):
        return "이미 아는 건"
    if not (case / "②본문.md").exists():
        return "열어야 할 것"
    return "돌릴 수 있는 것"


ORDER_B = ["막힌 것", "이미 아는 건", "열어야 할 것", "돌릴 수 있는 것", "끝난 것"]
WHY = {
    "막힌 것": "사람이 손대야 다음으로 간다",
    "이미 아는 건": "도구가 기존 줄과 이었다. 확정은 사람이 한다",
    "열어야 할 것": "게시글을 열고 포럼 킷을 누른다",
    "돌릴 수 있는 것": "재료가 들어왔다. ③ 부터 ⑥ 까지 돌린다",
    "끝난 것": "⑦ 검토와 ⑧ 판정으로 넘긴다",
}


def render(rows: list[tuple[str, dict]], q: Path, since: str | None) -> str:
    groups: dict[str, list] = {k: [] for k in ORDER_B}
    for name, st in rows:
        groups[bucket(st, q / name)].append((name, st))

    when = date.today().isoformat()
    h = ["# 브리핑 %s" % when, "",
         "    큐 %s" % q.name,
         "    범위 %s" % (("%s 이후" % since) if since else "전부"),
         "    건수 %d" % len(rows), ""]

    h += ["| 묶음 | 건수 | 무엇을 하나 |", "|---|---|---|"]
    for k in ORDER_B:
        if groups[k]:
            h.append("| %s | %d | %s |" % (k, len(groups[k]), WHY[k]))
    h.append("")

    for k in ORDER_B:
        if not groups[k]:
            continue
        h += ["## %s  (%d건)" % (k, len(groups[k])), ""]
        for name, st in groups[k]:
            org = val(st, "대상 조직") or "(조직 못 읽음)"
            actor = val(st, "행위자") or "?"
            h.append("### %s" % org)
            h.append("")
            h.append("    행위자 %s · 게시 %s" % (actor, val(st, "게시 시각")[:10] or "?"))
            url = val(st, "원 출처")
            # 포럼명만 적지 않는다. 주소까지 적는다
            h.append("    원 출처 %s" % (url or "못 봄. ③ 에서 찾는다"))
            h.append("    폴더 %s" % name)
            cls = st.get("도구 분류") or {}
            if cls:
                h.append("    도구 분류 %s"
                         % ", ".join("%s %d줄" % (a, b) for a, b in sorted(cls.items())))
            for x in st.get("막힌 것", []):
                h.append("    막힘 %s" % x)
            for x in st.get("충돌", []):
                h.append("    충돌 %s" % x)
            h.append("")

    h += ["---", "",
          "**도구가 낸 분류는 확정이 아니다.** 사람이 확인하고 정한다.",
          "**② 와 ⑧ 은 끝까지 사람이 한다.** 이 화면은 무엇을 볼지 고르는 데만 쓴다.",
          "샘플이 든 케이스는 끝나면 큐에서 지운다. 결과는 07_케이스 에 남는다."]
    return "\n".join(h)


def main() -> int:
    ap = argparse.ArgumentParser(description="큐를 한 장으로 요약한다")
    ap.add_argument("queue")
    ap.add_argument("--since", help="탐지 시각이 이 날짜 이후인 것만 (YYYY-MM-DD)")
    ap.add_argument("--out", help="파일로 쓴다. 안 주면 화면에만 낸다")
    a = ap.parse_args()

    q = Path(a.queue)
    if not q.is_dir():
        raise SystemExit("큐 폴더가 없다: %s" % q)
    rows = load(q, a.since)
    if not rows:
        print("해당하는 케이스가 없다")
        return 0

    text = render(rows, q, a.since)
    if a.out:
        p = Path(a.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        print("%s  %d건" % (p, len(rows)))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
