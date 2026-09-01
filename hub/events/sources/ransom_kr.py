"""랜섬웨어 유출 사이트에서 한국 관련 피해를 골라 옵니다.

원래 도구는 apps/kr-leak-alarm 입니다. 안유빈 님이 만든 것이고, 여기서는
그 소스들을 부르고 결과를 표 모양으로 바꾸기만 합니다.

**API 를 직접 치지 않습니다.** 그 앱에는 겪어서 얻은 방어가 들어 있습니다.

  · 연속 세 번 실패하면 멈춥니다. 차단당한 상태에서 계속 쏘면 차단
    기간만 길어집니다. 실제로 IP 가 막힌 적이 있습니다
  · 한 판에 도는 벤더 수를 제한하고 커서를 남겨 며칠에 걸쳐 훑습니다
  · 허용 목록 밖 호스트와 HTTPS 가 아닌 요청을 막습니다

여기서 API 를 새로 치면 그 방어가 없는 길이 하나 더 생깁니다.

한국 관련성과 공급망 위험 판정도 그 앱 것을 그대로 씁니다. 두 축은 서로
독립적으로 매겨집니다.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterator

NAME = "ransom-kr"
SUMMARY = "랜섬 피드 세 곳에서 한국 피해를 골라 옵니다"
OWNER = "안유빈"
EVERY = 360
RUNS_IN = "host"

ROOT = Path(__file__).resolve().parents[3]   # hub/events/sources/ 에서 세 칸
APP = ROOT / "apps" / "kr-leak-alarm"
sys.path.insert(0, str(APP))

from hub.events.contract import Ctx, Item, Needs, Skip  # noqa: E402

NEEDS = Needs(packages=["requests", "defusedxml"])


def _설정():
    """앱 설정을 읽습니다. config.json 이 없으면 기본값으로 돕니다."""
    from collector.config import load_config

    쓸것 = APP / "config.json"
    return load_config(쓸것 if 쓸것.is_file() else None)


def _항목으로(r) -> Item:
    """LeakRecord 를 표 한 줄로 바꿉니다.

    판정 결과(kr_tier · supply_tier)는 raw 에 dict 로 넣습니다. 표의 이름
    있는 칸에 그 개념이 없기 때문입니다. 나중에 칸을 만들면 옮기면 됩니다.

    today 를 받았지만 안에서 쓰지 않고 있었습니다. 날짜는 run.한판 이
    store.put(it, ctx.today) 로 따로 넣습니다. 안 쓰는 인자를 두면 여기서도
    날짜를 정하는 것처럼 보여서 뗍니다.
    """
    부가 = {
        "kr_tier": r.kr_tier, "kr_score": r.kr_score,
        "kr_reasons": list(r.kr_reasons or [])[:6],
        "supply_tier": r.supply_tier, "supply_score": r.supply_score,
        "supply_reasons": list(r.supply_reasons or [])[:6],
        "sector": r.sector, "discovered": r.discovered,
        "victim_key": r.victim_key, "group_key": r.group_key,
    }
    return Item(
        source="ransom",
        venue=r.source or "ransom",
        venue_kind="dls",
        src_id=r.uid or "",
        actor=r.group or "",
        target_org=r.victim or "",
        target_domain=r.website or "",
        title=f"{r.group} — {r.victim}".strip(" —"),
        body=r.description or "",
        body_kind="회사 소개" if r.description else "없음",
        body_via="api",
        posted_at=r.published or "",
        post_url=r.post_url or "",
        country=r.country or "",
        kind="유출 게시",
        got_by=f"kr-leak-alarm/{r.source}",
        # dc_store 가 dict 를 받아 자기가 JSON 으로 만듭니다(contract.Item.raw 는
        # dict, _impl.put 이 json.dumps 를 겁니다). 여기서 미리 만들어 넘기면
        # 두 겹이 되어 raw like '%"kr_tier"%' 로 못 찾습니다.
        # ransomlive.py 와 tg_post.py 는 처음부터 dict 를 넘깁니다
        raw={k: v for k, v in 부가.items() if v},
    )


def collect(ctx: Ctx) -> Iterator[Item]:
    if ctx.dry:
        raise Skip("미리보기에서는 안 돕니다. 이 어댑터는 밖에 요청을 보냅니다")

    from collector.http_client import SafeHttpClient
    from collector.kr_filter import KrClassifier
    from collector.sources import build_sources

    cfg = _설정()
    분류 = KrClassifier(cfg.get("kr_detection", {}))

    공급 = None
    try:
        from collector.supply_filter import SupplyClassifier
        공급 = SupplyClassifier(cfg.get("supply_detection", {}), root=APP)
    except Exception:  # noqa: BLE001  공급망 축은 없어도 수집은 됩니다
        pass

    client = SafeHttpClient(cfg.get("network", {}))
    try:
        소스들 = build_sources(client, cfg.get("sources", {}))
        if not 소스들:
            raise Skip("켜진 소스가 없습니다. config.json 의 sources 를 보십시오")

        for s in 소스들:
            try:
                레코드 = list(s.fetch())
            except Exception as e:  # noqa: BLE001  한 소스가 막혀도 다음으로
                print(f"    {s.name}: {e}", file=sys.stderr)
                continue

            if s.errors:
                # 앱이 남긴 오류는 그대로 보여 줍니다. 네트워크 장애로 0건인지
                # 진짜 0건인지 구분해야 합니다.
                for msg in s.errors[:3]:
                    print(f"    {s.name}: {msg}", file=sys.stderr)

            for r in 레코드:
                # classify 는 결과를 돌려주기만 합니다. 레코드에 얹는 것은
                # 부르는 쪽 몫이라 여기서 합니다.
                r.kr_tier, r.kr_score, r.kr_reasons = 분류.classify(r)
                if 공급 is not None and getattr(공급, "enabled", False):
                    r.supply_tier, r.supply_score, r.supply_reasons = 공급.classify(r)
                yield _항목으로(r)
    finally:
        try:
            client.close()
        except Exception:  # noqa: BLE001
            pass
