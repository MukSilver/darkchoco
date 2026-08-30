import argparse
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = BASE_DIR / "output" / "channel_messages.json"
DEFAULT_REPORT = BASE_DIR / "output" / "analysis_report.md"

WORD_PATTERN = re.compile(r"[가-힣]{2,}|[A-Za-z][A-Za-z0-9_-]{2,}")
URL_PATTERN = re.compile(r"https?://[^\s<>\]\[()]+")
STOPWORDS = {
    "그리고", "그러나", "대한", "에서", "으로", "하는", "있는", "없는", "the",
    "and", "for", "that", "this", "with", "from", "http", "https", "telegram",
}


def parse_args():
    parser = argparse.ArgumentParser(description="수집된 Telegram 메시지를 기본 분석합니다.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="입력 JSON 경로")
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT, help="분석 보고서 경로")
    parser.add_argument("--top", type=int, default=20, help="상위 항목 개수(기본값: 20)")
    return parser.parse_args()


def safe_domain(url: str):
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except ValueError:
        return ""


def analyze(input_path: Path, output_path: Path, top: int):
    payload = json.loads(input_path.expanduser().resolve().read_text(encoding="utf-8"))
    messages = payload.get("messages", [])

    words = Counter()
    domains = Counter()
    dates = Counter()
    media_count = 0

    for message in messages:
        text = message.get("text") or ""
        words.update(
            word.lower()
            for word in WORD_PATTERN.findall(text)
            if word.lower() not in STOPWORDS
        )

        for url in URL_PATTERN.findall(text):
            domain = safe_domain(url.rstrip(".,!?;:"))
            if domain:
                domains[domain] += 1

        date = message.get("date")
        if date:
            dates[date[:10]] += 1
        if message.get("has_media"):
            media_count += 1

    ranked = sorted(
        messages,
        key=lambda item: (item.get("views") or 0, item.get("forwards") or 0),
        reverse=True,
    )[:top]

    title = payload.get("channel", {}).get("title") or "알 수 없는 채널"
    lines = [
        f"# Telegram 채널 분석: {title}",
        "",
        f"- 분석 메시지: {len(messages)}개",
        f"- 텍스트 포함: {sum(bool(m.get('text')) for m in messages)}개",
        f"- 미디어 포함: {media_count}개",
        f"- 전체 조회수 합계: {sum(m.get('views') or 0 for m in messages):,}",
        f"- 전체 전달 수 합계: {sum(m.get('forwards') or 0 for m in messages):,}",
        "",
        "## 주요 키워드",
        "",
    ]

    lines.extend(f"- `{word}`: {count}" for word, count in words.most_common(top))
    lines.extend(["", "## 자주 등장한 도메인", ""])
    lines.extend(f"- `{domain}`: {count}" for domain, count in domains.most_common(top))
    lines.extend(["", "## 날짜별 게시량", ""])
    lines.extend(f"- {date}: {count}" for date, count in sorted(dates.items()))
    lines.extend(["", "## 조회수 상위 메시지", ""])

    for message in ranked:
        preview = " ".join((message.get("text") or "[텍스트 없음]").split())[:160]
        lines.append(
            f"- ID `{message.get('id')}` · 조회 {message.get('views') or 0:,} · "
            f"전달 {message.get('forwards') or 0:,} — {preview}"
        )

    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"분석 보고서 저장 위치: {output_path}")


if __name__ == "__main__":
    args = parse_args()
    analyze(args.input, args.output, args.top)
