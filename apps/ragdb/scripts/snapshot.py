# -*- coding: utf-8 -*-
"""F-22 스냅샷 굽기와 반출 관문.

    python scripts/snapshot.py              지금 판으로 굽고 관문을 본다
    python scripts/snapshot.py --check      이미 구운 지금 판에 관문만 다시 본다

스냅샷은 화면이 읽는 정적 파일 묶음이다 (설계서 「API와 스냅샷 파일」). 반출 대상만 담는다.

    data/snapshot/current.json                      지금 판 이름, 구운 시각
    data/snapshot/{판}/doc/{document_id}.json       출처 원문 (답의 출처를 눌렀을 때 보이는 반출 조각)
    data/snapshot/{판}/answers.json                 검토를 통과한 사전 답변 (예시 질문)
    data/snapshot/{판}/status.json                  판, 구운 시각, 문서 수, 조각 수

목록(list.json)과 전체 내려받기(export/ragdb_export.json)는 굽지 않는다 (2026-09-30 김무근, 설계서 판 1.5).
RAG DB 는 묻고 답하는 곳이고, 훑어보기는 생태계 지도가 맡는다. 조사 자료를 통째로 내주는 파일도 두지 않는다.

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


# 「오래됨」 을 따지는 종류. 팀이 다시 가서 확인하는 대상만이다.
# 사고와 판정의 날짜는 공표 시점, 수집일, 검증일이라 시간이 지나도 오래된 것이 아니다.
# 전에는 종류를 안 봐서 옛 사고 134건이 전부 「오래됨」 이 되었다 (2026-09-30 검토에서 찾음)
STALE_KINDS = ("포럼", "텔레그램", "랜섬웨어", "행위자")


def is_stale(observed_at, today=None, kind=None):
    """확인일이 기준(OI-29)보다 오래됐는가. 확인일이 없으면 오래됨으로 보지 않는다. 종류를 주면 STALE_KINDS 만 따진다."""
    if kind is not None and kind not in STALE_KINDS:
        return False
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


def version_files(version):
    """판 폴더의 문서 목록과 조각 (build_index.py 가 구운 것). ({document_id: 문서}, {chunk_id: 조각})"""
    d = os.path.join(cfg.INDEX_ROOT, version)
    with open(os.path.join(d, "documents.json"), encoding="utf-8") as f:
        docs = json.load(f)
    with open(os.path.join(d, "chunks.json"), encoding="utf-8") as f:
        chunks = json.load(f)
    return docs, chunks


def _order(chunk_id):
    try:
        return int(chunk_id.rsplit("#s", 1)[1])
    except (IndexError, ValueError):
        return 0


def bake(version, st=None):
    """스냅샷을 굽는다 (F-22 처리 1). 돌려주는 것: {dir, documents, chunks, answers, bytes, baked_at}"""
    out = os.path.join(cfg.SNAPSHOT_ROOT, version)
    if os.path.isdir(out):
        shutil.rmtree(out)
    doc_rows, all_chunks = version_files(version)
    rows = sorted(((did, r) for did, r in doc_rows.items() if r.get("visibility")),
                  key=lambda x: (x[1].get("kind") or "", x[1].get("title") or ""))
    live = {did for did, _ in rows}
    by_doc = {}
    for cid, c in all_chunks.items():
        if c.get("visibility"):
            by_doc.setdefault(c["document_id"], []).append(cid)

    docs = C.load_docs()
    g, _ = C.load_guard(docs)
    std = {d["document_id"]: C.cleaned(d, g) for d in docs if d["document_id"] in live}
    if C.PII_POLICY == "mask":
        std = {k: C.pii_masked(v) for k, v in std.items()}          # 조각을 만들 때와 같은 가리기 (F-03)

    baked_at = store.now()
    n_docs, n_chunks, size = 0, 0, 0
    # 태그를 지운 뒤에 한 번 더 가린다. 지우면서 글자가 바뀌기 때문이다
    safe = lambda v: g.clean(strip_active(v))
    strip = lambda v: [safe(x) for x in v] if isinstance(v, list) else safe(v)
    for did, r in rows:
        d = std.get(did)
        if d is None:
            continue
        attrs = {k: strip(v) for k, v in C.exported_metadata(d)[0].items()}
        chunks = []
        for cid in sorted(by_doc.get(did, []), key=_order):
            c = all_chunks[cid]
            chunks.append({"chunk_id": cid, "section": safe(c.get("section")), "body": safe(c.get("body")),
                           "observed_at": c.get("observed_at"), "status": c.get("status"), "images": []})
        n_chunks += len(chunks)
        head = {"document_id": did, "kind": r["kind"], "title": safe(r.get("title")),
                "summary": safe(r.get("summary")),
                "status": r.get("status"), "observed_at": r.get("observed_at"), "country": r.get("country"),
                "signup": r.get("signup"), "verdict": r.get("verdict") or None,
                "stale": is_stale(r.get("observed_at"), kind=r["kind"])}
        n_docs += 1
        detail = dict(head, attributes=attrs, related=r.get("related"), chunks=chunks)
        size += write(os.path.join(out, "doc", "%s.json" % did), detail)

    # 사전 답변도 지금 목록으로 한 번 더 가린다. 답을 만든 뒤에 새로 찾은 조직 표기가 있을 수 있다
    st = st or store.connect()
    answers = []
    for a in st.answers_all():
        if not a["reviewed"] or not store.holds(doc_rows, a):
            continue
        sents = [dict(s, text=safe(s.get("text"))) for s in a["answer"]]
        sources = [dict(s, title=safe(s.get("title")), section=safe(s.get("section"))) for s in a["sources"] or []]
        answers.append({"question": safe(a["question"]), "answer": sents, "sources": sources, "created_at": a["created_at"]})

    size += write(os.path.join(out, "answers.json"), {"version": version, "answers": answers})
    size += write(os.path.join(out, "status.json"), {"version": version, "baked_at": baked_at,
                                                    "documents": n_docs, "chunks": n_chunks})
    return {"dir": out, "documents": n_docs, "chunks": n_chunks, "answers": len(answers),
            "bytes": size, "baked_at": baked_at}


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

    지금은 세기만 하고 멈추지 않는다 (GATE_EXCLUDED_NAMES=warn). 멈출지는 설계서 「보류 및 확정 필요」 에 있다.
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
    live = {did for did, r in version_files(version)[0].items() if r.get("visibility")}
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
    """반출 기록 (SR-18). 판을 쓴 시각과 수만 남긴다."""
    store.connect().log_export(version, documents, chunks)


def main():
    with open(cfg.CURRENT, encoding="utf-8") as f:
        version = f.read().strip()
    if "--check" not in sys.argv:
        r = bake(version)
        print("판 %s 스냅샷: 문서 %d · 조각 %d · 사전 답변 %d · %.1fMB" % (
            version, r["documents"], r["chunks"], r["answers"], r["bytes"] / 1e6))
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
