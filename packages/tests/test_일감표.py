#!/usr/bin/env python3
"""대시보드 일감표와 워크플로가 어긋나지 않았나.

`apps/dash/deploy/worker.js` 의 `일감표` 는 각 단추가 **어느 워크플로를 어떤
입력으로** 부를지 적은 표다. 그 입력 이름은 워크플로의 `workflow_dispatch.inputs`
에 실제로 있어야 한다. 하나라도 어긋나면 단추를 눌렀을 때 GitHub 이 422 를 내는데,
**화면에는 그냥 실패로 뜨고 무엇이 틀렸는지 안 보인다.**

이 레포가 되풀이해 겪은 「조용한 불일치」를 겨냥한다. 밖으로 안 나간다.

    python packages/tests/test_일감표.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

루트 = Path(__file__).resolve().parents[2]
워커 = 루트 / "apps" / "dash" / "deploy" / "worker.js"
워크플로자리 = 루트 / ".github" / "workflows"

친것 = []
샌것 = []


def 봄(이름: str, 되나: bool, 말: str = "") -> None:
    """`말` 은 **틀렸을 때만** 찍는다. 통과 줄에 실패 문구가 붙으면 읽는 사람이
    무엇이 잘못됐나 하고 멈춘다."""
    (친것 if 되나 else 샌것).append(이름)
    print(("  OK  " + 이름) if 되나
          else ("  !!  " + 이름 + (("  — " + 말) if 말 else "")))


def 일감표읽기() -> dict:
    """`worker.js` 에서 일감표를 뽑는다. node 를 안 쓰고 정규식으로 읽는다.

    표가 규칙적인 꼴이라 이것으로 된다. 꼴이 흐트러지면 여기서 먼저 걸린다.
    """
    글 = 워커.read_text(encoding="utf-8")
    m = re.search(r"^const 일감표 = \{$(.*?)^\};$", 글, re.S | re.M)
    assert m, "worker.js 에서 일감표를 못 찾았다"
    몸 = m.group(1)

    밖 = {}
    for 덩이 in re.finditer(
            r"^  (\S+): \{$(.*?)^  \},$", 몸, re.S | re.M):
        열쇠, 속 = 덩이.group(1), 덩이.group(2)
        항목 = {}
        for 칸 in ("무리", "이름", "종류", "파일"):
            v = re.search(r'^    %s: "(.*?)",$' % 칸, 속, re.M)
            if v:
                항목[칸] = v.group(1)
        for 칸 in ("밖", "노션"):
            v = re.search(r"^    %s: (true|false),$" % 칸, 속, re.M)
            if v:
                항목[칸] = v.group(1) == "true"
        입력 = re.search(r"^    입력: \{(.*?)\},$", 속, re.M | re.S)
        항목["입력"] = dict(re.findall(r'(\w+): "(.*?)"', 입력.group(1))) if 입력 else {}
        밖[열쇠] = 항목
    return 밖


def 워크플로입력(파일: str) -> dict:
    """`workflow_dispatch.inputs` 를 읽는다. yaml 없이 줄로 읽는다.

    CI 의 `no-install` 잡에서도 돌아야 해서 pyyaml 에 안 기댄다.
    """
    글 = (워크플로자리 / 파일).read_text(encoding="utf-8")
    m = re.search(r"^  workflow_dispatch:$(.*?)^(?:\w|concurrency|permissions|env|jobs)",
                  글, re.S | re.M)
    if not m:
        return {}
    몸 = m.group(1)
    i = 몸.find("    inputs:")
    if i < 0:
        return {}
    밖 = {}
    이름 = None
    for 줄 in 몸[i:].splitlines()[1:]:
        if 줄.strip() and not 줄.startswith("      "):
            break
        m2 = re.match(r"^      (\w+):\s*$", 줄)
        if m2:
            이름 = m2.group(1)
            밖[이름] = {"options": []}
            continue
        if 이름 is None:
            continue
        m3 = re.match(r"^        type:\s*(\S+)", 줄)
        if m3:
            밖[이름]["type"] = m3.group(1)
        m4 = re.match(r"^        options:\s*\[(.*?)\]", 줄)
        if m4:
            밖[이름]["options"] = [x.strip() for x in m4.group(1).split(",")]
    return 밖


def 요약무늬읽기() -> list:
    """worker.js 의 `요약무늬` 를 파이썬 정규식으로 옮긴다. 이 범위에서는 꼴이 같다."""
    글 = 워커.read_text(encoding="utf-8")
    m = re.search(r"^const 요약무늬 = \[$(.*?)^\];$", 글, re.S | re.M)
    assert m, "worker.js 에서 요약무늬를 못 찾았다"
    return [re.compile(x) for x in re.findall(r"^\s*/(.+)/,\s*$", m.group(1), re.M)]


# 대시보드 로그 요약에 **떠야 하는** 명부 줄. (파일, 코드에 있어야 할 문구, 찍히는 꼴)
#
# 2026-09-23 에 `run.py` 가 건너뜀 문구를 바꾸고 worker.js 의 무늬를 안 바꿔서, 그 줄이
# 대시보드에서 조용히 빠졌다. 코드 문구가 바뀌면 둘째 칸 검사가 먼저 떨어져 여기를
# 같이 보게 된다.
떠야할줄 = [
    ("hub/places/run.py", "깊은 판을 건너뜁니다 — ",
     "깊은 판을 건너뜁니다 — playwright 가 안 깔렸습니다"),
    ("hub/places/run.py", "분에서 끊습니다",
     "깊은 판을 90분에서 끊습니다 (40/97)"),
    ("hub/places/run.py", "수치까지 본 것 ",
     "포럼 DB        열린 곳 8 · 수치까지 본 것 12 · 사람 줄과 다름 3 · 자동 줄 새로 2 · 고침 1  41초"),
    ("hub/places/run.py", "— 자동 줄 새로 ",
     "썼습니다 — 자동 줄 새로 12 · 고침 3 · 살펴볼 것 48 · 사람 줄은 안 건드립니다"),
    ("hub/places/run.py", "명부에 없는 이웃 ",
     "명부에 없는 이웃 42곳 (노션에 안 씁니다)"),
    ("hub/places/probe/ransom.py", "달치를 받습니다",
     "집계처에서 피해 6달치를 받습니다 (요청 사이 62초라 6분쯤 걸립니다)"),
]

# **떠서는 안 되는** 줄. `--요약만` 을 뺐을 때 찍히는 꼴이다. 레포가 공개라 무늬가
# 이런 줄을 집으면 이름이 화면과 로그 요약으로 나간다
안떠야할줄 = [
    "!! 다크포럼클론3: 스키마에 없는 칸 ['별칭']",
    "mirror2.onion                                    ← qilin",
]


def 로그무늬검사() -> None:
    무늬 = 요약무늬읽기()
    for 파일, 문구, 꼴 in 떠야할줄:
        봄("%s 가 「%s」 를 아직 찍는다" % (파일, 문구.strip()),
           문구 in (루트 / 파일).read_text(encoding="utf-8"),
           "문구가 바뀌었다. worker.js 요약무늬도 같이 본다")
        봄("대시보드가 「%s」 줄을 잡는다" % 문구.strip(),
           any(p.search(꼴.strip()) for p in 무늬), 꼴)
    for 꼴 in 안떠야할줄:
        걸린것 = [p.pattern for p in 무늬 if p.search(꼴.strip())]
        봄("이름이 든 줄을 안 잡는다 — %s" % 꼴[:24], not 걸린것, " · ".join(걸린것))


def main() -> int:
    표 = 일감표읽기()
    봄("일감표를 읽었다 (%d개)" % len(표), len(표) >= 4,
       " · ".join(표) if len(표) < 4 else "")

    # 워크플로마다 한 번만 읽는다
    입력표 = {}
    for 열쇠, 일감 in 표.items():
        f = 일감.get("파일")
        if f and f not in 입력표:
            있나 = (워크플로자리 / f).is_file()
            봄("%s 가 있다" % f, 있나)
            입력표[f] = 워크플로입력(f) if 있나 else {}

    for 열쇠, 일감 in sorted(표.items()):
        종류 = 일감.get("종류")
        봄("%s — 종류가 밖/손 중 하나다" % 열쇠, 종류 in ("밖", "손"), repr(종류))

        # 화면이 `무리` 로 단추를 묶습니다 (`index.html` 의 `무리차례`).
        # 빠지면 그 일감만 소제목 없이 맨 위에 떠서, 아홉이 다시 평평해집니다.
        # **조용히 어긋납니다** — 화면은 무리가 없어도 안 깨집니다
        봄("%s — 무리가 있다" % 열쇠, bool(일감.get("무리")), repr(일감.get("무리")))

        if 종류 == "밖":
            # 「밖」 인데 파일이 없으면 .../workflows/undefined/dispatches 로 나간다
            봄("%s — 밖이면 파일이 있다" % 열쇠, bool(일감.get("파일")))
        else:
            # 「손」 인데 파일이 있으면 상태보기가 엉뚱한 실행을 보여 준다
            봄("%s — 손이면 파일이 없다" % 열쇠, not 일감.get("파일"))
            continue

        가진입력 = 입력표.get(일감["파일"], {})
        for 이름, 값 in (일감.get("입력") or {}).items():
            봄("%s — %s 가 %s 에 있다" % (열쇠, 이름, 일감["파일"]),
               이름 in 가진입력)
            꼴 = (가진입력.get(이름) or {}).get("type")
            if 꼴 == "boolean":
                # 문자열로 보내야 한다. 워크플로가 "true"/"false" 만 받는다
                봄("%s — %s 는 true/false 다" % (열쇠, 이름),
                   값 in ("true", "false"), repr(값))
            if 꼴 == "choice":
                고를것 = (가진입력.get(이름) or {}).get("options") or []
                봄("%s — %s 가 고를 수 있는 값이다" % (열쇠, 이름),
                   값 in 고를것, "%r 은 %s 에 없다" % (값, 고를것))

    # 워크플로 입력 이름과 잡 ID 에 한글을 쓰면 파일 자체가 거부된다
    for f in sorted(p.name for p in 워크플로자리.glob("*.yml")):
        글 = (워크플로자리 / f).read_text(encoding="utf-8")
        잡들 = re.findall(r"^  ([^\s:]+):$", 글.split("jobs:", 1)[-1], re.M)
        나쁜 = [j for j in 잡들 if not j.isascii()]
        봄("%s — 잡 ID 가 영문이다" % f, not 나쁜, " · ".join(나쁜))
        나쁜입력 = [k for k in 워크플로입력(f) if not k.isascii()]
        봄("%s — 입력 이름이 영문이다" % f, not 나쁜입력, " · ".join(나쁜입력))

    로그무늬검사()

    print("\n%d개 중 %d개 실패" % (len(친것) + len(샌것), len(샌것)))
    return 1 if 샌것 else 0


if __name__ == "__main__":
    sys.exit(main())
