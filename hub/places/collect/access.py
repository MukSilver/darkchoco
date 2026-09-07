"""⑥ 접근성 프로빙. 요구사항 6 대응: 가입 조건 파악 (로드맵 M4).

절대 하지 않는 것: 가입 폼 제출. 입력 필드 목록만 수집하고 값을 채워 넣거나
전송하는 코드는 만들지 않는다 (CLAUDE.md §3-2, §3-3).
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from playwright.sync_api import Page

logger = logging.getLogger(__name__)

# TODO(M4): 실제 대상 사이트 마크업 확인 후 확정.
PASSWORD_INPUT_SELECTOR = "input[type=password]"  # noqa: S105 - 비밀번호 값이 아니라 CSS selector 문자열
REGISTER_FORM_FIELD_SELECTOR = "form input"


def run(page: Page, source: dict[str, Any]) -> dict[str, Any]:
    today = dt.date.today().isoformat()
    result: dict[str, Any] = {}

    has_login_form = page.locator(PASSWORD_INPUT_SELECTOR).count() > 0

    if not has_login_form:
        # **모름과 「필요 없음」을 가릅니다.** 첫 화면에 비밀번호 칸이 없다고
        # 가입이 필요 없는 것이 아닙니다 — 로그인 링크만 걸어 둔 포럼이
        # 흔하고, 챌린지 화면에 막혀도 여기는 0 이 나옵니다. Place.가입필요 는
        # 「모르면 None. False 와 다릅니다」로 정해 두었는데 이 수집기만
        # False 로 확정해 그 갈래를 지우고 있었습니다. 값이 아닌 것으로
        # 내면 Place 의 None 이 그대로 남습니다
        result["가입 필요"] = {
            "state": "BLOCKED",
            "reason": "로그인 폼이 안 보입니다. 가입이 필요 없다는 뜻은 아닙니다",
        }
        return result

    result["가입 필요"] = {"value": has_login_form, "observed_at": today, "source": "로그인 폼 존재 여부"}

    # 입력 필드 목록만 수집한다 — 절대 값을 채워 제출하지 않는다.
    fields = page.locator(REGISTER_FORM_FIELD_SELECTOR).all()
    field_names = []
    for field in fields:
        try:
            name = field.get_attribute("name") or field.get_attribute("placeholder") or ""
        except Exception:  # noqa: BLE001
            logger.debug("가입 필드 파싱 실패, 건너뜀", exc_info=True)
            continue
        if name:
            field_names.append(name)

    # 주의: 결과 키는 "들어가는 법"이 아니라 "_들어가는_법_가입폼"이다. structure.py의
    # 규칙 페이지 원문과 마찬가지로 AUTO-append 소유이므로, investigate.py가 두 Collector의
    # 결과를 하나로 합쳐 "들어가는 법"으로 만든다(한쪽이 다른 쪽을 덮어쓰지 않도록).
    if field_names:
        result["_들어가는_법_가입폼"] = {
            "value": f"요구 필드: {', '.join(dict.fromkeys(field_names))}",
            "observed_at": today,
            "source": "가입 페이지 입력 필드 (제출하지 않음)",
        }
    else:
        result["_들어가는_법_가입폼"] = {"state": "BLOCKED", "reason": "가입 폼 필드 파싱 실패"}

    return result
