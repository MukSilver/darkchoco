#!/usr/bin/env python3
"""매일 미검토 판정 — 대상을 읽고, AI 판정을 정리하고, 사건 X 만 노션에 씁니다 (2026-10-02, 최현서).

    python hub/events/review.py 대상 --자리 <폴더>                     미검토를 읽어 오늘 판 재료를 둡니다
    python hub/events/review.py 결과 --자리 <폴더> <판정.json> [--무인]  판정을 적용 재료 · 확정 목록으로
    python hub/events/review.py 반영 --자리 <폴더>                     미리보기. 되돌리기 기록을 씁니다
    python hub/events/review.py 반영 --자리 <폴더> --쓴다               사건 X 만 씁니다
    python hub/events/review.py 반영 --자리 <폴더> --되돌린다
    python hub/events/review.py 반영 --자리 <폴더> --사건O LEAK-1,LEAK-2 [--쓴다]
                                                                    사람이 정한 줄만 사건 O 로

`--자리` 를 안 주면 환경변수 `DARKCHOCO_REVIEW_DIR` 을 봅니다. **레포 밖 폴더**여야 합니다.
재료와 결과에 조직명이 들어 있습니다. 화면에는 건수와 사건 ID 만 냅니다.

## 왜 있나

9/23 · 9/25 · 9/29 · 10/01 에 미검토를 AI 로 판정했습니다. 그때마다 `06_도구/사건검토_<날>/` 에 같은 스크립트
셋을 복사해 재료 · 숫자만 바꿨습니다. 최현서가 10/02 에 「매일 아침 예약으로 돌리자」 고 해서 한 자리로 묶었습니다.
판정 자체(조직 특정 · 본사 국가 · 한국 거점 · 반박)는 에이전트가 합니다. 이 도구는 그 앞뒤만 합니다.

## 무엇을 판정하나

    대상     검토 여부 = 미검토. 소스 = 포럼은 뺍니다(판정 재료인 대상 조직 · 국가가 비어 있습니다).
             `<자리>/보류.txt` 에 적은 줄과, 전에 판정한 줄(`<자리>/판정기록.json`)도 뺍니다. --다시 면 다시 봅니다
    재료     사건 ID · 대상 조직 · 게시 시각 · 게시자 핸들 · 국가 · 집계처가 한국이라 했나. **게시 플랫폼은 안 넘깁니다**
             — 전한 채널 · 유출 사이트 · 포럼 주소가 섞여 있어, 웹을 보는 에이전트가 그곳을 열 수 있습니다.
             「한국 관련 근거」 도 안 넘깁니다. 사람이 쓴 줄에 이메일 꼴이 있었습니다
    물음     한국 조직인가, 아니면 한국 법인 · 지사를 둔 외국 본사인가(9/23 규칙: 그것도 사건 O)

집계처가 한국이라 한 「직접」 줄도 대상입니다. 브리핑(09:00)이 그 줄을 목록에 싣기 전에 맞는지 봅니다.
10/01 에 집계처가 한국이라 한 줄이 남아공 본사로 드러난 적이 있습니다.

## 무엇을 쓰나

    사건 X   판정 사건 X · 반박 시도에서 안 깨짐 · 확신 높음(--무인) 또는 높음 · 중간(사람이 시킨 판)
    사건 O   **이 도구가 스스로 고르지 않습니다.** 사건 O 는 DB 반영(공개 스위치)을 같이 켜서 다음 굽기 때
             지도 · RAG 에 나갑니다. 사람이 확정 목록을 보고 `--사건O LEAK-…` 로 줄을 적을 때만 씁니다.
             예약 판(--무인)은 이 옵션을 쓰지 않습니다(최현서 10/02 「사건 O 는 직접 돌릴 때만」)
    나머지   손대지 않습니다. 확정 목록(`<날>/확정목록.md`)과 누적 확정 대기(`<자리>/확정대기.md`)에 남깁니다

## 쓰는 길의 관문 — 9/23 부터 쓴 사건검토_반영.py 와 같습니다

  1. 되돌리기 기록이 없으면 `--쓴다` 가 안 돕니다
  2. 기록에 있는 줄만 봅니다
  3. 쓰기 직전에 그 줄을 다시 읽어 여전히 「미검토 · 꺼짐」 일 때만 씁니다. 그 사이 대시보드로 찍은 줄은 사람 판단입니다
  4. 검토 여부와 DB 반영을 PATCH 한 번에 씁니다(대시보드 전이 규칙과 같게)
  5. `--되돌린다` 는 우리가 쓴 값 그대로인 줄만 「미검토 · 꺼짐」 으로 되돌립니다
  6. 적용한 기록은 덮어쓰지 않습니다
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages"))
sys.path.insert(0, str(ROOT))

KST = timezone(timedelta(hours=9))
재료칸 = ("사건ID", "대상 조직", "게시 시각", "게시자 핸들", "국가", "집계처 한국")
판정값 = ("사건 O", "사건 X", "확신 낮음")
확신값 = ("높음", "중간", "낮음")
쓸값 = {"사건 O": True, "사건 X": False}        # 검토 여부 → DB 반영
집계처국가만 = "집계처 국가만"


def 수집DS() -> str:
    from hub.events.push import 수집DB_읽기
    return 수집DB_읽기()


def 노션():
    from dc_notion import Notion
    return Notion(verbose=False)


def 값(p: dict, 칸: str):
    """노션 줄의 칸 값을 글자로. 칸이 없으면 빈 글자."""
    v = (p.get("properties") or {}).get(칸) or {}
    t = v.get("type")
    if t in ("rich_text", "title"):
        return "".join(x.get("plain_text", "") for x in v.get(t) or [])
    if t == "select":
        return (v.get("select") or {}).get("name", "")
    if t == "date":
        return (v.get("date") or {}).get("start") or ""
    if t == "checkbox":
        return bool(v.get("checkbox"))
    if t == "unique_id":
        u = v.get("unique_id") or {}
        return "%s-%s" % (u.get("prefix") or "LEAK", u.get("number"))
    return ""


def 자리(a) -> Path:
    d = a.자리 or os.environ.get("DARKCHOCO_REVIEW_DIR") or ""
    if not d:
        raise SystemExit("--자리 나 DARKCHOCO_REVIEW_DIR 로 레포 밖 폴더를 주십시오")
    p = Path(d).resolve()
    try:
        p.relative_to(ROOT.resolve())
        raise SystemExit("--자리 가 레포 안입니다. 조직명이 든 파일이 생기므로 레포 밖 폴더를 주십시오")
    except ValueError:
        pass
    p.mkdir(parents=True, exist_ok=True)
    return p


def 날자리(a) -> Path:
    날 = a.날 or datetime.now(KST).strftime("%Y%m%d")
    p = 자리(a) / 날
    p.mkdir(exist_ok=True)
    return p


def 읽기(p: Path, 기본):
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else 기본


def 쓰기(p: Path, v) -> None:
    p.write_text(json.dumps(v, ensure_ascii=False, indent=1), encoding="utf-8")


def 보류(a) -> set[str]:
    f = 자리(a) / "보류.txt"
    if not f.is_file():
        return set()
    return {l.split("#")[0].strip() for l in f.read_text(encoding="utf-8").splitlines() if l.split("#")[0].strip()}


# ── 대상 ──────────────────────────────────────────────────────
def 고르기(줄들: list[dict], 뺄: set[str], 판정한것: set[str], 다시: bool) -> tuple[list[dict], Counter]:
    """(오늘 판정할 줄, 뺀 까닭별 건수). 노션 줄을 받습니다."""
    셈, 고른 = Counter(), []
    for p in 줄들:
        if 값(p, "검토 여부") != "미검토":
            continue
        iid = 값(p, "사건 ID")
        if iid in 뺄:
            셈["보류"] += 1
        elif 값(p, "소스") == "포럼":
            셈["포럼"] += 1
        elif iid in 판정한것 and not 다시:
            셈["전에 판정함"] += 1
        else:
            고른.append(p)
    return 고른, 셈


def 재료(p: dict) -> dict:
    """판정 에이전트에 넘기는 것. 게시 플랫폼 · 원문 URL · 한국 관련 근거는 안 넘깁니다(머리말)."""
    return {"사건ID": 값(p, "사건 ID"), "대상 조직": 값(p, "대상 조직"), "게시 시각": 값(p, "게시 시각")[:10],
            "게시자 핸들": 값(p, "게시자 핸들") or 값(p, "게시처"), "국가": 값(p, "국가"),
            "집계처 한국": 값(p, "한국 관련") == "직접" and 값(p, "한국 관련 근거").startswith(집계처국가만)}


def 대상(a) -> int:
    d = 날자리(a)                     # 자리부터 본다. 레포 안이면 노션에 붙기 전에 멈춘다
    기록 = 읽기(자리(a) / "판정기록.json", {})
    뺄 = 보류(a)
    줄들 = 노션().query_all(수집DS())
    고른, 셈 = 고르기(줄들, 뺄, set(기록), a.다시)
    쓰기(d / "대상.json", [{"page_id": p["id"], "사건ID": 값(p, "사건 ID")} for p in 고른])
    쓰기(d / "조사재료.json", [재료(p) for p in 고른])
    대기 = 확정대기(줄들, 기록, 뺄)
    (자리(a) / "확정대기.md").write_text(대기, encoding="utf-8")
    print("수집 DB %d줄 · 미검토 %d줄 → 오늘 판정 %d줄 (뺀 것: %s)"
          % (len(줄들), sum(1 for p in 줄들 if 값(p, "검토 여부") == "미검토"), len(고른),
             " · ".join("%s %d" % kv for kv in sorted(셈.items())) or "없음"))
    print("  소스 %s" % dict(Counter(값(p, "소스") or "빈칸" for p in 고른).most_common()))
    print("  집계처만 한국이라 한 「직접」 줄 %d" % sum(1 for p in 고른 if 재료(p)["집계처 한국"]))
    print("  재료 %s" % (d / "조사재료.json"))
    return 0


def 확정대기(줄들: list[dict], 기록: dict, 뺄: set[str]) -> str:
    """전에 판정했지만 아직 미검토인 줄. 사람이 볼 누적 목록입니다. 조직명이 들어 있습니다."""
    남은 = [(값(p, "사건 ID"), 기록[값(p, "사건 ID")]) for p in 줄들
          if 값(p, "검토 여부") == "미검토" and 값(p, "사건 ID") in 기록 and 값(p, "사건 ID") not in 뺄]
    남은.sort(key=lambda x: ({"사건 O": 0, "사건 X": 1}.get(x[1].get("판정"), 2), x[0]))
    md = ["# 확정 대기 — 전에 AI 가 판정했고 아직 미검토인 줄",
          "", "**조직명이 들어 있다. 레포 · 채팅 밖으로 안 낸다.** 사건 O 로 바꾸면 다음 굽기 때 지도 · RAG 에 나간다.",
          "대시보드에서 O / X 를 누르거나, 사람이 시킨 판에서 `review.py 반영 --사건O LEAK-…` 로 쓴다.", ""]
    for iid, r in 남은:
        md.append("- **%s** · 판정 %s (확신 %s) · %s · 본사 %s · 한국 거점 %s"
                  % (iid, r.get("판정"), r.get("확신"), r.get("날"), r.get("본사") or "모름", r.get("한국 거점") or "모름"))
        md.append("  - 근거: %s" % (r.get("근거") or ""))
        if r.get("출처"):
            md.append("  - 출처: %s" % " · ".join(r["출처"]))
        if (r.get("반박") or {}).get("refuted"):
            md.append("  - 반박: %s" % r["반박"].get("reason", ""))
    if not 남은:
        md.append("없음")
    return "\n".join(md) + "\n"


# ── 결과 ──────────────────────────────────────────────────────
def 제안(r: dict, 무인: bool) -> str:
    """판정 한 줄 → 「사건 X」 또는 「미검토」. **사건 O 는 제안하지 않습니다.**"""
    허용 = ("높음",) if 무인 else ("높음", "중간")
    반 = r.get("refute")
    if r.get("verdict") == "사건 X" and r.get("confidence") in 허용 and isinstance(반, dict) \
            and 반.get("refuted") is False:
        return "사건 X"
    return "미검토"


def 결과(a) -> int:
    d = 날자리(a)
    겉 = json.loads(Path(a.판정).read_text(encoding="utf-8"))
    줄들 = (겉.get("result") or 겉).get("rows") if isinstance(겉, dict) else 겉
    대상 = {x["사건ID"]: x for x in 읽기(d / "대상.json", [])}
    if not 대상:
        raise SystemExit("오늘 대상.json 이 없습니다. 「대상」 을 먼저 돌립니다")
    틀림 = [r.get("id") for r in 줄들 if r.get("verdict") not in 판정값 or r.get("confidence") not in 확신값]
    if 틀림:
        raise SystemExit("판정 · 확신 값이 틀린 줄이 있습니다: %s" % " · ".join(map(str, 틀림[:10])))
    모름 = sorted({r["id"] for r in 줄들} - set(대상))
    빠짐 = sorted(set(대상) - {r["id"] for r in 줄들})
    날 = d.name
    원판, 적용재료 = [], []
    기록 = 읽기(자리(a) / "판정기록.json", {})
    for r in 줄들:
        if r["id"] not in 대상:
            continue
        s = 제안(r, a.무인)
        원판.append({"사건ID": r["id"], "판정": r["verdict"], "확신": r["confidence"], "제안": s,
                   "본사": r.get("hq_country", ""), "한국 거점": r.get("kr_presence", ""),
                   "근거": r.get("reason", ""), "출처": r.get("sources") or [], "반박": r.get("refute")})
        적용재료.append({"page_id": 대상[r["id"]]["page_id"], "사건ID": r["id"], "판정": r["verdict"], "제안": s})
        기록[r["id"]] = {"날": 날, "판정": r["verdict"], "확신": r["confidence"], "제안": s,
                       "본사": r.get("hq_country", ""), "한국 거점": r.get("kr_presence", ""),
                       "근거": r.get("reason", ""), "출처": r.get("sources") or [], "반박": r.get("refute")}
    쓰기(d / "검토_원판.json", 원판)
    쓰기(d / "사건검토_결과.json", 적용재료)
    쓰기(자리(a) / "판정기록.json", 기록)
    (d / "확정목록.md").write_text(확정목록(원판, 날, a.무인), encoding="utf-8")
    print("판정 %d줄 · 대상 %d줄 · 대상에 없는 판정 %d · 판정 없는 대상 %d %s"
          % (len(줄들), len(대상), len(모름), len(빠짐), 빠짐[:5]))
    print("  판정 · 확신 %s" % dict(Counter((r["판정"], r["확신"]) for r in 원판)))
    print("  제안 %s (%s)" % (dict(Counter(r["제안"] for r in 원판)), "무인 — 사건 X 는 확신 높음만" if a.무인 else "사람이 시킨 판"))
    return 0


def 확정목록(원판: list[dict], 날: str, 무인: bool) -> str:
    O = [r for r in 원판 if r["판정"] == "사건 O"]
    X남음 = [r for r in 원판 if r["판정"] == "사건 X" and r["제안"] != "사건 X"]
    낮음 = [r for r in 원판 if r["판정"] == "확신 낮음"]

    def 한줄(r):
        out = ("- **%s** (확신 %s) · 본사 %s · 한국 거점 %s\n  - 근거: %s"
               % (r["사건ID"], r["확신"], r["본사"] or "모름", r["한국 거점"] or "모름", r["근거"]))
        if r["출처"]:
            out += "\n  - 출처: " + " · ".join(r["출처"])
        if (r.get("반박") or {}).get("refuted"):
            out += "\n  - 반박: " + r["반박"].get("reason", "")
        return out

    적용 = sum(1 for r in 원판 if r["제안"] == "사건 X")
    md = ["# 확정 목록 — %s 미검토 판정 (%s)" % (날, "예약 판" if 무인 else "사람이 시킨 판"), "",
          "**조직명이 들어 있다. 레포 · 채팅 밖으로 안 낸다.**", "",
          "사건 X %d줄을 적용 대상으로 골랐다. 아래 %d줄은 **미검토 그대로**다." % (적용, len(O) + len(X남음) + len(낮음)),
          "", "## 사건 O 후보 %d" % len(O), ""] + [한줄(r) for r in O] + \
         ["", "## 사건 X 였지만 적용 안 함 %d — 반박됐거나 확신이 모자람" % len(X남음), ""] + [한줄(r) for r in X남음] + \
         ["", "## 확신 낮음 %d — 조직을 못 특정했거나 한국 거점을 확인 못 함" % len(낮음), ""] + [한줄(r) for r in 낮음]
    return "\n".join(md) + "\n"


# ── 반영 ──────────────────────────────────────────────────────
def _상태(p: dict) -> tuple[str, bool]:
    return 값(p, "검토 여부") or "(빈칸)", bool(값(p, "DB 반영"))


def 반영미리보기(a, n) -> int:
    d = 날자리(a)
    기록자리 = d / "되돌리기.json"
    옛 = 읽기(기록자리, {})
    if 옛.get("적용됨"):
        print("!! 이미 적용한 기록이 있습니다 (%s). 덮어쓰지 않고 멈춥니다" % 옛["적용됨"])
        return 1
    재료들 = 읽기(d / "사건검토_결과.json", [])
    if not 재료들:
        print("사건검토_결과.json 이 없습니다. 「결과」 를 먼저 돌립니다")
        return 1
    뺄 = 보류(a)
    O지정 = {x.strip() for x in (a.사건O or "").split(",") if x.strip()}
    멈출것 = []
    대상 = []
    for x in 재료들:
        if x["사건ID"] in 뺄:
            continue
        if x["사건ID"] in O지정:
            if x["판정"] != "사건 O":
                멈출것.append("%s 는 AI 판정이 %s 입니다. 사건 O 로 쓰려면 대시보드에서 누릅니다" % (x["사건ID"], x["판정"]))
                continue
            대상.append((x, "사건 O"))
        elif x["제안"] == "사건 X":
            대상.append((x, "사건 X"))
    없는O = O지정 - {x["사건ID"] for x in 재료들}
    if 없는O:
        멈출것.append("오늘 판정에 없는 줄을 사건 O 로 적었습니다: %s" % " · ".join(sorted(없는O)))
    지금, 기록줄 = Counter(), []
    for x, 쓸 in 대상:
        p = n.page(x["page_id"])
        if 값(p, "사건 ID") != x["사건ID"]:
            멈출것.append("%s 의 page id 가 노션에서 %s 를 가리킵니다" % (x["사건ID"], 값(p, "사건 ID")))
            continue
        검, 반 = _상태(p)
        지금[(검, 반)] += 1
        기록줄.append({"page_id": x["page_id"], "사건 ID": x["사건ID"], "지금 검토 여부": 검, "지금 DB 반영": 반,
                     "쓸 검토 여부": 쓸, "쓸 DB 반영": 쓸값[쓸], "마지막 수정": p.get("last_edited_time", "")})
    print("대상 %d줄 · 쓸 것 %s" % (len(기록줄), dict(Counter(y["쓸 검토 여부"] for y in 기록줄))))
    for (검, 반), c in sorted(지금.items()):
        print("   지금 %-6s · %-3s %4d%s" % (검, "켜짐" if 반 else "꺼짐", c,
                                        "" if (검, 반) == ("미검토", False) else "   ← 쓸 때 건너뜁니다"))
    쓰기(기록자리, {"무엇": "미검토 판정 반영 — 검토 여부 · DB 반영을 한 번에", "날": d.name,
                 "읽은때": datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"), "데이터소스": 수집DS(),
                 "되돌리려면": "--되돌린다. 우리가 쓴 값 그대로인 줄만 「미검토 · 꺼짐」 으로", "줄": 기록줄})
    print("되돌리기 기록을 썼습니다 — %s" % 기록자리)
    if 멈출것:
        print("!! 멈춥니다")
        for s in 멈출것:
            print("   " + s)
        return 1
    return 0


def 반영쓰기(a, n) -> int:
    d = 날자리(a)
    기록자리 = d / "되돌리기.json"
    기록 = 읽기(기록자리, {})
    if not 기록:
        print("되돌리기 기록이 없습니다. 미리보기를 먼저 돌립니다")
        return 1
    if 기록.get("적용됨"):
        print("이미 적용했습니다 (%s)" % 기록["적용됨"])
        return 1
    쓴것, 건너뜀 = Counter(), []
    for x in 기록["줄"]:
        p = n.page(x["page_id"])
        if _상태(p) != ("미검토", False):
            건너뜀.append("%s 지금 %s" % (x["사건 ID"], _상태(p)[0]))
            continue
        n.update_page(x["page_id"], {"검토 여부": {"select": {"name": x["쓸 검토 여부"]}},
                                     "DB 반영": {"checkbox": x["쓸 DB 반영"]}})
        쓴것[x["쓸 검토 여부"]] += 1
    print("썼습니다 %d (%s) · 건너뜀 %d" % (sum(쓴것.values()), " · ".join("%s %d" % kv for kv in sorted(쓴것.items())),
                                       len(건너뜀)))
    for s in 건너뜀:
        print("  건너뜀  " + s)
    기록["적용됨"] = "%s · %d줄" % (datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"), sum(쓴것.values()))
    쓰기(기록자리, 기록)
    return 0


def 되돌리기(a, n) -> int:
    기록 = 읽기(날자리(a) / "되돌리기.json", {})
    if not 기록:
        print("되돌리기 기록이 없습니다")
        return 1
    되돌린, 그대로 = 0, []
    for x in 기록["줄"]:
        p = n.page(x["page_id"])
        if _상태(p) == (x["쓸 검토 여부"], x["쓸 DB 반영"]):
            n.update_page(x["page_id"], {"검토 여부": {"select": {"name": "미검토"}}, "DB 반영": {"checkbox": False}})
            되돌린 += 1
        else:
            그대로.append(x["사건 ID"])
    print("되돌렸습니다 %d · 그 뒤 바뀌어 안 건드림 %d" % (되돌린, len(그대로)))
    return 0


def 반영(a) -> int:
    날자리(a)                          # 자리부터 본다. 레포 안이면 노션에 붙기 전에 멈춘다
    n = 노션()
    if a.되돌린다:
        return 되돌리기(a, n)
    if a.쓴다:
        r = 반영미리보기(a, n)
        return r if r else 반영쓰기(a, n)
    return 반영미리보기(a, n)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="매일 미검토 판정")
    ap.add_argument("일", choices=["대상", "결과", "반영"])
    ap.add_argument("판정", nargs="?", help="「결과」 에 줄 판정 결과 파일(JSON)")
    ap.add_argument("--자리", help="레포 밖 작업 폴더. 없으면 DARKCHOCO_REVIEW_DIR")
    ap.add_argument("--날", help="YYYYMMDD. 없으면 오늘(KST)")
    ap.add_argument("--다시", action="store_true", help="「대상」: 전에 판정한 줄도 다시 본다")
    ap.add_argument("--무인", action="store_true", help="「결과」: 예약 판. 사건 X 는 확신 높음만")
    ap.add_argument("--쓴다", action="store_true", help="「반영」: 미리보기가 맞으면 노션에 쓴다")
    ap.add_argument("--되돌린다", action="store_true", help="「반영」: 되돌리기 기록대로 되돌린다")
    ap.add_argument("--사건O", help="「반영」: 사람이 정한 줄만 사건 O 로. LEAK-1,LEAK-2")
    a = ap.parse_args(argv)
    if a.사건O and a.무인:
        raise SystemExit("--사건O 는 사람이 시킨 판에서만 씁니다")
    if a.일 == "대상":
        return 대상(a)
    if a.일 == "결과":
        if not a.판정:
            raise SystemExit("판정 결과 파일을 주십시오")
        return 결과(a)
    return 반영(a)


if __name__ == "__main__":
    sys.exit(main())
