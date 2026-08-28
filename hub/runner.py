"""어댑터를 부르고 결과를 표에 넣습니다.

지키는 것 셋입니다.

  1. **어댑터 하나가 죽어도 나머지는 돕니다.** 한 출처가 막혔다고 그날
     수집이 통째로 멈추면 안 됩니다.
  2. **넣은 수와 나온 수를 셉니다.** 같은 글이 한 줄로 뭉치면 조용히
     사라집니다. dc_store 의 KEY 주석에 그 사고가 적혀 있습니다.
  3. **안 돈 것과 못 본 것을 나눕니다.** 준비가 안 돼 건너뛴 것을 실패로
     세면 화면이 거짓말을 합니다.

어댑터 안의 일은 어댑터에 맡깁니다. 여기서 요청을 보내거나 간격을 재지
않습니다. 그것은 원래 도구가 겪어서 얻은 것들이라 그대로 씁니다.
"""

from __future__ import annotations

import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "packages"))
sys.path.insert(0, str(ROOT))

from dc_store import Store  # noqa: E402

from hub import registry  # noqa: E402
from hub.contract import Ctx, Result, Skip  # noqa: E402

__all__ = ["한판", "여러판", "기본_표"]


def 기본_표() -> Path:
    """수집 표가 놓이는 자리. .gitignore 가 hub/data/ 를 막습니다."""
    return ROOT / "hub" / "data" / "darkchoco.db"


def _오늘() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")


def 한판(이름: str, store: Store, *, dry: bool = False, limit: int = 0,
        조용히: bool = False) -> Result:
    """어댑터 하나를 돌립니다. 예외를 밖으로 안 냅니다."""
    e = registry.하나(이름)
    if e is None:
        return Result(name=이름, error="그런 어댑터가 없습니다")

    r = Result(name=이름)
    t0 = time.time()
    ctx = Ctx(root=ROOT, env=dict(os.environ), today=_오늘(), dry=dry, limit=limit)

    try:
        mod = registry.불러오기(e)
    except ImportError as exc:
        # 무거운 것이 안 깔린 경우입니다. 실패가 아니라 안 돈 것입니다.
        r.skipped = f"안 깔림: {exc}"
        r.seconds = time.time() - t0
        return r

    모자람 = mod.NEEDS.모자란것(ctx.env, ROOT)
    if 모자람:
        r.skipped = " · ".join(모자람)
        r.seconds = time.time() - t0
        return r

    try:
        for it in mod.collect(ctx):
            r.got += 1
            if not dry and store.put(it, ctx.today):
                r.fresh += 1
            if limit and r.got >= limit:
                break
    except Skip as exc:
        r.skipped = str(exc) or "건너뜀"
    except KeyboardInterrupt:
        raise
    except Exception as exc:  # noqa: BLE001  한 어댑터가 전체를 멈추면 안 됩니다
        r.error = f"{type(exc).__name__}: {exc}"
        if not 조용히:
            print(f"  [{이름}] 실패 — {r.error}", file=sys.stderr)
            traceback.print_exc(limit=3, file=sys.stderr)

    r.seconds = time.time() - t0
    return r


def 여러판(이름들: list[str] | None = None, *, db: Path | None = None,
         dry: bool = False, limit: int = 0) -> list[Result]:
    """여럿을 차례로 돌립니다. 하나가 죽어도 계속합니다."""
    대상 = 이름들 or [e.name for e in registry.목록()]
    db = db or 기본_표()
    db.parent.mkdir(parents=True, exist_ok=True)

    결과 = []
    store = Store(db)
    try:
        for 이름 in 대상:
            r = 한판(이름, store, dry=dry, limit=limit)
            결과.append(r)
            if not dry:
                store.log_run(
                    started=datetime.now(timezone.utc).isoformat(),
                    source=이름, got=r.got, fresh=r.fresh,
                    note=r.skipped or r.error or "",
                )
    finally:
        store.close()
    return 결과


def 표로(결과: list[Result]) -> str:
    """사람이 읽을 한 판 요약."""
    if not 결과:
        return "  돌린 어댑터가 없습니다."

    폭 = max(len(r.name) for r in 결과) + 2
    줄 = []
    for r in 결과:
        if r.skipped:
            상태 = f"안 씀    {r.skipped}"
        elif r.error:
            상태 = f"실패     {r.error}"
        else:
            상태 = f"받음 {r.got:<5} 새것 {r.fresh:<5} {r.seconds:.1f}초"
        줄.append(f"  {r.name.ljust(폭)}{상태}")

    돈것 = [r for r in 결과 if r.됐나]
    안돈것 = [r for r in 결과 if r.skipped]
    실패 = [r for r in 결과 if r.error]
    줄.append("")
    줄.append(f"  돈 것 {len(돈것)} · 안 쓴 것 {len(안돈것)} · 실패 {len(실패)}"
              f" · 새로 들어온 것 {sum(r.fresh for r in 결과)}")
    return "\n".join(줄)
