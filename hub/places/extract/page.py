"""본문에서 뽑는 판정. apps/dls-observatory/tor_probe.py 에서 왔습니다.

그 파일 1,105줄 중 절반은 **직접 SOCKS5 터널을 여는 코드**입니다. hub 은
egress.py 로 나가고 하위 페이지는 브라우저가 보므로 안 옮겼습니다.

없던 것은 **본문에서 뽑는 판정** 넷입니다.

    detect_language      글자를 보고 사용 언어
    detect_gate          무엇에 막히는가 (가입 · 초대 · 캡차 · 클라우드플레어)
    meta_tags            title · description · keywords · h1
    extract_indicators   어니언 · 연락수단 · 지갑 주소

infer.py 가 이것들을 받아 「형식」「개인정보 유출」「유통 자리」를 냅니다.
그래서 둘은 같이 와야 합니다.
"""

from __future__ import annotations

import html as _html
import re
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urlparse

_TAG = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)

_TAGS = re.compile(r"<[^>]+>")

_WS = re.compile(r"\s+")

SCRIPTS = {
    "CYRILLIC": "러시아어", "HANGUL": "한국어", "ARABIC": "아랍어",
    "HEBREW": "히브리어", "HIRAGANA": "일본어", "KATAKANA": "일본어",
    "CJK": "중국어", "THAI": "타이어", "DEVANAGARI": "힌디어",
}

STOPWORDS = {
    "영어": (" the ", " and ", " you ", " for ", " with ", " your ", " login ",
             " price ", " about ", " home ", " search "),
    "러시아어": (" и ", " не ", " на ", " вход ", " цена ", " все ", " для "),
    "스페인어": (" que ", " para ", " con ", " los ", " precio "),
    "독일어": (" und ", " der ", " nicht ", " mit ", " preis "),
    "프랑스어": (" les ", " pour ", " avec ", " vous ", " prix "),
    "포르투갈어": (" para ", " com ", " você ", " preço "),
    "터키어": (" için ", " bir ", " ile ", " fiyat "),
    "베트남어": (" và ", " của ", " không ", " giá "),
}

SIGNALS = {
    "캡차": [
        (r"""<script[^>]+src=["'][^"']*(recaptcha|hcaptcha|turnstile|challenges\.cloudflare)""", "strong"),
        (r"""\b(g-recaptcha|h-captcha|cf-turnstile)\b""", "strong"),
        (r"""<img[^>]+(src|alt)=["'][^"']*captcha""", "strong"),
        (r"""<input[^>]+name=["']?captcha""", "strong"),
        (r"\bcaptcha\b", "weak"),
        (r"\bкапч", "weak"),
        (r"验证码", "weak"),
        (r"인증\s*코드", "weak"),
    ],
    "로그인": [
        (r"""<input[^>]+type=["']?password""", "strong"),
        (r"""<form[^>]*(action|id|class)=["'][^"']*(login|signin|auth)""", "strong"),
        (r"\bsign\s?in\b|\blog\s?in\b", "weak"),
        (r"\bвойти\b|\bавториз", "weak"),
        (r"로그인", "weak"),
    ],
    "회원가입": [
        (r"""<form[^>]*(action|id|class)=["'][^"']*(register|signup|registration)""", "strong"),
        (r"""<a[^>]+href=["'][^"']*(register|sign-?up)""", "strong"),
        (r"\bregister\b|\bsign\s?up\b|\bcreate\s+account\b", "weak"),
        (r"\bрегистрац", "weak"),
        (r"회원가입", "weak"),
    ],
    "초대코드": [
        (r"invite\s*code|invitation\s*code|referral\s*code", "strong"),
        (r"\bинвайт", "weak"),
        (r"초대\s*코드", "weak"),
    ],
    "가입비": [
        (r"registration\s+fee|deposit\s+required|вступительн", "strong"),
    ],
    "PoW/DDoS 방어": [
        (r"ddos-guard|proof[\s-]?of[\s-]?work|\bpow\s+challenge\b|"
         r"checking\s+your\s+browser|just\s+a\s+moment", "strong"),
    ],
}

CONTACT = {
    "tox":      r"\b[A-F0-9]{76}\b",
    "session":  r"\b05[a-f0-9]{64}\b",
    "telegram": r"(?:t\.me/|telegram(?:\.me)?[:/@\s]{1,3})([A-Za-z0-9_]{5,32})",
    "jabber":   r"\b[\w.\-]{2,32}@(?:jabber|xmpp|exploit|thesecure)[\w.\-]*\.[a-z]{2,}\b",
    "email":    r"\b[\w.\-]{2,40}@(?:protonmail|proton|tutanota|onionmail|cock|"
                r"mail2tor|dnmx|elude|riseup)\.[a-z.]{2,10}\b",
    "qtox":     r"\btox\s*(?:id)?\s*[:=]\s*([A-F0-9]{76})\b",
}

TELEGRAM_ROUTES = {
    "contact", "messenger", "channel", "channels", "share", "joinchat",
    "addstickers", "addtheme", "proxy", "socks", "login", "about", "apps",
    "faq", "blog", "privacy", "terms", "support", "download", "premium",
    "setlanguage", "confirmphone", "iv", "img", "telegram", "durov",
}

CRYPTO = {
    "btc": r"\b(?:bc1[a-z0-9]{25,62}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b",
    "xmr": r"\b4[0-9AB][1-9A-HJ-NP-Za-km-z]{93}\b",
    "eth": r"\b0x[a-fA-F0-9]{40}\b",
}

def visible_text(html: str) -> str:
    t = _TAG.sub(" ", html)
    t = _TAGS.sub(" ", t)
    t = (t.replace("&nbsp;", " ").replace("&amp;", "&")
          .replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"'))
    return _WS.sub(" ", t).strip()

def get_title(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    if not m:
        m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S | re.I)
    if not m:
        return ""
    return _WS.sub(" ", _TAGS.sub("", m.group(1))).strip()[:200]

def detect_language(html: str, text: str) -> tuple[str, str]:
    """(판별 결과, 근거) 반환."""
    m = re.search(r'<html[^>]*\blang\s*=\s*["\']?([a-zA-Z\-]+)', html[:3000])
    lang_attr = m.group(1).lower()[:5] if m else ""

    sample = text[:20000]
    counts: dict[str, int] = {}
    letters = 0
    for ch in sample:
        if not ch.isalpha():
            continue
        letters += 1
        try:
            nm = unicodedata.name(ch)
        except ValueError:
            continue
        for key, label in SCRIPTS.items():
            if nm.startswith(key):
                counts[label] = counts.get(label, 0) + 1
                break
        else:
            if nm.startswith("LATIN"):
                counts["_latin"] = counts.get("_latin", 0) + 1

    if letters < 40:
        return ("", f"본문이 짧아 판별 불가(문자 {letters}개)"
                    + (f", html lang={lang_attr}" if lang_attr else ""))

    nonlatin = {k: v for k, v in counts.items() if k != "_latin"}
    if nonlatin:
        top, n = max(nonlatin.items(), key=lambda x: x[1])
        ratio = n / letters
        if ratio >= 0.25:
            latin_ratio = counts.get("_latin", 0) / letters
            if latin_ratio >= 0.25:
                return (f"{top}, 영어", f"{top} {ratio:.0%} + 라틴문자 {latin_ratio:.0%}")
            return (top, f"{top} 문자 {ratio:.0%}")

    low = " " + sample.lower() + " "
    scores = {lang: sum(low.count(w) for w in ws) for lang, ws in STOPWORDS.items()}
    best = max(scores, key=lambda k: scores[k])
    if scores[best] >= 3:
        return (best, f"불용어 {scores[best]}회 일치")
    if lang_attr:
        return ("", f"판별 실패, html lang={lang_attr}")
    return ("", "판별 실패")

def detect_gate(html: str, text: str) -> dict:
    """진입 조건을 근거와 함께 반환. 통과 시도는 하지 않는다."""
    blob = (html[:300000] + " " + text[:50000])
    evidence, found = [], {}
    for name, pats in SIGNALS.items():
        for pat, strength in pats:
            m = re.search(pat, blob, re.I)
            if not m:
                continue
            evidence.append({"signal": name, "strength": strength,
                             "match": m.group(0)[:60]})
            # 같은 신호는 가장 강한 근거만 남긴다
            if found.get(name) != "strong":
                found[name] = strength
            if strength == "strong":
                break

    # 실제 벽으로 볼지는 strong 근거가 있을 때만
    gate_names = ("로그인", "회원가입", "초대코드", "가입비")
    needs = any(found.get(s) == "strong" for s in gate_names)

    captcha_conf = found.get("캡차", "none")

    if not found:
        how = "공개 접근 (로그인·캡차 신호 없음)"
    else:
        parts = []
        if found.get("PoW/DDoS 방어") == "strong":
            parts.append("봇 차단 페이지")
        if captcha_conf == "strong":
            parts.append("캡차 있음")
        elif captcha_conf == "weak":
            parts.append("캡차 가능성(약한 근거)")
        if found.get("초대코드"):
            parts.append("초대코드 필요")
        if found.get("가입비") == "strong":
            parts.append("가입비·보증금 언급")
        if found.get("회원가입") == "strong":
            parts.append("회원가입 필요")
        elif found.get("로그인") == "strong":
            parts.append("로그인 필요")
        elif found.get("회원가입") or found.get("로그인"):
            parts.append("로그인·가입 링크 있음(약한 근거)")
        how = ", ".join(parts) or "신호 약함"

    return {"signup_required": needs,
            "gate_signals": sorted(found),
            "gate_strength": found,
            "gate_evidence": evidence[:12],
            "captcha_confidence": captcha_conf,
            "how_to_enter": how}

def meta_tags(html: str) -> dict:
    """<meta> 와 <h1> 에서 사이트 성격 단서를 뽑는다."""
    head = html[:60000]
    out: dict[str, str] = {}

    def meta(attr: str, value: str) -> str | None:
        m = re.search(
            rf"""<meta[^>]+{attr}=["']{value}["'][^>]+content=["']([^"']{{1,300}})""",
            head, re.I)
        if not m:
            m = re.search(
                rf"""<meta[^>]+content=["']([^"']{{1,300}})["'][^>]+{attr}=["']{value}["']""",
                head, re.I)
        return _WS.sub(" ", m.group(1)).strip() if m else None

    for key, attr, val in (("meta_description", "name", "description"),
                           ("keywords", "name", "keywords"),
                           ("generator", "name", "generator"),
                           ("og_title", "property", "og:title"),
                           ("og_site_name", "property", "og:site_name"),
                           ("og_description", "property", "og:description")):
        v = meta(attr, val)
        if v:
            out[key] = v[:300]

    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S | re.I)
    if m:
        h1 = _WS.sub(" ", _TAGS.sub("", m.group(1))).strip()
        if h1:
            out["h1"] = h1[:200]
    return out

def extract_indicators(html: str, text: str, base_host: str) -> dict:
    """연락 수단·암호화폐 주소·링크 구조 등 실무 지표."""
    blob = html[:300000]
    out: dict = {}

    contacts: dict[str, list[str]] = {}
    for name, pat in CONTACT.items():
        hits = []
        for m in re.finditer(pat, blob, re.I):
            v = (m.group(1) if m.groups() else m.group(0)).strip()
            if name == "telegram" and v.lower() in TELEGRAM_ROUTES:
                continue          # t.me 의 시스템 경로지 핸들이 아니다
            if v and v not in hits:
                hits.append(v)
            if len(hits) >= 3:
                break
        if hits:
            contacts[name] = hits
    if contacts:
        out["contacts"] = contacts

    crypto: dict[str, list[str]] = {}
    for name, pat in CRYPTO.items():
        hits = []
        for m in re.finditer(pat, blob):
            v = m.group(0)
            if v not in hits:
                hits.append(v)
            if len(hits) >= 3:
                break
        if hits:
            crypto[name] = hits
    if crypto:
        out["crypto"] = crypto

    out["has_pgp"] = bool(re.search(r"BEGIN PGP (PUBLIC KEY|SIGNATURE)", blob, re.I))
    out["countdown"] = bool(re.search(
        r"countdown|time\s*left|days?\s*:\s*\d|deadline|таймер|осталось", blob, re.I))
    out["mirror_mentioned"] = bool(re.search(r"\bmirror\b|зеркал", blob, re.I))

    # 링크 구조 — 다른 onion 주소를 찾으면 '연결된 곳'/미러 후보가 된다
    hrefs = re.findall(r"""href=["']([^"'\s>]{1,300})""", blob, re.I)
    out["link_count"] = len(hrefs)

    onions, externals = [], []
    for h in hrefs:
        hm = re.search(r"([a-z2-7]{16,56}\.onion)", h, re.I)
        if hm:
            v = hm.group(1).lower()
            if v != base_host and v not in onions:
                onions.append(v)
            continue
        dm = re.match(r"https?://([^/:?#]+)", h, re.I)
        if dm:
            d = dm.group(1).lower().lstrip("www.")
            if d != base_host and not d.endswith(".onion") and d not in externals:
                externals.append(d)
    out["onion_links"] = onions[:20]
    out["onion_link_count"] = len(onions)
    out["external_domains"] = externals[:15]

    # 피해자 게시물처럼 보이는 링크의 '개수'만 센다.
    # 피해 기업 이름 자체는 유출 데이터라 저장하지 않는다.
    out["listing_link_count"] = len(re.findall(
        r"""href=["'][^"']*/(?:post|posts|company|companies|victim|victims|
            blog|leak|leaks|client|target)[s]?[/?]""",
        blob, re.I | re.X))

    # 페이지에 적힌 날짜 중 가장 최근 것 → '최근 활동' 추정 근거
    dates = set()
    for m in re.finditer(r"\b(20[12]\d)[-/.](\d{1,2})[-/.](\d{1,2})\b", text[:60000]):
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            dates.add(f"{y:04d}-{mo:02d}-{d:02d}")
    for m in re.finditer(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](20[12]\d)\b", text[:60000]):
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            dates.add(f"{y:04d}-{mo:02d}-{d:02d}")
    today = datetime.now(timezone.utc).date().isoformat()
    valid = sorted(d for d in dates if d <= today)
    if valid:
        out["latest_date_on_page"] = valid[-1]
        out["date_count"] = len(valid)
    return out
