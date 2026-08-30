"""
수집한 원자료에서 분류 칼럼을 추론한다 (형식·개인정보 유출·유통 자리·국가 등).

원칙
----
1. **근거 없는 추론은 하지 않는다.** 모든 함수는 (값, 근거) 를 함께 돌려준다.
   근거가 없으면 값도 없다.
2. **확신 수준을 값에 드러낸다.** 확실하면 그대로, 약하면 "추정: " 접두어.
   사람이 확인하고 접두어를 지우면 확정값이 된다.
   이렇게 해야 나중에 "이 값이 기계 추측인지 사람 확인인지" 를 구분할 수 있다.
3. 애매하면 비워둔다. 잘못 채운 칸은 빈 칸보다 나쁘다.
"""

from __future__ import annotations

import re

MAYBE = "추정: "


def _blob(*parts: str | None) -> str:
    return " ".join(p for p in parts if p).lower()


# --------------------------------------------------------------------------
# 형식 — RaaS / 데이터 갈취 / 포럼·마켓 …
# --------------------------------------------------------------------------
# 순서가 곧 우선순위다. 구체적인 신호를 먼저 보고, 가장 넓은 '데이터 갈취' 를
# 마지막에 둔다. 'leak' 한 단어는 거의 모든 유출 사이트에 나오므로 이걸 위에
# 두면 마켓·툴샵까지 전부 데이터 갈취로 빨려 들어간다.
#
# 패턴은 추측이 아니라 실제 수집 결과(제목·h1·meta·keywords)에서 뽑았다.
# 주석의 사이트 이름이 그 패턴을 넣은 근거다.
FORMAT_RULES = [
    # (값, 강한 근거 패턴, 약한 근거 패턴)
    ("RaaS",
     r"\braas\b|ransomware[- ]as[- ]a[- ]service|affiliate program|"
     r"recruit(ing)? (affiliates|partners)|партнёрск",
     r"\baffiliate"),

    # 초기 접근 — cPanel/RDP/SMTP/셸 판매.  근거: 0day("Buy Tools, Cpanel,
    # RDP, Hosting, SMTP"), xLeet 계열
    ("초기 접근",
     r"initial access broker|\biab\b|\brdp\b|\bcpanel\b|\bwebmail\b|"
     r"\bc-?panel\b|\bshells?\b\s*(shop|for sale)|selling access to|"
     r"\bssh\s+access\b|доступ",
     r"\bvpn access\b|\bwebshell|\bhosting\b"),

    # 사기 도구 — OTP 탈취기·SMS 발송기·체커·메일러.  근거: Hustlers
    # ("otp grabber, sms sender, email checker"), 0day("Mailler, COMBO, Leads")
    ("사기 도구",
     r"\botp\s*(grabber|bot)\b|\bsms\s*(sender|spoof)\b|"
     r"\bemail\s+checker\b|\bcombo\s*(list)?s?\b|\bmail(l)?er\b|"
     r"\bbrute(force)?\s*(tool|checker)\b|\bspam(ming)?\s+tools?\b|"
     r"\bsim\s*swap\b|\bcarding\s+tools?\b",
     r"\bchecker\b|\bgrabber\b|\bleads\b"),

    # 카딩 — 카드번호·풀즈·덤프 판매.  스틸러 로그샵과 상품이 다르므로
    # 나눈다.  근거: CVVUNION, PREPAID CARD STORE, CC SALE, BRIAN'S CLUB
    ("카딩",
     r"\bcvv2?\b|\bfullz\b|\bdumps?\s*\+?\s*pin\b|\bcarding\b|"
     r"\b(credit|prepaid|gift)\s+cards?\b|\bcc\s+(shop|store|sale)\b|"
     r"\bbins?\s+(shop|list)\b|\bкардинг",
     r"\bcards?\s+(shop|store)\b"),

    ("스틸러/로그",
     r"\b(info)?stealer\b|\blogs?\s+(shop|market|cloud)\b|"
     r"\bcloud of logs\b|\blog\s+shop\b",
     r"\bredline\b|\braccoon\b|\bvidar\b|\blogs\b"),

    # 포럼·마켓.  근거: ZISMO("Форум о социальных сетях"), CHANG'AN("mall"),
    # Amazon Market("Access Queue"), underground("Underground store")
    ("포럼·마켓",
     r"\bmarketplace\b|\bmarket\b|\bforum\b|\bфорум\b|\bboard\b|"
     r"vendor account|\bescrow\b|\bmall\b|\bbazaar\b|\bплощадк",
     r"\bshop\b|\bstore\b|\bvendors?\b|access queue"),

    # 데이터 갈취 — 가장 넓으므로 맨 마지막.  근거: crypto24("ransomware leak
    # site listing compromised companies and exfiltrated data"), daixin("Data
    # Leak"), Wallstreet("DLS"), abyss("free DATA"), embargo("locker")
    ("데이터 갈취",
     r"double[- ]extortion|data[- ]extortion|exfiltrat|\bdls\b|"
     r"leak\s*site|data\s*leak|\bleak(ed|s)?\b|\blocker\b|\bransoms?\b|"
     r"we (publish|leak|sell) (the )?(stolen |your )?data|"
     r"pay or (we )?(publish|leak)|system\s+breach|compromised\s+compan",
     r"\bleak(ed)? data\b|\bstolen data\b|\bfree\s+data\b|\bvictims?\b"),
]


# 랜섬웨어 그룹 설명문에서 읽어도 되는 형식.
#
# 같은 단어라도 어디서 나왔느냐에 따라 뜻이 다르다. 상점의 keywords 에 있는
# 'rdp' 는 파는 물건이지만, ransomware.live 의 그룹 설명문에 있는 'rdp' 는
# 그 그룹이 침투에 쓰는 경로다. everest 는 설명문의 'credit card'(유출된
# 데이터 종류) 때문에 카딩 상점이 됐고, cephalus 는 'rdp'(침투 기법) 때문에
# 초기 접근 브로커가 됐다. 둘 다 랜섬웨어 그룹이다.
#
# 그래서 그룹 설명문에서는 사업 모델을 말하는 두 값만 읽는다.
_GROUP_DESC_OK = ("RaaS", "데이터 갈취")


def infer_format(kind: str | None, description: str | None,
                 title: str | None, keywords: str | None,
                 h1: str | None = None,
                 page_description: str | None = None,
                 name: str | None = None,
                 override: str | None = None) -> tuple[str | None, str]:
    """description 은 API(그룹 설명문), 나머지는 사이트에서 직접 읽은 것.

    두 출처를 섞지 않는다 — 위 주석의 이유 때문이다.

    name 은 사이트 이름. 'AUTHORIZE CVV', 'CREDIT CARD DUMPS',
    'ALLWORLDCARDS' 처럼 이름이 곧 업종인 경우가 많은데 그동안 안 보고 있었다.
    **이름은 접속이 안 되는 사이트에도 남아 있으므로 죽은 379곳에도 통한다.**
    """
    if override:
        return override, "수동 지정"

    page_text = _blob(title, keywords, h1, page_description)
    name_text = _blob(name)
    api_text = _blob(description)
    if not (page_text.strip() or name_text.strip() or api_text.strip()):
        return None, ""

    def _conflicts(value: str) -> bool:
        """API 가 이미 종류를 정해둔 행에 모순되는 형식을 붙이지 않는다.
        랜섬웨어 그룹 설명에 'forum' 한 단어가 스쳤다고 포럼·마켓이 되면 안 된다."""
        if value == "포럼·마켓" and kind == "group":
            return True
        if value in ("RaaS", "데이터 갈취") and kind in ("market", "forum"):
            return True
        return False

    def _scan(text: str, use_strong: bool, allow: tuple[str, ...] | None,
              label: str) -> tuple[str | None, str]:
        if not text.strip():
            return None, ""
        for value, strong, weak in FORMAT_RULES:
            if _conflicts(value) or (allow and value not in allow):
                continue
            m = re.search(strong if use_strong else weak, text, re.I)
            if m:
                out = value if use_strong else MAYBE + value
                return out, f"{label} '{m.group(0)[:40]}'"
        return None, ""

    # 사이트에서 직접 읽은 텍스트가 우선이다. 그게 그 사이트가 스스로
    # 무엇이라 말하는지이기 때문이다.
    allow_api = _GROUP_DESC_OK if kind == "group" else None
    # 이름은 랜섬웨어 그룹에서는 믿지 않는다. 'BlackCat' 의 'cat' 처럼
    # 그룹 이름은 업종이 아니라 그냥 별명이기 때문이다. 마켓·상점은 다르다 —
    # 손님을 끌어야 하므로 이름에 파는 물건을 적어둔다.
    allow_name = _GROUP_DESC_OK if kind == "group" else None
    order = ((page_text, None, "본문"),
             (name_text, allow_name, "이름"),
             (api_text, allow_api, "그룹 설명"))
    for text, allow, label in order:
        v, why = _scan(text, True, allow, label)
        if v:
            return v, why
    for text, allow, label in order:
        v, why = _scan(text, False, allow,
                       "약한 근거" if label == "본문" else f"약한 근거({label})")
        if v:
            return v, why

    # 근거는 없지만 종류만으로 최소한 말할 수 있는 경우
    if kind in ("market", "forum"):
        return MAYBE + "포럼·마켓", f"종류={kind}"
    return None, ""


# --------------------------------------------------------------------------
# 개인정보 유출 — 이 사이트가 개인정보를 취급/유출하는가
# --------------------------------------------------------------------------
# 카딩·풀즈처럼 그 자체가 개인정보인 상품
PII_STRONG = (
    r"\bfullz\b", r"\bcvv2?\b", r"\bdumps?\s*\+?\s*pin\b", r"\bssn\b",
    r"\bpassport\s+scan", r"\bdriver'?s?\s+licen[cs]e\b", r"\bkyc\b",
    r"credit\s+card\s+(dump|number)", r"personal\s+(data|information)\s+"
    r"(leak|dump|for sale)", r"개인정보", r"주민등록", r"персональн",
)
PII_WEAK = (
    r"\bdatabase\s+(leak|dump|for sale)\b", r"\bdata\s*breach\b",
    r"\bcustomer\s+(data|records)\b", r"\bemployee\s+(data|records)\b",
    r"\bpii\b", r"\bmedical\s+records?\b", r"\bбаза\s+данных\b",
)


def infer_pii(kind: str | None, description: str | None, title: str | None,
              keywords: str | None, h1: str | None = None,
              fmt: str | None = None) -> tuple[str | None, str]:
    text = _blob(description, title, keywords, h1)

    for pat in PII_STRONG:
        m = re.search(pat, text, re.I)
        if m:
            return "있음", f"'{m.group(0)[:30]}' 취급"
    for pat in PII_WEAK:
        m = re.search(pat, text, re.I)
        if m:
            return MAYBE + "있음", f"'{m.group(0)[:30]}' 언급"

    # 여기서 '랜섬웨어 그룹이니까 개인정보도 있겠지' 로 채우지 않는다.
    # 그렇게 하면 500행 중 400행이 같은 값이 되어 칼럼이 아무것도 말하지
    # 못한다. 근거가 없으면 비워두고 사람이 판단하게 남긴다.
    return None, ""


# --------------------------------------------------------------------------
# 유통 자리 — 최초 유출인가, 재배포인가
# --------------------------------------------------------------------------
REDIST = (
    r"\bmirror\b", r"\brepost", r"\baggregat", r"we\s+collect\b",
    r"\bcollected\s+from\b", r"\barchive\s+of\s+leaks\b",
    r"\bre-?upload", r"зеркал", r"\bcompilation\b",
)
FIRST = (
    r"\bwe\s+(hacked|breached|attacked)\b", r"\bour\s+victims?\b",
    r"\bif\s+(you|the\s+company)\s+(do(es)?\s+not\s+)?pay\b",
    r"\bcontact\s+us\s+to\s+(negotiate|recover)\b", r"\bnegotiat",
    r"\bdeadline\b", r"\bransom\b",
)


def infer_distribution(kind: str | None, description: str | None,
                       title: str | None, h1: str | None = None,
                       has_countdown: bool = False,
                       listing_links: int = 0,
                       victim_count: int = 0,
                       named_victims: int = 0) -> tuple[list[str], str]:
    """victim_count 는 ransomware.live 가 '이 그룹이 주장했다' 고 기록한 피해자 수.

    그건 추측이 아니라 출처가 있는 사실이고, 자기가 턴 곳을 자기 사이트에
    올린다는 뜻이므로 '최초 유출' 의 직접 근거가 된다.

    named_victims 는 페이지에 실명 피해 기업 도메인이 몇 개 걸려 있는지다.
    titan 이 termotecnica.it 등 7곳을 걸어둔 것처럼, 피해자를 실명으로
    공개하는 것 자체가 최초 유출의 증거다.
    """
    text = _blob(description, title, h1)
    out, why = [], []

    for pat in FIRST:
        m = re.search(pat, text, re.I)
        if m:
            out.append("최초 유출")
            why.append(f"'{m.group(0)[:24]}'")
            break
    else:
        if has_countdown and kind == "group":
            out.append("최초 유출")
            why.append("협상 카운트다운")

    for pat in REDIST:
        m = re.search(pat, text, re.I)
        if m:
            out.append("재배포")
            why.append(f"'{m.group(0)[:24]}'")
            break

    if not out and kind == "group":
        if victim_count:
            return ["최초 유출"], f"API 에 이 그룹이 주장한 피해자 {victim_count}건"
        if named_victims >= 2:
            return ["최초 유출"], f"페이지에 피해 기업 {named_victims}곳 실명 공개"
        if listing_links >= 3:
            return ["최초 유출"], "자체 피해자 목록 운영"
    return out, ", ".join(why)


# --------------------------------------------------------------------------
# 국가 — 언어·도메인·피해자 분포로 추정 (확정 아님)
# --------------------------------------------------------------------------
LANG_COUNTRY = {
    "러시아어": "러시아", "독일어": "독일", "중국어": "중국",
    "스페인어": "스페인", "프랑스어": "프랑스", "포르투갈어": "브라질",
    "터키어": "튀르키예", "베트남어": "베트남", "아랍어": "미확인",
    "한국어": "한국", "일본어": "일본",
}
TLD_COUNTRY = {
    ".ru": "러시아", ".su": "러시아", ".de": "독일", ".cn": "중국",
    ".kr": "한국", ".jp": "일본", ".br": "브라질", ".ir": "이란",
}


def infer_country(language: str | None, url: str | None,
                  override: str | None = None,
                  kind: str | None = None,
                  external_domains=None) -> tuple[str | None, str]:
    """국가는 가장 틀리기 쉬운 칼럼이라 근거를 좁게 잡는다.

    **랜섬웨어 그룹이 거는 클리어넷 도메인은 운영자가 아니라 피해자다.**
    titan 은 termotecnica.it·poemasrl.it 등 이탈리아 기업을 걸어뒀는데
    그걸 TLD 로 읽으면 '이탈리아 조직' 이 된다. 정반대다 — 사냥터다.
    BOHEMIA 의 politie.nl 은 압수한 네덜란드 경찰이다.

    그래서 도메인 국가 코드는 마켓·포럼에서만 읽는다. 마켓이 자기 나라
    서비스를 거는 것(crimemarket → ipbmafia.ru)은 운영자 단서가 맞다.
    """
    if override:
        return override, "수동 지정"

    host = (url or "").lower()
    for tld, country in TLD_COUNTRY.items():
        if re.search(rf"{re.escape(tld)}(/|$|:)", host):
            return MAYBE + country, f"도메인 {tld}"

    if kind in ("market", "forum") and external_domains:
        for d in external_domains:
            if not d or _INFRA.search(d):
                continue
            tld = "." + str(d).rsplit(".", 1)[-1].lower()
            if tld in TLD_COUNTRY:
                return (MAYBE + TLD_COUNTRY[tld],
                        f"사이트가 거는 {d} ({tld})")

    if language:
        # '영어' 는 어디서나 쓰이므로 단서가 되지 않는다
        primary = language.split(",")[0].strip()
        c = LANG_COUNTRY.get(primary)
        if c and c != "미확인":
            return MAYBE + c, f"사용 언어 {primary}"
    return None, ""


# --------------------------------------------------------------------------
# 조사 단계 — 이미 '조사 완료' 인 행은 건드리지 않는다
# --------------------------------------------------------------------------
def infer_stage(current: str | None, observed: bool,
                done_values: tuple[str, ...] = ("조사 완료",),
                checked_value: str = "확인만 함") -> str | None:
    """접속 확인만 한 행에 '확인만 함' 을 넣는다. 사람이 조사를 마친 행은 유지."""
    if current and current.strip() in done_values:
        return None
    if not observed:
        return None
    if current and current.strip() == checked_value:
        return None
    return checked_value


# --------------------------------------------------------------------------
# 규모 — 마켓은 게시물 수, 랜섬웨어는 피해자 수
# --------------------------------------------------------------------------
def infer_scale(kind: str | None, listing_links: int | None,
                victim_count: int | None, months: int = 6) -> tuple[str | None, str]:
    if victim_count:
        return f"피해자 {victim_count}건 (최근 {months}개월)", "API 피해자 집계"
    if listing_links and listing_links >= 3:
        return f"게시물 약 {listing_links}건 (첫 페이지 기준)", "페이지 링크 수"
    return None, ""


# --------------------------------------------------------------------------
# 연락 수단 — 행위자 식별 지표
# --------------------------------------------------------------------------
CONTACT_LABEL = {"tox": "Tox", "qtox": "Tox", "session": "Session",
                 "telegram": "Telegram", "jabber": "Jabber", "email": "메일"}


def format_contacts(contacts: dict | None, sep: str = " · ") -> str | None:
    if not contacts:
        return None
    parts = []
    for key, values in contacts.items():
        label = CONTACT_LABEL.get(key, key)
        for v in values[:2]:
            parts.append(f"{label}: {v}")
    return sep.join(parts[:6]) if parts else None


def format_crypto(crypto: dict | None, sep: str = " · ") -> str | None:
    if not crypto:
        return None
    parts = [f"{k.upper()}: {v[0]}" for k, v in crypto.items() if v]
    return sep.join(parts[:4]) if parts else None

# --------------------------------------------------------------------------
# 연결된 곳 — 페이지에 박힌 다른 주소
# --------------------------------------------------------------------------
# 페이지가 부르는 외부 도메인 대부분은 폰트·CDN 이라 연결이 아니라 잡음이다.
# 이걸 안 거르면 '연결된 곳' 이 googleapis.com 으로 도배된다.
_INFRA = re.compile(
    r"(googleapis|gstatic|google-analytics|cloudflare|jsdelivr|unpkg|jquery|"
    r"bootstrapcdn|fontawesome|fonts\.|w3\.org|schema\.org|gravatar|"
    r"github(usercontent)?\.com|placeholder|example\.(com|org)|"
    r"mozilla\.org|whatsapp\.com|youtube\.com|twitter\.com|x\.com)", re.I)


def _name_tokens(name: str | None) -> list[str]:
    if not name:
        return []
    raw = re.split(r"[^A-Za-z0-9]+", name.lower())
    return [w for w in raw if len(w) >= 4]


def format_external(domains, name: str | None = None,
                    sep: str = " · ", limit: int = 6) -> tuple[str | None, str]:
    """클리어넷 도메인 목록 → '연결된 곳' 문자열.

    사이트 이름과 겹치는 도메인은 미러일 가능성이 높으므로 따로 표시한다.
    ORVX SHOP 이 orvx.to / orvx.io / orvx.is 를 걸고 있는 식이다.
    """
    if not domains:
        return None, ""
    kept = [d for d in domains if d and not _INFRA.search(d)]
    if not kept:
        return None, ""

    toks = _name_tokens(name)
    mirrors, others = [], []
    for d in kept:
        flat = re.sub(r"[^a-z0-9]", "", d.lower())
        (mirrors if any(t in flat for t in toks) else others).append(d)

    parts = [f"미러 후보: {d}" for d in mirrors[:limit]]
    parts += [f"외부: {d}" for d in others[:max(0, limit - len(parts))]]
    if not parts:
        return None, ""
    why = f"미러 {len(mirrors)}건" if mirrors else f"외부 도메인 {len(others)}건"
    return sep.join(parts), why


# --------------------------------------------------------------------------
# 최근 활동 — 서버가 알려주는 마지막 수정 시각
# --------------------------------------------------------------------------
def last_modified_date(header: str | None) -> tuple[str | None, str]:
    """HTTP Last-Modified 헤더 → YYYY-MM-DD.

    페이지 본문에 날짜가 없어도 서버가 '이 파일 언제 바뀌었다' 를 알려주는
    경우가 많다. 실제로 접속된 사이트의 3분의 1이 여기에만 날짜가 있었다.
    정적 페이지면 배포 시각이라 '갱신이 멈춘 시점' 으로 읽으면 된다.
    """
    if not header:
        return None, ""
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(str(header))
    except (TypeError, ValueError, IndexError):
        return None, ""
    if dt is None:
        return None, ""
    return dt.date().isoformat(), "서버 Last-Modified 헤더"
