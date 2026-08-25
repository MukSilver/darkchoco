#!/usr/bin/env python3
"""
Tor 경유 DLS 사이트 메타데이터 수집기 (Kali VM 에서 실행).

수집 항목 — 전부 HTML **하나만** 읽어서 판별합니다. 요청 횟수는 그대로입니다.

  [상태]     접속 여부, HTTP 코드, 응답 시간, 리다이렉트 여부
  [정체성]   <title>, <h1>, meta description, og:site_name, generator, keywords
  [언어]     문자 체계 비율 + 불용어, html lang 속성
  [진입 조건] 캡차·로그인·회원가입·초대코드·가입비·PoW 방어
             ↳ 근거의 '강도'를 함께 남깁니다. 실제 위젯/폼이면 strong,
               단어만 스쳐도 weak. 이래야 나중에 오탐을 걸러낼 수 있습니다.
  [연락 수단] Tox / Session / Telegram / Jabber / 익명 메일 — 행위자 식별 지표
  [암호화폐]  BTC / XMR / ETH 주소
  [링크 구조] 발견된 다른 onion 주소(미러·연관 사이트 후보), 외부 도메인,
             게시물처럼 보이는 링크 '개수'
  [활동 흔적] 페이지에 적힌 가장 최근 날짜, 카운트다운 타이머 유무
  [변경 감지] 본문 지문(해시) — 다음 수집 때 내용이 바뀌었는지 알아냅니다
  [인프라]   Server / X-Powered-By / Last-Modified 헤더

  ※ 피해 기업 이름 같은 유출 데이터 본문은 저장하지 않습니다. 개수만 셉니다.

설계 원칙
---------
1. 브라우저를 쓰지 않습니다. HTML 텍스트만 받으므로 JS 가 실행되지 않고,
   렌더링 엔진 취약점 표면이 없습니다.
2. socks5h 로만 접속합니다 — .onion 이름 해석을 Tor 에게 맡겨 DNS 누출을 막습니다.
3. 시작 전 Tor 경유가 실제로 되는지 확인하고, 안 되면 아무것도 하지 않고 종료합니다.
4. text/html · text/plain 이 아니면 즉시 끊습니다. 유출 데이터 아카이브를
   실수로라도 받지 않기 위한 장치입니다.
5. 응답 본문은 디스크에 저장하지 않습니다. 추출한 메타데이터만 남깁니다.
6. 캡차를 우회하지 않습니다. 존재 여부만 기록합니다 — 그게 '가입 필요' 칼럼의 답입니다.

사용법
------
  sudo apt install tor && sudo systemctl start tor      # 최초 1회
  python3 tor_probe.py targets.csv -o probe.json
  python3 tor_probe.py targets.csv -o probe.json --limit 5 --verbose
  python3 tor_probe.py --selftest                        # Tor 경유만 확인

targets.csv 형식 (dls_fill.py --export-targets 로 생성):
  name,url
  THE MATRIX,https://thematrixstore.at
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import http.client
import json
import os
import random
import re
import socket
import ssl
import sys
import time
import unicodedata
from datetime import datetime, timezone

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except (AttributeError, ValueError):
        pass

# 어느 버전이 도는지 셀프테스트에 찍는다.
# 3회차 때 VM 이 옛 파일로 5시간을 돌았는데 셀프테스트는 그대로 통과했다.
# 파일이 '도는지' 와 '맞는 버전인지' 는 다른 문제다. 크기를 눈으로 비교하는
# 방식은 언젠가 또 틀리므로, 실행이 스스로 자기 버전을 말하게 한다.
VERSION = "3.0 (하위 페이지 크롤링 · VM 내 판정 포함)"

MAX_BYTES = 1_500_000          # 응답 본문 상한
OK_TYPES = ("text/html", "text/plain", "application/xhtml")


# --------------------------------------------------------------------------
# SOCKS5 (socks5h) — 표준 라이브러리만으로 구현
# --------------------------------------------------------------------------
class SocksError(RuntimeError):
    pass


def socks5_connect(proxy_host: str, proxy_port: int,
                   dest_host: str, dest_port: int, timeout: float) -> socket.socket:
    """Tor SOCKS5 프록시에 도메인 이름을 그대로 넘겨 터널을 연다(=socks5h)."""
    s = socket.create_connection((proxy_host, proxy_port), timeout=timeout)
    s.settimeout(timeout)
    try:
        s.sendall(b"\x05\x01\x00")                  # VER=5, 방식1개, NOAUTH
        rep = s.recv(2)
        if len(rep) < 2 or rep[0] != 5 or rep[1] != 0:
            raise SocksError(f"SOCKS5 인증 협상 실패: {rep!r}")

        host_b = dest_host.encode("idna") if all(ord(c) < 128 for c in dest_host) \
            else dest_host.encode("utf-8")
        if len(host_b) > 255:
            raise SocksError("호스트 이름이 너무 깁니다")
        # CMD=CONNECT, ATYP=3(도메인) → 이름 해석을 Tor 가 담당
        s.sendall(b"\x05\x01\x00\x03" + bytes([len(host_b)]) + host_b
                  + dest_port.to_bytes(2, "big"))

        rep = s.recv(4)
        if len(rep) < 4:
            raise SocksError("SOCKS5 응답이 짧습니다")
        code = rep[1]
        if code != 0:
            raise SocksError({
                1: "일반 실패", 2: "규칙상 거부", 3: "네트워크 도달 불가",
                4: "호스트 도달 불가", 5: "연결 거부", 6: "TTL 만료",
                7: "지원하지 않는 명령", 8: "지원하지 않는 주소 형식",
            }.get(code, f"코드 {code}"))
        atyp = rep[3]
        n = {1: 4, 4: 16}.get(atyp)
        if n is None:                                # 도메인
            n = s.recv(1)[0]
        s.recv(n)
        s.recv(2)                                    # 포트
        return s
    except Exception:
        s.close()
        raise


class SocksHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host, port=None, *, proxy, timeout=30):
        super().__init__(host, port, timeout=timeout)
        self._proxy = proxy

    def connect(self):
        self.sock = socks5_connect(self._proxy[0], self._proxy[1],
                                   self.host, self.port, self.timeout)


class SocksHTTPSConnection(SocksHTTPConnection):
    default_port = 443

    def connect(self):
        raw = socks5_connect(self._proxy[0], self._proxy[1],
                             self.host, self.port, self.timeout)
        ctx = ssl.create_default_context()
        self.sock = ctx.wrap_socket(raw, server_hostname=self.host)


# --------------------------------------------------------------------------
# HTTP GET
# --------------------------------------------------------------------------
def split_url(url: str) -> tuple[str, str, int, str]:
    u = url.strip()
    scheme = "http"
    if u.startswith("https://"):
        scheme, u = "https", u[8:]
    elif u.startswith("http://"):
        u = u[7:]
    hostport, _, path = u.partition("/")
    path = "/" + path
    host, _, port_s = hostport.partition(":")
    port = int(port_s) if port_s.isdigit() else (443 if scheme == "https" else 80)
    return scheme, host, port, path or "/"


def _first_cookie(header: str | None) -> str | None:
    """Set-Cookie 에서 'name=value' 부분만. 대기 화면 통과용으로만 쓰고
    결과 파일에는 절대 기록하지 않는다."""
    if not header:
        return None
    return header.split(";", 1)[0].strip() or None


def fetch(url: str, proxy, timeout: float, max_redirects: int = 3,
          cookie: str | None = None, max_bytes: int | None = None) -> dict:
    """HTML 만 받아온다. 반환: {ok, status, final_url, title_raw, html, error}

    cookie 는 대기 화면(DDoS-guard 류)이 준 쿠키를 물고 재요청할 때 쓴다.
    max_bytes 로 하위 페이지는 더 짧게 끊는다.
    """
    seen = set()
    for _ in range(max_redirects + 1):
        if url in seen:
            return {"ok": False, "error": "리다이렉트 순환", "final_url": url}
        seen.add(url)
        scheme, host, port, path = split_url(url)
        cls = SocksHTTPSConnection if scheme == "https" else SocksHTTPConnection
        conn = None
        try:
            conn = cls(host, port, proxy=proxy, timeout=timeout)
            _headers = {
                "Host": host,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:128.0) Gecko/20100101 Firefox/128.0",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
                "Connection": "close",
            }
            if cookie:
                _headers["Cookie"] = cookie
            conn.request("GET", path, headers=_headers)
            resp = conn.getresponse()
            status = resp.status

            if status in (301, 302, 303, 307, 308):
                loc = resp.getheader("Location") or ""
                if not loc:
                    return {"ok": False, "status": status,
                            "error": "리다이렉트 대상 없음", "final_url": url}
                if loc.startswith("/"):
                    loc = f"{scheme}://{host}:{port}{loc}" if port not in (80, 443) \
                        else f"{scheme}://{host}{loc}"
                url = loc
                continue

            ctype = (resp.getheader("Content-Type") or "").lower()
            if ctype and not any(t in ctype for t in OK_TYPES):
                # HTML 이 아니면 본문을 받지 않고 끊는다 (아카이브 방지)
                return {"ok": True, "status": status, "final_url": url,
                        "html": "", "content_type": ctype,
                        "note": "HTML 아님 — 본문 수신 생략"}

            raw = resp.read(max_bytes or MAX_BYTES)
            charset = "utf-8"
            m = re.search(r"charset=([\w\-]+)", ctype)
            if m:
                charset = m.group(1)
            html = raw.decode(charset, "replace")
            if charset == "utf-8":
                m2 = re.search(r'charset=["\']?([\w\-]+)', html[:2000], re.I)
                if m2 and m2.group(1).lower() not in ("utf-8", "utf8"):
                    html = raw.decode(m2.group(1), "replace")
            return {"ok": True, "status": status, "final_url": url,
                    "html": html, "content_type": ctype, "bytes": len(raw),
                    "server": resp.getheader("Server"),
                    "powered_by": resp.getheader("X-Powered-By"),
                    "last_modified": resp.getheader("Last-Modified"),
                    # 기록용은 불리언, 재요청용은 값 자체.
                    # 쿠키 값은 rec 에 담지 않는다 — 세션 토큰이 결과 파일에
                    # 남으면 그 자체가 유출이다.
                    "set_cookie": bool(resp.getheader("Set-Cookie")),
                    "cookie": _first_cookie(resp.getheader("Set-Cookie"))}
        except SocksError as e:
            return {"ok": False, "error": f"Tor 연결: {e}", "final_url": url}
        except (socket.timeout, TimeoutError):
            return {"ok": False, "error": "시간 초과", "final_url": url}
        except ssl.SSLError as e:
            return {"ok": False, "error": f"TLS: {e}", "final_url": url}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": f"{e.__class__.__name__}: {e}",
                    "final_url": url}
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:  # noqa: BLE001
                    pass
    return {"ok": False, "error": "리다이렉트 한도 초과", "final_url": url}


# --------------------------------------------------------------------------
# HTML 분석
# --------------------------------------------------------------------------
_TAG = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)
_TAGS = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


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


# 진입 조건 탐지 — 존재 여부만 본다. 통과 시도는 하지 않는다.
#
# strength 가 핵심이다. HTML 아무 데나 "captcha" 라는 단어가 있다고 캡차가
# 걸린 게 아니다. 실제 위젯(recaptcha/hcaptcha/turnstile 스크립트)이나
# 입력 폼이 있어야 'strong' 이고, 단어만 있으면 'weak' 으로 남긴다.
# 이렇게 해야 나중에 오탐을 걸러낼 수 있다.
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


# --------------------------------------------------------------------------
# 페이지에서 뽑아낼 수 있는 나머지 — 같은 HTML 하나로 전부 처리한다
# --------------------------------------------------------------------------
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


# 위협 행위자 식별에 쓰이는 연락 수단. 값 자체가 CTI 지표라 저장한다.
CONTACT = {
    "tox":      r"\b[A-F0-9]{76}\b",
    "session":  r"\b05[a-f0-9]{64}\b",
    "telegram": r"(?:t\.me/|telegram(?:\.me)?[:/@\s]{1,3})([A-Za-z0-9_]{5,32})",
    "jabber":   r"\b[\w.\-]{2,32}@(?:jabber|xmpp|exploit|thesecure)[\w.\-]*\.[a-z]{2,}\b",
    "email":    r"\b[\w.\-]{2,40}@(?:protonmail|proton|tutanota|onionmail|cock|"
                r"mail2tor|dnmx|elude|riseup)\.[a-z.]{2,10}\b",
    "qtox":     r"\btox\s*(?:id)?\s*[:=]\s*([A-F0-9]{76})\b",
}
# t.me/<이것들> 은 텔레그램 자체 경로지 사용자 핸들이 아니다.
# 2회차에서 'Telegram: Contact', 'Telegram: Messenger', 'Telegram: channel'
# 같은 값이 33건 중 8건이나 섞여 나왔다.
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


# --------------------------------------------------------------------------
# 하위 페이지 크롤링 (3회차 신규)
# --------------------------------------------------------------------------
# 2회차에서 접속된 124곳 중 56곳이 첫 화면에 200자도 없었다. FREDDY 는 링크
# 25개에 본문 0자였다 — 내용이 한 클릭 뒤에 있는데 안 들어가고 있었다.
#
# 안전 규칙 (하나라도 어기면 설계가 무너진다)
#   * 같은 onion 호스트 안의 링크만 따라간다. 다른 onion 도 클리어넷도 안 간다.
#   * 깊이 1단계. 하위 페이지에서 또 링크를 타지 않는다.
#   * 아카이브 확장자는 링크 단계에서 거른다. Content-Type 필터는 그대로 두되,
#     하위 페이지는 .zip/.7z 링크가 훨씬 많으므로 한 겹 더 막는다.
#   * 가입·로그인 벽이 있는 사이트는 들어가지 않는다.
SUB_MAX_BYTES = 512_000

# 대기·검사 화면. 2회차에서 7곳이 여기 걸려 제목이 'Loading...' 으로 남았다.
INTERSTITIAL = re.compile(
    r"loading|one moment|just a moment|please wait|access queue|"
    r"checking your browser|ddos|подожд", re.I)

# 피해자 목록·게시물이 있을 법한 경로
_SUB_GOOD = re.compile(
    r"/(victims?|leaks?|leaked|posts?|blog|news|archive|all|companies|clients|"
    r"targets?|data|disclosures?|publications?|contacts?|about|shop|products?)"
    r"(/|\?|$)", re.I)
# 링크 글자에 이런 말이 있으면 내용 페이지일 가능성이 높다
_SUB_TEXT = re.compile(
    r"(victim|leak|post|news|blog|archive|compan|client|target|data|"
    r"disclosure|product|contact|about|피해|유출|게시)", re.I)
# 받으면 안 되는 것 — 유출물 아카이브와 미디어
_SUB_BAD = re.compile(
    r"\.(zip|7z|rar|tar|t?gz|bz2|torrent|iso|exe|dll|bin|sql|db|csv|xlsx?|"
    r"docx?|pptx?|pdf|jpe?g|png|gif|webp|svg|bmp|mp4|avi|mkv|mp3|wav)"
    r"(\?|#|$)", re.I)
_SUB_SKIP_SCHEME = re.compile(r"^\s*(mailto:|javascript:|tel:|data:|#)", re.I)


def pick_subpages(html: str, base_url: str, base_host: str,
                  limit: int = 3) -> list[str]:
    """랜딩 페이지에서 읽어볼 하위 경로를 고른다 (같은 호스트 한정)."""
    scheme, host, port, _ = split_url(base_url)
    root = f"{scheme}://{host}" + (f":{port}" if port not in (80, 443) else "")

    # href 와 링크 글자를 같이 뽑아 점수를 매긴다
    pairs = re.findall(
        r"""<a[^>]+href=["']([^"'\s>]{1,300})["'][^>]*>(.{0,120}?)</a>""",
        html[:300000], re.I | re.S)

    scored: list[tuple[int, str]] = []
    seen: set[str] = set()
    for href, label in pairs:
        href = href.strip()
        if not href or _SUB_SKIP_SCHEME.match(href) or _SUB_BAD.search(href):
            continue

        if href.startswith("//"):
            full = f"{scheme}:{href}"
        elif href.startswith("http"):
            full = href
        elif href.startswith("/"):
            full = root + href
        else:
            full = root + "/" + href.lstrip("./")

        _, h2, _, path = split_url(full)
        if h2.lower() != base_host.lower():
            continue                      # 다른 호스트로는 절대 안 간다
        if path in ("", "/") or full in seen:
            continue
        seen.add(full)

        score = 0
        if _SUB_GOOD.search(path):
            score += 2
        if _SUB_TEXT.search(_TAGS.sub(" ", label)):
            score += 1
        scored.append((score, full))

    scored.sort(key=lambda x: -x[0])
    return [u for _, u in scored[:limit]]


def merge_indicators(base: dict, extra: dict) -> None:
    """하위 페이지에서 얻은 지표를 랜딩 결과에 합친다."""
    for key in ("contacts", "crypto"):
        if not extra.get(key):
            continue
        dst = base.setdefault(key, {})
        for k, vals in extra[key].items():
            cur = dst.setdefault(k, [])
            for v in vals:
                if v not in cur and len(cur) < 3:
                    cur.append(v)
    for key, cap in (("onion_links", 20), ("external_domains", 15)):
        if not extra.get(key):
            continue
        cur = base.setdefault(key, [])
        for v in extra[key]:
            if v not in cur and len(cur) < cap:
                cur.append(v)
    base["onion_link_count"] = len(base.get("onion_links") or [])
    for key in ("listing_link_count", "link_count"):
        if extra.get(key):
            base[key] = (base.get(key) or 0) + extra[key]
    for key in ("has_pgp", "countdown", "mirror_mentioned"):
        if extra.get(key):
            base[key] = True
    d = extra.get("latest_date_on_page")
    if d and d > (base.get("latest_date_on_page") or ""):
        base["latest_date_on_page"] = d


# --------------------------------------------------------------------------
# VM 안에서 판정 끝내기 (3회차 신규)
# --------------------------------------------------------------------------
# 추론기가 본문을 봐야 정확해지는데, 본문을 probe.json 에 담으면 피해 기업
# 이름이 호스트로 넘어온다. 지금까지 지켜온 "유출 대상은 저장하지 않는다"
# 원칙이 깨진다.
#
# 그래서 뒤집는다 — 판정을 VM 안에서 끝내고 결과만 내보낸다.
# 본문은 이 프로세스 메모리에만 존재하고 디스크에 닿지 않는다.
# 내보내는 근거 문자열은 '매칭된 키워드 자체' 뿐이고 40자로 잘린다.
try:
    import infer as _infer
except ImportError:      # infer.py 를 같이 안 올린 경우 — 판정만 건너뛴다
    _infer = None

INFER_TEXT_CAP = 200_000


def infer_in_vm(rec: dict, body_text: str) -> None:
    """본문까지 넣어 형식·개인정보·유통자리를 판정하고 힌트만 rec 에 남긴다."""
    if _infer is None or not body_text:
        return
    text = body_text[:INFER_TEXT_CAP]
    kind = ""     # VM 은 API 종류를 모른다. 호스트가 나중에 다시 판단한다.

    fmt, why = _infer.infer_format(
        kind, None, rec.get("title"), rec.get("keywords"),
        rec.get("h1"), text, rec.get("name"))
    if fmt:
        rec["format_hint"] = fmt
        rec["format_why"] = why[:60]

    pii, why = _infer.infer_pii(
        kind, None, rec.get("title"), rec.get("keywords"), text, fmt)
    if pii:
        rec["pii_hint"] = pii
        rec["pii_why"] = why[:60]

    dist, why = _infer.infer_distribution(
        kind, None, rec.get("title"), text,
        bool(rec.get("countdown")), rec.get("listing_link_count") or 0)
    if dist:
        rec["dist_hint"] = dist
        rec["dist_why"] = why[:60]

    # 러시아어 마켓처럼 본문에만 언어 단서가 있는 경우가 있다
    rec["infer_text_len"] = len(text)


# --------------------------------------------------------------------------
# Tor 경유 확인
# --------------------------------------------------------------------------
# .onion 주소는 Tor 를 거치지 않으면 이름 해석 자체가 불가능하다.
# 따라서 onion 에 닿는다는 것은 Tor 경유의 가장 확실한 증거다.
TOR_ONION = ("http://2gzyxa5ihm7nsggfxnu52rck2vv4rvmdlkiu3zzui5du4xyclen53wid.onion/",
             "Tor Project 공식 onion")


def _check_chain(proxy, timeout: float, verbose: bool = False):
    """(성공여부, 설명) — 여러 방법을 순서대로 시도한다."""
    # 1) HTML 안내 페이지 (2026년 현재 /api/ip 는 404 라 이쪽이 주 경로)
    r = fetch("https://check.torproject.org/", proxy, timeout)
    if r.get("ok") and r.get("html"):
        h = r["html"]
        if "not appear to be using Tor" in h:
            return False, "Tor 를 쓰지 않는다고 응답함"
        if "Congratulations" in h and "configured to use Tor" in h:
            return True, "check.torproject.org 안내 페이지 확인"
    elif verbose:
        print(f"      (안내 페이지 실패: {r.get('error')})")

    # 2) JSON API — 예전 엔드포인트. 되살아나면 출구 IP 까지 알 수 있다.
    r = fetch("https://check.torproject.org/api/ip", proxy, timeout)
    if r.get("ok") and r.get("html"):
        try:
            info = json.loads(r["html"])
            if info.get("IsTor") is True:
                return True, f"출구 IP {info.get('IP')}"
            return False, f"IsTor=false (응답: {info})"
        except Exception:  # noqa: BLE001
            if verbose:
                print(f"      (api/ip 응답이 JSON 아님: {r['html'][:80]!r})")

    # 3) .onion 도달 — Tor 없이는 이름 해석조차 안 되므로 가장 확실한 증거
    r = fetch(TOR_ONION[0], proxy, timeout)
    if r.get("ok"):
        return True, f"{TOR_ONION[1]} 접속 성공 (onion 은 Tor 없이 접속 불가)"
    return False, f"모든 확인 방법 실패 (마지막 오류: {r.get('error')})"


def tor_alive(proxy, timeout: float) -> bool:
    """수집 도중 쓰는 조용한 재확인."""
    ok, _ = _check_chain(proxy, timeout)
    return ok


def selftest(proxy, timeout: float) -> bool:
    print(f"[버전] tor_probe {VERSION}")
    print(f"  infer.py 판정: {'사용 가능' if _infer else '없음 — 본문 판정을 건너뜁니다'}")
    print(f"[확인] Tor SOCKS 프록시 {proxy[0]}:{proxy[1]}")
    try:
        s = socket.create_connection(proxy, timeout=5)
        s.close()
        print("  [O] 프록시 포트 열려 있음")
    except Exception as e:  # noqa: BLE001
        print(f"  [X] 프록시에 붙지 못했습니다: {e}")
        print("      sudo systemctl start tor   (Kali: apt install tor)")
        print("      Tor Browser 를 쓰면 포트가 9150 입니다 → --proxy-port 9150")
        return False

    print("[확인] Tor 네트워크 경유 여부")
    ok, why = _check_chain(proxy, timeout, verbose=True)
    if ok:
        print(f"  [O] Tor 경유 확인 — {why}")
        return True
    print(f"  [X] 확인 실패 — {why}")
    print("      Tor 부팅 직후면 회로가 준비되기까지 30초쯤 걸립니다.")
    print("      sudo systemctl restart tor 후 잠시 뒤 다시 시도해 보세요.")
    return False


# --------------------------------------------------------------------------
# 메인
# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="Tor 경유 DLS 메타데이터 수집")
    ap.add_argument("targets", nargs="?", help="name,url 칼럼을 가진 CSV")
    ap.add_argument("-o", "--out", default="probe.json", help="결과 JSON 경로")
    ap.add_argument("--proxy-host", default="127.0.0.1")
    ap.add_argument("--proxy-port", type=int, default=9050,
                    help="tor 데몬 9050 / Tor Browser 9150")
    ap.add_argument("--timeout", type=float, default=60.0,
                    help="요청 타임아웃(초). 죽은 onion 이 많으면 25 정도로 낮추면 빨라집니다")
    ap.add_argument("--delay", type=float, default=3.0,
                    help="요청 간 대기 초 (지터 포함)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--retries", type=int, default=1, help="실패 시 재시도 횟수")
    ap.add_argument("--selftest", action="store_true", help="Tor 경유만 확인하고 종료")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--skip-selftest", action="store_true",
                    help="(권장하지 않음) Tor 확인을 건너뜀")
    ap.add_argument("--recheck-every", type=int, default=25, metavar="N",
                    help="N건마다 Tor 경유를 재확인 (0이면 끔)")
    ap.add_argument("--fail-streak", type=int, default=5, metavar="N",
                    help="연속 N건 실패하면 Tor 를 재확인하고, 끊겼으면 중단")
    ap.add_argument("--subpages", type=int, default=3, metavar="N",
                    help="사이트당 읽을 하위 페이지 수 (0 이면 랜딩만). "
                         "같은 onion 안, 깊이 1단계, 가입벽 있으면 건너뜀")
    ap.add_argument("--resume", action="store_true",
                    help="기존 결과 파일에 있는 항목은 건너뛰고 이어서 수집")
    args = ap.parse_args()

    proxy = (args.proxy_host, args.proxy_port)

    if args.selftest:
        return 0 if selftest(proxy, args.timeout) else 1

    if not args.targets:
        ap.error("targets CSV 경로가 필요합니다 (또는 --selftest)")

    if not args.skip_selftest:
        if not selftest(proxy, args.timeout):
            print("\n[중단] Tor 경유가 확인되지 않아 수집을 시작하지 않았습니다.")
            return 1
        print()

    with open(args.targets, encoding="utf-8-sig", newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if (r.get("url") or "").strip()]
    results = []
    if args.resume and os.path.exists(args.out):
        try:
            with open(args.out, encoding="utf-8") as fh:
                prev = json.load(fh)
            # 신뢰할 수 없는 구간은 버리고 다시 시도한다
            results = [r for r in prev if not r.get("unreliable")]
            done = {r.get("name") for r in results}
            before = len(rows)
            rows = [r for r in rows if (r.get("name") or "").strip() not in done]
            print(f"[이어하기] 이미 {len(results)}개 완료 — "
                  f"{before}개 중 {len(rows)}개 남음")
        except Exception as exc:  # noqa: BLE001
            print(f"[!] 기존 결과를 읽지 못해 처음부터 시작합니다: {exc}")
            results = []

    if args.limit:
        rows = rows[:args.limit]
    print(f"[대상] {len(rows)}개\n")

    if not rows:
        print("처리할 대상이 없습니다. (--resume 로 이미 전부 완료)")
        return 0

    t0 = time.time()
    base = len(results)   # 이어하기로 이미 끝난 건수
    streak = 0        # 연속 실패 횟수
    aborted = False
    for i, row in enumerate(rows, 1):
        # 주기적 재확인 — Tor 가 도중에 죽으면 남은 사이트가 전부 offline 로
        # 잘못 기록되는 것을 막는다. (IP 노출이 아니라 데이터 오염이 문제)
        if args.recheck_every and i > 1 and (i - 1) % args.recheck_every == 0:
            if not tor_alive(proxy, args.timeout):
                print(f"\n[중단] {i - 1}건 처리 후 Tor 경유가 끊겼습니다.")
                aborted = True
                break
            print(f"  [Tor] {i - 1}건 시점 경유 확인 OK")

        name = (row.get("name") or "").strip()
        url = (row.get("url") or "").strip()
        if not url.startswith("http"):
            url = "http://" + url

        rec = {"name": name, "url": url,
               "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        t_start = time.time()

        r = {}
        for attempt in range(args.retries + 1):
            r = fetch(url, proxy, args.timeout)
            if r.get("ok"):
                break
            if attempt < args.retries:
                time.sleep(args.delay)

        if r.get("ok"):
            html = r.get("html", "")
            text = visible_text(html)
            lang, why = detect_language(html, text)
            gate = detect_gate(html, text)
            reachable = 200 <= r["status"] < 400
            base_host, _ = (split_url(r.get("final_url") or url)[1].lower(), None)

            rec.update({
                "reachable": reachable,
                "status": "online" if reachable else "offline",
                "http_status": r["status"],
                "final_url": r.get("final_url"),
                "redirected": (r.get("final_url") or url) != url,
                "elapsed_ms": int((time.time() - t_start) * 1000),
                "title": get_title(html),
                "language": lang,
                "language_basis": why,
                "text_length": len(text),
                "body_bytes": r.get("bytes"),
                "content_type": r.get("content_type"),
                # 다음 수집 때 '내용이 바뀌었는지' 를 본문 저장 없이 알아내는 지문
                "content_hash": hashlib.sha256(
                    _WS.sub(" ", text).strip().encode("utf-8", "replace")).hexdigest()[:16],
                "server": r.get("server"),
                "powered_by": r.get("powered_by"),
                "last_modified": r.get("last_modified"),
                "sets_cookie": r.get("set_cookie"),
            })
            rec.update(gate)
            rec.update(meta_tags(html))
            rec.update(extract_indicators(html, text, base_host))
            if r.get("note"):
                rec["note"] = r["note"]

            # --- 대기 화면이면 쿠키를 물고 한 번 더 ---
            if INTERSTITIAL.search(rec.get("title") or ""):
                time.sleep(5)
                r2 = fetch(url, proxy, args.timeout,
                           cookie=r.get("cookie"))
                h2 = r2.get("html", "") if r2.get("ok") else ""
                if h2 and not INTERSTITIAL.search(get_title(h2)):
                    t2 = visible_text(h2)
                    lang2, why2 = detect_language(h2, t2)
                    html, text = h2, t2
                    base_host = split_url(r2.get("final_url") or url)[1].lower()
                    rec.update({"title": get_title(h2), "language": lang2,
                                "language_basis": why2, "text_length": len(t2),
                                "passed_interstitial": True})
                    rec.update(detect_gate(h2, t2))
                    rec.update(meta_tags(h2))
                    rec.update(extract_indicators(h2, t2, base_host))

            # --- 하위 페이지 한 겹 ---
            # 가입벽 뒤로는 들어가지 않는다. 존재만 기록한다.
            body_text = text
            if (args.subpages and reachable and not rec.get("signup_required")):
                subs = pick_subpages(html, r.get("final_url") or url,
                                     base_host, args.subpages)
                read = []
                for su in subs:
                    time.sleep(args.delay * 0.5)
                    rs = fetch(su, proxy, args.timeout,
                               max_bytes=SUB_MAX_BYTES)
                    if not rs.get("ok") or not rs.get("html"):
                        continue
                    st = visible_text(rs["html"])
                    merge_indicators(rec, extract_indicators(
                        rs["html"], st, base_host))
                    body_text += "\n" + st
                    read.append(split_url(su)[3][:60])
                if read:
                    rec["subpages"] = read
                    rec["subpage_count"] = len(read)

            # --- 본문까지 넣어 VM 안에서 판정 (본문은 내보내지 않는다) ---
            infer_in_vm(rec, body_text)
        else:
            rec.update({
                "reachable": False,
                "status": "offline",
                "error": r.get("error"),
                "final_url": r.get("final_url"),
            })

        results.append(rec)

        # 연속 실패가 쌓이면 사이트 문제인지 Tor 문제인지 가른다
        if rec.get("reachable"):
            streak = 0
        else:
            streak += 1
            if args.fail_streak and streak >= args.fail_streak:
                print(f"  [!] 연속 {streak}건 실패 — Tor 상태를 확인합니다…")
                if not tor_alive(proxy, args.timeout):
                    print(f"\n[중단] Tor 경유가 끊겼습니다. "
                          f"최근 {streak}건의 'offline' 판정은 신뢰할 수 없습니다.")
                    for r_ in results[-streak:]:
                        r_["status"] = "미확인"
                        r_["unreliable"] = "Tor 끊김 구간"
                    aborted = True
                    break
                print("  [Tor] 경유 정상 — 사이트 쪽 문제로 판단하고 계속합니다")
                streak = 0

        if args.verbose or i % 10 == 0 or i == len(rows):
            el = time.time() - t0
            mark = "O" if rec.get("reachable") else "X"
            extra = ""
            if rec.get("reachable"):
                extra = f" | {rec.get('title', '')[:34]} | {rec.get('language') or '언어?'}"
                extra += f" | {rec.get('how_to_enter', '')[:34]}"
                bits = []
                if rec.get("onion_link_count"):
                    bits.append(f"onion+{rec['onion_link_count']}")
                if rec.get("contacts"):
                    bits.append("연락처:" + ",".join(rec["contacts"]))
                if rec.get("crypto"):
                    bits.append("지갑:" + ",".join(rec["crypto"]))
                if rec.get("latest_date_on_page"):
                    bits.append(rec["latest_date_on_page"])
                if bits:
                    extra += " | " + " ".join(bits)
            else:
                extra = f" | {rec.get('error', '')[:50]}"
            print(f"  [{i}/{len(rows)}] {mark} {name[:26]:<26}{extra}")
            if i % 10 == 0:
                eta = el / i * (len(rows) - i)
                print(f"      … 경과 {el:.0f}s / 남은 예상 {eta:.0f}s")

        # 결과를 매 건마다 저장 — 중간에 끊겨도 잃지 않는다
        tmp = args.out + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(results, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, args.out)

        if i < len(rows):
            time.sleep(args.delay + random.uniform(0, args.delay * 0.5))

    # 결과 저장 (중단된 경우에도 여기까지의 내용은 남긴다)
    tmp = args.out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, args.out)

    on = sum(1 for r in results if r.get("reachable"))
    gate = sum(1 for r in results if r.get("signup_required"))
    lang = sum(1 for r in results if r.get("language"))
    print(f"\n{'=' * 60}")
    if aborted:
        print(f"[중단됨] {len(results)}/{len(rows)}건까지만 처리했습니다.")
        print("  Tor 를 되살린 뒤 남은 대상만 다시 돌리세요:")
        print("    sudo systemctl restart tor   (또는 Tor Browser 재연결)")
        # 파일명을 하드코딩해두면 다음 회차에 엉뚱한 파일을 덮어쓴다
        print(f"    python3 tor_probe.py {os.path.basename(args.targets)}"
              f" -o {os.path.basename(args.out)} --resume")
        print("  status='미확인' 으로 표시된 항목은 노션에 반영되지 않습니다.\n")
    print(f"완료 — {len(results)}개 중 접속 가능 {on}개 / 불가 {len(results) - on}개")
    print(f"  가입·로그인 필요로 판정: {gate}개")
    print(f"  언어 판별 성공:        {lang}개")
    print(f"  캡차(확실):           {sum(1 for r in results if r.get('captcha_confidence')=='strong')}개")
    print(f"  캡차(약한 근거):       {sum(1 for r in results if r.get('captcha_confidence')=='weak')}개")
    print(f"  새 onion 링크 발견:    "
          f"{sum(r.get('onion_link_count', 0) for r in results)}개 "
          f"({sum(1 for r in results if r.get('onion_link_count'))}개 사이트)")
    print(f"  연락 수단 발견:        {sum(1 for r in results if r.get('contacts'))}개")
    print(f"  암호화폐 주소 발견:     {sum(1 for r in results if r.get('crypto'))}개")
    print(f"  페이지 내 날짜 확인:    {sum(1 for r in results if r.get('latest_date_on_page'))}개")
    print(f"  결과: {args.out}")
    print("\n이 파일을 호스트로 옮긴 뒤:")
    print(f"  python dls_fill.py --probe {os.path.basename(args.out)} --report r.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
