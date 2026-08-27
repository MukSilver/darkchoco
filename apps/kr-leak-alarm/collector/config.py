"""config.py — config.json / .env 로더."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent

DEFAULTS: dict[str, Any] = {
    "sources": {
        "ransomware_live": {
            "enabled": True,
            "modes": ["country", "recent", "vendor_search"],
            "country_codes": ["KR"],
            "recent_lookback_days": 30,
            "vendor_search_per_run": 5,
            "vendor_search_delay_seconds": 3.0,
        },
        "ransomlook": {"enabled": True},
        "ransomfeed": {"enabled": False},
    },
    "kr_detection": {
        "min_tier_to_report": "likely",
        "exclude_north_korea": True,
        "extra_keywords": [],
        "exclude_keywords": [],
    },
    "supply_detection": {
        "enabled": True,
        "min_tier_to_store": "sector",
        "extra_critical_vendors": [],
        "exclude_keywords": [],
    },
    "notify": {
        "desktop_toast": True,
        "kr_min_score": 60,
        "supply_min_tier": "critical",
        "webhook": {"enabled": False, "type": "slack"},
        "email": {"enabled": False, "to": []},
        "max_items_per_notification": 10,
        "resync_threshold": 30,
    },
    "network": {
        "timeout_seconds": 30,
        "max_response_bytes": 33554432,
        "retries": 2,
        "user_agent": "Kr-Leak-alarm/1.0 (CTI research)",
    },
    "tor": {
        "enabled": False,
        "require_vmware": True,
        "socks_proxy": "socks5h://127.0.0.1:9050",
        "targets": [],
        "max_pages_per_target": 1,
        "delay_seconds": 5,
        "save_raw_html": False,
    },
    "paths": {
        "database": "data/krleak.db",
        "web_data_dir": "web/data",
        "log_file": "logs/collector.log",
    },
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, val in (override or {}).items():
        if key.startswith("_"):
            continue
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = val
    return out


def load_config(path: str | Path | None = None) -> dict[str, Any]:
    cfg_path = Path(path) if path else ROOT / "config.json"
    user_cfg: dict[str, Any] = {}

    if cfg_path.exists():
        try:
            with cfg_path.open("r", encoding="utf-8") as fh:
                user_cfg = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("config 로드 실패(%s) — 기본값으로 실행합니다.", exc)
    else:
        log.info("config.json 이 없어 기본값으로 실행합니다. (config.example.json 참고)")

    cfg = _deep_merge(DEFAULTS, user_cfg)
    cfg["_root"] = str(ROOT)
    return cfg


def load_dotenv(path: str | Path | None = None) -> None:
    """.env 를 os.environ 에 로드한다. 이미 설정된 환경변수는 덮어쓰지 않는다."""
    env_path = Path(path) if path else ROOT / ".env"
    if not env_path.exists():
        return
    try:
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = val
    except OSError as exc:
        log.warning(".env 로드 실패: %s", exc)


def resolve_path(cfg: dict[str, Any], key: str) -> Path:
    rel = cfg.get("paths", {}).get(key, "")
    p = Path(rel)
    return p if p.is_absolute() else ROOT / p
