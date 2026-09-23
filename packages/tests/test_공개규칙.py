"""검토를 바꿀 때 「DB 반영」(공개)을 어떻게 맞추나 — 시험. **노션에 안 붙습니다.**

    python packages/tests/test_공개규칙.py          CI 가 이렇게 돌린다
    python -m pytest packages/tests/test_공개규칙.py

2026-09-23 최현서 결정이다.

    미검토 · 사건 X → 사건 O     켠다
    사건 O · 빈칸  → 사건 O     안 건드린다   일부러 꺼 둔 것을 되살리지 않는다
    무엇이든      → 사건 X     끈다
    무엇이든      → 미검토     끈다

**규칙이 두 벌이다.** 로컬 `apps/dash/api.py` 는 파이썬, 배포 `deploy/worker.js` 는
JS 다. 한쪽만 고치면 로컬과 배포가 다르게 움직이고, 그것은 화면에서 안 보인다.
그래서 **같은 표를 양쪽에 먹여** 답이 같은지 본다.

**실행부를 둔다.** CI 는 이 폴더를 `python 파일` 로 돌린다. 실행부가 없으면 함수만
정의하고 아무 시험도 안 돈 채 통과한다 (`test_dash_reader.py` 가 지금 그렇다).

**가짜를 꼭 되돌린다.** `test_crawler.py` 가 파일을 불러오는 순간 가짜를 심고 안
되돌려서, pytest 로 여럿을 같이 돌리면 다른 시험이 떨어졌다 (2026-09-23 확인).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packages"))
sys.path.insert(0, str(ROOT / "apps" / "dash"))

import api  # noqa: E402

워커 = ROOT / "apps" / "dash" / "deploy" / "worker.js"

# (전, 후) → 켠다 True · 끈다 False · 안 건드린다 None
# 전 "" 는 노션 빈칸이다. 화면이 사건 O 로 센다
표 = {
    ("미검토", "사건 O"): True,
    ("사건 X", "사건 O"): True,
    ("사건 O", "사건 O"): None,
    ("", "사건 O"): None,

    ("미검토", "사건 X"): False,
    ("사건 O", "사건 X"): False,
    ("사건 X", "사건 X"): False,
    ("", "사건 X"): False,

    ("미검토", "미검토"): False,
    ("사건 O", "미검토"): False,
    ("사건 X", "미검토"): False,
    ("", "미검토"): False,
}


def test_파이썬_규칙이_표와_같다():
    for (전, 후), 기대 in 표.items():
        assert api.공개로(전, 후) is 기대, "%r → %r : %r (기대 %r)" % (전, 후, api.공개로(전, 후), 기대)


def _js_규칙():
    """worker.js 에서 `function 공개로` 를 떼어 온다. 손으로 베끼면 파일과 어긋난다."""
    글 = 워커.read_text(encoding="utf-8")
    m = re.search(r"^function 공개로\(전, 후\) \{\n.*?^\}\n", 글, re.S | re.M)
    assert m, "worker.js 에서 function 공개로 를 못 찾았다"
    return m.group(0)


def test_js_규칙이_표와_같다():
    node = shutil.which("node")
    if not node:
        # CI 러너(ubuntu-latest)에는 node 가 있다. 여기서 빠지는 것은 로컬뿐이다
        print("  ?? node 가 없어 JS 쪽을 못 봤다. 파이썬 쪽만 봤다")
        return
    물음 = [[전, 후] for (전, 후) in 표]
    코드 = _js_규칙() + "\nconst q = %s;\nconsole.log(JSON.stringify(q.map(([a,b]) => 공개로(a,b))));\n" % json.dumps(물음, ensure_ascii=False)
    r = subprocess.run([node, "-e", 코드], capture_output=True, text=True,
                       encoding="utf-8", timeout=30)
    assert r.returncode == 0, "node 가 실패했다: " + r.stderr[:300]
    답 = json.loads(r.stdout.strip())
    for (전, 후), js답 in zip(표, 답):
        assert js답 == 표[(전, 후)], "JS %r → %r : %r (기대 %r)" % (전, 후, js답, 표[(전, 후)])


# ── 검토바꾸기() 를 가짜 노션으로 끝까지 ─────────────────────

class _가짜노션:
    def __init__(self, 소속, 검토, 반영):
        self.줄 = {"parent": {"type": "data_source_id", "data_source_id": 소속},
                  "properties": {"검토 여부": {"select": {"name": 검토} if 검토 else None},
                                 "DB 반영": {"checkbox": 반영}}}
        self.쓴것 = []

    def page(self, page_id):
        return self.줄

    def request(self, method, path, body=None):
        self.쓴것.append((method, path, body))
        return {}


def _돌리기(가짜, 값):
    """api 의 노션을 가짜로 바꿔 한 번 부르고 **반드시 되돌린다.**"""
    옛n, 옛db = api._n, api._수집DB
    api._n = 가짜
    api._수집DB = lambda: "5160ce53-7ce2-4271-879e-06f3ad9957cf"
    try:
        return api.검토바꾸기("0" * 32, 값)
    finally:
        api._n, api._수집DB = 옛n, 옛db


def test_미검토에서_사건O_로_가면_한_번에_둘을_쓴다():
    가짜 = _가짜노션("5160ce53-7ce2-4271-879e-06f3ad9957cf", "미검토", False)
    답 = _돌리기(가짜, "사건 O")
    assert len(가짜.쓴것) == 1, "두 번 나눠 쓰면 하나만 될 수 있다"
    칸 = 가짜.쓴것[0][2]["properties"]
    assert 칸["검토 여부"] == {"select": {"name": "사건 O"}}
    assert 칸["DB 반영"] == {"checkbox": True}
    assert 답["공개"] is True and 답["DB반영"] is True


def test_이미_사건O_인_줄은_공개를_안_건드린다():
    """일부러 꺼 둔 사건 O 줄이다. O 를 한 번 더 눌러도 안 켜진다."""
    가짜 = _가짜노션("5160ce53-7ce2-4271-879e-06f3ad9957cf", "사건 O", False)
    답 = _돌리기(가짜, "사건 O")
    assert "DB 반영" not in 가짜.쓴것[0][2]["properties"]
    assert 답["공개"] is None and 답["DB반영"] is False


def test_다른_DB_줄이면_아무것도_안_쓴다():
    """검증 DB 에도 「DB 반영」 이 있다. page id 만 맞으면 남의 공개 스위치를 건드린다."""
    가짜 = _가짜노션("0d7b48c3-e744-4800-a591-a70b7c93fd20", "미검토", False)
    try:
        _돌리기(가짜, "사건 O")
    except ValueError as e:
        assert "수집 DB" in str(e)
    else:
        raise AssertionError("다른 DB 줄인데 막지 않았다")
    assert 가짜.쓴것 == [], "막았어야 하는데 썼다"


def test_가짜를_되돌렸다():
    """다음 시험이 가짜 노션을 받지 않는다."""
    _돌리기(_가짜노션("5160ce53-7ce2-4271-879e-06f3ad9957cf", "미검토", False), "미검토")
    assert not isinstance(api._n, _가짜노션)
    assert api._수집DB.__name__ == "_수집DB"


if __name__ == "__main__":
    시험들 = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    실패 = 0
    for 이름, f in 시험들:
        try:
            f()
            print("  OK  %s" % 이름)
        except Exception as e:  # noqa: BLE001
            실패 += 1
            print("  !!  %s — %s: %s" % (이름, type(e).__name__, e))
    print("\n%d개 중 %d개 실패" % (len(시험들), 실패))
    sys.exit(1 if 실패 else 0)
