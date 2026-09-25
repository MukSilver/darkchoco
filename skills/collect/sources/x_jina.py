#!/usr/bin/env python3
"""X(트위터) CTI 계정의 글을 Jina Reader 로 읽어 수집 표로 바꾼다. (2026-09-26 최현서 결정)

    python -m collect.sources.x_jina --db data/darkchoco.db
    python -m collect.sources.x_jina --dry

## 왜 이 길인가

조사 보고서 `프젝/02_리서치/X수집_조사_20260926.md` 를 본다. 줄이면 이렇다.

    X 에서만 나오는 한국 대상 포럼 판매 · 유출 알림   주 1건 안팎. 거의 한 계정(DailyDarkWeb)
    키 없는 Jina                                  x.com 이 익명 사용자 전체에 1시간씩 막힌다. 못 쓴다
    무료 · 계정 없는 다른 길                        오늘 기준 없다

그래서 **최현서가 받은 Jina 키로, 좁은 계정 목록만, 6시간마다** 읽는다. X 이용약관의
스크래핑 금지 조항과 Jina 무료 토큰의 비상업 조건은 최현서가 감수하기로 했다.

## 한 판에 무엇을 부르나

    계정마다 프로필 1쪽                  글 다섯 건 안팎. 글마다 약 250자에서 잘려 온다
    한국 신호가 있는 글만 단건 1번 더     전문과 게시 시각을 받는다

한국 신호가 없는 글은 잘린 글 그대로 넣고 raw 에 「잘린 글」 이라고 적는다. 모든 글을 단건으로
다시 받으면 토큰과 요청이 다섯 배가 된다. 수집 DB 는 한국 건만 올린다(`push.py --kr`).

## 무엇을 안 하나

- **로그에 계정 이름 · 제목 · 본문 · Jina 오류 문구를 안 찍는다.** 레포와 Actions 로그가 공개다.
  오류 문구에는 제3자 X 계정 주소가, 잔액 부족일 때는 우리 계정 id 가 들어 있다. 건수와 오류
  **이름**만 찍는다
- 이미지 파일을 안 받는다. 글에 이미지 주소가 있어도 부르지 않는다(샘플 개인정보가 있을 수 있다)
- `X-Set-Cookie`(팀 X 세션을 넘김) · `X-Proxy`(차단 우회) · 다른 지역 주소로 돌리기를 안 쓴다
- 키와 계정 목록은 **저장소 밖 파일**에서만 읽는다. 값을 찍지 않는다

## 이 계정은 원 출처가 아니다

집계 계정이다. X 글 주소는 raw 「X 글 주소」 에만 두고 `post_url` 은 비운다. 글 안의 링크는 대개
피해 조직 사이트라 원 출처로 쓰지 않는다. 원 포럼은 사람이 검토하며 적는다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterator

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from collect.fetch import Blocked, Fetcher  # noqa: E402
from collect.sources import tg_post  # noqa: E402
from collect.store import Item, Store  # noqa: E402

VER = "x_jina v1"
READER = "https://r.jina.ai/"
설정자리 = Path.home() / ".config" / "darkchoco"
# 한 판에 계정마다 단건으로 다시 받을 글의 상한. 한국 신호 글은 주 1건 안팎이라 넉넉하다
단건상한 = 5
# 토큰 상한. 프로필 1쪽이 약 1,063, 단건이 약 285 토큰이었다(2026-09-25 실측)
예산 = {"쪽": "8000", "단건": "3000"}
계정꼴 = re.compile(r"^[A-Za-z0-9_]{1,15}$")
# Jina 가 돌려줄 수 있는 멈춤 신호. 잔액이 없으면 그 판을 멈추고 다시 안 부른다
잔액없음 = {"InsufficientBalanceError"}
_X호스트 = ("x.com", "twitter.com", "t.co", "pbs.twimg.com", "abs.twimg.com")


class 잔액부족(Exception):
    """Jina 잔액이 없다. 이 판에서 더 부르지 않는다."""


# ── 설정 ───────────────────────────────────────────────────────────
def _파일(env: str, 이름: str) -> Path:
    v = (os.environ.get(env) or "").strip()
    return Path(v) if v else 설정자리 / 이름


def 키읽기() -> str:
    """Jina 키. `DARKCHOCO_JINA_KEY_FILE` 이 가리키는 파일, 없으면 ~/.config/darkchoco/jina_key.

    **값을 환경변수로 받지 않는다.** 노션 토큰과 같은 방침이다 — 파일 경로만 받는다."""
    p = _파일("DARKCHOCO_JINA_KEY_FILE", "jina_key")
    try:
        return p.read_text(encoding="utf-8").strip() if p.is_file() else ""
    except OSError:
        return ""


def 계정들() -> list[str]:
    """볼 계정. `DARKCHOCO_X_ACCOUNTS` 가 가리키는 파일, 없으면 ~/.config/darkchoco/x_accounts.

    한 줄에 하나. `@` 는 떼고, 빈 줄과 `#` 줄은 넘긴다. X 핸들 꼴이 아니면 버린다."""
    p = _파일("DARKCHOCO_X_ACCOUNTS", "x_accounts")
    try:
        줄들 = p.read_text(encoding="utf-8").splitlines() if p.is_file() else []
    except OSError:
        return []
    out = []
    for l in 줄들:
        s = l.strip().lstrip("@")
        if s and not s.startswith("#") and 계정꼴.match(s) and s not in out:
            out.append(s)
    return out


# ── 응답 읽기 ──────────────────────────────────────────────────────
def 글시각(글번호: str) -> str:
    """X 글 번호(snowflake)에서 게시 시각(UTC ISO). 절대 시각이 없는 프로필 쪽에 쓴다."""
    try:
        ms = (int(글번호) >> 22) + 1288834974657
    except (TypeError, ValueError):
        return ""
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat(timespec="seconds")


def 봉투(몸: bytes) -> tuple[dict | None, str]:
    """Jina JSON 봉투에서 (data, 오류 이름). **HTTP 상태만 믿지 않는다.**

    HTTP 200 안에 오류 봉투가 온 보고가 있다(2026-09-12). `code==200` 이고 `data.content` 가
    있을 때만 성공이다. 오류 문구(message)는 꺼내지 않는다."""
    try:
        d = json.loads(몸.decode("utf-8", "replace"))
    except ValueError:
        return None, "JSON 아님"
    if not isinstance(d, dict):
        return None, "JSON 아님"
    data = d.get("data")
    if d.get("code") == 200 and isinstance(data, dict) and str(data.get("content") or "").strip():
        return data, ""
    이름 = d.get("name")
    이름 = 이름 if isinstance(이름, str) and re.fullmatch(r"[A-Za-z]{1,60}", 이름) else ""
    return None, 이름 or ("code %s" % d.get("code") if d.get("code") else "내용 없음")


_그림 = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_링크 = re.compile(r"\[([^\]]*)\]\((https?://[^)\s]+)\)")


def _외부링크(u: str) -> bool:
    h = u.split("/")[2].lower() if u.count("/") >= 2 else ""
    return bool(h) and not any(h == x or h.endswith("." + x) for x in _X호스트)


def 글로(md: str) -> tuple[str, list[str]]:
    """마크다운 조각을 (글, 외부 링크들)로. 그림은 지우고 링크는 글자만 남긴다."""
    t = _그림.sub("", md or "")
    링크들 = [u for _, u in _링크.findall(t) if _외부링크(u)]
    t = _링크.sub(lambda m: m.group(1), t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    return t, 링크들


def _링크쌍(links) -> list[tuple[str, str]]:
    """links 요약을 (글자, 주소) 목록으로. 사전으로도 목록으로도 온다(`X-With-Links-Summary: all`)."""
    if isinstance(links, dict):
        return [(str(k), str(v)) for k, v in links.items()]
    out = []
    for x in links or []:
        if isinstance(x, (list, tuple)) and len(x) >= 2:
            out.append((str(x[0]), str(x[1])))
        elif isinstance(x, dict) and x.get("url"):
            out.append((str(x.get("text") or ""), str(x["url"])))
    return out


def 쪽읽기(계정: str, data: dict) -> tuple[list[dict], str]:
    """프로필 1쪽에서 글 목록. [{번호, 글, 링크들}] 과 못 읽은 까닭.

    글은 `*   ` 로 시작하는 목록 줄이다(2026-09-25 실측). 글 번호는 목록 줄 안의 이미지 주소
    (`/status/<번호>/photo/1`)에 있거나, 없으면 links 요약의 시각 표시(「2h」)가 가리키는 주소에
    같은 차례로 있다. **조용히 0 을 돌려주지 않는다.** 못 읽으면 까닭을 낸다."""
    내글 = re.compile(r"(?:x|twitter)\.com/%s/status/(\d{6,25})" % re.escape(계정), re.I)
    본문 = str(data.get("content") or "")
    조각들 = [c for c in re.split(r"\n(?=\*\s{1,4})", "\n" + 본문) if c.startswith("*")]
    차례번호 = []
    for _, u in _링크쌍(data.get("links")):
        m = 내글.search(u)
        if m and not u.rstrip("/").endswith(("/photo/1", "/analytics")) and m.group(1) not in 차례번호:
            차례번호.append(m.group(1))
    남은 = list(차례번호)
    out = []
    for c in 조각들:
        m = 내글.search(c)
        번호 = m.group(1) if m else ""
        if 번호 and 번호 in 남은:
            남은.remove(번호)
        elif not 번호 and 남은:
            번호 = 남은.pop(0)
        if not 번호:
            continue
        글, 링크들 = 글로(re.sub(r"^\*\s+", "", c))
        out.append({"번호": 번호, "글": 글, "링크들": 링크들})
    if not out:
        return [], ("쪽은 받았는데 글 목록이 없다. 계정이 비었거나 꼴이 바뀌었다" if 본문
                    else "쪽이 비었다")
    return out, ""


def 단건읽기(data: dict) -> tuple[str, list[str], str]:
    """단건 글에서 (전문, 외부 링크들, 게시 시각). 이름 줄 · 시각 줄 · 조회수 줄을 뗀다."""
    문단들 = []
    for 문단 in re.split(r"\n\s*\n", str(data.get("content") or "")):
        p = _그림.sub("", 문단).strip()
        if not p:
            continue
        # 링크만 있는 문단은 이름 · 핸들 · 시각 · 조회수다
        if not _링크.sub("", p).strip() and all(not _외부링크(u) for _, u in _링크.findall(p)):
            continue
        문단들.append(p)
    글, 링크들 = 글로("\n\n".join(문단들))
    when = str(data.get("publishedTime") or "").strip()
    return 글, 링크들, when


def 한국신호(글: str) -> bool:
    """단건으로 다시 받을 만한가. 잘린 글에서 싸게 본다. 넓게 잡는다 — 판정은 push.py 가 한다."""
    t = 글 or ""
    return (tg_post.flag_country(t) == "KR" or bool(tg_post.KR_DOMAIN.search(t))
            or "korea" in t.lower() or "한국" in t)


# ── 항목 ───────────────────────────────────────────────────────────
def to_item(*, 계정: str, 번호: str, 글: str, 링크들: list, when: str, 잘림: bool) -> Item:
    """글 하나를 항목으로. 칸 읽기는 텔레그램과 같은 공통 자리(`tg_post`)를 쓴다.

    `tg_post.to_item` 은 텔레그램 주소가 박혀 있어 못 쓴다. 칸만 다시 맞춘다."""
    fields, shape, note = tg_post.read_post(글)
    kind, ours = tg_post.classify(fields)
    org = tg_post.first(fields, tg_post.PICK["org"])
    org_how = "칸" if org else ""
    country = tg_post.first(fields, tg_post.PICK["country"])
    country_how = "칸" if country else ""
    if not org and ours is not False:
        org, org_how = tg_post.org_from_text(글)
    if not country:
        country = tg_post.flag_country(글)
        country_how = "국기" if country else ""
    org_dom = org if tg_post.DOMAIN.match(org or "") else ""
    # 글 안 링크가 대상 도메인이면 그것을 도메인 칸에 둔다. 원 출처로는 안 쓴다
    if not org_dom:
        for u in 링크들:
            h = u.split("/")[2].lower().removeprefix("www.") if u.count("/") >= 2 else ""
            if h and org and h.split(".")[0] in org.lower().replace(" ", ""):
                org_dom = h
                break
    주소 = "https://x.com/%s/status/%s" % (계정, 번호)
    return Item(
        source="x",
        src_id="%s/%s" % (계정, 번호),
        venue="x.com/" + 계정,
        venue_kind="x",
        actor=tg_post.first(fields, tg_post.PICK["actor"]),
        target_org=org,
        target_domain=org_dom,
        title=tg_post.title_of(글, fields, shape),
        body=글,
        body_kind="집계 계정 글",
        body_via="r.jina.ai",
        posted_at=when or 글시각(번호),
        # **원 출처가 아니다.** X 글 주소는 raw 에만 둔다
        post_url="",
        via=["x.com/" + 계정],
        # 규모는 raw 에만 둔다. 칸에 넣으면 규모 출처가 「원 출처」 로 잘못 찍힌다(push._규모출처)
        claimed_size="",
        country=country,
        kind=tg_post.TO_KIND.get(kind, ""),
        clues={"링크": 링크들[:10]} if 링크들 else {},
        raw={"글 종류": kind, "우리 대상": ours, "글 꼴": shape,
             "X 글 주소": 주소,
             **({"주장 규모": tg_post.first(fields, tg_post.PICK["size"])}
                if tg_post.first(fields, tg_post.PICK["size"]) else {}),
             **({"잘린 글": "프로필 쪽의 앞 250자 안팎. 한국 신호가 없어 전문을 안 받았다"} if 잘림 else {}),
             "본문 칸": {k: tg_post.clean(v) for k, v in fields.items()},
             **({"대상 조직 출처": org_how} if org else {}),
             **({"국가 출처": country_how} if country else {}),
             **({"못 읽은 것": note} if note else {})},
        got_by=VER,
    )


# ── 한 판 ──────────────────────────────────────────────────────────
def _받기(f: Fetcher, 키: str, 주소: str, 예산값: str, 셈: dict) -> dict | None:
    """Jina 로 한 번. 성공이면 data, 아니면 None. 오류는 **이름만** 센다."""
    머리 = {"Authorization": "Bearer " + 키, "X-With-Links-Summary": "all",
          "X-Token-Budget": 예산값}
    try:
        code, 몸, _ = f.get(READER + 주소, accept="application/json", headers=머리)
    except Blocked:
        셈["오류"]["호스트 꺼짐"] = 셈["오류"].get("호스트 꺼짐", 0) + 1
        return None
    except Exception as e:  # noqa: BLE001  요청이 죽어도 판은 돈다. 이름만 센다
        셈["오류"][type(e).__name__] = 셈["오류"].get(type(e).__name__, 0) + 1
        return None
    if f.dry:                   # 요청을 안 보냈다. 판정할 것이 없다
        return None
    if code != 200 and not 몸:
        이름 = f.last_err or ("HTTP %d" % code)
        셈["오류"][이름] = 셈["오류"].get(이름, 0) + 1
        if 이름 in 잔액없음 or code == 402:
            raise 잔액부족(이름)
        return None
    data, 이름 = 봉투(몸)
    if data is None:
        셈["오류"][이름] = 셈["오류"].get(이름, 0) + 1
        if 이름 in 잔액없음 or code == 402:
            raise 잔액부족(이름)
    return data


def 모으기(계정목록: list[str], 키: str, *, dry: bool = False,
         f: Fetcher | None = None, 셈: dict | None = None) -> Iterator[Item]:
    """계정마다 프로필 1쪽을 읽고, 한국 신호 글만 단건으로 다시 받아 항목을 낸다."""
    f = f or Fetcher(dry=dry)
    셈 = 셈 if 셈 is not None else {}
    셈.setdefault("오류", {})
    for k in ("계정", "쪽", "글", "단건", "못 읽은 쪽"):
        셈.setdefault(k, 0)
    try:
        for 계정 in 계정목록:
            셈["계정"] += 1
            data = _받기(f, 키, "https://x.com/" + 계정, 예산["쪽"], 셈)
            if dry or data is None:
                continue
            글들, 까닭 = 쪽읽기(계정, data)
            if not 글들:
                셈["못 읽은 쪽"] += 1
                continue
            셈["쪽"] += 1
            다시받음 = 0
            for g in 글들:
                셈["글"] += 1
                글, 링크들, when, 잘림 = g["글"], g["링크들"], "", True
                if 한국신호(g["글"]) and 다시받음 < 단건상한:
                    다시받음 += 1
                    셈["단건"] += 1
                    d = _받기(f, 키, "https://x.com/%s/status/%s" % (계정, g["번호"]), 예산["단건"], 셈)
                    if d is not None:
                        전문, 전문링크, when = 단건읽기(d)
                        if 전문:
                            글, 링크들, 잘림 = 전문, 전문링크 or 링크들, False
                yield to_item(계정=계정, 번호=g["번호"], 글=글, 링크들=링크들, when=when, 잘림=잘림)
    except 잔액부족:
        셈["잔액 부족으로 멈춤"] = 1


def 요약(셈: dict) -> str:
    """로그 한 줄. **계정 이름 · 제목 · 오류 문구를 안 찍는다.** 건수와 오류 이름만."""
    s = "X — 계정 %d · 읽은 쪽 %d · 글 %d · 전문 다시 받음 %d" % (
        셈.get("계정", 0), 셈.get("쪽", 0), 셈.get("글", 0), 셈.get("단건", 0))
    if 셈.get("못 읽은 쪽"):
        s += " · 글 목록을 못 읽은 쪽 %d" % 셈["못 읽은 쪽"]
    if 셈.get("오류"):
        s += " · 오류 " + " · ".join("%s %d" % kv for kv in sorted(셈["오류"].items()))
    if 셈.get("잔액 부족으로 멈춤"):
        s += " · **Jina 잔액이 없어 멈췄다**"
    return s


def run(db: Path | None, dry: bool) -> int:
    키, 목록 = 키읽기(), 계정들()
    if not 목록:
        print("X — 볼 계정이 없다. ~/.config/darkchoco/x_accounts 에 한 줄씩 적는다 (저장소 밖)")
        return 0
    if not 키 and not dry:
        print("X — Jina 키가 없다. ~/.config/darkchoco/jina_key 에 둔다 (저장소 밖). 이 판은 건너뛴다")
        return 0
    셈: dict = {}
    항목들 = list(모으기(목록, 키, dry=dry, 셈=셈))
    print(요약(셈))
    if dry or not db:
        print("dry run. 아무것도 안 넣었다" if dry else "--db 를 주면 넣는다")
        return 0
    s = Store(db)
    today = date.today().isoformat()
    fresh = sum(1 for it in 항목들 if s.put(it, today))
    s.log_run(today, "x", len(항목들), fresh, VER)
    s.close()
    print("X — %d건 중 처음 보는 것 %d건" % (len(항목들), fresh))
    # 막혀서 한 건도 못 읽었으면 실패로 끝낸다. 조용히 초록불이 되지 않게
    return 1 if (셈.get("오류") and not 셈.get("쪽")) or 셈.get("잔액 부족으로 멈춤") else 0


def main() -> int:
    ap = argparse.ArgumentParser(description="X CTI 계정 글을 Jina Reader 로 읽어 수집 표로")
    ap.add_argument("--db", help="수집 표 경로")
    ap.add_argument("--dry", action="store_true", help="요청을 안 보내고 무엇을 할지만")
    a = ap.parse_args()
    return run(Path(a.db) if a.db else None, a.dry)


if __name__ == "__main__":
    raise SystemExit(main())
