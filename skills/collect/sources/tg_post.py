#!/usr/bin/env python3
"""텔레그램 글 하나를 읽는 공통 자리. 공개 미리보기와 실계정 둘 다 여기를 쓴다.

글 꼴은 **채널마다 다르다.** 실어 나르는 길(웹/API)과는 상관이 없다.
그래서 읽는 자리를 여기 한 곳에 둔다. 채널이 늘면 여기에 꼴을 더한다.

## 지금 아는 꼴 (2026-08-27 실측)

| 꼴 | 어디서 봤나 | 어떻게 생겼나 |
|---|---|---|
| 라벨 | `t.me/osint_cti` | `• Target/Title: 값` 처럼 줄마다 이름과 값 |
| JSON | `t.me/breachdetect` | 글 전체가 `{"Source": …, "Type": …}` |
| 글자만 | 그 밖 | 칸이 없다. 본문만 남긴다 |

**모르는 꼴이 와도 버리지 않는다.** `글자만` 으로 두고 본문을 남긴다.
좁은 꼴이 안 맞으면 넓은 쪽으로 물러나고, 무엇으로 읽었는지 적는다.

## 무력화된 주소를 되돌린다

`breachdetect` 는 도메인을 `example[.]com` 으로 적는다. 49건 중 26건이 그랬다.
그대로 두면 같은 글 판별이 깨진다. 우리 표에는 원래 꼴로 넣는다.
**보여줄 때 무력화하는 것과 저장할 때 무력화하는 것은 다르다.**
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from collect.store import Item  # noqa: E402

# 값 앞에 붙은 이모지를 뗀다. 그대로 두면 이름 대조가 깨진다.
# `👤 OctopusBF` 와 `OctopusBF` 는 다른 글자다
# **코드포인트로 적는다.** 이모지를 문자 그대로 넣으면 옮겨 붙이는 사이에 깨진다.
# 2026-08-27 에 이 자리가 ` -㌀` 라는 범위로 변해 있었다. 공백부터 U+3300 까지라
# ASCII 가 통째로 범위 안에 들어 `A (B)` 가 빈칸이 됐다
LEAD = re.compile(
    r"^[\s\u200d\ufe0f"              # 공백 · ZWJ · 변형 선택자
    r"\u2190-\u27bf\u2b00-\u2bff"    # 화살표와 기타 기호. 경고 표시가 여기다
    r"\U0001F000-\U0001FAFF]+")       # 이모지. 깃발도 이 안이다

LABEL = re.compile(r"^[•\-\*]?\s*([A-Za-z][A-Za-z /_&]{2,30})\s*[:：]\s*(.*)$")
JSONISH = re.compile(r"\{.*\}", re.S)
LINK = re.compile(r"https?://\S{6,}")

# 무력화 표기를 되돌린다. 저장은 원래 꼴로 한다
DEFANG = [("[.]", "."), ("(.)", "."), ("[:]", ":"), ("[/]", "/"),
          ("hxxps://", "https://"), ("hxxp://", "http://"),
          ("hxxps[:]//", "https://"), ("hxxp[:]//", "http://")]


# 값이 통째로 괄호에 싸여 있으면 벗긴다. breachdetect 의 `author` 가
# `" (핸들)"` 꼴로 온다. 50건 중 33건이 그랬다. 벗기지 않으면 이름 대조가 깨진다.
# **가운데 괄호는 안 건드린다.** `A (B)` 는 그대로 둔다
WRAP = re.compile(r"^\(([^()]{1,60})\)$")


def clean(v: str) -> str:
    s = LEAD.sub("", (v or "").strip()).strip()
    m = WRAP.match(s)
    return m.group(1).strip() if m else s


def refang(v: str) -> str:
    """`example[.]com` 을 `example.com` 으로. 없으면 그대로."""
    s = (v or "").strip()
    for a, b in DEFANG:
        s = s.replace(a, b)
    return s


def read_post(text: str) -> tuple[dict, str, str]:
    """칸과 꼴과 못 읽은 사유를 돌려준다.

    JSON 을 먼저 본다. 라벨 정규식이 JSON 을 만나면 아무것도 못 잡기 때문이다."""
    t = (text or "").strip()
    if not t:
        return {}, "빈 글", ""

    m = JSONISH.search(t)
    if m:
        try:
            d = json.loads(m.group(0))
            if isinstance(d, dict) and d:
                return ({str(k).strip().lower(): str(v).strip() for k, v in d.items()},
                        "JSON", "")
        except ValueError as e:
            # 깨진 JSON 이 온다. 버리지 않고 한 단계씩 넓은 쪽으로 물러난다
            note = "JSON 이 깨져 줄 단위로 읽었다: %s" % e
            f = _loose_json(m.group(0))
            if f:
                return f, "JSON(깨짐)", note
            f = _labels(t)
            return f, ("라벨" if f else "글자만"), note

    f = _labels(t)
    # 중괄호로 시작했는데 닫는 짝이 없다. 글이 중간에 잘린 것이다.
    # 버리지 않고 읽히는 만큼 읽되, 잘렸다는 것을 적어 둔다
    note = "중괄호로 시작하는데 닫히지 않았다. 글이 잘렸을 수 있다" if t[:1] == "{" else ""
    return (f, "라벨", note) if f else ({}, "글자만", note)


def _labels(t: str) -> dict:
    out = {}
    for ln in t.split("\n"):
        m = LABEL.match(ln.strip())
        if m:
            out[m.group(1).strip().lower()] = m.group(2).strip()
    return out


# 깨진 JSON 을 줄 단위로 읽는다. 값 안의 따옴표를 안 막고 보내는 채널이 있다
LOOSE = re.compile(r'^\s*"([^"\n]{1,40})"\s*:\s*(.+?),?\s*$', re.M)
TAG = re.compile(r"<[^<>]{1,300}>")


def _loose_json(t: str) -> dict:
    """중괄호 안을 줄마다 `"이름": 값` 으로 읽는다.

    2026-08-27 breachdetect 50건 중 1건이 `Content` 안에 HTML 링크를 그대로
    넣어 따옴표가 짝이 안 맞았다. **채널 잘못이지만 버릴 이유는 아니다.**
    줄 단위로 보면 이름과 값은 멀쩡하다.

    값에 든 HTML 태그는 벗긴다. 우리 표에 태그가 들어갈 자리는 없다."""
    out = {}
    for k, v in LOOSE.findall(t):
        v = v.strip().rstrip(",").strip()
        if len(v) > 1 and v[0] == '"' and v[-1] == '"':
            v = v[1:-1]
        v = TAG.sub("", v).strip()
        if v:
            out[k.strip().lower()] = v
    return out


# 글 종류. **거르는 데 쓰지 않고 표시하는 데만 쓴다.**
# 앞에서부터 맞는 것을 고른다. 칸 이름으로 가르고 이모지로 가르지 않는다.
# 채널이 이모지를 바꾸면 깨지지만 칸 이름은 잘 안 바뀐다
KINDS = [
    ("유출 알림", {"target/title", "threat actor"}, True),
    ("랜섬 피해자", {"victim", "group"}, True),
    ("CVE 알림", {"cve id", "cvss score"}, False),
    ("악성코드 시그니처", {"signature", "file"}, False),
]

# JSON 꼴은 `type` 값 하나로 갈린다 (breachdetect)
BY_TYPE = {
    "data leak": ("유출 알림", True),
    "ransomware": ("랜섬 피해자", True),
    "combolist": ("유출 알림", True),
    "stealer log": ("유출 알림", True),
}

# 우리 수집 표의 `게시 성격` 으로 옮긴다
TO_KIND = {"유출 알림": "확인 못 함", "랜섬 피해자": "랜섬웨어 유출"}


def classify(fields: dict) -> tuple[str, bool | None]:
    t = (fields.get("type") or "").strip().lower()
    if t in BY_TYPE:
        return BY_TYPE[t]
    for name, need, mine in KINDS:
        if need <= set(fields):
            return name, mine
    if t:                       # 모르는 type 이다. 버리지 않고 그대로 적는다
        return "기타(%s)" % t, None
    return "기타", None


# 글 칸을 우리 칸으로. 채널마다 이름이 달라 둘 다 받는다
# **`source` 는 대상 조직이 아니다.** 2026-08-27 breachdetect 50건 실측으로
# `Source` 는 전부 도메인(26)이나 주소(23)였다. 어디서 났는지지 누가 당했는지가 아니다.
# 여기 넣었더니 대상 조직 칸에 출처 도메인이 들어갔다
PICK = {
    "org": ("target/title", "victim", "company", "organization", "target"),
    "actor": ("threat actor", "group", "author", "actor"),
    "country": ("country",),
    "size": ("size", "records", "rows", "data size"),
    "seen": ("detection date", "first seen", "date"),
    "note": ("content", "brief summary", "description", "intel source"),
}


def first(fields: dict, names: tuple) -> str:
    """맞는 첫 칸을 정리해서 돌려준다.

    **무력화 표기를 되돌린다.** 어느 칸에나 올 수 있어서 여기서 한다."""
    for n in names:
        v = fields.get(n)
        if v:
            return refang(clean(v))
    return ""


def title_of(text: str, fields: dict, shape: str) -> str:
    """제목 자리. 꼴마다 다른 데서 온다.

    JSON 꼴은 첫 줄이 `{` 라 쓸모가 없다. 2026-08-27 실측 50건이 전부 그랬다.
    그 꼴에서는 한 줄 요약 칸(`Content`)이 제목 자리에 맞다.

    **`JSON(깨짐)` 도 같이 본다.** 꼴 이름으로 정확히 견주면 새 꼴이 늘 때마다
    이 자리를 잊고 제목이 다시 중괄호가 된다.

    **라벨 꼴은 첫 줄이 채널 머리말이다.** 「🔒 New Ransomware Victim」 처럼
    채널이 글마다 똑같이 붙이는 문구라 제목으로 쓰면 줄이 서로 구분되지 않는다.
    2026-09-22 에 노션에 들어간 텔레그램 19줄이 전부 머리말 셋 중 하나였고,
    그 중 17줄이 같은 문구였다. 칸에 대상 조직이 있으면 그것을 제목으로 쓴다.
    랜섬 소스가 이미 조직명만 제목으로 써서 꼴도 맞는다."""
    if shape.startswith("JSON"):
        for n in ("content", "title", "brief summary", "description"):
            v = fields.get(n)
            if v:
                return refang(clean(v))[:120]
    org = first(fields, PICK["org"])
    if org:
        return org[:120]
    return (text.split("\n")[0] if text else "")[:120]


def origin(links: list, body: str, fields: dict) -> str:
    """원 출처를 찾는다. 집계 채널 주소는 원 출처가 아니다.

    순서는 이렇다. 글 안의 링크 → `source` 칸 → 본문에서 줍기.

    **본문 긁기가 맨 뒤다.** JSON 꼴에서는 본문이 원문 전체라, 먼저 긁으면
    주소 뒤의 따옴표까지 딸려 온다. 칸에 제대로 적혀 있으면 그것이 낫다.
    `source` 칸은 무력화되어 있을 수 있어 되돌린 뒤 본다."""
    for u in links:
        if "t.me/" not in u:
            return refang(u)
    s = refang(fields.get("source", ""))
    if s.startswith("http"):
        return s
    m = LINK.search(body or "")
    if m and "t.me/" not in m.group(0):
        return refang(m.group(0).rstrip('").,。\''))
    return ""


DOMAIN = re.compile(r"^[\w-]+(\.[\w-]+)+$")


def to_item(*, chan: str, src_id: str, text: str, links: list, when: str,
            perma: str, got_by: str, body_via: str) -> Item:
    """글 하나를 항목으로. **두 길이 같은 것을 낸다.**

    공개 미리보기든 실계정이든 여기를 지나므로 표에 같은 꼴로 들어간다."""
    fields, shape, note = read_post(text)
    kind, ours = classify(fields)
    src = origin(links, text, fields)
    org = first(fields, PICK["org"])
    # `source` 칸이 도메인만 적혀 있으면 그것이 원 출처의 자리다
    src_dom = refang(fields.get("source", ""))
    venue = (src.split("/")[2] if src.startswith("http")
             else (src_dom if DOMAIN.match(src_dom) else "t.me/" + chan))
    # 대상이 도메인 꼴이면 도메인 칸에도 넣는다. 아니면 비운다
    org_dom = org if DOMAIN.match(org or "") else ""
    return Item(
        source="telegram",
        src_id=src_id,
        venue=venue,
        venue_kind="forum" if venue != "t.me/" + chan else "telegram",
        actor=first(fields, PICK["actor"]),
        target_org=org,
        target_domain=org_dom,
        title=title_of(text, fields, shape),
        body=text,
        # 집계 채널이 쓴 글이다. 유출 게시글 본문이 아니다
        body_kind="집계 채널 글",
        body_via=body_via,
        posted_at=when,
        # **원 출처는 글 안에 적힌 주소다.** 텔레그램 주소가 아니다
        post_url=src,
        via=["t.me/" + chan],
        claimed_size=first(fields, PICK["size"]),
        country=first(fields, PICK["country"]),
        kind=TO_KIND.get(kind, ""),
        clues={"링크": links[:10]} if links else {},
        raw={"글 종류": kind, "우리 대상": ours, "글 꼴": shape,
             "집계 채널 글 주소": perma,
             "본문 칸": {k: clean(v) for k, v in fields.items()},
             **({"못 읽은 것": note} if note else {})},
        got_by=got_by,
    )
