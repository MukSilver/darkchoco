#!/usr/bin/env python3
"""번역이 나아졌는지 잰다. **사람이 판정하고 도구는 세기만 한다.**

    python 판정.py 돌리기 opus              판정결과/opus.md 가 나온다
    python 판정.py 세기 opus                사람이 표시한 것을 센다
    python 판정.py 견주기 opus gemma        두 판을 나란히. 뒤집힌 줄만

「스무 문장 중 넷이 틀렸다」가 유일한 기준선인데 재현할 수가 없었다.
모델을 바꾸든 프롬프트를 바꾸든 나아졌다고 말하려면 **같은 것을 다시 재야 한다.**

## 왜 사람이 판정하나

「뜻이 틀렸나」를 기계가 못 잰다. BLEU·COMET 은 코퍼스 수준 연속 점수라
한 문장을 보내도 되는지 아닌지에 답하지 못한다. 자동 판정을 붙이면
**틀린 것을 맞다고 세는 자**가 생긴다. 그것이 자 없는 것보다 나쁘다.

    O   뜻이 맞다.  보내도 된다
    X   **뜻이 틀렸다.**  보내면 조사가 망가진다
    ~   뜻은 맞는데 어색하다

## 세트를 고치면 옛 결과와 못 견준다

그래서 결과 파일 머리에 세트의 지문을 적는다. 세트가 바뀌면 세기와 견주기가 알린다.
**문장을 지우지 않는다. 늘리기만 한다.**
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

세트 = HERE / "판정세트.md"
결과 = HERE / "판정결과"

# 엔진을 늘릴 때 여기 한 줄만 더한다. 코드를 안 고친다
ENGINES = {
    "opus": "OPUS-MT 기계번역 (CPU int8) + 자리표 + 어미 고치기",
    "qwen1.7b": "로컬 LLM Qwen3-1.7B (CPU int8) + 프롬프트 사전",
}

줄 = re.compile(r"^-\s+(.+?)\s*$", re.M)
갈래 = re.compile(r"^##\s+(.+?)\s*$", re.M)
표시 = re.compile(r"^##\s+(\d+)\s+\[(.)\]", re.M)
지문줄 = re.compile(r"^    세트\s+(\S+)\s+·\s+(\d+)줄", re.M)


def 읽기() -> tuple[list[tuple[str, str]], str]:
    """(갈래, 문장) 목록과 세트 지문. 파일 순서가 번호다."""
    if not 세트.exists():
        raise SystemExit("판정세트.md 가 없다: %s" % 세트)
    t = 세트.read_text(encoding="utf-8")
    out, 현갈래 = [], ""
    for line in t.splitlines():
        m = 갈래.match(line)
        if m:
            현갈래 = m.group(1)
            continue
        m = 줄.match(line)
        if m:
            out.append((현갈래, m.group(1)))
    문장들 = "\n".join(s for _, s in out)
    return out, hashlib.sha256(문장들.encode("utf-8")).hexdigest()[:12]


def 엔진만들기(이름: str):
    if 이름 not in ENGINES:
        raise SystemExit("모르는 엔진: %s\n  있는 것: %s" % (이름, " · ".join(ENGINES)))
    import json
    import engine as E
    swaps = []
    for p in (HERE / "en_style.json",
              HERE.parents[1] / "skills" / "skills" / "darkweb-verify-ko"
              / "tools" / "en_style.json"):
        if p.exists():
            swaps = json.loads(p.read_text(encoding="utf-8")).get("바꿔 쓰기", [])
            break
    llm = 이름 if 이름 in getattr(E, "LLM_MODELS", {}) else None
    return E.Engine(swaps=swaps, llm=llm)


def 돌리기(이름: str, 엔진: str, 역번역: bool) -> int:
    문장들, 지문 = 읽기()
    eng = 엔진만들기(엔진)
    결과.mkdir(exist_ok=True)
    out = 결과 / ("%s.md" % 이름)
    if out.exists():
        print("  이미 있다: %s" % out)
        print("  덮으면 사람이 적은 판정이 날아간다. 다른 이름을 쓰거나 그 파일을 옮긴다.")
        return 1

    쪽 = ["# 판정 결과 — %s" % 이름, "",
         "    엔진   %s (%s)" % (엔진, ENGINES[엔진]),
         "    세트   %s · %d줄" % (지문, len(문장들)),
         "",
         "**각 줄의 `[ ]` 에 O · X · ~ 를 적는다.**",
         "",
         "    O   뜻이 맞다. 보내도 된다",
         "    X   뜻이 틀렸다. 보내면 조사가 망가진다",
         "    ~   뜻은 맞는데 어색하다",
         "",
         "다 적었으면 `python 판정.py 세기 %s`" % 이름, "", "---", ""]

    앞갈래, 총ms = None, 0.0
    for i, (g, s) in enumerate(문장들, 1):
        if g != 앞갈래:
            쪽 += ["", "### %s" % g, ""]
            앞갈래 = g
        try:
            r = eng.run(s, "ko-en", back=역번역)
            총ms += r.ms
            쪽 += ["## %d  [ ]" % i,
                  "    한국어  %s" % s,
                  "    영어    %s" % r.text]
            if r.back:
                쪽.append("    역번역  %s" % r.back)
            if r.terms:
                쪽.append("    용어    %s" % " · ".join(sorted(set(r.terms.values()))))
            쪽.append("")
        except Exception as e:
            쪽 += ["## %d  [ ]" % i,
                  "    한국어  %s" % s,
                  "    **못 돌렸다**  %s: %s" % (type(e).__name__, e), ""]
        print("\r  %d / %d" % (i, len(문장들)), end="", flush=True)

    쪽 += ["", "---", "", "    평균 %.0f ms · 합계 %.1f 초" % (총ms / max(len(문장들), 1), 총ms / 1000)]
    out.write_text("\n".join(쪽) + "\n", encoding="utf-8")
    print("\n  %s  %d줄 · 평균 %.0f ms" % (out, len(문장들), 총ms / max(len(문장들), 1)))
    print("  이제 그 파일을 열어 각 줄에 O · X · ~ 를 적는다.")
    return 0


def 표시읽기(이름: str) -> tuple[dict[int, str], str, int]:
    p = 결과 / ("%s.md" % 이름)
    if not p.exists():
        raise SystemExit("그 결과가 없다: %s" % p)
    t = p.read_text(encoding="utf-8")
    m = 지문줄.search(t)
    지문, n = (m.group(1), int(m.group(2))) if m else ("?", 0)
    표 = {}
    for num, mark in 표시.findall(t):
        표[int(num)] = mark.strip().upper()
    return 표, 지문, n


def 세기(이름: str) -> int:
    표, 지문, n = 표시읽기(이름)
    _, 지금지문 = 읽기()
    문장들, _ = 읽기()

    센것 = {"O": 0, "X": 0, "~": 0, "": 0}
    for i in range(1, n + 1):
        센것[표.get(i, "") if 표.get(i, "") in 센것 else ""] += 1

    print("\n  %s" % 이름)
    if 지문 != 지금지문:
        print("  **세트가 바뀌었다** (%s → %s). 옛 결과와 견주면 안 된다." % (지문, 지금지문))
    print("  --------------------------------")
    적힌것 = n - 센것[""]
    for k, 뜻 in [("O", "뜻이 맞다"), ("X", "뜻이 틀렸다"), ("~", "어색하다")]:
        비율 = (센것[k] / 적힌것 * 100) if 적힌것 else 0
        print("  %s  %3d개  %5.1f%%   %s" % (k, 센것[k], 비율, 뜻))
    if 센것[""]:
        print("      %3d개          아직 안 적었다" % 센것[""])
    print("  --------------------------------")
    if 적힌것:
        print("  보낼 수 있는 것 %.1f%%  (O 만)" % (센것["O"] / 적힌것 * 100))

    틀린것 = [i for i in range(1, n + 1) if 표.get(i) == "X"]
    if 틀린것:
        print("\n  뜻이 틀린 줄")
        for i in 틀린것:
            if i <= len(문장들):
                print("    %2d  %s" % (i, 문장들[i - 1][1][:56]))
    return 0


def 견주기(a: str, b: str) -> int:
    표a, 지문a, na = 표시읽기(a)
    표b, 지문b, nb = 표시읽기(b)
    문장들, _ = 읽기()
    if 지문a != 지문b:
        print("  **세트가 다르다** (%s vs %s). 견주면 안 된다." % (지문a, 지문b))
        return 1

    좋아짐, 나빠짐, 같음 = [], [], 0
    for i in range(1, max(na, nb) + 1):
        x, y = 표a.get(i, ""), 표b.get(i, "")
        if not x or not y:
            continue
        if x == y:
            같음 += 1
        elif x == "X" and y in ("O", "~"):
            좋아짐.append((i, x, y))
        elif y == "X" and x in ("O", "~"):
            나빠짐.append((i, x, y))
        elif x == "~" and y == "O":
            좋아짐.append((i, x, y))
        elif x == "O" and y == "~":
            나빠짐.append((i, x, y))

    print("\n  %s  →  %s" % (a, b))
    print("  --------------------------------")
    print("  좋아짐 %d · 나빠짐 %d · 그대로 %d" % (len(좋아짐), len(나빠짐), 같음))
    for 제목, 목록 in [("좋아진 줄", 좋아짐), ("**나빠진 줄**", 나빠짐)]:
        if 목록:
            print("\n  %s" % 제목)
            for i, x, y in 목록:
                s = 문장들[i - 1][1][:50] if i <= len(문장들) else ""
                print("    %2d  %s → %s   %s" % (i, x, y, s))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="번역이 나아졌는지 잰다. 판정은 사람이 한다")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("돌리기", help="세트를 돌려 판정할 파일을 만든다")
    p.add_argument("이름", help="이 판의 이름. 판정결과/<이름>.md 로 나온다")
    p.add_argument("--엔진", default="opus", choices=list(ENGINES))
    p.add_argument("--역번역없이", action="store_true", help="빠르게. 역번역을 안 낸다")

    q = sub.add_parser("세기", help="사람이 적은 판정을 센다")
    q.add_argument("이름")

    c = sub.add_parser("견주기", help="두 판을 나란히. 뒤집힌 줄만")
    c.add_argument("이름1")
    c.add_argument("이름2")

    a = ap.parse_args()
    if a.cmd == "돌리기":
        return 돌리기(getattr(a, "이름"), getattr(a, "엔진"),
                      not getattr(a, "역번역없이"))
    if a.cmd == "세기":
        return 세기(getattr(a, "이름"))
    return 견주기(getattr(a, "이름1"), getattr(a, "이름2"))


if __name__ == "__main__":
    raise SystemExit(main())
