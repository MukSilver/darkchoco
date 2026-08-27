"""출처 주소를 한곳에 모읍니다.

두 앱이 각자 같은 주소를 상수로 갖고 있었습니다. 한쪽이 바뀌면
다른 쪽이 모르는 상태였습니다. API 가 개편되면 여기만 고칩니다.

  dls-observatory   RL_BASE   = "https://api.ransomware.live/v2"
                    LOOK_BASE = "https://www.ransomlook.io/api"
  kr-leak-alarm     BASE      = "https://api.ransomware.live/v2"
                    BASE      = "https://www.ransomlook.io/api"
                    FEED_URL  = "https://ransomfeed.it/rss-complete.php"

주소는 전부 dc_safety.ALLOWED_HOSTS 안에 있어야 합니다.
새 출처를 붙일 때는 거기부터 고쳐야 하고, 그것이 검토 지점입니다.
"""

from __future__ import annotations

RANSOMWARE_LIVE = "https://api.ransomware.live/v2"
RANSOMLOOK = "https://www.ransomlook.io/api"
RANSOMFEED_RSS = "https://ransomfeed.it/rss-complete.php"


# ── ransomware.live ──────────────────────────────────────────────
def rl_groups() -> str:
    """랜섬웨어 그룹 목록. 사이트 주소와 성격이 들어 있습니다."""
    return f"{RANSOMWARE_LIVE}/groups"


def rl_country_victims(code: str = "KR") -> str:
    """국가별 피해자. dls-observatory 와 kr-leak-alarm 이 둘 다 씁니다."""
    return f"{RANSOMWARE_LIVE}/countryvictims/{code}"


def rl_recent_victims() -> str:
    return f"{RANSOMWARE_LIVE}/recentvictims"


def rl_victims(year: int, month: int) -> str:
    return f"{RANSOMWARE_LIVE}/victims/{year}/{month:02d}"


# ── ransomlook.io ────────────────────────────────────────────────
def look_list(kind: str) -> str:
    """kind: groups · markets · forums · telegram"""
    return f"{RANSOMLOOK}/{kind}"


def look_detail(kind: str, name: str) -> str:
    import urllib.parse
    return f"{RANSOMLOOK}/{kind}/{urllib.parse.quote(name)}"
