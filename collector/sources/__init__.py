"""수집 소스 레지스트리."""

from __future__ import annotations

from typing import Any

from .base import LeakRecord, Source  # noqa: F401
from .ransomfeed import RansomFeedSource
from .ransomlook import RansomLookSource
from .ransomware_live import RansomwareLiveSource

REGISTRY: dict[str, type[Source]] = {
    "ransomware_live": RansomwareLiveSource,
    "ransomlook": RansomLookSource,
    "ransomfeed": RansomFeedSource,
}


def build_sources(client: Any, sources_cfg: dict[str, Any]) -> list[Source]:
    """config 의 sources 블록에서 활성화된 소스만 인스턴스화한다."""
    built: list[Source] = []
    for key, cfg in (sources_cfg or {}).items():
        if key.startswith("_") or not isinstance(cfg, dict):
            continue
        if not cfg.get("enabled"):
            continue
        cls = REGISTRY.get(key)
        if cls is None:
            continue
        built.append(cls(client, cfg))
    return built
