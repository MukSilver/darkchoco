#!/usr/bin/env python3
"""정본 엑셀에서 **숫자 칸만** 뽑아 시험 기준 자료를 만든다.

    python tools/canon_fixture.py "<프젝>/생태계지도_온톨로지(설계서 기반).xlsx" \
      --out src/lib/fixtures/canon_20260922.json

정본은 팀 구글 드라이브의 온톨로지판 엑셀과 설계서 PDF 63쪽이다 (2026-09-23
최현서). 이 엑셀이 설계서 3.5 실측 표를 한 칸도 안 틀리게 재현하므로 시험의
기준으로 쓴다.

**엑셀은 저장소에 넣지 않는다.** 사건 탭과 피해대상 탭에 피해 조직 이름 ·
자료 제목 · 게시자 핸들 · 원문 URL 이 있다. 여기서 뽑는 것은 이것뿐이다.

    영토    영토 번호(TER-xxxx) · 섬 코드 · 활동도 원자료 숫자 · 처음 분기
    사건    사건 ID(LEAK-/INC-) · 게시 시각 · 영토 번호 · 행위자 영토 번호 ·
           검증 결과 코드 · 규모 등급 코드 · 빠짐 여부
    기대값  영토 탭 · 섬 탭 · 분기별 탭의 계산 결과 숫자

**이름을 영토 번호로 바꾼다.** 행위자 섬은 영토 이름이 곧 핸들이라, 사건의
행위자 칸도 행위자 영토의 번호로만 싣는다.

다 만든 뒤 모든 글자 값을 허용 모양(번호 · 날짜 · 코드)과 대 보고, 하나라도
벗어나면 파일을 쓰지 않는다.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import openpyxl

ISLAND = {"포럼": "FORUM", "랜섬웨어": "RANSOMWARE", "텔레그램": "TELEGRAM", "행위자": "ACTOR"}
VERDICT = {
    "확인됨": "confirmed", "신뢰성 높음": "high", "검증 전": "unverified",
    "미확인": "unknown", "신뢰성 낮음": "low", "허위": "false",
}
SIZE = {"큼": "large", "중간": "medium", "작음": "small", "모름": "unknown"}

#: 기준 자료에 들어가도 되는 글자 값의 모양
ALLOWED_STR = re.compile(
    r"^(TER-\d{4}|LEAK-\d+|INC-\d+|\d{4}-Q[1-4]|\d{4}-\d{2}-\d{2}(T[\d:.]+Z)?|"
    r"FORUM|RANSOMWARE|TELEGRAM|ACTOR|confirmed|high|unverified|unknown|low|false|"
    r"large|medium|small|활성|관측 중)$"
)


def blank(v) -> bool:
    return v is None or v == ""


def iso(v) -> str | None:
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%dT%H:%M:%S.") + f"{v.microsecond // 1000:03d}Z"
    return None


def day(v) -> str | None:
    return v.strftime("%Y-%m-%d") if isinstance(v, datetime) else None


def num(v):
    if isinstance(v, bool):
        return None
    return v if isinstance(v, (int, float)) else None


def quarter_start(q: str) -> str:
    y, n = q.split("-Q")
    return f"{y}-{(int(n) - 1) * 3 + 1:02d}-01"


def header(ws, row=5) -> dict[str, int]:
    return {ws.cell(row, c).value: c for c in range(1, ws.max_column + 1) if ws.cell(row, c).value}


def main() -> int:
    ap = argparse.ArgumentParser(description="정본 엑셀에서 시험 기준 자료를 뽑습니다")
    ap.add_argument("xlsx")
    ap.add_argument("--out", default="src/lib/fixtures/canon_20260922.json")
    args = ap.parse_args()

    wb = openpyxl.load_workbook(args.xlsx, data_only=True)

    # ── 가중치 ────────────────────────────────────────────────────────
    W = wb["가중치"]
    trust = {VERDICT[W.cell(r, 1).value]: W.cell(r, 2).value for r in range(29, 35)}
    size = {SIZE[W.cell(r, 1).value]: W.cell(r, 2).value for r in range(37, 41)}
    as_of = W["B47"].value
    weights = {
        "asOf": day(as_of),
        "totalCells": W["B48"].value,
        "recentDays": W["B49"].value,
        "surgeDays": W["B50"].value,
        "base": W["B51"].value,
        "activityMin": W["B52"].value,
        "islandAlpha": W["B53"].value,
        "trust": trust,
        "size": size,
    }

    # ── 영토 ──────────────────────────────────────────────────────────
    T = wb["영토"]
    th = header(T)
    ter_rows = []
    by_name: dict[tuple[str, str], str] = {}
    for r in range(6, T.max_row + 1):
        tid = T.cell(r, th["영토 번호"]).value
        if blank(tid):
            continue
        isl = ISLAND[T.cell(r, th["섬"]).value]
        name = str(T.cell(r, th["영토 이름"]).value)
        by_name[(isl, name.casefold())] = tid
        ter_rows.append((r, tid, isl))

    # 처음 분기 — 분기별 탭에 그 영토 줄이 처음 나오는 분기
    QT = wb["영토분기별"]
    qh = header(QT)
    first_q: dict[str, str] = {}
    qrows = []
    for r in range(6, QT.max_row + 1):
        q = QT.cell(r, qh["기준 분기"]).value
        tid = QT.cell(r, qh["영토 ID"]).value
        if blank(q) or blank(tid):
            continue
        if tid not in first_q or q < first_q[tid]:
            first_q[tid] = q
        g = lambda h: QT.cell(r, qh[h]).value  # noqa: E731
        qrows.append({
            "q": q, "d": day(g("기준일")), "t": tid, "order": g("순번"),
            "H": g("누적 사건 수"), "I": g("누적 점수"), "raw": num(g("활동도 원자료")),
            "S": g("활동도"), "J": g("누적 사건 지수"), "U": g("누적 크기 점수"),
            "X": g("칸 수"), "AA": g("칸 수 (최종)"),
            "AB": g("최근 30일 건수"), "AC": g("직전 30일 건수"),
            "AF": g("최근 7일 점수"), "AG": g("직전 7일 점수"),
        })

    territories = []
    expect_t = {}
    for r, tid, isl in ter_rows:
        g = lambda h: T.cell(r, th[h]).value  # noqa: E731
        t = {"id": tid, "island": isl}
        # 활동도 원자료. 행위자는 사건 수라 싣지 않는다 (코드가 센다)
        if isl != "ACTOR":
            t["raw"] = num(g("DB 규모 숫자"))
        if isl == "FORUM":
            t["posts"] = num(g("DB 게시물 수"))
            t["threads"] = num(g("DB 스레드 수"))
        t["since"] = quarter_start(first_q[tid]) if tid in first_q else None
        territories.append(t)
        expect_t[tid] = {
            "H": g("사건 수"), "I": g("점수"), "J": g("사건 지수"),
            "S": g("활동도"), "T": g("w(활동도)"), "U": g("크기 점수"),
            "V": g("섬 안 비중"), "W": g("전체 비중"),
            "X": g("칸 수"), "AA": g("칸 수 (최종)"),
            "AB": g("최근 30일 건수"), "AC": g("직전 30일 건수"),
            "AD": num(g("30일 변화율")), "AE": g("지도 상태"),
            "AF": g("최근 7일 점수"), "AG": g("직전 7일 점수"), "AH": g("급상승 폭"),
            "AL": iso(g("첫 사건")), "AM": iso(g("마지막 사건")),
        }

    # ── 사건 ──────────────────────────────────────────────────────────
    S = wb["사건"]
    sh = header(S)
    events = []
    blank_verdict_in_map = 0
    for r in range(6, S.max_row + 1):
        g = lambda h: S.cell(r, sh[h]).value  # noqa: E731
        eid = g("사건 ID")
        if blank(eid):
            continue
        c, d, e = g("섬"), g("영토"), g("행위자")
        tid = g("영토 ID") or None
        isl = ISLAND.get(c) if not blank(c) else None
        # 엑셀 「계산 대상」에서 날짜와 허위를 뺀 나머지 조건. 날짜와 허위는
        # 코드가 스스로 본다 (score.ts inScope)
        excluded = (
            not blank(g("지도 점수 제외"))
            or blank(c) or blank(d) or not tid
            or (c == "랜섬웨어" and g("한국 관련") != "직접")
        )
        actor = by_name.get(("ACTOR", str(e).casefold())) if not blank(e) else None
        gv = g("검증 결과")
        if blank(gv) and g("지도 포함") == 1:
            blank_verdict_in_map += 1
        events.append({
            "id": eid,
            "t": tid,
            **({"a": actor} if actor else {}),
            "at": iso(g("게시 시각")),
            "v": VERDICT.get(gv, "unverified") if not blank(gv) else "unverified",
            "s": SIZE.get(g("규모 등급"), "unknown"),
            "x": bool(excluded),
            "island": isl,
            # 기대값 대조용
            "N": g("계산 대상"), "O": g("지도 포함"),
        })
    if blank_verdict_in_map:
        sys.exit(f"지도 포함 사건 {blank_verdict_in_map}건의 검증 결과가 비었습니다. 코드값이 없습니다")

    # ── 섬 ────────────────────────────────────────────────────────────
    I = wb["섬"]
    ih = header(I)
    expect_i = {}
    for r in range(6, 10):
        isl = ISLAND[I.cell(r, ih["섬"]).value]
        g = lambda h: I.cell(r, ih[h]).value  # noqa: E731
        expect_i[isl] = {
            "score": g("크기 점수"), "adjusted": g("조정 크기 점수"),
            "target": g("섬 칸 목표"), "cells": g("칸 수 합"),
            "territories": g("지도에 있는 영토 수"), "avgActivity": g("평균 활동도"),
        }

    QS = wb["섬분기별"]
    qsh = header(QS)
    expect_iq = []
    for r in range(6, QS.max_row + 1):
        q = QS.cell(r, qsh["기준 분기"]).value
        if blank(q):
            continue
        expect_iq.append({
            "q": q, "island": ISLAND[QS.cell(r, qsh["섬"]).value],
            "target": QS.cell(r, qsh["섬 칸 목표"]).value,
            "cells": QS.cell(r, qsh["칸 수 합"]).value,
        })

    out = {
        "_": "정본 온톨로지판 엑셀에서 숫자 칸만 뽑은 시험 기준 자료. "
             "이름 · 핸들 · 주소 · 제목은 없다. tools/canon_fixture.py 가 만든다",
        "weights": weights,
        "territories": territories,
        "events": events,
        "expect": {
            "territories": expect_t, "islands": expect_i,
            "quarters": qrows, "islandQuarters": expect_iq,
        },
    }

    # ── 이름이 섞이지 않았는지 본다 ────────────────────────────────────
    bad: list[str] = []

    def walk(node, path):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{path}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")
        elif isinstance(node, str) and path != "._" and not ALLOWED_STR.match(node):
            bad.append(path)

    walk(out, "")
    if bad:
        print("허용 모양 밖의 글자 값이 있어 쓰지 않습니다:", file=sys.stderr)
        for p in bad[:20]:
            print(f"  {p}", file=sys.stderr)
        return 1

    dst = Path(args.out)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"영토 {len(territories)} · 사건 {len(events)} · 분기 줄 {len(qrows)} · "
          f"섬 분기 {len(expect_iq)} → {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
