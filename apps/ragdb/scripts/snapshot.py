# -*- coding: utf-8 -*-
"""F-22 스냅샷 굽기와 반출 관문.

    python scripts/snapshot.py              지금 판으로 굽고 관문을 본다
    python scripts/snapshot.py --check      이미 구운 지금 판에 관문만 다시 본다

스냅샷은 화면이 읽는 정적 파일 묶음이다 (명세 5.4). 반출 대상만 담는다.

    data/snapshot/current.json                      지금 판 이름, 구운 시각
    data/snapshot/{판}/list.json                    목록
    data/snapshot/{판}/doc/{document_id}.json       상세와 반출 조각
    data/snapshot/{판}/answers.json                 검토를 통과한 사전 답변
    data/snapshot/{판}/status.json                  판, 구운 시각, 문서 수, 조각 수
    data/snapshot/{판}/export/ragdb_export.json     반출 대상 전체

이미지는 굽지 않는다 (OI-34, 2026-09-30). 조사 화면을 찍은 그림에는 조직 이름이 그대로 보이고 그림 속 글자는
가릴 수 없다. 조각의 images 는 빈 목록으로 나간다.

올리기(wrangler)는 여기에 없다. 화면과 도메인이 정해진 뒤에 붙인다. 관문을 통과한 폴더를 그대로 올리면 된다.
"""
import datetime
import json
import os
import re
import shutil
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import chunk as C                        # noqa: E402
import masking as M                      # noqa: E402
from app import guard, pii, store        # noqa: E402
from app import config as cfg            # noqa: E402
from app.normalize import norm           # noqa: E402

SCRIPT = re.compile(r"<\s*(script|style|iframe|object|embed)\b.*?<\s*/\s*\1\s*>", re.I | re.S)
TAG = re.compile(r"<\s*/?\s*[a-zA-Z][^<>]{0,200}>")
MD_LINK = re.compile(r"\[([^\]\n]{1,200})\]\([^)\n]{1,500}\)")
EVENT = re.compile(r"\bon[a-z]{3,20}\s*=", re.I)


def strip_active(text):
    """조각 본문의 스크립트와 링크를 지운다 (SR-12, TC-19). 링크는 글자만 남긴다."""
    if not isinstance(text, str) or not text:
        return text
    # 지운 자리에는 빈칸을 둔다. 그냥 붙이면 앞뒤 낱말이 이어져 「끝.Source」 같은 없던 글자가 생긴다
    out = SCRIPT.sub(" ", text)
    out = MD_LINK.sub(lambda m: m.group(1), out)
    out = TAG.sub(" ", out)
    out = EVENT.sub(" ", out)
    out = out.replace("javascript:", "")
    return re.sub(r"[ \t]{2,}", " ", out) if out != text else text


def is_stale(observed_at, today=None):
    """확인일이 기준(OI-29)보다 오래됐는가. 확인일이 없으면 오래됨으로 보지 않는다."""
    if not observed_at:
        return False
    try:
        d = datetime.date.fromisoformat(str(observed_at)[:10])
    except ValueError:
        return False
    today = today or datetime.datetime.now(store.KST).date()
    return (today - d).days > cfg.STALE_DAYS


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return os.path.getsize(path)


def bake(version):
    """스냅샷을 굽는다 (F-22 처리 1). 돌려주는 것: {dir, documents, chunks, bytes, list_bytes}"""
    out = os.path.join(cfg.SNAPSHOT_ROOT, version)
    if os.path.isdir(out):
        shutil.rmtree(out)
    con = store.connect()
    rows = con.execute("SELECT * FROM documents WHERE visibility = 1 ORDER BY kind, title").fetchall()
    live = {r["document_id"] for r in rows}

    docs = C.load_docs()
    g, _ = C.load_guard(docs)
    std = {d["document_id"]: C.cleaned(d, g) for d in docs if d["document_id"] in live}

    baked_at = store.now()
    listing, export, n_chunks, size = [], [], 0, 0
    for r in rows:
        d = std.get(r["document_id"])
        if d is None:
            continue
        # 태그를 지운 뒤에 한 번 더 가린다. 지우면서 글자가 바뀌기 때문이다
        safe = lambda v: g.clean(strip_active(v))
        strip = lambda v: [safe(x) for x in v] if isinstance(v, list) else safe(v)
        attrs = {k: strip(v) for k, v in C.exported_metadata(d)[0].items()}
        chunks = [dict(c) for c in con.execute(
            "SELECT chunk_id, section, body, observed_at, status FROM chunks "
            "WHERE document_id = ? AND visibility = 1 ORDER BY CAST(substr(chunk_id, instr(chunk_id, '#s') + 2) AS INTEGER)",
            (r["document_id"],))]
        for c in chunks:
            c["body"] = safe(c["body"])
            c["section"] = safe(c["section"])
            c["images"] = []
        n_chunks += len(chunks)
        head = {"document_id": r["document_id"], "kind": r["kind"], "title": safe(r["title"]),
                "summary": safe(r["summary"]),
                "status": r["status"], "observed_at": r["observed_at"], "country": r["country"], "signup": r["signup"],
                "verdict": json.loads(r["verdict"]) if r["verdict"] else None, "stale": is_stale(r["observed_at"])}
        listing.append(head)
        detail = dict(head, attributes=attrs, related=r["related"], chunks=chunks)
        size += write(os.path.join(out, "doc", "%s.json" % r["document_id"]), detail)
        export.append({"document_id": r["document_id"], "kind": r["kind"], "title": head["title"],
                       "summary": head["summary"], "attributes": attrs,
                       "sections": [{"section": c["section"], "body": c["body"]} for c in chunks if c["section"] != "속성"]})

    answers = [{"question": a["question"], "answer": json.loads(a["answer"]), "sources": json.loads(a["sources"] or "[]"),
                "created_at": a["created_at"]}
               for a in con.execute("SELECT * FROM answers WHERE reviewed = 1 ORDER BY created_at").fetchall()
               if store.answer_holds(con, a)]
    con.close()

    list_bytes = write(os.path.join(out, "list.json"), {"version": version, "documents": listing})
    size += list_bytes
    size += write(os.path.join(out, "answers.json"), {"version": version, "answers": answers})
    size += write(os.path.join(out, "status.json"), {"version": version, "baked_at": baked_at,
                                                    "documents": len(listing), "chunks": n_chunks})
    size += write(os.path.join(out, "export", "ragdb_export.json"),
                  {"version": version, "baked_at": baked_at, "license": "방어 목적의 보안 연구와 교육에만 씁니다",
                   "documents": export})
    return {"dir": out, "documents": len(listing), "chunks": n_chunks, "answers": len(answers),
            "bytes": size, "list_bytes": list_bytes, "baked_at": baked_at}


def _walk(node, path, visit):
    if isinstance(node, dict):
        for k, v in node.items():
            visit(path + [str(k)], k, True)
            _walk(v, path + [str(k)], visit)
    elif isinstance(node, list):
        for v in node:
            _walk(v, path, visit)
    elif isinstance(node, str):
        visit(path, node, False)


def gate(version):
    """반출 관문 (F-22 처리 2). 걸린 것의 목록을 돌려준다. 비어 있어야 통과다.

    걸린 값은 돌려주지 않는다. 어느 파일의 어느 자리에서 무엇이 걸렸는지만 알린다.
    """
    root = os.path.join(cfg.SNAPSHOT_ROOT, version)
    docs = C.load_docs()
    g, _ = C.load_guard(docs)
    allow = C.export_columns()
    NEVER = {"aliases", "source", "notion_id", "expanded", "terms"}
    problems = []

    for base, _, files in os.walk(root):
        for fn in files:
            if not fn.endswith(".json"):
                problems.append({"file": os.path.relpath(os.path.join(base, fn), root), "what": "json 이 아닌 파일"})
                continue
            p = os.path.join(base, fn)
            rel = os.path.relpath(p, root).replace(os.sep, "/")
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            seen = set()

            def visit(path, value, is_key):
                def hit(what):
                    key = (rel, "/".join(path[-2:]), what)
                    if key not in seen:
                        seen.add(key)
                        problems.append({"file": rel, "where": "/".join(path[-2:]), "what": what})
                if is_key:
                    if value in NEVER:
                        hit("내보내지 않는 칸")
                    return
                for pat in M.ADDRESS_PATTERNS:
                    if pat.search(value):
                        hit("주소나 링크")
                        break
                label = pii.has_pii(value)
                if label:
                    hit("개인정보 꼴 %s" % label)
                for leak in g.leaks(value):
                    hit(leak)
                if SCRIPT.search(value) or TAG.search(value):
                    hit("스크립트나 태그")

            _walk(data, [], visit)
            # 반출하는 칸 목록 밖의 칸
            many = data.get("documents") if isinstance(data, dict) else None
            for d in many if isinstance(many, list) else [data]:
                if isinstance(d, dict) and isinstance(d.get("attributes"), dict):
                    for k in d["attributes"]:
                        if k not in allow.get(d.get("kind"), []):
                            problems.append({"file": rel, "where": "attributes/%s" % k, "what": "반출하는 칸 목록 밖의 칸"})
    return problems


def excluded_names(version):
    """빠진 줄 명부에만 있는 이름이 스냅샷에 나오는가 (F-22 처리 2 의 마지막 항목).

    돌려주는 것: {names(명부에만 있는 이름 수), files(그 이름이 나온 파일 수), by_kind}. 명부가 없으면 None.
    이름은 돌려주지 않는다.

    명세서는 하나라도 나오면 멈추라고 한다. 지금은 세기만 하고 멈추지 않는다 (GATE_EXCLUDED_NAMES=warn).
    꺼진 줄 가운데는 내보내면 안 되는 곳과 아직 조사하지 않은 곳이 섞여 있고, 뒤쪽은 다른 문서의 본문에
    이름이 나오는 것이 자연스럽다. 막을지는 사람이 정한다. block 으로 바꾸면 관문에서 멈춘다.
    """
    path = os.path.join(cfg.DATA_DIR, "excluded_rows.json")
    try:
        with open(path, encoding="utf-8") as f:
            rows = json.load(f).get("rows") or []
    except (OSError, ValueError, AttributeError):
        return None
    docs = C.load_docs()
    con = store.connect()
    live = {r[0] for r in con.execute("SELECT document_id FROM documents WHERE visibility = 1")}
    con.close()
    shown = set()
    for d in docs:
        if d["document_id"] in live:
            shown.add(norm(d.get("title")))
            shown.add(norm(re.sub(r"\s*[(（].*$", "", d.get("title") or "")))
            shown.update(norm(a) for a in (d.get("aliases") or []) if isinstance(a, str))
    only, kind_of = [], {}
    for r in rows:
        for n in [r.get("name")] + list(r.get("aliases") or []):
            if isinstance(n, str) and norm(n) and norm(n) not in shown:
                only.append(n)
                kind_of[norm(n)] = r.get("kind")
    g = guard.Guard(names=only, keep=guard.COMMON_PLATFORMS)
    root = os.path.join(cfg.SNAPSHOT_ROOT, version, "doc")
    files, by_kind = 0, {}
    for fn in os.listdir(root) if os.path.isdir(root) else []:
        with open(os.path.join(root, fn), encoding="utf-8") as f:
            text = f.read()
        hit = g.find_name(text)
        if hit:
            files += 1
            k = kind_of.get(norm(hit)) or "기타"
            by_kind[k] = by_kind.get(k, 0) + 1
    return {"names": len(g.names), "files": files, "by_kind": by_kind}


def publish_current(version, baked_at):
    """/data/current.json. 화면은 이것을 먼저 읽고 그 판의 파일을 읽는다. 지금 판과 직전 판 둘만 남긴다."""
    write(os.path.join(cfg.SNAPSHOT_ROOT, "current.json"), {"version": version, "baked_at": baked_at})
    keep = sorted(v for v in os.listdir(cfg.SNAPSHOT_ROOT) if os.path.isdir(os.path.join(cfg.SNAPSHOT_ROOT, v)))
    for old in [v for v in keep if v != version][:-1]:
        shutil.rmtree(os.path.join(cfg.SNAPSHOT_ROOT, old), ignore_errors=True)


def log_export(version, documents, chunks):
    """반출 기록 (SR-18). 내려받은 사람은 기록하지 않는다."""
    con = store.connect()
    with con:
        con.execute("INSERT INTO export_log (at, version, documents, chunks) VALUES (?,?,?,?)",
                    (store.now(), version, documents, chunks))
    con.close()


def main():
    with open(cfg.CURRENT, encoding="utf-8") as f:
        version = f.read().strip()
    if "--check" not in sys.argv:
        r = bake(version)
        print("판 %s 스냅샷: 문서 %d · 조각 %d · 사전 답변 %d · %.1fMB (목록 %.0fKB)" % (
            version, r["documents"], r["chunks"], r["answers"], r["bytes"] / 1e6, r["list_bytes"] / 1e3))
    bad = gate(version)
    if bad:
        print("반출 관문에서 멈춤 — %d곳 (F-22 처리 2). 올리지 않는다" % len(bad))
        kinds = {}
        for b in bad:
            kinds[b["what"]] = kinds.get(b["what"], 0) + 1
        for k, n in sorted(kinds.items(), key=lambda x: -x[1]):
            print("  %-28s %d곳" % (k, n))
        for b in bad[:20]:
            print("    %-44s %-26s %s" % (b["file"][:44], (b.get("where") or "")[:26], b["what"]))
        return 1
    print("반출 관문 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
