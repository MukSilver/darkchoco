"""
export.py — 웹 대시보드가 읽을 데이터 파일 생성.

두 가지를 만든다:
  web/data/data.js    — `window.KRLEAK = {...}` 형태. file:// 로 index.html 을
                        더블클릭만 해도 동작한다(fetch CORS 제약 회피).
  web/data/latest.json — 다른 도구에서 쓰기 좋은 표준 JSON.

★ 여기서 모든 공격자 URL 은 defang 처리된다. 대시보드에는 클릭 가능한
  .onion 링크가 절대 들어가지 않는다.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .safety import defang_url, is_onion, sanitize_text

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1


def _shape(row: dict[str, Any]) -> dict[str, Any]:
    post_url = row.get("post_url") or ""
    return {
        "uid": row.get("uid", ""),
        "victim": sanitize_text(row.get("victim"), 300),
        "group": sanitize_text(row.get("group_name") or row.get("group"), 100),
        "country": sanitize_text(row.get("country"), 8),
        "sector": sanitize_text(row.get("sector"), 120),
        "website": sanitize_text(row.get("website"), 253),
        "description": sanitize_text(row.get("description"), 1200),
        "published": row.get("published") or "",
        "discovered": row.get("discovered") or "",
        # 원문 URL 은 defang 된 문자열로만 노출한다 (클릭 불가)
        "post_url_defanged": defang_url(post_url),
        "post_is_onion": is_onion(post_url),
        "sources": row.get("sources") or [],
        # 축 1: 한국 관련성
        "tier": row.get("kr_tier", "none"),
        "score": int(row.get("kr_score") or 0),
        "reasons": row.get("kr_reasons") or [],
        # 축 2: 공급망 위험
        "supply_tier": row.get("supply_tier") or "none",
        "supply_score": int(row.get("supply_score") or 0),
        "supply_reasons": row.get("supply_reasons") or [],
        "first_seen": row.get("first_seen") or "",
        "is_new": bool(row.get("is_new")),
    }


def export(
    store: Any, web_data_dir: Path, *, min_score: int = 0, min_supply_score: int = 999
) -> dict[str, Any]:
    web_data_dir = Path(web_data_dir)
    web_data_dir.mkdir(parents=True, exist_ok=True)

    rows = store.list_victims(min_score=min_score, min_supply_score=min_supply_score)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stats": store.stats(),
        "items": [_shape(r) for r in rows],
    }

    json_text = json.dumps(payload, ensure_ascii=False, indent=1)

    (web_data_dir / "latest.json").write_text(json_text, encoding="utf-8")

    # </script> 조각이 문자열 안에 들어가 스크립트를 조기 종료시키는 것을 방지
    js_safe = json_text.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    (web_data_dir / "data.js").write_text(
        "/* 자동 생성 파일 — 직접 수정하지 마세요. `python -m collector.main run` 으로 갱신됩니다. */\n"
        f"window.KRLEAK = {js_safe};\n",
        encoding="utf-8",
    )

    log.info("웹 데이터 내보내기 완료: %d건 → %s", len(payload["items"]), web_data_dir)
    return payload
