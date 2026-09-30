# -*- coding: utf-8 -*-
"""주간 배치. 받기부터 판 교체까지 한 번에 (설계서 4.1). 새 판이 없으면 아무것도 하지 않는다.

    .venv\\Scripts\\python scripts\\refresh.py            새 판이 있을 때만
    .venv\\Scripts\\python scripts\\refresh.py --force    판이 같아도 다시
    .venv\\Scripts\\python scripts\\refresh.py --local    받지 않고, 받아 둔 표준 문서로 다시 만든다

순서 (하나라도 실패하면 거기서 멈추고 지금 판을 그대로 쓴다)

    1 받기            fetch_docs.py     Supabase rag → data/standard/
    2 이름 찾기        find_names.py     바뀐 문서에서 피해 조직 표기를 찾는다 (모델 호출, 바뀐 문서만)
    3 조각            chunk.py          가리기, 가리기 검사(F-03), 조각과 목록
    4 색인            build_index.py    금지어 검사, 색인, 넓히기 사전, 지킴이 목록. 갈아 끼우지는 않는다
    5 스냅샷과 관문     snapshot.py       굽기, 반출 관문 (F-22)
    6 갈아 끼우기                        current.txt 한 줄, 옛 판의 재사용 답변 지움, 반출 기록
    7 재조사 추출      recheck.py        (F-20)
    8 배치 기록                          data/batch_log.jsonl 에 한 줄

색인(bm25s, kiwipiepy)이 .venv 에만 있으므로 .venv 의 python 으로 돌린다.
실패하면 디스코드로 알린다. 알림에는 자료 내용을 싣지 않고 어느 단계인지만 보낸다 (F-23 처리 5, 6).
"""
import argparse
import json
import os
import subprocess
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)


def run(name, *args):
    return subprocess.run([sys.executable, os.path.join(HERE, name), *args]).returncode


def notify(step):
    """실패 알림. 무엇이 어느 단계에서 실패했는지만 보낸다."""
    from app import config as cfg
    if not cfg.DISCORD_WEBHOOK:
        return
    try:
        import httpx
        httpx.post(cfg.DISCORD_WEBHOOK, json={"content": "RAG DB 배치가 「%s」 단계에서 멈췄습니다. 지금 판은 그대로입니다." % step},
                   timeout=10)
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--local", action="store_true")
    ap.add_argument("--quiet-fail", action="store_true", help="실패해도 디스코드로 알리지 않는다")
    a = ap.parse_args()

    from app import config as cfg
    from app import store
    import build_index
    import chunk as C
    import recheck
    import snapshot

    started, t0 = store.now(), time.monotonic()
    line = {"started_at": started, "kind": "색인", "observed": {}, "excluded": [], "failed": []}

    def finish(step=None):
        line["finished_at"] = store.now()
        line["seconds"] = round(time.monotonic() - t0, 1)
        if step:
            line["stopped_at"] = step
        os.makedirs(os.path.dirname(cfg.BATCH_LOG), exist_ok=True)
        with open(cfg.BATCH_LOG, "a", encoding="utf-8") as f:      # 덧붙이기만 한다. 지우거나 다시 만들지 않는다
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
        if step and not a.quiet_fail:
            notify(step)
        return 1 if step else 0

    # 1. 받기
    # 받기는 받은 판 이름을 곧바로 적어 둔다. 그래서 뒤 단계에서 멈추면 다음 회차에 「받을 새 판이 없다」 가 되어
    # 다시 만들지 않는다 (2026-09-30 검토에서 찾음). 받았는데 끝까지 못 간 것을 표시해 두고, 다음 회차에 이어서 만든다
    pending = os.path.join(cfg.DATA_DIR, "pending_build.txt")
    if not a.local:
        got = run("fetch_docs.py", *(["--force"] if a.force else []))
        if got == 0:
            with open(pending, "w", encoding="utf-8") as f:
                f.write(started + "\n")
        elif got == 10:
            if not os.path.exists(pending):
                return 0          # 받을 새 판이 없다. 기록도 남기지 않는다
            print("받을 새 판은 없지만 지난 배치가 끝까지 가지 못했다. 받아 둔 자료로 다시 만든다")
        else:
            return finish("받기")

    # 2. 이름 찾기. 못 본 문서가 있어도(끝 값 2) 계속한다. 그 문서는 조각으로 만들지 않을 뿐이다
    rc = run("find_names.py")
    if rc not in (0, 2):
        return finish("이름 찾기")
    line["observed"]["names_incomplete"] = rc == 2

    # 3. 조각
    t = time.monotonic()
    st = C.run()
    if st is None:
        return finish("조각")
    line["observed"].update(documents=st["documents"], chunks=st["chunks"], not_indexed=st["not_indexed"],
                            write_lock_seconds=round(time.monotonic() - t, 2), dropped_columns=st["dropped_columns"])
    line["excluded"] = [{"document_id": e["document_id"], "why": ", ".join("%s %s" % (h["where"], h["what"]) for h in e["hits"][:4])}
                        for e in st["excluded"]]
    line["pii_masked"] = [{"document_id": e["document_id"], "why": ", ".join("%s %s" % (h["where"], h["what"]) for h in e["hits"][:4])}
                          for e in st["pii_masked"]]

    # 4. 색인. 갈아 끼우지 않고 만들기만 한다
    ix = build_index.build(hold=True)
    if ix is None:
        return finish("색인")
    version = ix["version"]
    line["version"] = version
    line["observed"].update(indexed=ix["chunks"], terms=ix["terms"], terms_seconds=ix["terms_seconds"],
                            guard_names=ix["guard_names"])
    if ix["terms"] is None:
        line["failed"].append({"what": "넓히기 사전 굽기", "note": "직전 사전을 씀"})

    # 5. 스냅샷과 반출 관문
    snap = snapshot.bake(version)
    bad = snapshot.gate(version)
    ex = snapshot.excluded_names(version)
    line["observed"]["excluded_names_in_snapshot"] = ex
    if ex and ex["files"] and (os.getenv("GATE_EXCLUDED_NAMES") or "warn").strip() == "block":
        bad = bad + [{"file": "doc/", "where": "%d개 파일" % ex["files"], "what": "빠진 줄 명부에만 있는 이름"}]
    line["observed"].update(snapshot_bytes=snap["bytes"],
                            snapshot_documents=snap["documents"], snapshot_chunks=snap["chunks"])
    if bad:
        kinds = {}
        for b in bad:
            kinds[b["what"]] = kinds.get(b["what"], 0) + 1
        line["failed"].append({"what": "반출 관문", "counts": kinds,
                               "files": sorted({b["file"] for b in bad})[:50]})
        print("반출 관문에서 멈춤 — %d곳. current.txt 는 그대로 (TC-40)" % len(bad))
        for k, n in sorted(kinds.items(), key=lambda x: -x[1]):
            print("  %-28s %d곳" % (k, n))
        return finish("반출 관문")

    # 6. 갈아 끼우기. 여기까지 와야 새 판이 쓰인다
    build_index.activate(version)
    snapshot.publish_current(version, snap["baked_at"])
    snapshot.log_export(version, snap["documents"], snap["chunks"])
    con = store.connect()
    line["observed"]["dropped_cache"] = store.drop_old_cache(con, version)
    con.close()
    if os.path.exists(pending):
        os.remove(pending)          # 새 판까지 왔다. 다음 회차는 새 판이 있을 때만 돈다

    # 7. 재조사 추출
    rs = recheck.run(quiet=True)
    if rs is not None:
        line["observed"]["recheck"] = rs

    # 8. 배치 기록
    line["observed"]["sqlite_bytes"] = os.path.getsize(cfg.SQLITE_PATH) if os.path.exists(cfg.SQLITE_PATH) else None
    for k in ("append_wait_max_seconds", "append_failed", "resident_memory_bytes", "excluded_rows_seconds"):
        line["observed"][k] = None          # 질의 서버가 돌 때 재는 값. 아직 잴 자리가 없어 빈 값으로 둔다
    print("판 %s: 문서 %d · 조각 %d (색인 %d) · 사전 %s항목 · 스냅샷 %.1fMB · 뺀 문서 %d" % (
        version, st["documents"], st["chunks"], ix["chunks"], ix["terms"], snap["bytes"] / 1e6, len(st["excluded"])))
    return finish()


if __name__ == "__main__":
    sys.exit(main())
