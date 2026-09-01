"""Telegram 보고서를 Notion에 기록하기 전 대상 페이지를 안전하게 선택한다.

정책
1. 일치 페이지 0개: 중단하고 확인 방법 안내
2. 일치 페이지 1개: 자동 업데이트 허용
3. 일치 페이지 2개 이상: 중단하고 사람이 page_id를 선택

이 파일에는 Notion 토큰을 저장하지 않는다. 실제 API 연결 코드는 이 모듈의
``run_guarded_update``를 통과한 뒤에만 쓰기 요청을 보내야 한다.
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "packages"))
from dc_notion import Notion  # noqa: E402


TELEGRAM_HOSTS = {"t.me", "telegram.me", "www.t.me", "www.telegram.me"}
NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2026-03-11"

SCHEMA_REQUIREMENTS = (
    {
        "key": "title",
        "label": "채널명",
        "aliases": ("채널명", "이름", "name", "title"),
        "types": {"title"},
        "level": "필수",
        "purpose": "Notion 페이지 제목",
    },
    {
        "key": "telegram_address",
        "label": "Telegram 주소",
        "aliases": ("telegram 주소", "텔레그램 주소", "채널 주소", "주소", "address", "url"),
        "types": {"url", "rich_text"},
        "level": "필수",
        "purpose": "정확한 채널 매칭",
    },
    {
        "key": "telegram_id",
        "label": "Telegram 고유 ID",
        "aliases": ("telegram id", "텔레그램 id", "채널 id", "telegram 고유 id"),
        "types": {"rich_text", "number"},
        "level": "권장",
        "purpose": "username 변경 시에도 같은 채널 식별",
    },
    {
        "key": "checked_at",
        "label": "확인일",
        "aliases": ("확인일", "마지막 확인일", "수집일"),
        "types": {"date"},
        "level": "자동입력",
        "purpose": "마지막 조사 시점",
    },
    {
        "key": "status",
        "label": "상태",
        "aliases": ("상태", "수집 상태", "채널 상태"),
        "types": {"status", "select", "rich_text"},
        "level": "자동입력",
        "purpose": "접근·수집 상태",
    },
    {
        "key": "participants",
        "label": "구독자·참가자 수",
        "aliases": ("구독자 수", "참가자 수", "구독자·참가자 수", "규모"),
        "types": {"number", "rich_text"},
        "level": "자동입력",
        "purpose": "채널 규모",
    },
    {
        "key": "last_post",
        "label": "마지막 게시일",
        "aliases": ("마지막 게시일", "최근 게시일", "마지막 메시지 일시"),
        "types": {"date"},
        "level": "자동입력",
        "purpose": "최근 활동 시점",
    },
    {
        "key": "auto_collect",
        "label": "자동 수집",
        "aliases": ("자동 수집", "모니터링", "수집 대상"),
        "types": {"checkbox"},
        "level": "향후",
        "purpose": "정기 모니터링 대상 선택",
    },
    {
        "key": "last_message_id",
        "label": "마지막 메시지 ID",
        "aliases": ("마지막 메시지 id", "last message id"),
        "types": {"number", "rich_text"},
        "level": "향후",
        "purpose": "신규 메시지만 수집",
    },
)


@dataclass(frozen=True)
class NotionCandidate:
    page_id: str
    title: str
    identifiers: tuple[str, ...]
    notion_url: str = ""
    data_source_id: str = ""
    data_source_title: str = ""
    telegram_ids: tuple[str, ...] = ()
    last_edited_time: str = ""


@dataclass(frozen=True)
class MatchDecision:
    status: str
    message: str
    matches: tuple[NotionCandidate, ...]
    selected: NotionCandidate | None = None
    match_method: str = ""


@dataclass(frozen=True)
class SchemaCheck:
    key: str
    label: str
    level: str
    status: str
    property_name: str = ""
    actual_type: str = ""
    expected_types: tuple[str, ...] = ()
    purpose: str = ""


def normalize_telegram_identifier(value: object) -> str:
    """Telegram URL, @username, username을 비교 가능한 소문자 username으로 바꾼다."""
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    raw = raw.replace("hxxps://", "https://").replace("hxxp://", "http://")
    if raw.startswith("@"):
        raw = raw[1:]
    if "://" not in raw and raw.startswith(("t.me/", "telegram.me/")):
        raw = "https://" + raw
    if "://" in raw:
        try:
            parsed = urlparse(raw)
            hostname = parsed.hostname
        except ValueError:
            return ""
        if hostname and hostname.lower() in TELEGRAM_HOSTS:
            raw = parsed.path.strip("/").split("/", 1)[0]
        elif hostname:
            return ""
    raw = raw.split("?", 1)[0].split("#", 1)[0].strip("/@ ")
    return raw if re.fullmatch(r"[a-z0-9_]{4,}", raw) else ""


def channel_identifiers(channel: dict) -> set[str]:
    values = {
        normalize_telegram_identifier(channel.get("username")),
        normalize_telegram_identifier(channel.get("url")),
    }
    return {value for value in values if value}


def normalize_telegram_id(value: object) -> str:
    raw = str(value or "").strip().replace(" ", "")
    if not re.fullmatch(r"-?\d+", raw):
        return ""
    digits = raw.lstrip("-")
    if digits.startswith("100") and len(digits) > 10:
        digits = digits[3:]
    return digits.lstrip("0") or "0"


def channel_telegram_ids(channel: dict) -> set[str]:
    return {
        value for value in (
            normalize_telegram_id(channel.get("id")),
            normalize_telegram_id(channel.get("peer_id")),
        ) if value
    }


def candidate_telegram_ids(candidate: NotionCandidate) -> set[str]:
    return {
        normalized for value in candidate.telegram_ids
        if (normalized := normalize_telegram_id(value))
    }


def candidate_identifiers(candidate: NotionCandidate) -> set[str]:
    values = {
        normalize_telegram_identifier(value)
        for value in candidate.identifiers
    }
    return {value for value in values if value}


def find_exact_matches(channel: dict, candidates: Iterable[NotionCandidate]) -> tuple[list[NotionCandidate], str]:
    candidate_list = list(candidates)
    target_ids = channel_telegram_ids(channel)
    if target_ids:
        id_matches = [
            candidate for candidate in candidate_list
            if target_ids.intersection(candidate_telegram_ids(candidate))
        ]
        if id_matches:
            return id_matches, "telegram_id"
    targets = channel_identifiers(channel)
    if not targets:
        return [], ""
    matches = [
        candidate for candidate in candidate_list
        if targets.intersection(candidate_identifiers(candidate))
    ]
    return matches, "username_or_url" if matches else ""


def find_name_candidates(channel: dict, candidates: Iterable[NotionCandidate]) -> list[NotionCandidate]:
    title = normalized_title(channel.get("title"))
    if not title:
        return []
    return [candidate for candidate in candidates if normalized_title(candidate.title) == title]


def decide_update_target(
    channel: dict,
    candidates: Iterable[NotionCandidate],
    selected_page_id: str | None = None,
) -> MatchDecision:
    candidate_list = list(candidates)
    exact_matches, method = find_exact_matches(channel, candidate_list)
    matches = tuple(exact_matches)
    if not matches:
        name_matches = tuple(find_name_candidates(channel, candidate_list))
        if name_matches:
            if selected_page_id:
                selected = next(
                    (item for item in name_matches if item.page_id == selected_page_id),
                    None,
                )
                if selected:
                    return MatchDecision(
                        status="ready_manual_name_match",
                        message=(
                            "이름만 일치한 후보를 사용자가 선택했습니다. "
                            "선택한 페이지에 한해서 업데이트할 수 있습니다."
                        ),
                        matches=name_matches,
                        selected=selected,
                        match_method="manual_name_match",
                    )
            return MatchDecision(
                status="stopped_name_only",
                message=(
                    f"채널명만 일치하는 후보가 {len(name_matches)}개 있습니다. "
                    "Telegram ID·주소가 확인되지 않아 자동 업데이트를 중단합니다."
                ),
                matches=name_matches,
                match_method="name_only",
            )
        return MatchDecision(
            status="stopped_no_match",
            message="일치하는 Notion 페이지가 0개입니다. 업데이트를 중단합니다.",
            matches=matches,
        )
    if len(matches) == 1:
        return MatchDecision(
            status="ready_auto",
            message="일치하는 Notion 페이지가 1개이므로 자동 업데이트할 수 있습니다.",
            matches=matches,
            selected=matches[0],
            match_method=method,
        )
    if selected_page_id:
        selected = next((item for item in matches if item.page_id == selected_page_id), None)
        if selected:
            return MatchDecision(
                status="ready_manual",
                message="중복 후보 중 하나가 선택되었습니다. 선택된 페이지만 업데이트할 수 있습니다.",
                matches=matches,
                selected=selected,
                match_method=method,
            )
        return MatchDecision(
            status="stopped_invalid_selection",
            message="선택한 page_id가 일치 후보에 없습니다. 업데이트를 중단합니다.",
            matches=matches,
        )
    return MatchDecision(
        status="stopped_multiple_matches",
        message=(
            f"일치하는 Notion 페이지가 {len(matches)}개입니다. 업데이트하지 않았습니다. "
            "아래 후보 중 올바른 page_id를 선택해 다시 실행하세요."
        ),
        matches=matches,
        match_method=method,
    )


def run_guarded_update(
    channel: dict,
    candidates: Iterable[NotionCandidate],
    update_function: Callable[[NotionCandidate], None],
    selected_page_id: str | None = None,
) -> MatchDecision:
    """대상이 하나로 확정된 경우에만 전달받은 실제 쓰기 함수를 실행한다."""
    decision = decide_update_target(channel, candidates, selected_page_id)
    if decision.selected is not None:
        update_function(decision.selected)
    return decision


_clients: dict[str, "Notion"] = {}


def notion_request(token: str, method: str, path: str, payload: dict | None = None) -> dict:
    """공용 dc_notion 을 쓴다. 부르는 쪽 형태는 그대로다.

    직접 짜 두었던 것과 견주면 이만큼이 달라진다.
      · 429 를 받으면 Retry-After 헤더가 말한 만큼 기다린다 (전에는 1초·2초 고정)
      · 502·503·504 도 다시 보낸다 (전에는 한 번 끊기면 그대로 중단)
      · 요청 사이를 벌려 초당 3건을 넘기지 않는다
      · 재시도 3회에서 6회로 늘었다
      · 한 번의 읽기 타임아웃이 30초에서 60초로 늘었다

    노션 판 번호는 이 앱 것(NOTION_VERSION)을 그대로 쓴다. data_sources 는
    판마다 응답이 달라서 공용 기본값으로 바꾸면 판정이 어긋난다.

    NotionError 는 RuntimeError 를 물려받으므로 잡는 쪽은 손댈 것이 없다.

    대부분 나아진 것인데 대신 딸려 온 것이 둘이다. 2026-09-01 에 확인만
    하고 코드는 안 건드렸다. 여기 적어 두는 이유는, 둘 다 지금 고치면
    나은지 아닌지를 사람이 정해야 하기 때문이다.

      1. 최악의 경우 한 요청이 훨씬 오래 매달린다. 재시도 6회 × 타임아웃
         60초에 백오프까지 더해진다. 통합 전에는 telegram_schedule.ps1 이
         예약 작업에 ExecutionTimeLimit 1시간을 걸어 이것을 잘랐는데,
         그 스크립트가 통합본에 없다. 지금은 상한이 아무 데도 없다.
      2. dc_notion 은 verbose 가 기본 True 라 「[notion] 429 rate limit」
         같은 줄이 표준출력에 섞인다. monitor.py 가 자식 프로세스의
         표준출력을 그대로 로그 파일에 담으므로 로그에도 들어간다.
         메시지 원문이 아니라 재시도 사실만 찍히므로 유출은 아니다.
         조용히 하려면 여기서 Notion(..., verbose=False) 로 만들면 된다.
    """
    client = _clients.get(token)
    if client is None:
        client = _clients[token] = Notion(token=token, version=NOTION_VERSION)
    return client.request(method, path, payload)


def rich_text_value(items: object) -> list[str]:
    if not isinstance(items, list):
        return []
    values = []
    for item in items:
        if not isinstance(item, dict):
            continue
        value = item.get("plain_text")
        if value:
            values.append(str(value))
    return values


def property_text_values(properties: object, aliases: Iterable[str] | None = None) -> list[str]:
    """페이지 속성에서 사람이 볼 수 있는 텍스트·URL만 추출한다."""
    if not isinstance(properties, dict):
        return []
    values = []
    allowed = {normalized_title(alias) for alias in aliases} if aliases else None
    for property_name, prop in properties.items():
        if not isinstance(prop, dict):
            continue
        if allowed is not None and normalized_title(property_name) not in allowed:
            continue
        prop_type = prop.get("type")
        if prop_type in {"title", "rich_text"}:
            values.extend(rich_text_value(prop.get(prop_type)))
        elif prop_type == "url" and prop.get("url"):
            values.append(str(prop["url"]))
        elif prop_type in {"select", "status"}:
            option = prop.get(prop_type)
            if isinstance(option, dict) and option.get("name"):
                values.append(str(option["name"]))
        elif prop_type == "multi_select":
            values.extend(
                str(option["name"]) for option in prop.get("multi_select") or []
                if isinstance(option, dict) and option.get("name")
            )
        elif prop_type == "formula":
            formula = prop.get("formula") or {}
            if formula.get("type") == "string" and formula.get("string"):
                values.append(str(formula["string"]))
    return values


def requirement_aliases(key: str) -> tuple[str, ...]:
    for requirement in SCHEMA_REQUIREMENTS:
        if requirement["key"] == key:
            return tuple(requirement["aliases"])
    return ()


def page_telegram_ids(properties: object) -> list[str]:
    if not isinstance(properties, dict):
        return []
    aliases = {normalized_title(value) for value in requirement_aliases("telegram_id")}
    values = []
    for name, prop in properties.items():
        if normalized_title(name) not in aliases or not isinstance(prop, dict):
            continue
        prop_type = prop.get("type")
        if prop_type == "number" and prop.get("number") is not None:
            values.append(str(prop["number"]))
        elif prop_type == "rich_text":
            values.extend(rich_text_value(prop.get("rich_text")))
    return values


def page_title(properties: object) -> str:
    if not isinstance(properties, dict):
        return "제목 없음"
    for prop in properties.values():
        if isinstance(prop, dict) and prop.get("type") == "title":
            values = rich_text_value(prop.get("title"))
            if values:
                return "".join(values)
    return "제목 없음"


def object_title(item: dict) -> str:
    title = rich_text_value(item.get("title"))
    return "".join(title) if title else "이름 없는 데이터 소스"


def paginated_post(token: str, path: str, initial_payload: dict | None = None):
    cursor = None
    while True:
        payload = dict(initial_payload or {})
        payload["page_size"] = 100
        if cursor:
            payload["start_cursor"] = cursor
        response = notion_request(token, "POST", path, payload)
        yield from response.get("results") or []
        if not response.get("has_more"):
            break
        cursor = response.get("next_cursor")
        if not cursor:
            break


def discover_data_sources(token: str, title_query: str) -> list[dict]:
    return list(paginated_post(
        token,
        "/search",
        {
            "query": title_query,
            "filter": {"property": "object", "value": "data_source"},
        },
    ))


def normalized_title(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def inspect_schema(properties: object) -> list[SchemaCheck]:
    schema = properties if isinstance(properties, dict) else {}
    normalized_properties = {
        normalized_title(name): (str(name), config)
        for name, config in schema.items()
        if isinstance(config, dict)
    }
    checks = []
    for requirement in SCHEMA_REQUIREMENTS:
        found = None
        for alias in requirement["aliases"]:
            found = normalized_properties.get(normalized_title(alias))
            if found:
                break
        expected = tuple(sorted(requirement["types"]))
        if not found:
            checks.append(SchemaCheck(
                key=requirement["key"],
                label=requirement["label"],
                level=requirement["level"],
                status="missing",
                expected_types=expected,
                purpose=requirement["purpose"],
            ))
            continue
        property_name, config = found
        actual_type = str(config.get("type") or "미확인")
        status = "ok" if actual_type in requirement["types"] else "wrong_type"
        checks.append(SchemaCheck(
            key=requirement["key"],
            label=requirement["label"],
            level=requirement["level"],
            status=status,
            property_name=property_name,
            actual_type=actual_type,
            expected_types=expected,
            purpose=requirement["purpose"],
        ))
    return checks


def print_schema_report(data_source: dict, checks: list[SchemaCheck]):
    properties = data_source.get("properties") or {}
    print("\n[Notion DB 열 점검]")
    print(f"데이터 소스: {object_title(data_source)}")
    print(f"현재 열 수: {len(properties)}개")
    for check in checks:
        if check.status == "ok":
            print(
                f"[정상/{check.level}] {check.label}: "
                f"{check.property_name} ({check.actual_type})"
            )
        elif check.status == "wrong_type":
            expected = ", ".join(check.expected_types)
            print(
                f"[형식 확인/{check.level}] {check.label}: {check.property_name} "
                f"(현재 {check.actual_type}, 권장 {expected})"
            )
        else:
            expected = ", ".join(check.expected_types)
            print(f"[없음/{check.level}] {check.label}: 권장 형식 {expected}")
    unknown = [
        f"{name}({config.get('type', '미확인')})"
        for name, config in properties.items()
        if isinstance(config, dict)
        and normalized_title(name) not in {
            normalized_title(alias)
            for requirement in SCHEMA_REQUIREMENTS
            for alias in requirement["aliases"]
        }
    ]
    if unknown:
        print("[기존 기타 열] " + ", ".join(unknown))
    print("주의: 이 단계에서는 열을 만들거나 수정하지 않습니다.\n")


def select_data_source(
    sources: list[dict],
    data_source_name: str,
    selected_data_source_id: str | None = None,
) -> dict:
    exact = [
        source for source in sources
        if normalized_title(object_title(source)) == normalized_title(data_source_name)
    ]
    if selected_data_source_id:
        selected = next(
            (source for source in exact if str(source.get("id")) == selected_data_source_id),
            None,
        )
        if selected:
            return selected
        raise RuntimeError("선택한 data_source_id가 정확히 일치하는 텔레그램 DB 후보에 없습니다.")
    if not exact:
        found = ", ".join(object_title(source) for source in sources[:10]) or "없음"
        raise RuntimeError(
            f"이름이 정확히 ‘{data_source_name}’인 데이터 소스를 찾지 못했습니다. 검색 후보: {found}"
        )
    if len(exact) > 1:
        choices = ", ".join(
            f"{object_title(source)}({source.get('id')})" for source in exact
        )
        raise RuntimeError(
            f"이름이 같은 데이터 소스가 {len(exact)}개입니다. 자동 조회를 중단합니다: {choices}"
        )
    return exact[0]


def discover_candidates(
    token: str,
    data_source_name: str = "텔레그램 DB",
    selected_data_source_id: str | None = None,
) -> tuple[list[NotionCandidate], list[str], dict]:
    """이름이 정확히 일치하는 데이터 소스 하나에서만 페이지 후보를 수집한다."""
    candidates = []
    warnings = []
    sources = discover_data_sources(token, data_source_name)
    source_summary = select_data_source(sources, data_source_name, selected_data_source_id)
    source_id = str(source_summary.get("id") or "")
    source = notion_request(token, "GET", f"/data_sources/{source_id}")
    source_title = object_title(source)
    try:
        pages = paginated_post(token, f"/data_sources/{source_id}/query")
        for page in pages:
            if not isinstance(page, dict) or page.get("object") != "page":
                continue
            properties = page.get("properties") or {}
            values = property_text_values(
                properties,
                requirement_aliases("telegram_address"),
            )
            candidates.append(NotionCandidate(
                page_id=str(page.get("id") or ""),
                title=page_title(properties),
                identifiers=tuple(values),
                notion_url=str(page.get("url") or ""),
                data_source_id=source_id,
                data_source_title=source_title,
                telegram_ids=tuple(page_telegram_ids(properties)),
                last_edited_time=str(page.get("last_edited_time") or ""),
            ))
    except RuntimeError as error:
        warnings.append(f"{source_title}: {error}")
    return candidates, warnings, source


def load_candidates(path: Path) -> list[NotionCandidate]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, list):
        raise ValueError("후보 JSON의 최상위 구조는 배열이어야 합니다.")
    candidates = []
    for item in payload:
        if not isinstance(item, dict) or not item.get("page_id"):
            continue
        identifiers = item.get("identifiers") or []
        if isinstance(identifiers, str):
            identifiers = [identifiers]
        candidates.append(NotionCandidate(
            page_id=str(item["page_id"]),
            title=str(item.get("title") or "제목 없음"),
            identifiers=tuple(str(value) for value in identifiers),
            notion_url=str(item.get("notion_url") or ""),
            telegram_ids=tuple(str(value) for value in item.get("telegram_ids") or []),
            last_edited_time=str(item.get("last_edited_time") or ""),
        ))
    return candidates


def candidate_identity_text(candidate: NotionCandidate) -> str:
    parts = []
    usernames = sorted(candidate_identifiers(candidate))
    telegram_ids = sorted(candidate_telegram_ids(candidate))
    if usernames:
        parts.append("Telegram: " + ", ".join(f"@{value}" for value in usernames))
    if telegram_ids:
        parts.append("ID: " + ", ".join(telegram_ids))
    return " | ".join(parts) or "Telegram 식별정보 없음"


def print_candidate_menu(candidates: tuple[NotionCandidate, ...]):
    print("\n[Notion 페이지 후보]")
    for index, candidate in enumerate(candidates, start=1):
        print(f"[{index}] {candidate.title}")
        print(f"    {candidate_identity_text(candidate)}")
        if candidate.notion_url:
            print(f"    Notion: {candidate.notion_url}")
    print("[0] 취소")


def prompt_candidate_number(candidates: tuple[NotionCandidate, ...]) -> str | None:
    print_candidate_menu(candidates)
    while True:
        try:
            raw = input("선택할 번호를 입력하세요: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n선택을 취소했습니다.")
            return None
        if raw == "0":
            print("선택을 취소했습니다.")
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(candidates):
            return candidates[int(raw) - 1].page_id
        print(f"0부터 {len(candidates)} 사이의 번호를 입력하세요.")


def parse_args():
    parser = argparse.ArgumentParser(description="Notion 자동 업데이트 전 대상 페이지 안전 검사")
    parser.add_argument("--channel-json", type=Path, required=True, help="collect.py 가 만든 JSON")
    parser.add_argument(
        "--candidates-json", type=Path,
        help="테스트용 후보 JSON. 생략하면 NOTION_TOKEN으로 데이터 소스를 자동 탐색",
    )
    parser.add_argument(
        "--data-source-name", default="텔레그램 DB",
        help="자동 탐색할 데이터 소스의 정확한 이름 (기본값: 텔레그램 DB)",
    )
    parser.add_argument(
        "--select-data-source-id",
        help="같은 이름의 데이터 소스가 2개 이상일 때 사람이 선택한 ID",
    )
    parser.add_argument("--select-page-id", help="후보가 2개 이상일 때 사람이 선택한 Notion page_id")
    parser.add_argument(
        "--non-interactive", action="store_true",
        help="후보가 여러 개여도 번호 입력을 기다리지 않고 중단 (정기 실행용)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    payload = json.loads(args.channel_json.read_text(encoding="utf-8-sig"))
    channel = payload.get("channel") or {}
    if args.candidates_json:
        candidates = load_candidates(args.candidates_json)
        warnings = []
        source = None
    else:
        token = os.environ.get("NOTION_TOKEN", "").strip()
        if not token:
            raise ValueError("NOTION_TOKEN 환경변수가 없습니다.")
        print(f"Notion에서 ‘{args.data_source_name}’ 데이터 소스만 탐색합니다...")
        candidates, warnings, source = discover_candidates(
            token,
            args.data_source_name,
            args.select_data_source_id,
        )
        print(f"‘{args.data_source_name}’에서 조회한 페이지: {len(candidates)}개")
    if source:
        print_schema_report(source, inspect_schema(source.get("properties")))
    for warning in warnings:
        print(f"[조회 경고] {warning}")
    decision = decide_update_target(
        channel,
        candidates,
        args.select_page_id,
    )
    print(decision.message)
    can_prompt = (
        decision.selected is None
        and bool(decision.matches)
        and not args.non_interactive
        and sys.stdin.isatty()
    )
    if can_prompt:
        selected_page_id = prompt_candidate_number(decision.matches)
        if selected_page_id:
            decision = decide_update_target(channel, candidates, selected_page_id)
            print(decision.message)
    elif decision.matches:
        print_candidate_menu(decision.matches)
    if decision.selected is None:
        raise SystemExit(2)
    print(f"선택 페이지: {decision.selected.title}")
    print(f"매칭 방식: {decision.match_method}")
    print("안전 검사 통과: 실제 Notion 쓰기 함수를 호출할 수 있습니다.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(f"오류: {error}")
