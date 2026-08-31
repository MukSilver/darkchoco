"""
main.py — Kr-Leak-alarm CLI 진입점.

사용법:
  python -m collector.main run          # 수집 → KR 판별 → 저장 → 알림 → 웹 데이터 생성
  python -m collector.main run --no-notify
  python -m collector.main stats        # 현황 요약
  python -m collector.main new          # 미확인(NEW) 목록 출력
  python -m collector.main ack          # 전체 NEW 해제
  python -m collector.main ack --uid <uid> ...
  python -m collector.main export       # DB → 웹 데이터만 재생성
  python -m collector.main doctor       # 환경/보안 설정 점검
  python -m collector.main serve        # localhost 정적 서버로 대시보드 열기
"""

from __future__ import annotations

import argparse
import http.server
import logging
import sys
from pathlib import Path
from typing import Any

# 윈도우 콘솔(cp949)에서 한글·기호로 죽는 것을 막습니다.
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "packages"))
from dc_console import use_utf8  # noqa: E402

use_utf8()

from .config import load_config, load_dotenv, resolve_path
from .export import export
from .http_client import SafeHttpClient
from .kr_filter import TIER_SCORE, KrClassifier
from .notify import notify_new
from .safety import defang_url, detect_hypervisor
from .sources import build_sources
from .store import Store
from .supply_filter import TIER_LABEL as SUPPLY_LABEL
from .supply_filter import TIER_SCORE as SUPPLY_SCORE
from .supply_filter import SupplyClassifier

log = logging.getLogger("krleak")


def setup_logging(log_file: Path | None, verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )


# ─────────────────────────────────────────────────────────────
# run
# ─────────────────────────────────────────────────────────────

def cmd_run(cfg: dict[str, Any], args: argparse.Namespace) -> int:
    db_path = resolve_path(cfg, "database")
    web_dir = resolve_path(cfg, "web_data_dir")
    root = Path(cfg["_root"])

    # 축 1: 한국 관련성 / 축 2: 공급망 위험 — 서로 독립적으로 평가된다
    classifier = KrClassifier(cfg.get("kr_detection", {}))
    supply = SupplyClassifier(cfg.get("supply_detection", {}), root=root)
    min_score = TIER_SCORE.get(classifier.min_tier, 60)
    min_supply = SUPPLY_SCORE.get(supply.min_tier, 50) if supply.enabled else 10_000

    with Store(db_path) as store, SafeHttpClient(cfg.get("network", {})) as client:
        run_id = store.start_run()
        try:
            return _run_once(cfg, args, store, client, supply, classifier,
                             run_id, web_dir, min_score, min_supply)
        except KeyboardInterrupt:
            # ★ 중단해도 실행 상태를 'running' 으로 방치하지 않는다.
            #    그러면 대시보드에 영원히 '상태: running' 이 남는다.
            store.finish_run(run_id, fetched=0, kr_matched=0, new_count=0,
                             status="interrupted", detail="사용자 중단(Ctrl+C)")
            print("\n중단되었습니다.")
            return 130
        except Exception as exc:
            store.finish_run(run_id, fetched=0, kr_matched=0, new_count=0,
                             status="error", detail=f"예외: {exc}"[:2000])
            raise


def _run_once(cfg, args, store, client, supply, classifier,
              run_id, web_dir, min_score, min_supply) -> int:
    first_run = store.is_first_run()
    if first_run:
        log.info("최초 실행입니다 — 기존 이력 전체를 적재하며, 알림은 보내지 않습니다.")

    sources_cfg = _prepare_sources_cfg(cfg, supply, store)
    if getattr(args, "no_vendor_search", False):
        rl = sources_cfg.get("ransomware_live")
        if isinstance(rl, dict):
            rl["_skip_vendor_search"] = True
    sources = build_sources(client, sources_cfg)
    if not sources:
        log.error("활성화된 소스가 없습니다. config.json 의 sources 를 확인하세요.")
        store.finish_run(run_id, fetched=0, kr_matched=0, new_count=0,
                         status="error", detail="no sources enabled")
        return 2

    fetched: list[Any] = []
    errors: list[str] = []
    healthy = 0
    for src in sources:
        try:
            got = list(src.fetch())
            fetched.extend(got)
            log.info("소스 %s: %d건 수집", src.name, len(got))
            # 벤더 순회 커서를 다음 실행으로 넘긴다
            if hasattr(src, "next_vendor_cursor"):
                store.set_setting("vendor_cursor", str(src.next_vendor_cursor))
        except Exception as exc:  # 한 소스가 죽어도 나머지는 계속
            src.note_error(str(exc))
            log.exception("소스 %s 실패", src.name)
        # 어댑터가 내부에서 삼킨 오류도 여기서 회수한다
        for e in src.errors:
            errors.append(f"{src.name}: {e}")
        if not src.errors:
            healthy += 1

    rate_limited = any(getattr(s, "rate_limited", False) for s in sources)
    if rate_limited:
        print("\n" + "=" * 72)
        print("  ⚠ ransomware.live 가 요청을 거부하고 있습니다 (레이트리밋 추정).")
        print("=" * 72)
        print("  이번 실행에서는 추가 요청을 보내지 않고 중단했습니다.")
        print("  · 30분~수 시간 뒤 자동으로 풀립니다. 그때 다시 실행하세요.")
        print("  · 그동안 요청을 반복하면 차단이 길어집니다.")
        print("  · 벤더 검색 없이 핵심 데이터만 받으려면:")
        print("      scripts\\run.bat --no-vendor-search\n")

    if healthy == 0:
        # 모든 소스가 실패 — 기존 DB 내용은 보존한 채 상태만 error 로 남긴다
        log.error("모든 소스가 실패했습니다. 네트워크/방화벽을 확인하세요.")
        export(store, web_dir, min_score=min_score, min_supply_score=min_supply)
        store.finish_run(run_id, fetched=0, kr_matched=0, new_count=0,
                         status="rate_limited" if rate_limited else "error",
                         detail="; ".join(errors)[:2000])
        print("\n⚠ 모든 데이터 소스 조회에 실패했습니다. 기존 데이터는 그대로 유지됩니다.")
        for e in errors[:5]:
            print(f"   · {e[:160]}")
        return 1

    # ── 이중 축 판별 ──
    matched: list[Any] = []
    kr_hits = supply_hits = 0
    for rec in fetched:
        tier, score, reasons = classifier.classify(rec)
        rec.kr_tier, rec.kr_score, rec.kr_reasons = tier, score, reasons

        s_tier, s_score, s_reasons = supply.classify(rec)
        rec.supply_tier, rec.supply_score, rec.supply_reasons = s_tier, s_score, s_reasons

        kr_ok = classifier.meets_threshold(tier)
        supply_ok = supply.enabled and supply.meets_threshold(s_tier)
        if kr_ok:
            kr_hits += 1
        if supply_ok:
            supply_hits += 1
        if kr_ok or supply_ok:      # 두 축은 OR — 어느 쪽이든 걸리면 보관
            matched.append(rec)

    log.info(
        "수집 %d건 → 저장 대상 %d건 (한국 관련 %d · 공급망 %d, 중복 포함)",
        len(fetched), len(matched), kr_hits, supply_hits,
    )

    # ── 저장 & NEW 추출 ──
    newly = store.upsert_many(matched)
    newly = [
        n for n in newly
        if int(n.get("kr_score") or 0) >= min_score
        or int(n.get("supply_score") or 0) >= min_supply
    ]

    baseline_mode = first_run or getattr(args, "baseline", False)

    # ★ 대량 신규는 '진짜 신규'가 아니라 재동기화다.
    #   DB 를 지웠거나 며칠 API 가 막혔다가 복구되면 수백 건이 한꺼번에
    #   들어오는데, 그걸 전부 토스트로 띄우면 알림이 무의미해진다.
    surge_limit = int(cfg.get("notify", {}).get("resync_threshold", 30))
    if not baseline_mode and len(newly) > surge_limit:
        baseline_mode = True
        print(f"\n  ℹ 신규 {len(newly)}건은 임계값({surge_limit})을 초과합니다.")
        print("    DB 초기화 또는 장기간 수집 공백 이후의 재동기화로 판단해")
        print("    이번에는 알림을 보내지 않고 기준선으로 처리합니다.")
        print("    (데이터는 정상 저장되며 대시보드 '전체' 탭에서 볼 수 있습니다)\n")
        log.info("재동기화 감지 — 신규 %d건을 기준선으로 처리합니다.", len(newly))

    if baseline_mode:
        store.acknowledge()  # 기준선 적재분은 NEW 로 두지 않는다
        newly = []

    # ── 알림 ──
    if newly and not args.no_notify:
        notify_new(newly, cfg.get("notify", {}))
    elif newly:
        log.info("신규 %d건 (알림 비활성화)", len(newly))

    # ── 웹 데이터 ──
    export(store, web_dir, min_score=min_score, min_supply_score=min_supply)

    store.finish_run(
        run_id, fetched=len(fetched), kr_matched=len(matched), new_count=len(newly),
        status="ok" if not errors else "partial", detail="; ".join(errors)[:2000],
    )

    _print_new(newly)
    if errors:
        log.warning("일부 소스 실패: %s", "; ".join(errors))
    return 0


def _prepare_sources_cfg(cfg: dict[str, Any], supply: SupplyClassifier, store: Store) -> dict[str, Any]:
    """소스 설정에 공급망 벤더 검색어와 순회 커서를 주입한다.

    핵심 벤더는 '최근 100건' 피드에 안 잡히는 경우가 많아(몇 주 전 사고),
    검색 엔드포인트로 별도 확인이 필요하다. 매 실행마다 목록의 일부만 돌려
    레이트리밋을 피하면서 며칠에 걸쳐 전체를 훑는다.
    """
    import copy

    sources_cfg = copy.deepcopy(cfg.get("sources", {}) or {})
    rl = sources_cfg.get("ransomware_live")
    if not isinstance(rl, dict) or not rl.get("enabled"):
        return sources_cfg
    if "vendor_search" not in (rl.get("modes") or []):
        return sources_cfg
    if not supply.enabled:
        rl["modes"] = [m for m in rl["modes"] if m != "vendor_search"]
        return sources_cfg

    terms: list[str] = []
    for patterns in supply.vendor_groups.values():
        terms.extend(term for term, _ in patterns)
    for vendor in supply.vendors:          # 우리 회사 협력사를 최우선으로 앞에 붙인다
        terms = list(vendor["names"]) + terms

    # 검색어로 쓰기엔 너무 일반적인 단어는 제외 (검색 결과가 수천 건 나옴)
    terms = [t for t in terms if len(t) >= 5 and " " not in t.strip()[:4]]

    rl["vendor_terms"] = terms
    rl["_vendor_cursor"] = int(store.get_setting("vendor_cursor", "0") or 0)
    return sources_cfg


def _print_new(items: list[dict[str, Any]]) -> None:
    if not items:
        print("\n신규 건 없음.")
        return

    # 두 목록은 같은 기준의 앞뒤다. 전에는 `i not in kr_items` 로 dict 를 통째로
    # 값 비교해서 건수가 늘면 느려졌다. 같은 판정식을 한 번 더 쓰면 결과는 같다.
    def _is_kr(item: dict[str, Any]) -> bool:
        return int(item.get("kr_score") or 0) >= 60

    kr_items = [i for i in items if _is_kr(i)]
    supply_only = [i for i in items if not _is_kr(i)]

    print(f"\n{'='*72}\n  🚨 신규 {len(items)}건 "
          f"(한국 관련 {len(kr_items)} · 공급망 {len(supply_only)})\n{'='*72}")

    def show(it: dict[str, Any], axis: str) -> None:
        if axis == "kr":
            badge, reasons = it.get("kr_tier", ""), it.get("kr_reasons") or []
        else:
            badge = SUPPLY_LABEL.get(it.get("supply_tier", ""), it.get("supply_tier", ""))
            reasons = it.get("supply_reasons") or []
        country = it.get("country") or "?"
        print(f"  [{badge:<9}] {it.get('victim')}  ({country})")
        print(f"      그룹: {it.get('group_name')}   도메인: {defang_url(it.get('website') or '-')}")
        print(f"      근거: {', '.join(reasons) or '-'}")
        print(f"      시각: {(it.get('discovered') or it.get('published') or '')[:19]}")
        print()

    if kr_items:
        print("── 한국 관련 ────────────────────────────────────────────\n")
        for it in kr_items:
            show(it, "kr")
    if supply_only:
        print("── 공급망 위험 (해외 벤더/협력사) ───────────────────────\n")
        for it in supply_only:
            show(it, "supply")


# ─────────────────────────────────────────────────────────────
# 기타 커맨드
# ─────────────────────────────────────────────────────────────

def cmd_stats(cfg: dict[str, Any], args: argparse.Namespace) -> int:
    with Store(resolve_path(cfg, "database")) as store:
        s = store.stats()
        print(f"\n총 {s['total']}건  |  미확인 NEW {s['new']}건")
        print("\n  [한국 관련]")
        print(f"    확정 {s['confirmed']}  유력 {s['strong']}  "
              f"추정 {s['likely']}  검토필요 {s['review']}")
        print("\n  [공급망 위험]")
        print(f"    직거래 {s.get('supply_direct',0)}  핵심벤더 {s.get('supply_critical',0)}  "
              f"한국진출 {s.get('supply_korea_ops',0)}  업종위험 {s.get('supply_sector',0)}"
              f"   (합계 {s.get('supply_total',0)})")
        if s["top_groups"]:
            print("\n  한국 대상 상위 그룹:")
            for g in s["top_groups"][:10]:
                print(f"    {g['count']:>4}건  {g['group']}")
        lr = s.get("last_run")
        if lr:
            print(f"\n  최근 실행: {lr.get('started_at','')[:19]} "
                  f"({lr.get('status')}) 수집 {lr.get('fetched')}건 / 신규 {lr.get('new_count')}건")
    return 0


def cmd_new(cfg: dict[str, Any], args: argparse.Namespace) -> int:
    classifier = KrClassifier(cfg.get("kr_detection", {}))
    supply = SupplyClassifier(cfg.get("supply_detection", {}), root=Path(cfg["_root"]))
    with Store(resolve_path(cfg, "database")) as store:
        items = store.list_new(
            min_score=TIER_SCORE.get(classifier.min_tier, 60),
            min_supply_score=SUPPLY_SCORE.get(supply.min_tier, 50) if supply.enabled else 10_000,
        )
        _print_new(items)
    return 0


def cmd_ack(cfg: dict[str, Any], args: argparse.Namespace) -> int:
    with Store(resolve_path(cfg, "database")) as store:
        n = store.acknowledge(args.uid or None)
        print(f"{n}건을 확인 처리했습니다.")
    return 0


def cmd_export(cfg: dict[str, Any], args: argparse.Namespace) -> int:
    classifier = KrClassifier(cfg.get("kr_detection", {}))
    supply = SupplyClassifier(cfg.get("supply_detection", {}), root=Path(cfg["_root"]))
    with Store(resolve_path(cfg, "database")) as store:
        payload = export(store, resolve_path(cfg, "web_data_dir"),
                         min_score=TIER_SCORE.get(classifier.min_tier, 60),
                         min_supply_score=SUPPLY_SCORE.get(supply.min_tier, 50)
                         if supply.enabled else 10_000)
        print(f"{len(payload['items'])}건을 web/data/ 로 내보냈습니다.")
    return 0


def cmd_doctor(cfg: dict[str, Any], args: argparse.Namespace) -> int:
    from .http_client import ALLOWED_HOSTS

    env = detect_hypervisor()
    tor_cfg = cfg.get("tor", {}) or {}

    print("\n── 실행 환경 ─────────────────────────────────")
    print(f"  OS           : {env['system']}")
    print(f"  제조사/모델   : {env['vendor'] or '-'} / {env['product'] or '-'}")
    print(f"  가상머신      : {'예' if env['is_vm'] else '아니오'}"
          f"{' (VMware)' if env['is_vmware'] else ''}")
    for e in env["evidence"]:
        print(f"    · {e}")

    print("\n── 네트워크 보안 ─────────────────────────────")
    print("  HTTPS 강제           : 예")
    print("  쿠키 저장            : 아니오 (전부 거부)")
    print(f"  허용된 호스트({len(ALLOWED_HOSTS)}개) :")
    for h in sorted(ALLOWED_HOSTS):
        print(f"    · {h}")

    print("\n── Tor 모듈 게이트 ───────────────────────────")
    g1 = bool(tor_cfg.get("enabled"))
    g3_required = bool(tor_cfg.get("require_vmware", True))
    print(f"  게이트1 config.tor.enabled     : {'통과' if g1 else '차단 (권장 상태)'}")
    print("  게이트2 --i-understand-the-risk : 실행 시 확인")
    print(f"  게이트3 VMware 요구            : {'예' if g3_required else '아니오 ⚠'} "
          f"→ 현재 환경 {'통과' if env['is_vmware'] else '차단'}")
    if not g1:
        print("\n  ✅ 현재 설정에서는 .onion 에 접속하지 않습니다. 호스트 PC 는 안전합니다.")
    elif g3_required and not env["is_vmware"]:
        print("\n  ✅ Tor 가 켜져 있으나 VMware 가 아니므로 실행이 차단됩니다.")
    else:
        print("\n  ⚠ 경고: Tor 직접 크롤링이 실행될 수 있는 상태입니다. 격리된 VM 인지 확인하십시오.")

    # ── 공급망 축 상태 ──
    root = Path(cfg["_root"])
    sup_cfg = cfg.get("supply_detection", {}) or {}
    sup = SupplyClassifier(sup_cfg, root=root)
    n_vendors = sum(len(v) for v in sup.vendor_groups.values())
    print("\n── 공급망 감시 ───────────────────────────────")
    print(f"  활성화             : {'예' if sup.enabled else '아니오'}")
    print(f"  글로벌 핵심 벤더    : {n_vendors}개 ({len(sup.vendor_groups)}개 계층)")
    print(f"  우리 직거래 협력사  : {len(sup.vendors)}곳 "
          f"({'vendors.json' if sup.vendors else 'vendors.json 없음 — vendors.example.json 참고'})")
    print(f"  저장 기준           : {sup.min_tier} 이상")
    print(f"  알림 기준           : {cfg.get('notify', {}).get('supply_min_tier', 'critical')} 이상")

    modes = (cfg.get("sources", {}).get("ransomware_live", {}) or {}).get("modes", [])
    if "vendor_search" not in modes:
        print("\n  ⚠ config.json 의 sources.ransomware_live.modes 에 \"vendor_search\" 가 없습니다.")
        print("     벤더 순회 검색이 꺼져 있어, 몇 주 전 발생한 벤더 침해를 놓칠 수 있습니다.")
        print("     config.json 을 지우고 다시 실행하면 최신 기본값으로 재생성됩니다.")
    db = resolve_path(cfg, "database")
    print(f"\n── 저장소 ────────────────────────────────────\n  DB: {db} "
          f"({'존재' if db.exists() else '미생성'})")
    return 0


def cmd_serve(cfg: dict[str, Any], args: argparse.Namespace) -> int:
    import functools
    import webbrowser

    root = Path(cfg["_root"]) / "web"
    if not (root / "index.html").exists():
        log.error("web/index.html 을 찾을 수 없습니다.")
        return 2
    if not (root / "data" / "data.js").exists():
        print("\n[!] 아직 수집 데이터가 없습니다.")
        print("    먼저 실행:  scripts\\run.bat")
        print("    또는 샘플:  python scripts\\make_demo_data.py\n")
        return 2

    handler = functools.partial(_QuietHandler, directory=str(root))

    # ★ 반드시 ThreadingHTTPServer 를 쓸 것.
    #   단일 스레드 TCPServer 는 브라우저가 미리 열어두는 선연결(preconnect) 소켓에
    #   accept 가 물려 그대로 멈춘다 — 페이지가 무한 로딩되는 원인.
    httpd = None
    port = int(args.port)
    for candidate in range(port, port + 10):
        try:
            httpd = http.server.ThreadingHTTPServer(("127.0.0.1", candidate), handler)
            port = candidate
            break
        except OSError as exc:
            if candidate == port + 9:
                print(f"\n[!] 포트 {port}~{candidate} 가 모두 사용 중입니다: {exc}")
                print("    다른 포트로 시도:  python -m collector.main serve --port 9000\n")
                return 3
            continue

    if httpd is None:
        return 3

    httpd.daemon_threads = True
    url = f"http://127.0.0.1:{port}/index.html"
    print(f"\n  대시보드: {url}")
    print("  브라우저가 자동으로 열리지 않으면 위 주소를 직접 붙여넣으세요.")
    print("  종료: 이 창에서 Ctrl+C\n")

    if not getattr(args, "no_browser", False):
        try:
            webbrowser.open(url)
        except Exception:
            pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n종료합니다.")
    finally:
        httpd.shutdown()
        httpd.server_close()
    return 0


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    """로컬 전용 정적 핸들러 — 보안 헤더를 붙이고 접근 로그를 남기지 않는다."""

    # HTTP/1.0 + Connection: close 로 소켓을 오래 붙들지 않는다.
    protocol_version = "HTTP/1.0"
    timeout = 20          # 유휴 소켓을 무한정 기다리지 않는다

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt: str, *a: Any) -> None:
        pass


def cmd_tor(cfg: dict[str, Any], args: argparse.Namespace) -> int:
    from tor.onion_crawler import run_tor_scan  # 지연 임포트: 기본 경로에서 로드조차 안 함

    return run_tor_scan(cfg, acknowledged=args.i_understand_the_risk, dry_run=args.dry_run)


# ─────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="collector",
        description="Kr-Leak-alarm — 랜섬웨어 DLS 한국 기업 피해 모니터링",
    )
    p.add_argument("-c", "--config", help="config.json 경로")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)

    r = sub.add_parser("run", help="수집 실행")
    r.add_argument("--no-notify", action="store_true", help="알림 보내지 않음")
    r.add_argument("--no-vendor-search", action="store_true",
                   help="벤더 순회 검색 건너뛰기 (요청 수 최소화 — 레이트리밋 회복 중일 때 사용)")
    r.add_argument("--baseline", action="store_true",
                   help="이번 수집분을 전부 기준선으로 처리 (알림 없이 NEW 해제) — DB 재구축용")
    r.set_defaults(func=cmd_run)

    sub.add_parser("stats", help="현황 요약").set_defaults(func=cmd_stats)
    sub.add_parser("new", help="미확인 NEW 목록").set_defaults(func=cmd_new)
    sub.add_parser("export", help="웹 데이터 재생성").set_defaults(func=cmd_export)
    sub.add_parser("doctor", help="환경/보안 점검").set_defaults(func=cmd_doctor)

    a = sub.add_parser("ack", help="NEW 상태 해제")
    a.add_argument("--uid", action="append", help="특정 uid 만 (반복 지정 가능)")
    a.set_defaults(func=cmd_ack)

    s = sub.add_parser("serve", help="로컬 대시보드 서버")
    s.add_argument("--port", type=int, default=8787)
    s.add_argument("--no-browser", action="store_true", help="브라우저를 자동으로 열지 않음")
    s.set_defaults(func=cmd_serve)

    t = sub.add_parser("tor-scan", help="[위험] .onion 직접 크롤링 — VMware 전용")
    t.add_argument("--i-understand-the-risk", action="store_true",
                   help="위험을 이해했음을 명시 (필수)")
    t.add_argument("--dry-run", action="store_true", help="게이트 검사만 하고 종료")
    t.set_defaults(func=cmd_tor)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = load_config(args.config)
    load_dotenv()
    setup_logging(resolve_path(cfg, "log_file"), args.verbose)
    try:
        return int(args.func(cfg, args))
    except KeyboardInterrupt:
        print("\n중단되었습니다.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
