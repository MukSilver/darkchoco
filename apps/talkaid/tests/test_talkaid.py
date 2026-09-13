#!/usr/bin/env python3
"""들어가는 자리 시험. **모델을 안 올리고 창도 안 띄운다.**

    python tests/test_talkaid.py

여기서 보는 것은 하나다 — **바꿔 쓰기 규칙이 조용히 빠지지 않는가.**

`en_style.json` 은 스킬 쪽이 정본이고 이 앱에는 사본을 두지 않는다. 그래서
앱 폴더만 떼어 오거나 exe 에 안 실으면 규칙 스물다섯 짝이 통째로 빠지는데,
죽지도 경고하지도 않아서 쓰는 사람이 모른다. 2026-09-13 에 실제로 지어 둔
exe 가 그 상태였다. 그 일이 되풀이되지 않게 여기서 묶어 둔다.

윈도우가 아니어도 돈다. 창과 클립보드를 안 건드린다.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

여기 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(여기))
import talkaid as T  # noqa: E402

fails = []


def check(name, got, want):
    if got != want:
        fails.append("%s\n     받음 %r\n     기대 %r" % (name, got, want))


# ── 규칙 읽기 ────────────────────────────────────
swaps, 상용구, 알림 = T.규칙()
check("셋을 낸다", (type(swaps), type(상용구), type(알림)), (list, dict, str))

# 레포 안에서 돌리고 있으니 정본이 잡혀야 한다
if not swaps:
    fails.append("레포 안인데 바꿔 쓰기가 비었다. 정본을 못 찾았다:\n     %s" % 알림)
if "en_style.json" not in 알림:
    fails.append("어느 파일을 읽었는지 안 적었다: %r" % 알림)
if not 상용구:
    fails.append("snippets.json 을 못 읽었다")

# ── 못 찾으면 반드시 알린다 ──────────────────────
# 이것이 이 파일의 존재 이유다. 조용히 빠지면 쓰는 사람이 모른다
원래 = T.HERE
try:
    T.HERE = Path(tempfile.mkdtemp()) / "없는앱" / "자리"
    빈swaps, _, 빈알림 = T.규칙()
    check("못 찾으면 규칙이 빈다", 빈swaps, [])
    if "못 찾았다" not in 빈알림:
        fails.append("못 찾았는데 조용하다: %r" % 빈알림)
    if "찾아본 자리" not in 빈알림:
        fails.append("어디를 찾았는지 안 알려 준다: %r" % 빈알림)
finally:
    T.HERE = 원래

# ── exe 에도 실리나 ──────────────────────────────
# spec 이 정본을 읽어 넣어야 한다. 안 넣으면 exe 로 받은 사람만 규칙이 빠진다
spec = (여기 / "talkaid.spec").read_text(encoding="utf-8")
for 이름 in ("terms.json", "snippets.json", "en_style.json"):
    if 이름 not in spec:
        fails.append("talkaid.spec 이 %s 를 안 싣는다. "
                     "exe 로 받은 사람만 그것이 빠진 채 돈다" % 이름)

# 정본은 스킬 쪽 하나다. 앱 폴더에 사본을 두면 갱신이 두 번이 되고 갈린다
if (여기 / "en_style.json").exists():
    fails.append("apps/talkaid/en_style.json 이 생겼다. **사본을 두지 않는다** — "
                 "정본은 skills/skills/darkweb-verify-ko/tools 다")

# ── 로그 자리 ────────────────────────────────────
# TEMP 는 안 된다. 이 PC 에서 TEMP 가 C:\Users\Public\... 이었고 거기는 남도 읽는다
if "Public" in str(T.로그파일):
    fails.append("로그가 공용 폴더로 간다: %s" % T.로그파일)
check("로그는 설정 자리에 둔다", T.로그파일.parent.name, "darkchoco")

# ── 결과 ─────────────────────────────────────────
if fails:
    print("실패 %d" % len(fails))
    for f in fails:
        print("  - %s" % f)
    sys.exit(1)
print("통과. 시험 4 묶음")
