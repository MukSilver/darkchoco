# -*- coding: utf-8 -*-
"""나가는 글 지키기 — 피해 조직 이름과 주소가 나가지 않게 한다 (2026-09-29 팀 결정, 2026-09-30 김무근).

정제 배치(darkchoco-data)가 먼저 가린다. 그쪽은 노션의 「대상 조직」, 「조직명」 칸에 적힌 표기만 가리므로
조사 기록 본문에 다르게 적힌 이름과, 주소 머리(https)가 없는 도메인은 남는다. 여기서 한 번 더 가린다.

  도메인   규칙으로 전부 가린다. 장소와 행위자의 이름으로 쓰이는 것(breached.st)만 남긴다
  이름     찾아 둔 이름 목록(scripts/find_names.py)으로 가린다. 장소와 행위자의 이름은 가리지 않는다

쓰는 곳 셋: 조각을 만들 때(scripts/chunk.py), 스냅샷 반출 관문(scripts/snapshot.py), 답을 내보내기 직전(pipeline.py).
"""
import json
import os
import re

from .normalize import has_hangul, norm

NAME_MASK = "(조직명 가림)"
ADDR_MASK = "(주소 가림)"
ALIAS_MASK = "(다른 이름 가림)"

# 주소 머리가 없는 도메인. 앞뒤가 글자나 숫자로 이어지지 않는 것
DOMAIN = re.compile(r"(?<![0-9A-Za-z@._\-])((?:[A-Za-z0-9](?:[A-Za-z0-9\-]*[A-Za-z0-9])?\.)+[A-Za-z]{2,24})(?![0-9A-Za-z_\-]|\.[0-9A-Za-z])")
# 끝이 이것이면 도메인이 아니라 파일 이름이다
FILE_EXT = {"sql", "csv", "txt", "zip", "rar", "gz", "tar", "json", "xml", "xlsx", "xls", "doc", "docx", "pdf", "ppt",
            "pptx", "hwp", "php", "html", "htm", "js", "ts", "py", "exe", "dll", "log", "db", "bak", "png", "jpg",
            "jpeg", "gif", "md", "yml", "yaml", "ini", "conf", "cfg", "dat", "bin", "apk", "iso", "sh", "bat", "asp",
            "aspx", "jsp", "mdb", "sqlite", "pcap", "eml", "msg", "pst", "mp4", "torrent", "env", "pem", "key"}
# 도구나 자리 이름으로 더 많이 쓰이는 플랫폼. 이름 목록에 들어와도 가리지 않는다 (darkchoco-data names.mjs 와 같은 목록)
COMMON_PLATFORMS = ["Discord", "Telegram", "GitHub", "GitLab", "Pastebin", "Twitter", "Facebook", "Instagram", "Meta",
                    "Google", "Microsoft", "Apple", "Amazon", "AWS", "Cisco", "Oracle", "Citrix", "Fortinet", "FortiGate",
                    "Ivanti", "VMware", "Cloudflare", "Snowflake", "Okta", "Salesforce", "ServiceNow", "Signal",
                    "WhatsApp", "YouTube", "TikTok", "Tor", "Tox", "Session", "Jabber", "XMPP", "Monero", "Bitcoin"]
_MARKS = (NAME_MASK, ADDR_MASK, ALIAS_MASK, "(개인정보 가림)")
_MARK_TEXT = " ".join(_MARKS)


def _usable(name, keep):
    """가릴 이름으로 쓸 수 있는가. 가림 표시와 겹치는 것, 너무 짧은 것, 가리면 안 되는 이름은 버린다."""
    n = (name or "").strip() if isinstance(name, str) else ""
    k = norm(n)
    if not k or k in keep:
        return None
    if "가림" in n or n in _MARK_TEXT:          # 「(조직명 가림)」 을 이름으로 넣으면 가린 자리가 다시 걸린다
        return None
    if has_hangul(n):
        if len(k) < 2:
            return None
    elif len(k) < 3:
        return None
    return n


def _patterns(names):
    W = r"[0-9A-Za-z가-힣]"
    out = []
    hangul = [re.escape(n) for n in names if has_hangul(n)]
    latin = [re.escape(n) for n in names if not has_hangul(n)]
    # 한글 이름 뒤에는 조사가 바로 붙으므로 앞 경계만 본다. 영문은 앞뒤를 다 본다
    for i in range(0, len(hangul), 200):
        out.append(re.compile(r"(?<!%s)(?:%s)" % (W, "|".join(hangul[i:i + 200])), re.I))
    for i in range(0, len(latin), 200):
        out.append(re.compile(r"(?<!%s)(?:%s)(?!%s)" % (W, "|".join(latin[i:i + 200]), W), re.I))
    return out


class Guard:
    def __init__(self, names=None, keep=None, hidden=None):
        """names: 가릴 조직 이름. keep: 가리면 안 되는 이름(장소와 행위자의 명칭, 장소의 별칭).
        hidden: 행위자의 다른 이름. 동일인 추정이라 어디에도 내보내지 않는다 (TC-22)."""
        self.keep = {norm(k) for k in list(keep or []) + COMMON_PLATFORMS if norm(k)}

        def pick(src):
            seen, use = set(), []
            for n in src or []:
                n = _usable(n, self.keep)
                if n and norm(n) not in seen:
                    seen.add(norm(n))
                    use.append(n)
            use.sort(key=lambda x: (-len(x), x))          # 긴 이름부터 맞춰 본다
            return use

        self.names = pick(names)
        self.hidden = pick(hidden)
        self._patterns = _patterns(self.names)
        self._hidden = _patterns(self.hidden)

    # ── 도메인 ──
    def _is_domain(self, s):
        last = s.rsplit(".", 1)[-1].lower()
        if last in FILE_EXT:
            return False
        return norm(s) not in self.keep

    def mask_domains(self, text):
        return DOMAIN.sub(lambda m: ADDR_MASK if self._is_domain(m.group(1)) else m.group(0), text)

    def find_domain(self, text):
        for m in DOMAIN.finditer(text or ""):
            if self._is_domain(m.group(1)):
                return m.group(1)
        return None

    # ── 이름 ──
    def mask_names(self, text):
        for p in self._patterns:
            text = p.sub(NAME_MASK, text)
        return text

    def find_name(self, text):
        for p in self._patterns:
            m = p.search(text or "")
            if m:
                return m.group(0)
        return None

    def mask_hidden(self, text):
        for p in self._hidden:
            text = p.sub(ALIAS_MASK, text)
        return text

    # ── 셋 다 ──
    def clean(self, text):
        """글 하나를 가린다. 문자열이 아니면 그대로."""
        if not isinstance(text, str) or not text:
            return text
        out = self.mask_hidden(self.mask_names(self.mask_domains(text)))
        if out == text:
            return text
        for mark in _MARKS:          # 이어진 가림 표시는 하나로
            out = re.sub(r"%s(?:[\s,·/()\-]*%s)+" % (re.escape(mark), re.escape(mark)), mark, out)
        return out

    def clean_value(self, v):
        if isinstance(v, list):
            return [self.clean(x) if isinstance(x, str) else x for x in v]
        return self.clean(v)

    def leaks(self, text):
        """남은 것의 종류 목록. 값은 돌려주지 않는다."""
        if not isinstance(text, str) or not text:
            return []
        out = []
        if self.find_domain(text):
            out.append("도메인")
        if self.find_name(text):
            out.append("조직 이름")
        if any(p.search(text) for p in self._hidden):
            out.append("행위자의 다른 이름")
        return out

    def leak(self, text):
        found = self.leaks(text)
        return found[0] if found else None


def keep_names(docs):
    """가리면 안 되는 이름 — 장소(포럼, 텔레그램, 랜섬웨어)의 명칭과 별칭, 행위자의 명칭.

    행위자의 다른 이름은 넣지 않는다. 동일인 추정이라 가리는 쪽이다 (hidden_names).
    """
    out = []
    for d in docs:
        if d.get("kind") in ("포럼", "텔레그램", "랜섬웨어", "행위자"):
            out.append(d.get("title") or "")
        if d.get("kind") in ("포럼", "텔레그램", "랜섬웨어"):
            out.extend(a for a in (d.get("aliases") or []) if isinstance(a, str))
    # 제목에 붙은 설명은 떼고도 넣는다: 「BreachForums (원본, 2025 압수)」 → BreachForums
    out.extend(re.sub(r"\s*[(（].*$", "", t).strip() for t in list(out))
    # 이름 안에 든 도메인도 넣는다: 「XSS (xss.example)」 의 xss.example
    out.extend(m.group(1) for t in list(out) for m in DOMAIN.finditer(t))
    return [t for t in out if t]


def hidden_names(docs):
    """행위자의 다른 이름. 어느 문서의 명칭과 같은 것은 뺀다 (그 이름은 그 문서의 이름으로 나간다)."""
    titles = {norm(d.get("title")) for d in docs}
    out = []
    for d in docs:
        if d.get("kind") != "행위자":
            continue
        for a in d.get("aliases") or []:
            if isinstance(a, str) and norm(a) and norm(a) not in titles:
                out.append(a)
    return out


def save(path, names, keep, hidden=None):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"names": sorted(set(names)), "keep": sorted(set(keep)), "hidden": sorted(set(hidden or []))},
                  f, ensure_ascii=False)
    os.replace(tmp, path)


def load(path):
    """판 폴더의 guard.json 을 읽는다. 없으면 도메인만 가리는 지킴이를 돌려준다."""
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return Guard(d.get("names"), d.get("keep"), d.get("hidden"))
    except (OSError, ValueError, TypeError):
        return Guard()
