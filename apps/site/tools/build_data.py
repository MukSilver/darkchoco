# -*- coding: utf-8 -*-
"""노션 → apps/site/data/leak-map.json

화면은 노션을 직접 부르지 않습니다. 토큰이 브라우저로 나가면 안 되기 때문입니다.
이 스크립트가 노션을 읽어 JSON 한 장을 만들고, 화면은 그 파일만 읽습니다.

    python apps/site/tools/build_data.py --out apps/site/data/leak-map.json

NOTION_TOKEN_FILE 이 있어야 합니다. 토큰을 저장소에 커밋하지 않습니다.
지금은 뼈대이고, 실제 조회는 packages/dc_notion 을 붙여 채웁니다.
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

# 도메인이 이름에 섞여 나가면 안 됩니다. 나가기 전에 여기서 막습니다.
DOMAINISH = re.compile(
    r"\b[A-Za-z0-9][A-Za-z0-9-]{1,30}\."
    r"(?:io|is|in|to|net|com|onion|st|cx|ws|cc|su|ru|as|pw)\b")


def strip_domain(name: str) -> str:
    """이름은 남기고 TLD만 뗍니다. 팀 규칙은 이름 허용 · 도메인 금지입니다."""
    return DOMAINISH.sub(lambda m: m.group(0).rsplit(".", 1)[0], name or "").strip()


def decide_layer(row: dict) -> str:
    """오픈웹이냐 다크웹이냐. 포럼 DB의 주소·어니언 주소 칸으로 정합니다.
    조사 진척도가 아니라 그 자리에 닿는 데 필요한 것입니다."""
    if row.get("어니언 주소") and not row.get("주소"):
        return "deep"
    if row.get("가입 필요"):
        return "deep"
    return "sky"


def build(client=None) -> dict:
    """packages/dc_notion 의 읽기 함수를 붙여 채웁니다.
    지금은 자리만 잡아 두고, 붙기 전까지는 기존 예시 파일을 건드리지 않습니다."""
    raise NotImplementedError(
        "packages/dc_notion 연결이 아직입니다. "
        "붙기 전까지 data/leak-map.json 의 예시 데이터를 씁니다.")


def check(doc: dict) -> list:
    """내보내기 전 검사. 화면이 하는 검사와 같은 규칙입니다."""
    bad = []
    ids = {p["id"] for p in doc.get("places", [])}
    cases = {p["id"]: p.get("cases", 0) for p in doc.get("places", [])}
    layer = {p["id"]: p.get("layer") for p in doc.get("places", [])}

    for p in doc.get("places", []):
        if DOMAINISH.search(p.get("name", "")):
            bad.append("자리 이름에 도메인: %s" % p["id"])
    for f in doc.get("flows", []):
        if f["from"] not in ids or f["to"] not in ids:
            bad.append("없는 자리를 잇는 선: %s → %s" % (f["from"], f["to"]))
            continue
        if f.get("cases") is not None and f["cases"] > min(cases[f["from"]], cases[f["to"]]):
            bad.append("선의 건수가 자리보다 큼: %s → %s" % (f["from"], f["to"]))
        if f["kind"] == "drop" and layer[f["from"]] != "sky":
            bad.append("내려가는 선인데 출발이 위층이 아님: %s" % f["from"])
        if f["kind"] == "rise" and layer[f["from"]] != "deep":
            bad.append("올라오는 선인데 출발이 아래층이 아님: %s" % f["from"])
    s = doc.get("stats", {})
    order = ["reported", "matched", "circulating", "judged"]
    for a, b in zip(order, order[1:]):
        if s.get(b, 0) > s.get(a, 0):
            bad.append("깔때기 순서가 뒤집힘: %s < %s" % (a, b))
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--check-only", action="store_true",
                    help="기존 파일만 검사하고 끝냅니다")
    args = ap.parse_args()

    if args.check_only:
        doc = json.load(open(args.out, encoding="utf-8"))
    else:
        doc = build()
        doc.setdefault("meta", {})["generated"] = datetime.now(KST).isoformat()
        doc["meta"]["is_sample"] = False

    bad = check(doc)
    if bad:
        print("검사에서 걸렸습니다:", file=sys.stderr)
        for b in bad:
            print("  · " + b, file=sys.stderr)
        sys.exit(1)

    if not args.check_only:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
    print("이상 없습니다 · 자리 %d · 선 %d"
          % (len(doc.get("places", [])), len(doc.get("flows", []))))


if __name__ == "__main__":
    main()
