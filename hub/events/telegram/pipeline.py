"""Telegram 수집 → 분석 보고서 → Notion 안전 동기화를 한 번에 실행한다."""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


BASE_DIR = Path(__file__).resolve().parent


def parse_args():
    parser = argparse.ArgumentParser(description="Telegram 채널 조사·Notion 보고서 통합 자동화")
    parser.add_argument("channel", help="Telegram username, @username 또는 t.me 주소")
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--output-dir", type=Path, default=BASE_DIR / "output")
    parser.add_argument("--data-source-name", default="텔레그램 DB")
    parser.add_argument("--select-data-source-id")
    parser.add_argument("--select-page-id")
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--skip-collect", action="store_true", help="이미 생성된 JSON을 재사용")
    parser.add_argument(
        "--full-refresh",
        action="store_true",
        help="기존 JSON과 합치지 않고 최근 메시지를 처음부터 다시 수집",
    )
    parser.add_argument("--apply-notion", action="store_true", help="미리보기가 아니라 실제 Notion 쓰기 실행")
    return parser.parse_args()


def channel_slug(value: str) -> str:
    raw = value.strip().removeprefix("@")
    if "://" in raw:
        parsed = urlparse(raw)
        raw = parsed.path.strip("/").split("/", 1)[0]
    elif raw.lower().startswith(("t.me/", "telegram.me/")):
        raw = raw.split("/", 1)[1]
    slug = re.sub(r"[^0-9A-Za-z_-]+", "_", raw).strip("_").lower()
    if not slug:
        raise ValueError("출력 파일명으로 사용할 Telegram username을 확인할 수 없습니다.")
    return slug


def run_step(label: str, command: list[str]):
    print(f"\n=== {label} ===")
    result = subprocess.run(command, cwd=BASE_DIR)
    if result.returncode != 0:
        raise RuntimeError(f"‘{label}’ 단계가 실패했습니다. 이후 단계는 실행하지 않습니다.")


def read_new_message_count(json_path: Path):
    try:
        payload = json.loads(json_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"수집 결과 JSON을 확인할 수 없습니다: {json_path}") from error
    value = payload.get("new_message_count")
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise ValueError("수집 결과의 new_message_count 값이 올바르지 않습니다.") from error


def main():
    args = parse_args()
    slug = channel_slug(args.channel)
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{slug}_messages.json"
    report_path = output_dir / f"{slug}_channel_report.md"

    if not args.skip_collect:
        collect_command = [
            sys.executable,
            str(BASE_DIR / "collect.py"),
            args.channel,
            "--limit", str(args.limit),
            "--output", str(json_path),
        ]
        if not args.full_refresh:
            collect_command.append("--incremental")
        run_step("1/3 Telegram 메시지 수집", collect_command)
        if not args.full_refresh and read_new_message_count(json_path) == 0:
            print("\n=== 신규 메시지 없음 ===")
            print("새로 수집된 메시지가 없어 보고서 생성과 Notion 업데이트를 건너뜁니다.")
            print(f"수집 JSON: {json_path}")
            print("Notion 모드: 업데이트 안 함")
            return
    elif not json_path.exists():
        raise ValueError(f"--skip-collect를 사용했지만 JSON 파일이 없습니다: {json_path}")

    run_step("2/3 자동 분석 보고서 생성", [
        sys.executable,
        str(BASE_DIR / "analyze.py"),
        "--input", str(json_path),
        "--output", str(report_path),
    ])

    notion_command = [
        sys.executable,
        str(BASE_DIR / "report.py"),
        "--channel-json", str(json_path),
        "--report", str(report_path),
        "--data-source-name", args.data_source_name,
    ]
    if args.select_data_source_id:
        notion_command.extend(["--select-data-source-id", args.select_data_source_id])
    if args.select_page_id:
        notion_command.extend(["--select-page-id", args.select_page_id])
    if args.non_interactive:
        notion_command.append("--non-interactive")
    if args.apply_notion:
        notion_command.append("--apply")
    run_step("3/3 Notion 안전 검사·동기화", notion_command)

    print("\n=== 전체 작업 완료 ===")
    print(f"수집 JSON: {json_path}")
    print(f"분석 보고서: {report_path}")
    print("Notion 모드: " + ("실제 작성" if args.apply_notion else "미리보기"))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        raise SystemExit(f"오류: {error}")
