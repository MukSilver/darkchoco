"""생성된 Telegram 조사 보고서를 Notion의 안전한 자동 보고서 영역에 동기화한다.

기본 실행은 미리보기만 수행한다. 실제 쓰기는 --apply를 명시한 경우에만 진행한다.
사람이 작성한 채널 페이지 본문은 수정하지 않고, 그 아래의 '자동 분석 보고서'
하위 페이지만 생성하거나 갱신한다.
"""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urlencode

# `hub` 로 시작하는 경로를 쓰므로 저장소 뿌리가 검색 경로에 있어야 합니다.
# 파일 경로로 직접 부르면 이 폴더만 들어가서 못 찾습니다.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from hub.events.telegram.safe_update import (
    MatchDecision,
    NotionCandidate,
    decide_update_target,
    discover_candidates,
    inspect_schema,
    notion_request,
    prompt_candidate_number,
)


AUTO_REPORT_TITLE = "자동 분석 보고서"
REQUIRED_REPORT_HEADINGS = (
    "## DB 요약",
    "## 어떤 곳인가",
    "## 권장 캡처 목록",
    "## 분석 근거",
    "## 수동 검증 체크리스트",
)
PROTECTED_MANUAL_FIELDS = {
    "DB 반영", "담당자", "국가", "웹에 올림", "유통 자리", "이전 이름·별칭", "연결된 곳",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Telegram 자동 보고서를 Notion에 안전하게 동기화")
    parser.add_argument("--channel-json", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--data-source-name", default="텔레그램 DB")
    parser.add_argument("--select-data-source-id")
    parser.add_argument("--select-page-id")
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--apply", action="store_true", help="미리보기 후 실제 Notion 쓰기 실행")
    parser.add_argument(
        "--backup-dir", type=Path, default=Path("output") / "notion_backups",
        help="기존 자동 보고서 백업 폴더",
    )
    return parser.parse_args()


def read_json(path: Path) -> dict:
    payload = json.loads(path.expanduser().resolve().read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("채널 JSON의 최상위 구조는 객체여야 합니다.")
    return payload


def read_report(path: Path) -> str:
    report = path.expanduser().resolve().read_text(encoding="utf-8-sig").strip()
    if not report:
        raise ValueError("보고서 파일이 비어 있습니다.")
    missing = [heading for heading in REQUIRED_REPORT_HEADINGS if heading not in report]
    if missing:
        raise ValueError("보고서 필수 구역이 없습니다: " + ", ".join(missing))
    return report + "\n"


def report_summary(report: str) -> dict:
    headings = re.findall(r"^#{2,3}\s+(.+)$", report, flags=re.MULTILINE)
    capture_rows = len(re.findall(r"^\|\s*(?:필수|권장|선택)\s*\|", report, flags=re.MULTILINE))
    return {
        "characters": len(report),
        "headings": headings,
        "capture_rows": capture_rows,
        "sha256": hashlib.sha256(report.encode("utf-8")).hexdigest(),
    }


def select_target(
    channel: dict,
    candidates: list[NotionCandidate],
    selected_page_id: str | None,
    non_interactive: bool,
) -> MatchDecision:
    decision = decide_update_target(channel, candidates, selected_page_id)
    print(decision.message)
    if decision.selected is None and decision.matches and not non_interactive and sys.stdin.isatty():
        chosen = prompt_candidate_number(decision.matches)
        if chosen:
            decision = decide_update_target(channel, candidates, chosen)
            print(decision.message)
    return decision


def schema_property_map(checks) -> dict:
    return {
        check.key: check
        for check in checks
        if check.status == "ok" and check.property_name
    }


def rich_text_property(value: object) -> dict:
    return {"rich_text": [{"type": "text", "text": {"content": str(value)}}]}


def date_property(value: object) -> dict:
    return {"date": {"start": str(value)}}


def property_value(actual_type: str, value: object) -> dict | None:
    if value is None or value == "":
        return None
    if actual_type == "url":
        return {"url": str(value)}
    if actual_type == "rich_text":
        return rich_text_property(value)
    if actual_type == "number":
        try:
            return {"number": int(value)}
        except (TypeError, ValueError):
            return None
    if actual_type == "date":
        return date_property(value)
    return None


def latest_message_date(messages: list[dict]) -> str | None:
    dates = [str(message.get("date")) for message in messages if message.get("date")]
    return max(dates) if dates else None


def build_property_plan(payload: dict, checks) -> tuple[dict, list[str]]:
    channel = payload.get("channel") or {}
    messages = payload.get("messages") or []
    collected_at = payload.get("collected_at")
    mapping = schema_property_map(checks)
    values = {
        "telegram_address": channel.get("url") or (
            f"https://t.me/{channel['username']}" if channel.get("username") else None
        ),
        "telegram_id": channel.get("id"),
        "checked_at": collected_at,
        "participants": channel.get("participants_count"),
        "last_post": latest_message_date(messages),
    }
    properties = {}
    notes = []
    for key, value in values.items():
        check = mapping.get(key)
        if not check:
            notes.append(f"{key}: 대응하는 정상 형식의 DB 열이 없어 건너뜀")
            continue
        converted = property_value(check.actual_type, value)
        if converted is None:
            notes.append(f"{check.property_name}: 값 또는 형식 문제로 건너뜀")
            continue
        properties[check.property_name] = converted
    status_check = mapping.get("status")
    if status_check:
        if status_check.actual_type == "rich_text":
            properties[status_check.property_name] = rich_text_property("수집 완료")
        else:
            notes.append(
                f"{status_check.property_name}: select/status 선택지는 자동 생성하지 않아 이번에는 유지"
            )
    return properties, notes


def paginated_block_children(token: str, page_id: str):
    cursor = None
    while True:
        query = {"page_size": 100}
        if cursor:
            query["start_cursor"] = cursor
        response = notion_request(
            token,
            "GET",
            f"/blocks/{quote(page_id)}/children?{urlencode(query)}",
        )
        yield from response.get("results") or []
        if not response.get("has_more"):
            break
        cursor = response.get("next_cursor")
        if not cursor:
            break


def find_auto_report_children(token: str, parent_page_id: str) -> list[dict]:
    matches = []
    for block in paginated_block_children(token, parent_page_id):
        if block.get("type") != "child_page":
            continue
        child = block.get("child_page") or {}
        if str(child.get("title") or "").strip() == AUTO_REPORT_TITLE:
            matches.append(block)
    return matches


def retrieve_page_markdown(token: str, page_id: str) -> str:
    response = notion_request(token, "GET", f"/pages/{quote(page_id)}/markdown")
    if response.get("truncated"):
        raise RuntimeError("Notion 보고서가 너무 커서 전체 내용을 읽지 못했습니다. 업데이트를 중단합니다.")
    return str(response.get("markdown") or "")


def create_auto_report(token: str, parent_page_id: str, report: str) -> str:
    response = notion_request(token, "POST", "/pages", {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "properties": {
            "title": {
                "type": "title",
                "title": [{"type": "text", "text": {"content": AUTO_REPORT_TITLE}}],
            }
        },
        "markdown": report,
    })
    page_id = str(response.get("id") or "")
    if not page_id:
        raise RuntimeError("자동 분석 보고서를 만들었지만 page_id를 받지 못했습니다.")
    return page_id


def replace_auto_report(token: str, page_id: str, report: str):
    notion_request(token, "PATCH", f"/pages/{quote(page_id)}/markdown", {
        "type": "replace_content",
        "replace_content": {"new_str": report},
    })


def backup_markdown(backup_dir: Path, channel_name: str, page_id: str, markdown: str) -> Path:
    backup_dir = backup_dir.expanduser().resolve()
    backup_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^0-9A-Za-z가-힣._-]+", "_", channel_name).strip("_") or "channel"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = backup_dir / f"{safe_name}_{page_id}_{timestamp}.md"
    path.write_text(markdown, encoding="utf-8")
    return path


def verify_report(markdown: str):
    missing = [heading for heading in REQUIRED_REPORT_HEADINGS if heading not in markdown]
    if missing:
        raise RuntimeError("작성 후 재검증 실패. 누락 구역: " + ", ".join(missing))


def page_changed_since_discovery(token: str, candidate: NotionCandidate) -> bool:
    if not candidate.last_edited_time:
        return False
    current = notion_request(token, "GET", f"/pages/{quote(candidate.page_id)}")
    return str(current.get("last_edited_time") or "") != candidate.last_edited_time


def print_preview(
    candidate: NotionCandidate,
    decision: MatchDecision,
    report_info: dict,
    properties: dict,
    notes: list[str],
    child_count: int,
):
    print("\n[Notion 업데이트 미리보기]")
    print(f"대상 페이지: {candidate.title}")
    print(f"매칭 방식: {decision.match_method}")
    print(f"Notion 주소: {candidate.notion_url or '미확인'}")
    print(f"DB 열 업데이트 예정: {len(properties)}개")
    for name in properties:
        print(f"  - {name}")
    print(f"자동 보고서 구역: {len(report_info['headings'])}개")
    print(f"권장 캡처 항목: {report_info['capture_rows']}개")
    print(f"자동 보고서 기존 페이지: {child_count}개")
    print("수동 작성 본문: 변경하지 않음")
    print("수동 판단 DB 열: 변경하지 않음 — " + ", ".join(sorted(PROTECTED_MANUAL_FIELDS)))
    for note in notes:
        print(f"[건너뜀] {note}")


def apply_sync(
    token: str,
    payload: dict,
    candidate: NotionCandidate,
    report: str,
    properties: dict,
    child_pages: list[dict],
    backup_dir: Path,
):
    if page_changed_since_discovery(token, candidate):
        raise RuntimeError("대상 페이지가 안전 검사 이후 수정되었습니다. 다시 조회한 뒤 실행하세요.")
    if len(child_pages) > 1:
        raise RuntimeError("‘자동 분석 보고서’ 하위 페이지가 2개 이상이므로 업데이트를 중단합니다.")
    channel_name = str((payload.get("channel") or {}).get("title") or candidate.title)
    if child_pages:
        child_id = str(child_pages[0].get("id") or "")
        previous = retrieve_page_markdown(token, child_id)
        backup = backup_markdown(backup_dir, channel_name, child_id, previous)
        print(f"기존 자동 보고서 백업: {backup}")
        replace_auto_report(token, child_id, report)
        action = "갱신"
    else:
        child_id = create_auto_report(token, candidate.page_id, report)
        action = "생성"
    if properties:
        notion_request(token, "PATCH", f"/pages/{quote(candidate.page_id)}", {
            "properties": properties,
        })
    written = retrieve_page_markdown(token, child_id)
    verify_report(written)
    print(f"[성공] 자동 분석 보고서 {action}")
    print(f"[성공] DB 열 {len(properties)}개 업데이트")
    print("[성공] 작성 결과 재검증")


def main():
    args = parse_args()
    token = os.environ.get("NOTION_TOKEN", "").strip()
    if not token:
        raise ValueError("NOTION_TOKEN 환경변수가 없습니다.")
    payload = read_json(args.channel_json)
    report = read_report(args.report)
    candidates, warnings, source = discover_candidates(
        token,
        args.data_source_name,
        args.select_data_source_id,
    )
    for warning in warnings:
        print(f"[조회 경고] {warning}")
    decision = select_target(
        payload.get("channel") or {},
        candidates,
        args.select_page_id,
        args.non_interactive,
    )
    if decision.selected is None:
        raise SystemExit(2)
    checks = inspect_schema(source.get("properties"))
    properties, notes = build_property_plan(payload, checks)
    children = find_auto_report_children(token, decision.selected.page_id)
    info = report_summary(report)
    print_preview(decision.selected, decision, info, properties, notes, len(children))
    if len(children) > 1:
        raise RuntimeError("자동 분석 보고서 하위 페이지가 중복되어 쓰기를 중단합니다.")
    if not args.apply:
        print("\n미리보기만 완료했습니다. 실제 작성은 --apply를 추가해야 실행됩니다.")
        return
    apply_sync(
        token,
        payload,
        decision.selected,
        report,
        properties,
        children,
        args.backup_dir,
    )


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        raise SystemExit(f"오류: {error}")
