import asyncio
import calendar
import io
import json
import os
import re
import sqlite3
import time
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DART_CORP_CODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"
GEMINI_MODEL = "gemini-3.5-flash-lite"
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)
DART_REFRESH_DAYS = 7
DEFAULT_GEMINI_MIN_INTERVAL_SECONDS = 5.0
DEFAULT_GEMINI_RETRY_SECONDS = 60.0

KOREA_PATTERN = re.compile(
    r"(?:"
    r"\b(?:south\s+korea|republic\s+of\s+korea|korean|seoul|busan|incheon|daegu|daejeon|gwangju|ulsan)\b"
    r"|\b(?:KR|KOR)\b"
    r"|(?:https?://)?(?:[a-z0-9-]+\.)+kr(?:\b|/)"
    r"|\b[a-z0-9-]+\.(?:co|go|or|ac|ne|re|pe)\.kr\b"
    r"|(?:\uB300\uD55C\uBBFC\uAD6D|\uD55C\uAD6D|\uC11C\uC6B8|\uBD80\uC0B0|\uC778\uCC9C|\uB300\uAD6C|\uB300\uC804|\uAD11\uC8FC|\uC6B8\uC0B0)"
    r")",
    re.IGNORECASE,
)

COUNTRY_FIELD_PATTERN = re.compile(
    r"(?im)^\s*(?:country|location|headquarters|hq|nation)\s*[:=-]\s*([^\n|,;]{2,50})"
)
KOREA_COUNTRY_VALUES = {
    "kr",
    "kor",
    "korea",
    "south korea",
    "republic of korea",
    "korean",
    "\uD55C\uAD6D",
    "\uB300\uD55C\uBBFC\uAD6D",
}
FOREIGN_COUNTRY_VALUES = {
    "argentina", "australia", "austria", "belgium", "brazil", "canada", "chile",
    "china", "colombia", "czech republic", "denmark", "egypt", "finland", "france",
    "germany", "greece", "hong kong", "hungary", "india", "indonesia", "ireland",
    "israel", "italy", "japan", "malaysia", "mexico", "netherlands", "new zealand",
    "norway", "pakistan", "philippines", "poland", "portugal", "romania", "russia",
    "saudi arabia", "singapore", "south africa", "spain", "sweden", "switzerland",
    "taiwan", "thailand", "turkey", "ukraine", "united arab emirates", "united kingdom",
    "united states", "usa", "u.s.", "u.s.a.", "uk", "vietnam",
}
COMPANY_PATTERNS = [
    re.compile(
        r"(?im)^\s*(?:victim|company|organization|organisation|target|entity|company name|victim name)"
        r"\s*[:=-]\s*([^\n|]{2,160})"
    ),
    re.compile(r"(?im)^\s*(?:\U0001f3e2|\U0001f3af)\s*([^\n|]{2,160})"),
]
SECURITY_CONTEXT_PATTERN = re.compile(
    r"\b(?:ransomware|ransom|data\s+leak|data\s+breach|breached|victim|leaked|extortion)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Classification:
    is_korean: bool
    conclusive: bool
    source: str
    confidence: float
    company_name: str = ""
    evidence: str = ""


UNKNOWN = Classification(False, False, "unknown", 0.0)


class GeminiRateLimitError(RuntimeError):
    def __init__(self, message, retry_after):
        super().__init__(message)
        self.retry_after = retry_after


class GeminiQuotaDisabledError(RuntimeError):
    pass


def next_pacific_midnight_utc(now=None):
    """Return the next US Pacific midnight without requiring system tzdata."""
    now = now or datetime.now(timezone.utc)
    year = now.year

    march = calendar.monthcalendar(year, 3)
    march_sundays = [week[calendar.SUNDAY] for week in march if week[calendar.SUNDAY]]
    november = calendar.monthcalendar(year, 11)
    november_sundays = [week[calendar.SUNDAY] for week in november if week[calendar.SUNDAY]]
    dst_start = datetime(year, 3, march_sundays[1], 10, tzinfo=timezone.utc)
    dst_end = datetime(year, 11, november_sundays[0], 9, tzinfo=timezone.utc)
    offset_hours = -7 if dst_start <= now < dst_end else -8

    pacific_now = now + timedelta(hours=offset_hours)
    next_date = pacific_now.date() + timedelta(days=1)
    next_midnight_as_utc = datetime.combine(next_date, datetime.min.time(), timezone.utc)
    return next_midnight_as_utc - timedelta(hours=offset_hours)


def normalize_company_name(value):
    value = unicodedata.normalize("NFKC", value).casefold().strip()
    value = re.sub(r"https?://\S+", " ", value)
    value = re.sub(r"\([^)]*\)", " ", value)
    value = re.sub(
        r"\b(?:co|company|corp|corporation|inc|incorporated|ltd|limited|llc|plc|group|holdings)\b\.?,?",
        " ",
        value,
    )
    value = value.replace("\uC8FC\uC2DD\uD68C\uC0AC", " ").replace("\u321C", " ")
    return re.sub(r"[^0-9a-z\u3131-\u318e\uac00-\ud7a3]+", "", value)


def extract_company_name(text):
    for pattern in COMPANY_PATTERNS:
        match = pattern.search(text)
        if match:
            candidate = match.group(1).strip(" -*_`#")
            if 2 <= len(candidate) <= 160:
                return candidate
    return ""


def sanitize_for_gemini(text):
    text = re.sub(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "[REDACTED_EMAIL]", text, flags=re.I)
    text = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "[REDACTED_IP]", text)
    text = re.sub(r"\b[A-F0-9]{32,}\b", "[REDACTED_TOKEN]", text, flags=re.I)
    return text[:3000]


def rule_classification(text):
    match = KOREA_PATTERN.search(text)
    if match:
        return Classification(True, True, "keyword/domain", 1.0, evidence=match.group(0))

    country_match = COUNTRY_FIELD_PATTERN.search(text)
    if not country_match:
        return UNKNOWN
    country = country_match.group(1).strip().casefold()
    if country in KOREA_COUNTRY_VALUES:
        return Classification(True, True, "explicit-country", 1.0, evidence=country_match.group(0))
    if country in FOREIGN_COUNTRY_VALUES:
        return Classification(False, True, "explicit-country", 1.0, evidence=country_match.group(0))
    return UNKNOWN


def fetch_dart_companies(api_key):
    url = f"{DART_CORP_CODE_URL}?{urlencode({'crtfc_key': api_key})}"
    try:
        with urlopen(url, timeout=30) as response:
            payload = response.read()
    except (HTTPError, URLError) as exc:
        raise RuntimeError(f"DART company list request failed: {exc}") from exc

    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            xml_data = archive.read("CORPCODE.xml")
    except (zipfile.BadZipFile, KeyError) as exc:
        raise RuntimeError("DART returned an invalid company list archive") from exc

    companies = []
    root = ET.fromstring(xml_data)
    for item in root.findall("list"):
        corp_code = (item.findtext("corp_code") or "").strip()
        corp_name = (item.findtext("corp_name") or "").strip()
        if corp_code and corp_name:
            companies.append(
                (
                    corp_code,
                    corp_name,
                    normalize_company_name(corp_name),
                    (item.findtext("stock_code") or "").strip(),
                    (item.findtext("modify_date") or "").strip(),
                )
            )
    return companies


def call_gemini(api_key, text, company_name=""):
    schema = {
        "type": "OBJECT",
        "properties": {
            "company_name": {"type": "STRING"},
            "country_code": {"type": "STRING"},
            "confidence": {"type": "NUMBER"},
        },
        "required": ["company_name", "country_code", "confidence"],
    }
    if company_name:
        subject = f"Company: {company_name[:200]}"
    else:
        subject = "Extract the victim company from this post:\n" + sanitize_for_gemini(text)[:1200]
    prompt = (
        "Return only the victim company's headquarters country. Use a 2-letter ISO country code, "
        "or UNKNOWN if uncertain. Do not research or explain. Confidence must be 0 to 1.\n" + subject
    )
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 80,
            "responseMimeType": "application/json",
            "responseSchema": schema,
        },
    }
    request = Request(
        GEMINI_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            response_data = json.load(response)
    except HTTPError as exc:
        raw_detail = exc.read().decode("utf-8", errors="replace")
        detail = raw_detail[:500]
        if exc.code == 429:
            retry_after = None
            retry_after_header = exc.headers.get("Retry-After")
            if retry_after_header:
                try:
                    retry_after = float(retry_after_header)
                except ValueError:
                    pass
            if retry_after is None:
                match = re.search(
                    r"(?:Please retry in|retryDelay[^0-9]*)([0-9]+(?:\.[0-9]+)?)s?",
                    raw_detail,
                    re.IGNORECASE,
                )
                if match:
                    retry_after = float(match.group(1))
            raise GeminiRateLimitError(
                f"Gemini request failed with HTTP 429: {detail}",
                retry_after or DEFAULT_GEMINI_RETRY_SECONDS,
            ) from exc
        raise RuntimeError(f"Gemini request failed with HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Gemini request failed: {exc}") from exc

    try:
        result_text = response_data["candidates"][0]["content"]["parts"][0]["text"]
        result = json.loads(result_text)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Gemini returned an unexpected response") from exc

    country_code = str(result.get("country_code", "UNKNOWN")).strip().upper()
    confidence = max(0.0, min(1.0, float(result.get("confidence", 0.0))))
    return {
        "company_name": str(result.get("company_name", "")).strip(),
        "country_code": country_code,
        "confidence": confidence,
        "evidence": "",
    }


class CompanyCountryClassifier:
    def __init__(self, database, dart_api_key, gemini_api_key):
        self.database = database
        self.dart_api_key = dart_api_key
        self.gemini_api_key = gemini_api_key
        self.gemini_min_interval = max(
            0.0,
            float(
                os.environ.get(
                    "GEMINI_MIN_INTERVAL_SECONDS",
                    DEFAULT_GEMINI_MIN_INTERVAL_SECONDS,
                )
            ),
        )
        self._gemini_request_lock = asyncio.Lock()
        self._last_gemini_request_at = None
        self._create_schema()

    def _gemini_disabled_until(self):
        row = self.database.execute(
            "SELECT value FROM classifier_metadata WHERE key = 'gemini_disabled_until'"
        ).fetchone()
        if not row:
            return None
        try:
            disabled_until = datetime.fromisoformat(row[0])
        except ValueError:
            disabled_until = None
        if disabled_until and datetime.now(timezone.utc) < disabled_until:
            return disabled_until
        self.database.execute(
            "DELETE FROM classifier_metadata WHERE key = 'gemini_disabled_until'"
        )
        self.database.commit()
        if disabled_until:
            print("[gemini] daily quota reset; Gemini classification enabled")
        return None

    def _disable_gemini_until_reset(self):
        disabled_until = next_pacific_midnight_utc()
        self.database.execute(
            """
            INSERT INTO classifier_metadata (key, value) VALUES ('gemini_disabled_until', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (disabled_until.isoformat(),),
        )
        self.database.commit()
        print(
            "[gemini] repeated HTTP 429; Gemini classification disabled until "
            f"{disabled_until.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}"
        )
        return disabled_until

    def _create_schema(self):
        self.database.execute(
            """
            CREATE TABLE IF NOT EXISTS dart_companies (
                corp_code TEXT PRIMARY KEY,
                corp_name TEXT NOT NULL,
                normalized_name TEXT NOT NULL,
                stock_code TEXT,
                modify_date TEXT
            )
            """
        )
        self.database.execute(
            "CREATE INDEX IF NOT EXISTS idx_dart_normalized_name ON dart_companies(normalized_name)"
        )
        self.database.execute(
            """
            CREATE TABLE IF NOT EXISTS company_country_cache (
                normalized_name TEXT PRIMARY KEY,
                company_name TEXT NOT NULL,
                country_code TEXT NOT NULL,
                source TEXT NOT NULL,
                confidence REAL NOT NULL,
                evidence TEXT,
                checked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.database.execute(
            """
            CREATE TABLE IF NOT EXISTS classifier_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        self.database.commit()

    def _dart_is_stale(self):
        row = self.database.execute(
            "SELECT value FROM classifier_metadata WHERE key = 'dart_synced_at'"
        ).fetchone()
        if not row:
            return True
        try:
            synced_at = datetime.fromisoformat(row[0])
        except ValueError:
            return True
        return datetime.now(timezone.utc) - synced_at > timedelta(days=DART_REFRESH_DAYS)

    async def initialize(self):
        disabled_until = self._gemini_disabled_until()
        if disabled_until:
            print(
                "[gemini] quota pause active until "
                f"{disabled_until.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}"
            )
        if not self._dart_is_stale():
            count = self.database.execute("SELECT COUNT(*) FROM dart_companies").fetchone()[0]
            print(f"[dart] using cached company list ({count} companies)")
            return
        try:
            companies = await asyncio.to_thread(fetch_dart_companies, self.dart_api_key)
        except RuntimeError as exc:
            print(f"[dart] sync failed; continuing with existing cache: {exc}")
            return

        self.database.execute("DELETE FROM dart_companies")
        self.database.executemany(
            """
            INSERT INTO dart_companies
                (corp_code, corp_name, normalized_name, stock_code, modify_date)
            VALUES (?, ?, ?, ?, ?)
            """,
            companies,
        )
        self.database.execute(
            """
            INSERT INTO classifier_metadata (key, value) VALUES ('dart_synced_at', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (datetime.now(timezone.utc).isoformat(),),
        )
        self.database.commit()
        print(f"[dart] company list synchronized ({len(companies)} companies)")

    def _cached(self, candidate):
        normalized = normalize_company_name(candidate)
        if not normalized:
            return None
        row = self.database.execute(
            """
            SELECT company_name, country_code, source, confidence, evidence
            FROM company_country_cache WHERE normalized_name = ?
            """,
            (normalized,),
        ).fetchone()
        if not row:
            return None
        company_name, country_code, source, confidence, evidence = row
        return Classification(
            country_code == "KR",
            country_code != "UNKNOWN",
            f"cache:{source}",
            confidence,
            company_name,
            evidence or "",
        )

    def _dart_match(self, candidate):
        normalized = normalize_company_name(candidate)
        if not normalized:
            return None
        row = self.database.execute(
            "SELECT corp_name FROM dart_companies WHERE normalized_name = ? LIMIT 1",
            (normalized,),
        ).fetchone()
        if not row:
            return None
        result = Classification(True, True, "dart", 0.98, candidate, f"DART match: {row[0]}")
        self._save_cache(candidate, "KR", result.source, result.confidence, result.evidence)
        return result

    def _save_cache(self, company_name, country_code, source, confidence, evidence):
        normalized = normalize_company_name(company_name)
        if not normalized:
            return
        self.database.execute(
            """
            INSERT INTO company_country_cache
                (normalized_name, company_name, country_code, source, confidence, evidence)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(normalized_name) DO UPDATE SET
                company_name = excluded.company_name,
                country_code = excluded.country_code,
                source = excluded.source,
                confidence = excluded.confidence,
                evidence = excluded.evidence,
                checked_at = CURRENT_TIMESTAMP
            """,
            (normalized, company_name, country_code, source, confidence, evidence),
        )
        self.database.commit()

    async def _call_gemini_rate_limited(self, text, candidate):
        async with self._gemini_request_lock:
            if self._gemini_disabled_until():
                raise GeminiQuotaDisabledError
            attempt = 0
            while True:
                if self._last_gemini_request_at is not None:
                    elapsed = time.monotonic() - self._last_gemini_request_at
                    delay = self.gemini_min_interval - elapsed
                    if delay > 0:
                        print(f"[gemini] request interval wait: {delay:.1f}s")
                        await asyncio.sleep(delay)

                attempt += 1
                self._last_gemini_request_at = time.monotonic()
                try:
                    return await asyncio.to_thread(
                        call_gemini, self.gemini_api_key, text, candidate
                    )
                except GeminiRateLimitError as exc:
                    if attempt >= 2:
                        self._disable_gemini_until_reset()
                        raise GeminiQuotaDisabledError from exc
                    retry_after = max(exc.retry_after, self.gemini_min_interval) + 1.0
                    print(
                        f"[gemini] HTTP 429; retrying the same post in "
                        f"{retry_after:.1f}s (attempt {attempt + 1})"
                    )
                    await asyncio.sleep(retry_after)

    async def classify(self, text):
        rule_result = rule_classification(text)
        if rule_result.conclusive:
            return rule_result

        if not SECURITY_CONTEXT_PATTERN.search(text):
            return UNKNOWN

        candidate = extract_company_name(text)
        if candidate:
            cached = self._cached(candidate)
            if cached:
                return cached
            dart_result = self._dart_match(candidate)
            if dart_result:
                return dart_result

        if self._gemini_disabled_until():
            return Classification(
                False,
                False,
                "gemini-quota-skipped",
                0.0,
                candidate,
                "Gemini daily quota unavailable; rules/cache/DART only",
            )

        try:
            result = await self._call_gemini_rate_limited(text, candidate)
        except GeminiQuotaDisabledError:
            return Classification(
                False,
                False,
                "gemini-quota-skipped",
                0.0,
                candidate,
                "Gemini daily quota unavailable; rules/cache/DART only",
            )
        except RuntimeError as exc:
            print(f"[gemini] classification failed: {exc}")
            return UNKNOWN

        company_name = result["company_name"] or candidate
        country_code = result["country_code"]
        confidence = result["confidence"]
        evidence = result["evidence"]
        if company_name and confidence >= 0.75:
            self._save_cache(company_name, country_code, "gemini", confidence, evidence)

        conclusive = country_code != "UNKNOWN" and confidence >= 0.75
        return Classification(
            country_code == "KR" and confidence >= 0.75,
            conclusive,
            "gemini",
            confidence,
            company_name,
            evidence,
        )
