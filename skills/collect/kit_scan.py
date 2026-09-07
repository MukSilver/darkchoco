#!/usr/bin/env python3
"""포럼 킷이 낸 수집 파일에서 재유포 후보를 추린다. **읽기만 한다.**

    python -m collect.kit_scan 수집.txt
    python -m collect.kit_scan a.txt b.txt --actor AshleyWood2022 --actor KoreanAshley
    python -m collect.kit_scan 수집.txt --targets 대상목록.txt
    python -m collect.kit_scan 수집.txt --full        걸린 줄을 다 보인다

## 무엇을 가르나

찾는 것은 **원 게시자가 아닌 사람이 그 데이터를 다시 올린 글**이다.
그래서 한 스레드마다 셋을 본다.

    누가 썼나          원문 게시자가 조사 대상(--actor)인가 아닌가
    대상이 나오나       우리가 쫓는 도메인이 제목·본문·답글에 있나
    조사 대상을 부르나   본문이나 답글에 그 핸들이 언급되나

**원문 게시자가 조사 대상이 아닌데 그 대상을 부르거나 우리 도메인이 나오면 재유포 후보다.**
`credits` · `reup` · `dump by` 같은 말이 같이 있으면 거의 확실하다. 퍼간 쪽이 스스로 밝힌 것이다.

## 값은 안 낸다

킷을 마스킹 없이 받으면 파일에 유출 원문이 그대로 있다. 이 도구는 **어느 글 어느 게시물에서
무엇이 걸렸는지만** 낸다. 값을 옮겨 적지 않는다. `--full` 을 줘도 걸린 낱말과 줄 번호까지다.
샘플이 든 스레드는 건수로만 알린다.

## 답글이 잘렸는지도 본다

킷 v2.6 전에는 글 하나에서 첫 쪽 답글만 받았다. 답글 수가 9 나 19 에서 끊겨 있으면
쪽당 10·20건에서 잘린 것이다. 그런 스레드를 따로 알린다. **다시 받아야 한다.**
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

REUP = ("credit", "not my leak", "not mine", "reup", "re-up", "repost", "re-post",
        "mirror", "dump by", "dumped by", "originally", "original post", "source :",
        "found by", "thanks to", "shared by")
# 값이 든 줄로 보이는 꼴. 세기만 하고 내용은 안 낸다
VALUE = (re.compile(r'","'), re.compile(r"[\w.+-]+@[\w-]+\.[\w.]{2,}"))
CUT = (9, 19, 14, 24)      # 쪽당 10·20·15·25건에서 잘린 흔적
# 인사만 한 답글. 받아만 간 사람이다. 재유포 후보에서 뺀다
THANKS = re.compile(
    r"^\W*(thx|thanks?|ty|tysm|thank you|nice|good|great|cool|gg|\+rep|rep\+|bump|"
    r"appreciate\w*|legend|goat|based|first|awesome|amazing|perfect|useful|"
    r"감사|고마|굿|잘 ?쓸|ㄱㅅ)\b", re.I)
# 답글에 뭔가 실려 있다고 볼 꼴. 링크 · 파일 이름 · 도메인
CARRY = (re.compile(r"https?://|magnet:|\.onion\b", re.I),
         re.compile(r"\b[\w.-]+\.(zip|rar|7z|csv|sql|txt|tar|gz)\b", re.I),
         re.compile(r"\b[\w-]+\.(co\.kr|or\.kr|ac\.kr|go\.kr|kr|com|net|org|io|it|fr)\b", re.I))


class 글:
    def __init__(self, 제목):
        self.제목 = 제목
        self.url = ""
        self.게시자 = ""
        self.게시물 = []          # (라벨, 이름, 시작줄)
        self.본문 = []            # 게시물마다 그 글의 줄 목록. 게시물과 자리가 같다
        self.줄 = []              # (줄번호, 본문)
        self.답글쪽 = 1
        self.쪽표시 = False

    @property
    def 답글수(self):
        return sum(1 for L, _, _ in self.게시물 if L.startswith("답글"))

    @property
    def 값줄(self):
        return sum(1 for _, t in self.줄 if any(p.search(t) for p in VALUE))


def 읽기(path: Path) -> list:
    글들, 이제 = [], None
    라벨, 이름 = "", ""
    for i, ln in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
        if ln.startswith("## ") and not ln.startswith("### "):
            이제 = 글(ln[3:].strip())
            글들.append(이제)
            라벨 = 이름 = ""
        elif 이제 is None:
            continue
        elif ln.startswith("- URL : "):
            이제.url = ln[8:].strip()
        elif ln.startswith("- 답글 쪽 : "):
            이제.쪽표시 = True
            m = re.search(r"(\d+)쪽", ln)
            이제.답글쪽 = int(m.group(1)) if m else 1
        elif ln.startswith("### "):
            m = re.match(r"(원문|답글 \d+)\s+(\S+)", ln[4:].strip())
            라벨, 이름 = (m.group(1), m.group(2)) if m else (ln[4:].strip()[:12], "?")
            이제.게시물.append((라벨, 이름, i))
            이제.본문.append([])
            if 라벨 == "원문":
                이제.게시자 = 이름
        else:
            이제.줄.append((i, ln))
            if 이제.본문 and ln.strip() not in ("```", ""):
                이제.본문[-1].append(ln)
    return [g for g in 글들 if g.제목 not in ("수집 요약", "추출된 단서", "못 가져온 것")]


def 걸린것(g: 글, 낱말들) -> dict:
    """낱말마다 (게시물 라벨, 줄번호) 목록. 제목도 같이 본다."""
    out = {}
    for n in 낱말들:
        low = n.lower()
        자리 = []
        if low in g.제목.lower():
            자리.append(("제목", 0))
        for i, t in g.줄:
            if low in t.lower():
                라벨 = "머리"
                for L, nm, s in g.게시물:
                    if s <= i:
                        라벨 = "%s %s" % (L, nm)
                    else:
                        break
                자리.append((라벨, i))
        if 자리:
            out[n] = 자리
    return out


def _실린것(t: str) -> set:
    """글에 실린 링크·파일 이름·도메인. 소문자로 모은다. 값은 안 낸다."""
    s = set()
    for p in CARRY:
        for m in p.finditer(t or ""):
            s.add(m.group(0).lower())
    return s


def 답글자(글들: list, actors: list) -> list:
    """조사 대상의 글에 답글을 단 사람들. 재유포 후보를 좁히는 자리다.

    **많이 나타난 사람과 뭔가 올린 사람은 다르다.** 스물다섯 글에 「thx」만 단 사람은
    받아만 간 사람이고, 여덟 글에 링크를 남긴 사람이 재유포자에 가깝다.
    그래서 인사만 한 답글을 빼고 「실린 것이 있는 답글」 을 따로 센다.

    반환 [(이름, 스레드 수, 답글 수, 실린 답글 수)]. 실린 답글 많은 순.
    """
    낮은 = [a.lower() for a in actors]
    표 = {}
    for g in 글들:
        if not g.게시자 or g.게시자.lower() not in 낮은:
            continue                      # 조사 대상의 글만 본다
        원문토큰 = _실린것("\n".join(g.본문[0])) if g.본문 else set()
        for (라벨, 이름, _), 본문 in zip(g.게시물, g.본문):
            if 라벨 == "원문" or 이름.lower() in 낮은:
                continue
            t = "\n".join(본문).strip()
            인사 = bool(THANKS.match(t)) and len(t) < 120
            # 인용을 걸러야 한다. 답글이 원문을 통째로 인용하면 그 안의 도메인과 샘플이 같이
            # 걸린다. 실측에서 상위 답글자의 「실림」 이 거의 다 인용이었다. 원문에 없던 것만 센다
            새것 = _실린것(t) - 원문토큰
            r = 표.setdefault(이름, {"글": set(), "답글": 0, "실림": 0, "무엇": set()})
            r["글"].add(g.제목)
            r["답글"] += 1
            if not 인사 and 새것:
                r["실림"] += 1
                r["무엇"] |= 새것
    out = [(n, len(v["글"]), v["답글"], v["실림"], sorted(v["무엇"])[:4]) for n, v in 표.items()]
    out.sort(key=lambda x: (-x[3], -x[1], -x[2]))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="킷 수집 파일에서 재유포 후보를 추린다. 읽기만 한다")
    ap.add_argument("files", nargs="+", help="킷이 낸 .txt · .md")
    ap.add_argument("--actor", action="append", default=[],
                    help="조사 대상 핸들. 여러 번 줄 수 있다. 기본은 애슐리 두 핸들")
    ap.add_argument("--targets", help="쫓는 도메인 목록 파일. 한 줄에 하나")
    ap.add_argument("--full", action="store_true", help="걸린 줄 번호를 다 보인다")
    ap.add_argument("--repliers", type=int, nargs="?", const=20, default=0, metavar="N",
                    help="조사 대상 글에 답글을 단 사람을 상위 N명 보인다 (기본 20)")
    a = ap.parse_args(argv)

    actors = a.actor or ["AshleyWood2022", "KoreanAshley"]
    낱말 = list(actors) + [x.lower() for x in actors] + ["애슐리"]
    도메인 = []
    if a.targets:
        도메인 = [l.strip() for l in Path(a.targets).read_text(encoding="utf-8").split("\n")
                if l.strip() and not l.startswith("#")]

    후보, 잘림, 값있음, 모든글 = [], [], [], []
    for f in a.files:
        p = Path(f)
        글들 = 읽기(p)
        모든글 += 글들
        print("=" * 74)
        print("%s  ·  스레드 %d" % (p.name, len(글들)))
        print("=" * 74)
        print("%-40s %-16s %5s %5s" % ("스레드", "원문 게시자", "답글", "쪽"))
        print("-" * 74)
        for g in 글들:
            print("%-40s %-16s %5d %5s" % (g.제목[:40], g.게시자[:16] or "?", g.답글수,
                                          g.답글쪽 if g.쪽표시 else "?"))
            if not g.쪽표시 and g.답글수 in CUT:
                잘림.append((p.name, g))
            if g.값줄:
                값있음.append((p.name, g))

            h_a = 걸린것(g, 낱말)
            h_d = 걸린것(g, 도메인) if 도메인 else {}
            h_r = 걸린것(g, REUP)
            남이썼나 = g.게시자 and g.게시자.lower() not in [x.lower() for x in actors]
            if 남이썼나 and (h_a or h_d):
                후보.append((p.name, g, h_a, h_d, h_r))
        print()

    print("=" * 74)
    print("재유포 후보 — 원문 게시자가 조사 대상이 아닌데 대상이나 도메인이 나온 글")
    print("=" * 74)
    if not 후보:
        print("  없다")
    for fn, g, h_a, h_d, h_r in 후보:
        print("\n★ %s" % g.제목)
        print("   파일     %s" % fn)
        print("   게시자   %s" % g.게시자)
        if g.url:
            print("   주소     %s" % g.url)
        if h_a:
            print("   대상 언급 %s" % " · ".join("%s(%d곳)" % (k, len(v)) for k, v in h_a.items()))
        if h_d:
            print("   도메인   %s" % " · ".join("%s(%d곳)" % (k, len(v)) for k, v in h_d.items()))
        if h_r:
            print("   퍼감 표시 %s" % " · ".join(sorted(h_r)))
        if a.full:
            for k, v in list(h_a.items()) + list(h_d.items()):
                for 라벨, i in v[:6]:
                    print("        「%s」 %s 줄 %s" % (k, 라벨, i or "제목"))

    if 잘림:
        print()
        print("=" * 74)
        print("답글이 잘린 것으로 보이는 글 — 킷 v2.6 으로 다시 받을 것")
        print("=" * 74)
        for fn, g in 잘림:
            print("   %-44s 답글 %d (쪽당 %d건에서 잘림)" % (g.제목[:44], g.답글수, g.답글수 + 1))

    if 값있음:
        print()
        print("=" * 74)
        print("유출 원문이 든 글 — 값은 안 낸다. 건수만")
        print("=" * 74)
        for fn, g in 값있음:
            print("   %-52s 값으로 보이는 줄 %d" % (g.제목[:52], g.값줄))

    답글꾼 = 답글자(모든글, actors) if a.repliers else []
    if a.repliers:
        print()
        print("=" * 74)
        print("조사 대상 글에 답글을 단 사람 — 실린 것이 있는 답글 많은 순")
        print("=" * 74)
        print("「실림」 은 인사말이 아니고 **원문에 없던** 링크·파일 이름·도메인이 든 답글이다.")
        print("원문을 인용만 한 답글은 안 센다. 인용에는 원문의 도메인과 샘플이 그대로 들어 있다.")
        print()
        print("%-22s %6s %6s %6s   %s" % ("사람", "스레드", "답글", "실림", "무엇이 실렸나"))
        print("-" * 74)
        for n, s, r, c, 무엇 in 답글꾼[:a.repliers]:
            print("%-22s %6d %6d %6d   %s" % (n[:22], s, r, c, " · ".join(무엇)[:34]))
        보임 = sum(1 for x in 답글꾼 if x[3])
        print()
        print("답글을 단 사람 %d명 · 그중 실린 것이 있는 사람 %d명" % (len(답글꾼), 보임))

    print()
    print("스레드 %d · 재유포 후보 %d · 답글 잘림 %d · 원문 든 글 %d"
          % (len(모든글), len(후보), len(잘림), len(값있음)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
