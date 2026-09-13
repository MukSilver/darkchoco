"""목록에 적힌 Telegram 공개 채널을 차례대로 안전하게 검사한다."""

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_LOG_DIR = BASE_DIR / "output" / "logs"

# 목록 파일을 찾는 차례. **저장소 밖이 기본입니다.** 무엇을 보고 있는지가
# 드러나기 때문입니다. `tg_preview.py` 의 `_채널들` 과 같은 규칙입니다.
#
# 전에는 `BASE_DIR / "telegram_channels.txt"` 가 기본값이었는데 그 파일은
# 한 번도 만들어진 적이 없어서, 인자 없이 부르면 늘 FileNotFoundError 였습니다.
CHANNELS_ENV = "DARKCHOCO_MANUAL_CHANNELS"
FALLBACK_CHANNELS_FILE = Path.home() / ".config" / "darkchoco" / "수동조사채널"


def 기본_채널파일() -> Path:
    """환경변수가 가리키는 파일이 먼저이고, 없으면 집 설정 폴더를 봅니다."""
    env = (os.environ.get(CHANNELS_ENV) or "").strip()
    return Path(env) if env else FALLBACK_CHANNELS_FILE


DEFAULT_CHANNELS_FILE = 기본_채널파일()


def parse_args():
    parser = argparse.ArgumentParser(description="Telegram 채널 목록 일괄 모니터링")
    parser.add_argument("--channels-file", type=Path, default=기본_채널파일())
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR)
    parser.add_argument(
        "--apply-notion",
        action="store_true",
        help="신규 메시지가 있을 때 검증된 Notion 페이지에 실제 작성",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Notion 후보가 여러 개면 터미널에서 직접 선택(예약 실행에는 사용하지 않음)",
    )
    return parser.parse_args()


def load_channels(path: Path):
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(
            f"채널 목록 파일이 없습니다: {resolved}\n"
            f"  한 줄에 하나씩 적으십시오. 저장소 밖에 둡니다.\n"
            f"  기본 자리는 {FALLBACK_CHANNELS_FILE} 이고,\n"
            f"  {CHANNELS_ENV} 환경변수나 --channels-file 로 다른 자리를 줄 수 있습니다.")
    channels = []
    seen = set()
    for line_number, raw in enumerate(resolved.read_text(encoding="utf-8-sig").splitlines(), 1):
        value = raw.strip()
        if not value or value.startswith("#"):
            continue
        if any(character.isspace() for character in value):
            raise ValueError(f"{line_number}번째 줄의 채널 주소에 공백이 있습니다: {value}")
        key = value.lower().rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        channels.append(value)
    if not channels:
        raise ValueError(f"채널 목록이 비어 있습니다: {resolved}\n"
                         f"  주석(#)과 빈 줄만 있습니다. 채널 이름을 한 줄에 하나씩 적으십시오.")
    return resolved, channels


def run_channel(channel: str, args):
    command = [
        sys.executable,
        str(BASE_DIR / "pipeline.py"),
        channel,
        "--limit", str(args.limit),
    ]
    if not args.interactive:
        command.append("--non-interactive")
    if args.apply_notion:
        command.append("--apply-notion")

    environment = os.environ.copy()
    environment.setdefault("PYTHONUTF8", "1")
    return subprocess.run(
        command,
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )


def main():
    args = parse_args()
    channels_path, channels = load_channels(args.channels_file)
    log_dir = args.log_dir.expanduser().resolve()
    log_dir.mkdir(parents=True, exist_ok=True)
    started = datetime.now()
    log_path = log_dir / f"telegram_monitor_{started:%Y%m%d_%H%M%S}.log"
    log_lines = [
        f"실행 시각: {started.isoformat(timespec='seconds')}",
        f"채널 목록: {channels_path}",
        f"채널 수: {len(channels)}",
        f"Notion 모드: {'실제 작성' if args.apply_notion else '미리보기'}",
    ]
    failures = []

    for index, channel in enumerate(channels, 1):
        heading = f"[{index}/{len(channels)}] {channel}"
        print(f"\n=== {heading} ===")
        result = run_channel(channel, args)
        output = (result.stdout or "").rstrip()
        error_output = (result.stderr or "").rstrip()
        if output:
            print(output)
        if error_output:
            print(error_output, file=sys.stderr)
        status = "성공" if result.returncode == 0 else f"실패({result.returncode})"
        log_lines.extend(["", f"=== {heading} / {status} ===", output])
        if error_output:
            log_lines.extend(["[표준 오류]", error_output])
        if result.returncode != 0:
            failures.append(channel)

    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    print("\n=== 채널 모니터링 완료 ===")
    print(f"성공: {len(channels) - len(failures)}개")
    print(f"실패: {len(failures)}개")
    print(f"로그: {log_path}")
    if failures:
        print("실패 채널: " + ", ".join(failures))
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        raise SystemExit(f"오류: {error}")
