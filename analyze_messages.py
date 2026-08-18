import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = BASE_DIR / "output" / "channel_messages.json"
DEFAULT_REPORT = BASE_DIR / "output" / "preliminary_analysis.md"
WORD_PATTERN = re.compile(r"[가-힣]{2,}|[A-Za-z][A-Za-z0-9_.-]{2,}")
URL_PATTERN = re.compile(r"https?://[^\s<>\]\[()]+")
STOPWORDS = {
    "그리고", "그러나", "그런데", "대한", "에서", "으로", "하는", "있는", "없는", "합니다", "입니다",
    "the", "and", "for", "that", "this", "with", "from", "http", "https", "telegram", "www",
    "you", "your", "are", "not", "can", "what", "why", "who", "how", "him", "her", "they", "them",
    "have", "has", "had", "was", "were", "will", "would", "just", "like", "bro", "nigga", "dont", "don't",
}
SIGNALS = {
    "개인정보·계정": ("개인정보", "주민번호", "전화번호", "계정", "credential", "password", "database", "db"),
    "금전·거래": ("판매", "구매", "가격", "송금", "입금", "지갑", "bitcoin", "btc", "usdt", "crypto"),
    "침해·악성행위": ("해킹", "침해", "랜섬웨어", "악성코드", "exploit", "ransomware", "malware", "breach", "botnet"),
    "유출 주장": ("유출", "덤프", "샘플", "leak", "dump", "stolen", "data breach"),
    "긴급성·위협": ("긴급", "즉시", "협박", "공격", "삭제", "urgent", "attack", "threat", "deadline"),
}
TOPICS = {
    "데이터베이스·유출 자료 공유/판매": ("database", " db ", "데이터 판매", "유출", "leak", "dump", "samples will", "sell data", "data sell"),
    "포럼·CDN·서비스 운영": ("breachforums", " cdn ", "database index", "forum update", "forum as", "forum without"),
    "취약점·침해 기술": ("vuln", "exploit", "hacking", "spoof", "phish", "malware", "ransomware", "ddos"),
    "암호화폐·금전 거래": ("btc", "xmr", "eth", "usdt", "crypto", "wallet", "payment", "price", "가격", "송금"),
    "사기 의혹·커뮤니티 분쟁": ("scam", "exit scam", "fraud", "사기", "싸움", "분쟁"),
    "계정·인증정보": ("account", "login", "password", "credential", "otp", "계정", "비밀번호"),
}


def parse_args():
    parser = argparse.ArgumentParser(description="수집한 Telegram 대화의 통계와 키워드 검토 후보를 Markdown 초벌 자료로 정리합니다.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="입력 JSON 경로")
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT, help="출력 Markdown 경로")
    parser.add_argument("--date", help="특정 날짜만 분석 (YYYY-MM-DD)")
    parser.add_argument("--timezone", help="날짜 판정 시간대 (기본: 수집 JSON 값 또는 Asia/Seoul)")
    parser.add_argument("--top", type=int, default=10, help="날짜별 상위 항목 수 (기본: 10)")
    return parser.parse_args()


def get_timezone(name):
    try:
        return ZoneInfo(name)
    except Exception:
        if name == "Asia/Seoul":
            return timezone(timedelta(hours=9), name)
        if name in {"UTC", "Etc/UTC"}:
            return timezone.utc
        raise ValueError(f"시간대 '{name}'을 불러올 수 없습니다. tzdata를 설치하거나 Asia/Seoul 또는 UTC를 사용하세요.")


def local_day(value, tz):
    if not value:
        return "날짜 없음"
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz)
    return parsed.astimezone(tz).date().isoformat()


def keywords(messages, top):
    counts = Counter()
    for message in messages:
        counts.update(w.lower() for w in WORD_PATTERN.findall(message.get("text") or "") if w.lower() not in STOPWORDS)
    return counts.most_common(top)


def preview(message, length=180):
    text = " ".join((message.get("text") or "[텍스트 없음]").split())
    return text[:length] + ("…" if len(text) > length else "")


def message_link(channel, message_id):
    username = channel.get("username")
    if username:
        return f"https://t.me/{username}/{message_id}"
    return None


def signal_hits(messages):
    hits = defaultdict(list)
    for message in messages:
        lowered = (message.get("text") or "").lower()
        for label, terms in SIGNALS.items():
            matched = sorted({term for term in terms if term in lowered})
            if matched:
                hits[label].append((message, matched))
    return hits


def topic_counts(messages):
    counts = Counter()
    examples = defaultdict(list)
    for message in messages:
        lowered = f" {(message.get('text') or '').lower()} "
        for label, terms in TOPICS.items():
            if any(term in lowered for term in terms):
                counts[label] += 1
                examples[label].append(message.get("id"))
    return counts, examples


def daily_summary(day, messages, top_words, hits):
    topics, examples = topic_counts(messages)
    minimum_repetition = max(2, round(len(messages) * 0.005))
    ranked_topics = [(name, count) for name, count in topics.most_common(3) if count >= minimum_repetition]
    notes = []
    if ranked_topics:
        topic_text = ", ".join(f"{name}({count}건)" for name, count in ranked_topics)
        notes.append(f"**{day} 대화 요약:** 전체적으로는 일상 대화와 커뮤니티 내부 잡담의 비중이 컸고, 그중 의미 있는 화제로는 {topic_text} 관련 이야기가 반복됐다.")
        lead = ranked_topics[0][0]
        ids = ", ".join(str(item) for item in examples[lead][:5])
        notes.append(f"가장 두드러진 주제는 **{lead}**였으며, 대표 근거 메시지는 ID {ids}이다.")
    else:
        notes.append(f"**{day} 대화 요약:** 특정 보안·거래 주제가 유의미하게 반복되지 않았으며, 일상적인 대화와 커뮤니티 내부 잡담이 중심이었다.")

    if top_words:
        notes.append("대화 맥락을 대표하는 빈출 표현은 " + ", ".join(f"`{word}`" for word, _ in top_words[:5]) + "였다.")
    if hits:
        lead_signal, items = max(hits.items(), key=lambda item: len(item[1]))
        notes.append(f"심층 검토 후보 중에는 **{lead_signal}** 관련 메시지가 {len(items)}건으로 가장 많았다. 이는 키워드 선별 결과이므로 원문 주장과 확인된 사실을 구분해야 한다.")
    else:
        notes.append("심층 검토 규칙에서 반복적으로 포착된 주의 신호는 없었다.")
    return notes


def analyze(input_path: Path, output_path: Path, top: int, selected_date=None, timezone_name=None):
    if top < 1:
        raise ValueError("--top은 1 이상이어야 합니다.")
    payload = json.loads(input_path.expanduser().resolve().read_text(encoding="utf-8-sig"))
    tz_name = timezone_name or payload.get("timezone") or "Asia/Seoul"
    tz = get_timezone(tz_name)
    channel = payload.get("channel", {})
    grouped = defaultdict(list)
    for message in payload.get("messages", []):
        day = local_day(message.get("date"), tz)
        if not selected_date or day == selected_date:
            grouped[day].append(message)

    title = channel.get("title") or channel.get("username") or "알 수 없는 대화방"
    total = sum(len(items) for items in grouped.values())
    lines = [
        f"# Telegram 자동 분석 초벌 자료: {title}", "",
        f"- 분석 기간: {selected_date or (f'{min(grouped)} ~ {max(grouped)}' if grouped else '해당 메시지 없음')}",
        f"- 기준 시간대: `{tz_name}`", f"- 분석 메시지: {total}개", "",
        "> 이 파일은 키워드·빈도 기반 초벌 자료입니다. 대화 맥락을 검토한 최종 보고서가 아니며, 아래 후보를 중요 사건이나 위법행위로 단정할 수 없습니다.", "",
    ]

    if not grouped:
        lines.extend(["## 결과", "", "조건에 맞는 메시지가 없습니다."])

    for day in sorted(grouped):
        messages = grouped[day]
        senders = Counter((m.get("sender_name") or m.get("sender_username") or str(m.get("sender_id") or "알 수 없음")) for m in messages)
        domains = Counter()
        for message in messages:
            for url in URL_PATTERN.findall(message.get("text") or ""):
                domain = urlparse(url.rstrip(".,!?;:")).netloc.lower().removeprefix("www.")
                if domain:
                    domains[domain] += 1
        day_keywords = keywords(messages, top)
        ranked = sorted(messages, key=lambda m: ((m.get("reply_count") or 0), (m.get("forwards") or 0), (m.get("views") or 0)), reverse=True)
        hits = signal_hits(messages)

        lines.extend([f"## {day}", "", "### 한눈에 보기", "",
                      f"- 메시지 {len(messages)}개 · 참여자 {len(senders)}명 · 미디어 {sum(bool(m.get('has_media')) for m in messages)}개",
                      f"- 주요 화자: {', '.join(f'{name}({count})' for name, count in senders.most_common(5)) or '없음'}",
                      f"- 주로 언급된 말: {', '.join(f'`{word}`({count})' for word, count in day_keywords) or '추출할 단어 없음'}",
                      f"- 공유 도메인: {', '.join(f'`{domain}`({count})' for domain, count in domains.most_common(5)) or '없음'}", "",
                      "### 대화 흐름을 대표하는 메시지", ""])
        for message in ranked[:top]:
            who = message.get("sender_name") or message.get("sender_username") or message.get("sender_id") or "알 수 없음"
            link = message_link(channel, message.get("id"))
            ref = f"[ID {message.get('id')}]({link})" if link else f"ID `{message.get('id')}`"
            lines.append(f"- {ref} · {who} · 답글 {message.get('reply_count') or 0}: {preview(message)}")

        lines.extend(["", "### 키워드 검토 후보 (자동 선별)", ""])
        if not hits:
            lines.append("- 현재 자동 규칙에서 선별된 후보가 없습니다. 이것이 실제 검토 대상이 없다는 의미는 아닙니다.")
        else:
            for label, items in hits.items():
                lines.append(f"#### {label} ({len(items)}건)")
                lines.append("")
                for message, matched in items[:top]:
                    link = message_link(channel, message.get("id"))
                    ref = f"[ID {message.get('id')}]({link})" if link else f"ID `{message.get('id')}`"
                    lines.append(f"- {ref} · 탐지어: {', '.join(f'`{term}`' for term in matched)} · {preview(message)}")
                lines.append("")
        lines.extend([f"### {day} 대화 내용 요약", ""])
        lines.extend(f"- {note}" for note in daily_summary(day, messages, day_keywords, hits))
        lines.append("")

    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"분석 보고서 저장 위치: {output_path}")


if __name__ == "__main__":
    args = parse_args()
    analyze(args.input, args.output, args.top, args.date, args.timezone)
