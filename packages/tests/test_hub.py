"""hub 골격이 서는지 확인합니다.

    python packages/tests/test_hub.py

밖에 요청을 보내지 않습니다. 등록·건너뛰기·표 넣기만 봅니다.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages"))
sys.path.insert(0, str(ROOT))

from dc_console import use_utf8  # noqa: E402
from dc_store import Item, Store  # noqa: E402

from hub import registry, runner  # noqa: E402
from hub.contract import Ctx, Needs, Skip  # noqa: E402

use_utf8()


def _dc(*args: str):
    r = subprocess.run([sys.executable, "dc.py", *args], cwd=ROOT,
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120,
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def test_어댑터가_등록된다():
    es = registry.목록()
    assert es, "어댑터를 하나도 못 찾는다"
    이름 = [e.name for e in es]
    assert "tg-preview" in 이름, 이름


def test_머리글을_모듈_없이_읽는다():
    """목록만 볼 때 무거운 것이 딸려 오면 안 된다."""
    e = registry.하나("tg-preview")
    assert e is not None
    assert e.owner == "최현서", e.owner
    assert e.every == 60, f"주기가 {e.every} 로 읽혔다. 뒤 주석을 못 뗀 것이다"
    assert "미리보기" in e.summary


def test_목록은_requests_없이도_읽힌다():
    """자식 프로세스에서 requests 를 막고 목록을 읽어 본다."""
    막기 = "\n".join([
        "import sys",
        "class _막개:",
        "    def find_spec(self, name, path=None, target=None):",
        "        if name.split('.')[0] in ('requests', 'telethon'):",
        "            raise ImportError(name + ' 없음')",
        "        return None",
        "sys.meta_path.insert(0, _막개())",
        f"sys.path.insert(0, r'{ROOT}')",
        "from hub import registry",
        "print(len(registry.목록()))",
    ])
    r = subprocess.run([sys.executable, "-c", 막기], cwd=ROOT,
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=60)
    assert r.returncode == 0, "목록을 읽는 데 무거운 것이 필요하다\n" + (r.stderr or "")[:400]


def test_준비가_안되면_안씀으로_센다():
    """실패가 아니라 건너뛴 것이어야 한다. 그 둘은 다르다."""
    with tempfile.TemporaryDirectory() as d:
        store = Store(Path(d) / "t.db")
        try:
            env = dict(os.environ)
            env.pop("DARKCHOCO_CHANNELS", None)
            옛 = os.environ.pop("DARKCHOCO_CHANNELS", None)
            try:
                r = runner.한판("tg-preview", store, dry=True, 조용히=True)
            finally:
                if 옛 is not None:
                    os.environ["DARKCHOCO_CHANNELS"] = 옛
        finally:
            store.close()
    # 이 PC 에 채널 목록이 있으면 정상적으로 돌 수도 있다. 둘 다 실패는 아니다.
    assert not r.error, f"실패로 셌다: {r.error}"


def test_없는_어댑터는_실패로_돌려준다():
    with tempfile.TemporaryDirectory() as d:
        store = Store(Path(d) / "t.db")
        try:
            r = runner.한판("없는것", store, dry=True, 조용히=True)
        finally:
            store.close()
    assert r.error, "없는 어댑터인데 성공으로 셌다"


def test_Needs_가_모자란것을_짚는다():
    n = Needs(packages=["절대로없는모듈이름"], secrets=["절대로없는환경변수"])
    모자람 = n.모자란것({}, ROOT)
    assert len(모자람) == 2, 모자람
    assert any("안 깔림" in m for m in 모자람)
    assert any("비어 있음" in m for m in 모자람)


def test_표에_넣고_다시_넣으면_안_늘어난다():
    """같은 글이 두 줄로 갈리지 않아야 한다."""
    with tempfile.TemporaryDirectory() as d:
        store = Store(Path(d) / "t.db")
        try:
            it = Item(source="telegram", venue="t.me/x", src_id="1",
                      title="같은 글")
            첫번 = store.put(it, "2026-08-28")
            두번 = store.put(it, "2026-08-28")
            assert 첫번 is True, "처음 넣은 것이 새것이 아니라고 한다"
            assert 두번 is False, "같은 글이 두 번 새것으로 들어간다"
            assert len(store.rows()) == 1, "같은 글이 두 줄이 됐다"
        finally:
            store.close()


def test_dc_plan_이_돈다():
    code, out = _dc("plan")
    assert code == 0, out[:400]
    assert "tg-preview" in out, out[:400]


def test_dc_run_dry_가_돈다():
    code, out = _dc("run", "--dry", "--limit", "1")
    assert code == 0, "미리보기가 실패로 끝났다\n" + out[:600]
    assert "돈 것" in out, out[:400]


def test_차례표가_실패로_안_밀린다():
    """실패했을 때 last_ok 를 갱신하면 다음 시도가 주기만큼 밀린다.

    6시간짜리는 18시간, 하루짜리는 사흘이 되어 사실상 멈춘다.
    """
    from hub.sched import Sched

    with tempfile.TemporaryDirectory() as d:
        s = Sched(Path(d) / "s.db")
        try:
            t = 1_000_000.0
            s.됐다("x", now=t)
            s.안됐다("x", "일부러", now=t + 100)
            줄 = s.상태()[0]
            assert 줄["last_ok"] == t, "실패가 last_ok 를 밀었다"
            assert 줄["fails"] == 1
        finally:
            s.close()


def test_실패하면_짧은_간격으로_다시_본다():
    from hub.sched import Sched

    with tempfile.TemporaryDirectory() as d:
        s = Sched(Path(d) / "s.db")
        try:
            t = 1_000_000.0
            s.안됐다("x", now=t)
            assert s.언제("x", 360, t + 60) is None, "실패 직후에 또 시도한다"
            assert s.언제("x", 360, t + 5 * 60 + 1) is not None, "5분 뒤에 안 한다"
            s.안됐다("x", now=t + 400)
            assert s.언제("x", 360, t + 400 + 5 * 60 + 1) is None, "간격이 안 늘었다"
            assert s.언제("x", 360, t + 400 + 10 * 60 + 1) is not None
        finally:
            s.close()


def test_안쓴것은_차례를_안건드린다():
    """준비가 안 돼 건너뛴 것은 성공도 실패도 아니다."""
    from hub.sched import Sched

    with tempfile.TemporaryDirectory() as d:
        db = Path(d) / "t.db"
        옛 = os.environ.pop("DARKCHOCO_CHANNELS", None)
        try:
            runner.여러판(["tg-preview"], db=db)
        finally:
            if 옛 is not None:
                os.environ["DARKCHOCO_CHANNELS"] = 옛
        s = Sched(db)
        try:
            줄 = s.상태()
        finally:
            s.close()
    if 줄:   # 채널 목록이 이 PC 에 있으면 돌았을 수도 있다
        assert 줄[0]["fails"] == 0, "안 쓴 것을 실패로 셌다"


def test_install_task_가_명령을_만든다():
    code, out = _dc("install-task", "--show")
    assert code == 0, out[:400]
    assert "Register-ScheduledTask" in out
    assert "Unregister-ScheduledTask" in out, "끄는 방법을 안 알려준다"
    # 예전에는 "run --due" 가 들어 있는지만 봤다. 그것이 auto 로 못 바꾸게
    # 막고 있었다 — 스케줄러가 수집기만 부르고 명부 조사는 안 하는 상태를
    # 이 검사가 굳혀 두고 있었다.
    #
    # 봐야 하는 것은 낱말이 아니라 뜻이다. **때가 된 것만 돌리는가.**
    assert 'dc.py" auto' in out, "auto 를 안 부른다"
    from hub.crawler.run import 여러갈래
    import inspect
    assert "때된것만" in inspect.signature(여러갈래).parameters
    from hub.runner import 여러판
    assert "때된것만" in inspect.signature(여러판).parameters


def test_plan_이_다음차례를_보여준다():
    code, out = _dc("plan")
    assert code == 0, out[:400]
    assert "다음" in out and "돌 때가 된 것" in out, out[:400]


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_"):
            v(); print(f"  OK  {k}"); n += 1
    print(f"\n{n}개 통과")
