import argparse
import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = BASE_DIR / "output" / "channel_messages.json"
DEFAULT_OUTPUT = BASE_DIR / "output" / "channel_report.md"
KST = timezone(timedelta(hours=9))

# 다크웹 DB팀 공통 규칙: 아래 필드는 자동 분석 결과로 확정하지 않는다.
MANUAL_FIELDS = frozenset({
    "DB 반영",
    "담당자",
    "국가",
    "웹에 올림",
    "유통 자리",
    "이전 이름·별칭",
    "연결된 곳",
})

URL_RE = re.compile(r"(?i)\b(?:https?://|hxxps?://|www\.)[^\s<>\"'\]\[()]+")
DOMAIN_RE = re.compile(
    r"(?i)\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"(?:com|net|org|io|co|ru|su|st|cc|me|info|biz|xyz|top|site|online|kr|onion|gov)\b"
)
HANDLE_RE = re.compile(r"(?<![\w.])@[A-Za-z0-9_]{4,}")
PRICE_RE = re.compile(
    r"(?i)(?:[$€£]\s?\d+(?:[.,]\d+)?|\d+(?:[.,]\d+)?\s?[$€£]|"
    r"\d+(?:[.,]\d+)?\s?(?:usd|eur|euro|usdt|btc|xmr)(?![a-z]))"
)

KOREA_TERMS = {
    "한국", "대한민국", "국내", "한국인", "서울", "부산", "인천", "대구",
    "south korea", "south korean", "republic of korea", "seoul", "busan",
}

MESSAGE_TYPE_RULES = (
    ("활성 악용 취약점", ("new actively exploited vulnerability",)),
    ("취약점(CVE)", ("new high-severity cve published",)),
    ("랜섬웨어 피해 주장", ("new ransomware victim",)),
    ("유출 탐지", ("leak detected",)),
    ("악성코드 샘플", ("new malware sample detected",)),
    ("보안 권고·공개", ("security advisory / disclosure",)),
    ("위협 인텔리전스 뉴스", ("threat intelligence news",)),
    ("위협 인텔리전스", ("new threat intelligence pulse",)),
    ("보안 뉴스", ("security news alert",)),
    ("공개 익스플로잇", ("new public exploit released",)),
)

CATEGORY_TERMS = {
    "개인정보·DB 관련": {
        "leak", "leaked", "breach", "breached", "database", "database dump",
        "data leak", "data of", "data sale", "selling-data", "private archive", "db", "유출",
        "개인정보", "데이터베이스", "고객정보",
    },
    "판매·거래": {
        "sell", "selling", "sale", "buyer", "buy", "price", "deal",
        "advertisement", "advertisements", "pricing", "lifetime", "contact now",
        "dm me", "판매", "구매", "가격", "거래",
    },
    "무료 공개·공유": {
        "free download", "free leak", "free database", "released for free",
        "download", "shared", "sharing", "무료 공개", "무료 배포", "공유", "배포",
    },
    "샘플·증거 주장": {
        "sample", "proof", "preview", "샘플", "증거", "미리보기",
    },
    "계정·인증정보": {
        "credential", "credentials", "combo", "password", "login", "account",
        "계정", "비밀번호", "로그인", "인증정보",
    },
    "결제·암호화폐": {
        "bitcoin", "btc", "usdt", "crypto", "monero", "xmr", "wallet",
        "암호화폐", "비트코인", "지갑", "결제",
    },
    "에스크로·보증": {
        "escrow", "middleman", "guarantor", "mm", "에스크로", "보증", "중개",
    },
    "랜섬웨어": {
        "ransomware", "ransom", "dls", "raas", "랜섬웨어", "몸값",
    },
    "포럼·외부 채널 연결": {
        "forum", "forums", "telegram", "channel", "mirror", "onion",
        "포럼", "채널", "미러", "다크웹",
    },
    "운영 공지": {
        "announcement", "maintenance", "downtime", "update", "domain change",
        "registration", "registrations", "reopened", "offline", "online",
        "working now", "disabled", "new channel", "join our", "support", "backup",
        "shoutbox", "공지", "점검", "업데이트",
        "도메인 변경", "서버", "가입", "재개", "백업", "지원",
    },
}

FALLBACK_MESSAGE_TYPES = (
    ("판매·거래", "판매·거래 게시물"),
    ("개인정보·DB 관련", "개인정보·DB 언급"),
    ("무료 공개·공유", "자료 공개·공유"),
    ("랜섬웨어", "랜섬웨어 관련"),
    ("운영 공지", "운영 공지"),
    ("포럼·외부 채널 연결", "포럼·외부 채널 안내"),
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Telegram 채널 JSON을 기존 WHS DB 양식의 단일 보고서로 변환합니다."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument(
        "--output", "--report", dest="output", type=Path, default=DEFAULT_OUTPUT,
        help="통합 채널 보고서 출력 경로",
    )
    parser.add_argument(
        "--assignee",
        default="미입력",
        help="이전 명령과의 호환용. 담당자 칸은 자동 확정 금지 규칙에 따라 입력하지 않음",
    )
    return parser.parse_args()


def load_payload(path):
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"입력 JSON 파일이 없습니다: {resolved}")
    payload = json.loads(resolved.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("입력 JSON의 최상위 구조는 객체여야 합니다.")
    messages = payload.get("messages") or []
    if not isinstance(messages, list):
        raise ValueError("JSON의 messages 항목은 배열이어야 합니다.")
    return payload, payload.get("channel") or {}, messages


def as_text(value):
    return "" if value is None else str(value)


def safe_int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def parse_datetime(value):
    raw = as_text(value).strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def display_datetime(value):
    parsed = parse_datetime(value)
    return parsed.isoformat(timespec="seconds") if parsed else (as_text(value).strip() or "미확인")


def display_date(value):
    parsed = parse_datetime(value)
    if parsed:
        return parsed.date().isoformat()
    raw = as_text(value).strip()
    return raw.split("T", 1)[0] if raw else "미확인"


def display_kst(value, date_only=False):
    parsed = parse_datetime(value)
    if not parsed:
        return as_text(value).strip() or "미확인"
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    converted = parsed.astimezone(KST)
    return converted.strftime("%Y.%m.%d" if date_only else "%Y.%m.%d %H:%M (KST)")


def contains_term(lowered_text, term):
    lowered_term = term.lower()
    if re.fullmatch(r"[a-z0-9 ]+", lowered_term):
        return re.search(
            rf"(?<![a-z0-9]){re.escape(lowered_term)}(?![a-z0-9])",
            lowered_text,
        ) is not None
    return lowered_term in lowered_text


def extract_urls(body):
    return [match.rstrip(".,;:!?") for match in URL_RE.findall(body)]


def extract_domains(body, urls):
    domains = {
        domain.lower().removeprefix("www.")
        for domain in DOMAIN_RE.findall(body)
    }
    for raw_url in urls:
        normalized = raw_url.replace("hxxps://", "https://").replace("hxxp://", "http://")
        if normalized.startswith("www."):
            normalized = "https://" + normalized
        hostname = urlparse(normalized).hostname
        if hostname:
            domains.add(hostname.lower().removeprefix("www."))
    return sorted(domains)


def extract_handles(body):
    return sorted(set(HANDLE_RE.findall(body)), key=str.lower)


def classify(body):
    lowered = body.lower()
    return [
        category for category, terms in CATEGORY_TERMS.items()
        if any(contains_term(lowered, term) for term in terms)
    ]


def detect_message_type(body, keyword_categories=None):
    lowered = body.lower()
    for message_type, markers in MESSAGE_TYPE_RULES:
        if any(marker in lowered for marker in markers):
            return message_type
    category_set = set(keyword_categories or ())
    for category, message_type in FALLBACK_MESSAGE_TYPES:
        if category in category_set:
            return message_type
    return "기타·미분류"


def is_korea_related(body, domains):
    lowered = body.lower()
    return any(contains_term(lowered, term) for term in KOREA_TERMS) or any(
        domain.endswith(".kr") for domain in domains
    )


def sender_label(message):
    return (
        as_text(message.get("post_author")).strip()
        or as_text(message.get("sender_username")).strip()
        or as_text(message.get("sender_display_name")).strip()
        or as_text(message.get("sender_id")).strip()
        or "미확인"
    )


def infer_language(messages):
    sample = " ".join(as_text(message.get("text")) for message in messages)
    counts = {
        "한국어": len(re.findall(r"[가-힣]", sample)),
        "러시아어": len(re.findall(r"[А-Яа-яЁё]", sample)),
        "영어": len(re.findall(r"[A-Za-z]", sample)),
    }
    total = sum(counts.values())
    if total == 0:
        return "미확인"
    shares = sorted(
        ((name, count / total) for name, count in counts.items()),
        key=lambda item: item[1], reverse=True,
    )
    if shares[0][1] >= 0.75:
        return shares[0][0]
    present = [name for name, share in shares if share >= 0.1]
    return "·".join(present) + " 혼합" if present else shares[0][0]


def analyze(messages):
    rows = []
    counters = {name: Counter() for name in (
        "types", "categories", "domains", "handles", "senders", "dates", "prices"
    )}
    for message in messages:
        if not isinstance(message, dict):
            continue
        body = as_text(message.get("text"))
        service_action = as_text(message.get("service_action")).strip()
        urls = extract_urls(body)
        domains = extract_domains(body, urls)
        handles = extract_handles(body)
        keyword_categories = classify(body)
        message_type = "서비스 메시지" if service_action else detect_message_type(body, keyword_categories)
        categories = [message_type]
        if message_type == "유출 탐지":
            categories.extend(
                category for category in keyword_categories
                if category not in {"개인정보·DB 관련", "랜섬웨어"}
            )
        elif message_type == "보안 뉴스" and "랜섬웨어" in keyword_categories:
            categories.append("랜섬웨어")
        else:
            categories.extend(
                category for category in keyword_categories
                if category not in categories
            )
        # 판매글의 '지원', '업데이트', '무료 업그레이드' 같은 혜택 문구는
        # 운영 공지나 무료 배포로 별도 분류하지 않는다.
        if message_type == "판매·거래 게시물":
            categories = [
                category for category in categories
                if category not in {"운영 공지", "무료 공개·공유"}
            ]
        prices = [item.strip() for item in PRICE_RE.findall(body)] if "판매·거래" in categories else []
        sender = sender_label(message)
        day = display_date(message.get("date"))
        # 채널 생성·고정 같은 Telegram 서비스 이벤트는 원본에는 보존하지만,
        # 게시물 유형·활동 간격·링크 비율 통계에서는 제외한다.
        if not service_action:
            counters["types"].update([message_type])
            counters["categories"].update(categories)
            counters["domains"].update(domains)
            counters["handles"].update(handle.lower() for handle in handles)
            counters["senders"].update([sender])
            counters["dates"].update([day])
            counters["prices"].update(prices)
        rows.append({
            "id": message.get("id", "미확인"),
            "date": display_datetime(message.get("date")),
            "day": day,
            "views": safe_int(message.get("views")),
            "forwards": safe_int(message.get("forwards")),
            "replies": safe_int(message.get("reply_count")),
            "reactions": safe_int(message.get("reaction_count")),
            "has_media": bool(message.get("has_media")),
            "url_count": len(urls),
            "domains": domains,
            "handles": handles,
            "categories": categories,
            "message_type": message_type,
            "sender": sender,
            "message_url": as_text(message.get("message_url")).strip(),
            "is_forwarded": bool(message.get("is_forwarded")),
            "via_bot_id": message.get("via_bot_id"),
            "service_action": service_action or None,
            "korea_related": is_korea_related(body, domains),
        })
    return rows, counters


def md(value):
    return as_text(value).replace("|", "\\|").replace("\n", " ").strip()


def joined_top(counter, limit=5):
    return ", ".join(f"{name}({count}회)" for name, count in counter.most_common(limit)) or "미확인"


def normalized_price(value):
    raw = as_text(value).strip()
    match = re.fullmatch(r"(\d+(?:[.,]\d+)?)\s*([$€£])", raw)
    if match:
        amount = match.group(1)
        if amount.isdigit():
            amount = f"{int(amount):,}"
        return f"{match.group(2)}{amount}"
    match = re.fullmatch(r"([$€£])\s*(\d+)", raw)
    if match:
        return f"{match.group(1)}{int(match.group(2)):,}"
    return raw


def joined_prices(counter, limit=5):
    normalized = Counter()
    for value, count in counter.items():
        normalized[normalized_price(value)] += count
    return joined_top(normalized, limit)


def top_bullets(counter, limit=15):
    return [f"- `{md(name)}`: {count}회" for name, count in counter.most_common(limit)] or ["- 확인된 항목 없음"]


def manual_value(reason="사람 확인 후 입력"):
    return f"자동 입력 안 함 - {reason}"


def validate_manual_fields(summary):
    values = dict(summary)
    missing = MANUAL_FIELDS.difference(values)
    if missing:
        raise ValueError(f"자동 확정 금지 필드 누락: {', '.join(sorted(missing))}")
    invalid = [
        field for field in MANUAL_FIELDS
        if not as_text(values[field]).startswith("자동 입력 안 함")
    ]
    if invalid:
        raise ValueError(f"자동 확정 금지 필드에 값이 입력됨: {', '.join(sorted(invalid))}")


def activity_summary(rows):
    dates = [parse_datetime(row["date"]) for row in rows]
    dates = [item for item in dates if item]
    if not dates:
        return {"first": "미확인", "last": "미확인", "duration": "미확인", "days": 0, "interval": "미확인", "interval_text": "미확인", "per_day": "미확인"}
    first, last = min(dates), max(dates)
    span = max((last.date() - first.date()).days + 1, 1)
    active_days = len({item.date() for item in dates})
    elapsed_seconds = max((last - first).total_seconds(), 0)
    interval_minutes = elapsed_seconds / (len(dates) - 1) / 60 if len(dates) > 1 else None
    observed_days = elapsed_seconds / 86400
    duration_days, remainder = divmod(int(elapsed_seconds), 86400)
    duration_hours, remainder = divmod(remainder, 3600)
    duration_minutes = remainder // 60
    duration_parts = []
    if duration_days:
        duration_parts.append(f"{duration_days}일")
    if duration_hours:
        duration_parts.append(f"{duration_hours}시간")
    if duration_minutes or not duration_parts:
        duration_parts.append(f"{duration_minutes}분")
    rounded_interval = round(interval_minutes, 1) if interval_minutes is not None else "미확인"
    return {
        "first": first.isoformat(timespec="seconds"),
        "last": last.isoformat(timespec="seconds"),
        "duration": " ".join(duration_parts),
        "days": active_days,
        "interval": rounded_interval,
        "interval_text": readable_interval(rounded_interval),
        "per_day": round(len(dates) / observed_days, 1) if observed_days > 0 else "미확인",
    }


def readable_interval(minutes):
    if not isinstance(minutes, (int, float)):
        return "미확인"
    total_minutes = max(int(round(minutes)), 0)
    days, remainder = divmod(total_minutes, 1440)
    hours, mins = divmod(remainder, 60)
    parts = []
    if days:
        parts.append(f"{days}일")
    if hours:
        parts.append(f"{hours}시간")
    if mins or not parts:
        parts.append(f"{mins}분")
    return " ".join(parts)


def candidate_table(rows, limit=25):
    if not rows:
        return ["- 자동 탐지된 후보 없음"]
    lines = [
        "| 메시지 ID | 날짜 | 게시자 | 조회·반응 | 자동 분류 | 연결 정보 |",
        "|---:|---|---|---:|---|---|",
    ]
    for row in rows[:limit]:
        message_id = md(row["id"])
        if row["message_url"]:
            message_id = f"[{message_id}]({row['message_url']})"
        display_categories = list(row["categories"])
        duplicate_category = {
            "판매·거래 게시물": "판매·거래",
            "개인정보·DB 언급": "개인정보·DB 관련",
            "자료 공개·공유": "무료 공개·공유",
            "랜섬웨어 관련": "랜섬웨어",
            "포럼·외부 채널 안내": "포럼·외부 채널 연결",
        }.get(row["message_type"])
        if duplicate_category:
            display_categories = [
                category for category in display_categories
                if category != duplicate_category
            ]
        categories = ", ".join(display_categories) or "기타·미분류"
        connections = ", ".join(row["handles"] + row["domains"]) or "-"
        lines.append(
            f"| {message_id} | {md(row['day'])} | {md(row['sender'])} | "
            f"{row['views'] + row['reactions']} | {md(categories)} | {md(connections)} |"
        )
    return lines


def capture_plan_table(channel_url, rows, korea_rows, trade_rows, leak_rows, forum_domains, top_type):
    """보고서에 첨부할 권장 화면을 선정하되 원문·개인정보는 복사하지 않는다."""
    lines = [
        "| 우선순위 | 캡처 대상 | 메시지·주소 | 선정 이유 | 화면에 포함할 내용 |",
        "|---|---|---|---|---|",
    ]
    channel_reference = (
        f"[채널 열기]({channel_url})" if channel_url != "미확인" else "공개 주소 미확인"
    )
    lines.append(
        f"| 필수 | 채널 기본정보 | {channel_reference} | 채널 식별과 현재 상태 확인 | "
        "채널명, username, 구독자 수, 소개문, 캡처일 |"
    )
    selected_ids = set()

    def add_candidates(candidates, priority, label, reason, visible_items, limit):
        added = 0
        for row in candidates:
            message_id = as_text(row["id"])
            if message_id in selected_ids:
                continue
            selected_ids.add(message_id)
            reference = md(row["id"])
            if row["message_url"]:
                reference = f"[메시지 {reference}]({row['message_url']})"
            else:
                reference = f"메시지 {reference}"
            media_note = " 이미지·파일 표시," if row["has_media"] else ""
            lines.append(
                f"| {priority} | {label} | {reference} | {reason} | "
                f"채널명, 메시지 날짜, 게시자,{media_note} {visible_items} |"
            )
            added += 1
            if added >= limit:
                break

    add_candidates(
        korea_rows,
        "필수",
        "한국 관련 후보",
        "국내 기업·기관 관련 여부와 주장을 검증하기 위한 대표 근거",
        "대상명, 주장 문구, 조회·반응 수",
        3,
    )
    add_candidates(
        sorted(trade_rows, key=lambda row: row["views"] + row["reactions"], reverse=True),
        "권장",
        "판매·거래 후보",
        "판매 방식과 유통 위치를 판단하기 위한 대표 사례",
        "판매 표현, 가격·연락 방식, 출처 링크",
        1,
    )
    add_candidates(
        sorted(leak_rows, key=lambda row: row["views"] + row["reactions"], reverse=True),
        "권장",
        "개인정보·DB 관련 후보",
        "데이터 관련 주장과 출처를 확인하기 위한 대표 사례",
        "데이터 종류, 판매·공개 주장, 출처",
        2,
    )
    forum_set = set(forum_domains)
    forum_rows = [row for row in rows if forum_set.intersection(row["domains"])]
    add_candidates(
        forum_rows,
        "권장",
        "포럼 연결 후보",
        "Telegram과 외부 포럼의 연결 여부를 검토하기 위한 근거",
        "외부 도메인과 링크가 언급된 부분",
        1,
    )
    return lines


def count_with_share(counter, total, limit=5):
    if not counter or total == 0:
        return "확인된 유형 없음"
    return ", ".join(
        f"{name} {count}개({count / total * 100:.1f}%)"
        for name, count in counter.most_common(limit)
    )


def readable_duration(activity):
    if activity["duration"] == "미확인":
        return "분석 기간을 계산하지 못했다"
    return f"{activity['duration']} 동안"


def likely_forum_domains(counter):
    return Counter({
        domain: count for domain, count in counter.items()
        if (
            "forum" in domain.lower()
            or "breach" in domain.lower()
            or "darkforum" in domain.lower()
            or domain.lower().startswith("pwnforum")
            or domain.lower() == "spear.cx"
        )
    })


def build_report(payload, channel, messages, rows, counters, assignee):
    raw_total = len(rows)
    content_rows = [row for row in rows if not row["service_action"]]
    service_rows = [row for row in rows if row["service_action"]]
    total = len(content_rows)
    collected_at = display_datetime(payload.get("collected_at"))
    confirmed_date = display_kst(payload.get("collected_at"), date_only=True)
    activity = activity_summary(content_rows)
    content_ids = {as_text(row["id"]) for row in content_rows}
    content_messages = [
        message for message in messages
        if as_text(message.get("id")) in content_ids
    ]
    language = infer_language(content_messages)
    participants = channel.get("participants_count") or "미확인"
    channel_url = channel.get("url") or (
        f"https://t.me/{channel['username']}" if channel.get("username") else "미확인"
    )
    channel_type_phrase = {"channel": "공지형 채널로", "supergroup": "슈퍼그룹으로", "group": "그룹으로"}.get(
        channel.get("channel_type"), "유형을 확인하지 못한 채널로"
    )
    public = bool(channel.get("is_public") or channel.get("username"))
    access = "공개 주소로 접근 가능하며, 별도 초대 링크는 필요하지 않음" if public else "초대·가입 조건 추가 확인 필요"
    status = f"접근 가능 ({confirmed_date}, Telegram API)"

    leak_rows = [row for row in content_rows if "개인정보·DB 관련" in row["categories"]]
    trade_rows = [row for row in content_rows if "판매·거래" in row["categories"]]
    payment_rows = [row for row in content_rows if "결제·암호화폐" in row["categories"]]
    escrow_rows = [row for row in content_rows if "에스크로·보증" in row["categories"]]
    korea_rows = [row for row in content_rows if row["korea_related"]]
    korea_leak_rows = [row for row in leak_rows if row["korea_related"]]
    forwarded_rows = [row for row in content_rows if row["is_forwarded"]]
    media_count = sum(row["has_media"] for row in content_rows)
    external_count = sum(row["url_count"] > 0 for row in content_rows)
    external_ratio = external_count / total if total else 0
    known_type_ratio = 1 - counters["types"].get("기타·미분류", 0) / total if total else 0
    top_types = count_with_share(counters["types"], total, 5)
    top_type, top_type_count = counters["types"].most_common(1)[0] if counters["types"] else ("미확인", 0)
    senders = counters["senders"]
    top_sender, top_sender_count = senders.most_common(1)[0] if senders else ("미확인", 0)
    forum_domains = likely_forum_domains(counters["domains"])

    about = as_text(channel.get("about")).strip()
    about_domains = extract_domains(about, extract_urls(about))
    official_domains = [
        domain for domain in about_domains
        if domain not in {"t.me", "telegram.me"}
    ]
    connected_parts = []
    if official_domains:
        connected_parts.append(f"공식·자체 사이트 후보: {', '.join(official_domains)}")
    if channel.get("linked_chat_id"):
        connected_parts.append(f"연결 채팅 ID: {channel['linked_chat_id']}")
    connected = "; ".join(connected_parts) or "운영상 연결 관계 미확인"

    trade_ratio = len(trade_rows) / max(total, 1)
    if top_type == "취약점(CVE)" and top_type_count / max(total, 1) >= 0.5:
        role = "소프트웨어 취약점과 사이버 위협 소식을 모아 전달하는 위협정보 알림 채널"
    elif trade_ratio >= 0.5 and forum_domains:
        role = "DarkForums 포럼의 공지와 데이터·서비스 판매 홍보를 전달하는 채널"
    elif trade_ratio >= 0.5:
        role = "데이터·서비스 판매 홍보를 중심으로 게시하는 채널"
    elif top_type in {"운영 공지", "포럼·외부 채널 안내"} or forum_domains:
        role = "포럼 운영 공지와 공식·연결 주소를 전달하는 안내 채널"
    elif len(leak_rows) / max(total, 1) >= 0.3:
        role = "유출 주장과 관련 게시물을 중심으로 전달하는 정보 채널"
    else:
        role = "여러 유형의 사이버 위협 정보를 전달하는 채널"

    feed_like = total >= 20 and known_type_ratio >= 0.7 and external_ratio >= 0.5
    automation_note = (
        "반복되는 형식과 높은 게시 빈도로 볼 때 자동 수집·게시 가능성 있음"
        if feed_like else
        "게시 방식이 자동화되어 있는지는 추가 확인 필요"
    )
    if trade_ratio >= 0.5 and forum_domains:
        distribution_position = "DarkForums 공지·판매 홍보 및 문의 연결 창구로 추정"
    elif total >= 20 and external_ratio >= 0.5:
        distribution_position = "외부 출처 정보를 텔레그램으로 재전달하는 집계·알림 채널로 추정"
    else:
        distribution_position = "최초 게시·홍보·재유통 여부 추가 확인 필요"

    channel_name = channel.get("title") or channel.get("username") or "이 채널"
    overview_short = f"‘{channel_name}’은 {role}이다."
    overview_detail = f"수집된 실제 게시물은 {total}개이며, 유형별로는 {top_types}가 확인됐다. "
    if trade_ratio >= 0.3:
        overview_detail += "가격과 연락처가 반복적으로 등장해 판매 홍보 성격이 뚜렷하지만, 실제 거래 여부는 별도 확인이 필요하다."
    elif top_type == "취약점(CVE)" and top_type_count / max(total, 1) >= 0.5:
        overview_detail += "취약점과 위협정보 관련 게시물의 비중이 높아 정보 알림 기능이 중심인 것으로 보인다."
    elif external_ratio >= 0.5:
        overview_detail += "외부 출처 링크가 자주 포함돼 정보 전달과 재공유 기능이 중심인 것으로 보인다."
    else:
        overview_detail += "현재 표본만으로 채널의 전체 운영 성격을 확정하기는 어려워 추가 확인이 필요하다."
    leak_summary = (
        f"개인정보·DB 관련 주장 후보 {len(leak_rows)}건 ({confirmed_date}, 실제 게시물 {total}건 기준) — 확정 필요"
        if leak_rows else f"후보 없음 ({confirmed_date}, 메시지 {total}건 표본 기준)"
    )
    summary = [
        ("DB 반영", manual_value("사람 검토 후 입력")),
        ("가입 필요", f"없음 ({confirmed_date}, 공개 username 확인, Telegram API)" if public else f"확인하지 못함 - 공개 접근 여부를 API 정보만으로 확정할 수 없음 ({confirmed_date})"),
        ("개인정보 유출", leak_summary),
        ("국가", manual_value()),
        ("규모", f"구독자·참가자 {participants}명 ({confirmed_date}, Telegram API)" if participants != "미확인" else f"확인하지 못함 - Telegram API에서 참가자 수를 제공하지 않음 ({confirmed_date})"),
        ("담당자", manual_value("사람 입력")),
        ("들어가는 법", f"{access} ({confirmed_date}, Telegram API)"),
        ("비고", f"자동 수집 초안. 원본 {raw_total}건 중 서비스 메시지 {len(service_rows)}건을 제외한 실제 게시물 {total}건 기준"),
        ("사용 언어", f"{language} ({confirmed_date}, 메시지 {total}건 자동 감지)"),
        ("상태", status),
        ("어떤 곳인지", f"{overview_short} ({confirmed_date}, 실제 게시물 {total}건 자동 분석)"),
        ("연결된 곳", manual_value("발견 후보는 본문에서 사람 검토")),
        ("웹에 올림", manual_value()),
        ("유통 자리", manual_value("본문의 자동 분석 후보를 검토한 뒤 입력")),
        ("이전 이름·별칭", manual_value()),
        ("일부러 반출하지 않음", manual_value()),
        ("주소", f"{channel_url} ({confirmed_date}, Telegram API)" if channel_url != "미확인" else f"확인하지 못함 - 공개 주소 없음 ({confirmed_date})"),
        ("출처", f"{channel_url} ({confirmed_date}, Telegram API)" if channel_url != "미확인" else "확인하지 못함 - 출처 주소 없음"),
        ("확인일", confirmed_date),
    ]
    validate_manual_fields(summary)

    if total:
        activity_text = (
            f"서비스 알림을 제외한 실제 게시물 {total}개는 {display_kst(activity['first'])}부터 {display_kst(activity['last'])}까지 "
            f"{readable_duration(activity)} 게시됐다. 이 구간에서는 하루 평균 약 {activity['per_day']}개, "
            f"평균 약 {activity['interval_text']} 간격으로 새 글이 올라왔다."
        )
    else:
        activity_text = "수집된 메시지가 없어 게시 빈도와 활동 시점을 판단할 수 없다."

    if trade_rows:
        if counters["prices"]:
            price_sentence = f"공개된 가격 표현은 {joined_prices(counters['prices'], 5)}였으며,"
        else:
            price_sentence = "구체적인 가격 표현은 확인되지 않았으며,"
        trade_text = (
            f"판매·거래 표현이 포함된 게시물은 {len(trade_rows)}개로 확인됐다. "
            f"{price_sentence} 결제수단 관련 표현은 {len(payment_rows)}개였고, "
            f"에스크로·중개 관련 표현은 {len(escrow_rows)}개였다. "
        )
        if trade_ratio >= 0.3:
            trade_text += (
                "가격과 연락처가 반복되는 점을 볼 때, 이 채널은 판매 홍보와 문의 연결 창구로 활용되는 것으로 보인다. "
                "다만 실제 거래 성사 여부와 판매 주체의 신원은 추가 확인이 필요하다."
            )
        else:
            trade_text += (
                f"전체 게시물에서 차지하는 비중은 {trade_ratio * 100:.1f}%로 낮아, "
                "해당 표현만으로 채널의 주된 성격을 거래 중심이라고 보기는 어렵다."
            )
    else:
        trade_text = "수집 범위에서는 판매·거래로 분류할 만한 게시물이 확인되지 않았다. 채널 자체의 거래 기능과 결제 방식도 확인되지 않았다."
    if leak_rows:
        privacy_text = (
            f"개인정보·DB 관련 표현이 포함된 게시물은 {len(leak_rows)}개로, 전체의 {len(leak_rows) / max(total, 1) * 100:.1f}%를 차지했다. "
            "게시물에서 데이터 종류와 유출·판매 관련 주장은 확인됐으나, 실제 유출 여부와 데이터의 진위는 추가 검증이 필요하다. "
            f"한국 관련 게시물은 {len(korea_rows)}개였으며, 이 중 개인정보·DB 관련 후보는 {len(korea_leak_rows)}개였다."
        )
    else:
        privacy_text = (
            "수집 범위에서는 개인정보·DB 관련 주장 게시물이 확인되지 않았다. "
            f"한국 관련 게시물은 {len(korea_rows)}개 확인됐지만, 개인정보 유출 주장인지는 별도 검증이 필요하다."
        )
    distribution_text = (
        f"전체 게시물 중 외부 링크가 포함된 비율은 {external_ratio * 100:.1f}%이며, Telegram의 공식 포워딩 표시가 있는 글은 {len(forwarded_rows)}개다. "
        "외부 사이트의 내용을 정형화해 다시 전달하는 패턴이 많아, 이 채널은 정보를 처음 공개하는 장소라기보다 여러 출처의 정보를 모아 알리는 재전달·집계 채널에 가까운 것으로 보인다. "
        "개별 유출 건의 최초 게시처는 링크된 포럼과 게시 시각을 비교해 별도로 판단해야 한다."
        if total >= 20 and external_ratio >= 0.5 else
        "외부 링크와 포워딩 정보만으로는 이 채널이 최초 게시처인지 재유통 채널인지 판단하기 어렵다. 개별 게시물의 출처와 게시 시각을 비교해야 한다."
    )
    connection_text = (
        (f"채널 소개에는 {', '.join(official_domains)} 도메인이 기재돼 있어 공식·자체 사이트 후보로 볼 수 있다. " if official_domains else "채널 소개에서는 공식 사이트를 확인하지 못했다. ")
        + "확인된 외부 도메인과 Telegram 핸들은 아래 표에 정리했다. "
        + "다만 링크가 언급됐다는 사실만으로 제휴 관계나 동일 운영 주체라고 단정하기는 어렵다."
    )
    creation_events = [
        row for row in rows if row["service_action"] == "MessageActionChannelCreate"
    ]
    creation_event = min(
        (parse_datetime(row["date"]) for row in creation_events if parse_datetime(row["date"])),
        default=None,
    )
    created_raw = parse_datetime(channel.get("created_at"))
    first_message_raw = parse_datetime(activity["first"])
    created_is_consistent = bool(
        created_raw and (not first_message_raw or created_raw <= first_message_raw)
    )
    status_text = (
        f"{confirmed_date} 확인 당시 API를 통해 정상 접근됐고, 마지막으로 확인된 게시물 시각은 {display_kst(activity['last'])}다. "
        "주소 변경, 폐쇄, 병합 또는 다른 채널로의 이전 정황은 자동 수집 결과에서 확인되지 않았다. "
        "이후 상태가 바뀌면 기존 주소와 새 주소의 공지·운영자·게시 이력을 비교해야 한다."
    )
    type_table = [
        "| 게시물 유형 | 건수 | 비중 |",
        "|---|---:|---:|",
        *[
            f"| {md(name)} | {count}개 | {count / max(total, 1) * 100:.1f}% |"
            for name, count in counters["types"].most_common(7)
        ],
    ]
    activity_note = (
        "짧은 시간에 게시물이 매우 많이 올라오는 고빈도 채널이다."
        if total >= 20 and activity["interval"] != "미확인" and activity["interval"] <= 30
        else "수집 범위만으로 장기적인 게시 주기를 확정하기는 어렵다."
    )
    official_text = ", ".join(official_domains) if official_domains else "미확인"
    forum_text = joined_top(forum_domains, 8) if forum_domains else "미확인"
    price_text = (
        joined_prices(counters["prices"], 5)
        if counters["prices"]
        else f"후보 없음 ({confirmed_date}, 메시지 {total}건 자동 탐지)"
    )
    handle_text = (
        joined_top(counters["handles"], 5)
        if counters["handles"]
        else f"후보 없음 ({confirmed_date}, 메시지 {total}건 자동 추출)"
    )
    if creation_event:
        created_at_text = f"{display_kst(creation_event.isoformat())} (Telegram 채널 생성 서비스 기록)"
    elif created_is_consistent:
        created_at_text = display_kst(channel.get("created_at"))
    else:
        created_at_text = "확인하지 못함 - API 메타데이터 날짜가 첫 게시물보다 늦어 생성 시점으로 사용하지 않음"

    about_categories = classify(about) if about else []
    backup_declared = bool(re.search(r"\bbackup\s*:", about, re.IGNORECASE))
    backup_part = re.split(r"\bbackup\s*:", about, maxsplit=1, flags=re.IGNORECASE)[-1] if backup_declared else ""
    backup_has_url = bool(extract_urls(backup_part)) if backup_declared else False
    if "포럼" in role or top_type in {"운영 공지", "포럼·외부 채널 안내"}:
        if backup_declared and not backup_has_url:
            about_explanation = "채널 소개문은 포럼 공지 채널임을 밝히고 관련 채팅 주소를 안내한다. 백업 항목은 있으나 주소는 확인되지 않았다."
        else:
            about_explanation = "채널 소개문은 포럼 공지 채널임을 밝히고 관련 채팅·백업 주소를 안내한다."
    elif top_type == "취약점(CVE)" and top_type_count / max(total, 1) >= 0.5:
        about_explanation = "채널 소개문은 다루는 위협정보 범위와 공식 사이트·연락처를 안내한다."
    elif official_domains:
        about_explanation = "채널 소개문은 채널의 목적과 공식·자체 사이트 후보를 안내한다."
    elif about:
        about_explanation = "채널 소개문에는 채널의 목적과 연결 주소가 기재돼 있다."
    else:
        about_explanation = "채널 소개문은 확인되지 않았다."
    capture_plan = capture_plan_table(
        channel_url,
        content_rows,
        korea_rows,
        trade_rows,
        leak_rows,
        forum_domains,
        top_type,
    )

    report = [
        f"# {channel.get('title') or channel.get('username') or '미확인 채널'} 조사 결과 (자동 수집 초안 — 검토 필요)",
        "", "## DB 요약", "", "| 항목 | 내용 |", "|---|---|",
        *[f"| {md(key)} | {md(value)} |" for key, value in summary],
        "", "## 어떤 곳인가", "", overview_short, "", overview_detail,
        "", "### 핵심 특징", "",
        f"- **접근 방식:** {access}",
        f"- **주요 역할:** {role}",
        f"- **운영 형태:** {automation_note}",
        f"- **유통 위치 후보:** {distribution_position} (자동 분석, 확정 아님)",
    ]
    if about:
        report.extend([
            "", "### 채널 소개", "",
            f"> {md(about)}",
            "",
            about_explanation,
        ])
    report.extend([
        "", "## 규모와 활성도", "",
        "| 확인 항목 | 결과 |", "|---|---|",
        f"| 구독자·참가자 | {participants if participants != '미확인' else '미확인'} |",
        f"| 원본 수집 건수 | {raw_total}건 |",
        f"| 실제 게시물 | {total}개 |",
        f"| 제외한 서비스 메시지 | {len(service_rows)}개 (채널 생성·고정 알림) |",
        f"| 게시 구간 | {display_kst(activity['first'])} ~ {display_kst(activity['last'])} |",
        f"| 구간 길이 | {activity['duration']} |",
        f"| 하루 평균 게시량 | 약 {activity['per_day']}개 |",
        f"| 평균 게시 간격 | 약 {activity['interval_text']} |",
        "", f"- {activity_note}",
        "- 평균 게시 간격과 유형 비중은 채널 생성·고정 알림을 제외한 실제 게시물만으로 계산했다.",
        "- 분석값은 수집된 메시지 구간을 기준으로 하며 채널 전체 운영 기간을 의미하지 않는다.",

        "", "## 구성", "",
        f"운영 주체가 게시하고, 구독자가 내용을 받아보는 **{channel_type_phrase}** 확인됐다.",
        "", *type_table,
        "", f"- **외부 링크 포함:** {external_count}개 ({external_ratio * 100:.1f}%)",
        f"- **이미지·파일 포함:** {media_count}개",
        f"- **주 게시자 표시:** {top_sender} ({top_sender_count}개)",
        "- **용어 설명:** CVE는 공개된 소프트웨어 취약점에 부여되는 식별번호다." if counters["types"].get("취약점(CVE)") else "- **용어 설명:** 별도 설명이 필요한 주요 전문 용어는 자동 확인되지 않았다.",

        "", "## 거래", "", trade_text,
        "", "| 확인 항목 | 결과 |", "|---|---|",
        f"| 판매·거래 표현 포함 | {len(trade_rows)}개 |",
        f"| 공개된 가격 | {price_text} |",
        f"| 결제수단 관련 표현 | {len(payment_rows)}개 |",
        f"| 에스크로·중개 관련 표현 | {len(escrow_rows)}개 |",
        "", "## 개인정보 유출 관련", "", privacy_text,
        "", "| 확인 항목 | 결과 |", "|---|---:|",
        f"| 개인정보·DB 관련 주장 후보 | {len(leak_rows)}개 ({len(leak_rows) / max(total, 1) * 100:.1f}%) |",
        f"| 한국 관련 전체 후보 | {len(korea_rows)}개 |",
        f"| 한국 관련 개인정보·DB 후보 | {len(korea_leak_rows)}개 |",
        "", "- 게시자의 주장과 링크를 자동 탐지한 단계이며 실제 유출 여부는 미검증 상태다.",

        "", "## 유통에서 어느 자리인가", "",
        f"**분석 결과:** {distribution_position} (확정 아님)",
        "", distribution_text,
        "", "| 판단 근거 | 결과 |", "|---|---:|",
        f"| 외부 링크 포함 비율 | {external_ratio * 100:.1f}% |",
        f"| Telegram 포워딩 표시 | {len(forwarded_rows)}개 |",
        "- 개별 사건의 최초 게시처는 포럼과 Telegram의 게시 시각을 직접 비교해야 한다.",

        "", "## 연결", "",
        "자동 수집에서 확인된 연결 후보를 정리했다. DB의 `연결된 곳`은 아래 내용을 검토한 뒤 입력해야 한다.",
        "", connection_text,
        "", "| 구분 | 확인 결과 |", "|---|---|",
        f"| 공식·자체 사이트 후보 | {official_text} |",
        f"| 자주 등장한 외부 출처 | {joined_top(counters['domains'], 5)} |",
        f"| 포럼·유출 출처 후보 | {forum_text} |",
        f"| Telegram 핸들 | {handle_text} |",
        "", "## 운영", "",
        "| 확인 항목 | 결과 |", "|---|---|",
        f"| 주 게시자 표시 | {top_sender} ({top_sender_count}개) |",
        f"| 채널 생성 시점 | {created_at_text} |",
        f"| 자동화 가능성 | {automation_note} |",
        "", "- 게시자 표기와 생성 기록을 바탕으로 정리한 운영 단서이며, 실제 운영자의 신원이나 소유 관계를 확정한 결과는 아니다.",
        "", "## 지금 상태와 사라진 뒤", "",
        "| 확인 항목 | 결과 |", "|---|---|",
        f"| 확인일 | {confirmed_date} |",
        f"| API 접근 상태 | 정상 접근 |",
        f"| 마지막 확인 게시물 | {display_kst(activity['last'])} |",
        f"| 확인 주소 | {channel_url} |",
        "| 폐쇄·이전·병합 정황 | 자동 수집에서는 확인되지 않음 |",
        "", "- 상태가 바뀌면 기존 주소와 새 주소의 공지·운영자·게시 이력을 비교해야 한다.",

        "", "## 특이사항", "",
        "- 게시량이 많다면 유형·국가·키워드 필터를 함께 사용하는 것이 좋다." if total >= 20 else "- 표본이 적어 채널 전체 성격을 판단하려면 추가 수집이 필요하다.",
        "- 아래 후보 목록은 조사 대상을 좁히기 위한 근거이며 사실 확인 결과가 아니다.",

        "", "## 권장 캡처 목록", "",
        "보고서에 첨부하면 좋은 화면을 수집 결과에서 자동으로 골랐다. 실제 캡처 여부와 최종 첨부 사진은 사람이 원문을 확인한 뒤 결정한다.",
        "", *capture_plan,
        "", "### 캡처 시 주의사항", "",
        "- 외부 링크나 첨부파일은 열거나 내려받지 않고, Telegram에 보이는 게시물 화면만 캡처한다.",
        "- 전화번호·이메일·계정정보·유출 샘플 등 개인정보가 보이면 가린 뒤 보고서에 넣는다.",
        "- 채널명, 메시지 날짜, 게시자와 메시지 ID가 함께 보이도록 캡처한다.",
        "- 하나의 메시지가 여러 조건에 해당하면 한 번만 사용하고 캡션에서 의미를 함께 설명한다.",
        "- 삭제됐거나 접근할 수 없는 메시지는 억지로 대체하지 말고 `확인하지 못함`으로 기록한다.",

        "", "## 분석 근거", "",
        "보고서 본문은 채널 메타데이터와 메시지 형식·키워드·링크를 바탕으로 자동 작성했다. 메시지 원문과 개인정보 값은 복사하지 않았으며, 아래 표는 수동 검증이 필요한 후보만 보여준다.",
        "", "### 값 기록 기준", "",
        "| 표시 | 의미 |", "|---|---|",
        "| 값 + 날짜 + 출처 | 자동 수집으로 확인함 |",
        "| 없음 | 확인했으나 해당 항목이 없었음 |",
        "| 확인하지 못함 | 접근 제한이나 API 한계로 확인하지 못함 |",
        "| 자동 입력 안 함 | 자동 확정 금지 또는 이번 수집 범위 밖이라 사람이 확인해야 함 |",
        "", "- 원본 메시지 JSON은 내부 분석용 근거 파일이며 Notion·보고서·외부 공유 대상으로 사용하지 않는다.",
        "", "### 한국 관련 후보", "", *candidate_table(korea_rows, 10),
        "", "### 개인정보·DB 관련 주장 후보", "", *candidate_table(sorted(leak_rows, key=lambda row: row["views"], reverse=True), 15),
        "", "### 판매·거래 표현 포함 후보", "", *candidate_table(sorted(trade_rows, key=lambda row: row["views"], reverse=True), 10),
        "", "### 주요 외부 링크 도메인", "", *top_bullets(counters["domains"], 15),
        "", "## 수동 검증 체크리스트", "",
        "- [ ] 채널 소개와 공식 사이트의 운영 주체가 같은지 확인",
        "- [ ] 운영자·이전 이름·주소 변경 이력 확인",
        "- [ ] 개인정보·DB 관련 주장 후보의 원문과 최초 게시처 확인",
        "- [ ] 한국 관련 후보의 대상·피해 주장·공식 입장 확인",
        "- [ ] 판매 가격·결제수단·중개 여부 확인",
        "- [ ] 포럼·사이트 링크가 단순 출처인지 운영상 연결인지 확인",
    ])
    return "\n".join(report) + "\n"


def main():
    args = parse_args()
    payload, channel, messages = load_payload(args.input)
    rows, counters = analyze(messages)
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        build_report(payload, channel, messages, rows, counters, args.assignee),
        encoding="utf-8",
    )
    print(f"채널: {channel.get('title') or channel.get('username') or '미확인'}")
    print(f"불러온 메시지: {len(messages)}개")
    print(f"통합 채널 보고서 저장: {output}")
    print("주의: 입력 JSON은 메시지 원문이 포함될 수 있는 내부 분석용 파일입니다. 외부 공유는 생성된 MD 보고서만 사용하세요.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise SystemExit(f"오류: {error}")
