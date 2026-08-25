"""
sources/ransomfeed.py — ransomfeed.it RSS 어댑터 (3차 소스, 기본 비활성).

RSS/XML 파싱은 XXE·엔티티 폭탄 위험이 있으므로:
  1) defusedxml 이 있으면 그것을 사용
  2) 없으면 표준 ElementTree + 응답 크기 상한 + 엔티티 사전 검사로 폴백
"""

from __future__ import annotations

import logging
import re
from typing import Any, Iterable

from .base import LeakRecord, Source, parse_timestamp

log = logging.getLogger(__name__)

FEED_URL = "https://ransomfeed.it/rss-complete.php"

_ENTITY_DECL_RE = re.compile(rb"<!(DOCTYPE|ENTITY)\b", re.IGNORECASE)


def _parse_xml(raw: bytes):
    """가능하면 defusedxml, 아니면 안전 검사 후 ElementTree."""
    try:
        from defusedxml.ElementTree import fromstring as safe_fromstring  # type: ignore

        return safe_fromstring(raw)
    except ImportError:
        pass

    # 폴백: DOCTYPE/ENTITY 선언이 있으면 파싱 자체를 거부 (XXE·billion laughs 차단)
    if _ENTITY_DECL_RE.search(raw[:8192]):
        raise ValueError(
            "XML 에 DOCTYPE/ENTITY 선언이 있어 파싱을 거부했습니다. "
            "`pip install defusedxml` 후 다시 시도하십시오."
        )
    import xml.etree.ElementTree as ET

    return ET.fromstring(raw)


class RansomFeedSource(Source):
    name = "ransomfeed.it"

    def fetch(self) -> Iterable[LeakRecord]:
        try:
            raw = self.client.get_bytes(FEED_URL)
            root = _parse_xml(raw)
        except Exception as exc:
            self.note_error(str(exc))
            log.error("[%s] 조회/파싱 실패: %s", self.name, exc)
            return []

        items = root.findall(".//item")
        log.info("[%s] rss → %d건", self.name, len(items))

        out: list[LeakRecord] = []
        for node in items:
            title = _text(node, "title")
            group = _text(node, "category")
            desc = _text(node, "description")
            pub = _text(node, "pubDate")
            link = _text(node, "link")
            if not title:
                continue
            out.append(
                LeakRecord(
                    victim=title,
                    group=group,
                    country="",
                    sector="",
                    website=title,
                    description=desc,
                    published=parse_timestamp(pub),
                    discovered=parse_timestamp(pub),
                    post_url=link,
                    source=self.name,
                ).finalize()
            )
        return out


def _text(node: Any, tag: str) -> str:
    child = node.find(tag)
    if child is None:
        return ""
    return (child.text or "").strip()
