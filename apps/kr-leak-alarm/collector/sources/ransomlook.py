"""
sources/ransomlook.py — ransomlook.io 공개 API 어댑터 (2차 소스).

country 필드가 없어 도메인/키워드 기반 판별에 의존한다.
ransomware.live 가 놓친 건을 보완하는 용도.

응답 필드: post_title, discovered, description, link, magnet, screen,
           misp_uuid, group_name
"""

from __future__ import annotations

import logging
from typing import Any, Iterable

from ..http_client import NotFoundError
from .base import LeakRecord, Source, parse_timestamp

log = logging.getLogger(__name__)

from dc_ransomfeed import RANSOMLOOK as BASE        # packages/dc_ransomfeed


class RansomLookSource(Source):
    name = "ransomlook.io"

    def fetch(self) -> Iterable[LeakRecord]:
        try:
            payload = self.client.get_json(f"{BASE}/recent")
        except NotFoundError:
            log.info("[%s] 결과 없음(404)", self.name)
            return []
        except Exception as exc:
            self.note_error(str(exc))
            log.error("[%s] 조회 실패: %s", self.name, exc)
            return []

        items = payload if isinstance(payload, list) else []
        log.info("[%s] recent → %d건", self.name, len(items))

        out: list[LeakRecord] = []
        for it in items:
            if not isinstance(it, dict):
                continue
            # link 는 상대경로(/blog?uuid=...)인 경우가 많아 그대로 두고 defang 처리한다.
            out.append(
                LeakRecord(
                    victim=it.get("post_title") or "",
                    group=it.get("group_name") or "",
                    country="",  # 제공 안 함
                    sector="",
                    website=it.get("post_title") or "",  # 제목이 도메인인 경우가 많음
                    description=it.get("description") or "",
                    published=parse_timestamp(it.get("discovered")),
                    discovered=parse_timestamp(it.get("discovered")),
                    post_url=it.get("link") or "",
                    source=self.name,
                ).finalize()
            )
        return out
