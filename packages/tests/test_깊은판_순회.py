"""깊은 판의 사이트맵 순회가 시간 상한에서 멈추고 공개 로그에 주소를 안 찍는가 — 시험.

    python packages/tests/test_깊은판_순회.py          CI 가 이렇게 돌린다

2026-09-29 인계 H-4. 깊은 판 미리보기(places-deep.yml)에서 포럼 9줄이 187분을 썼다. 90분 상한이
줄 사이에서만 걸렸고, 한 줄 안의 사이트맵 순회(content.crawl_site)는 하위 게시판을 따라 끝없이 늘어났다.
같은 판의 공개 로그에 「카테고리 접속 실패, 건너뜀: <어니언 주소>」 와 `mailto:` 주소가 찍혔다.

**밖에 안 나가고 브라우저도 안 띄운다.** 가짜 page 와 가짜 수집기로 돈다. 주소는 지어낸 것이다.
**실행부를 둔다.** CI 는 이 폴더를 `python 파일` 로 돌린다.
"""
from __future__ import annotations

import logging
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packages"))

from hub.places.collect import content, structure  # noqa: E402


class _가짜쪽:
    """crawl_site 가 쓰는 것만 흉내 낸다. 막힐 주소를 주면 goto 가 예외를 낸다."""

    def __init__(self, 막힘=()):
        self.url = "http://home.example.test/"
        self.연것: list[str] = []
        self.막힘 = set(막힘)

    def goto(self, url, **_kw):
        self.연것.append(url)
        if url in self.막힘:
            raise TimeoutError("가짜 시간 초과")
        self.url = url


def _바꿔끼우기(하위=None):
    """순회가 부르는 수집기를 가짜로. 되돌릴 함수를 돌려준다."""
    옛 = {}
    가짜 = {
        (content, "_random_delay"): lambda: None,
        (content, "_save_checkpoint"): lambda *a, **k: None,
        (content, "_clear_checkpoint"): lambda *a, **k: None,
        (content, "_save_headline_dump"): lambda *a, **k: None,
        (content, "_load_checkpoint"): lambda *a, **k: None,
        (content, "collect_posts"): lambda page, source, limit=0: [{"title": "t", "author": "a", "date": ""}],
        (content, "_find_next_page_href"): lambda *a, **k: "",
        (content.challenge, "detect"): lambda page: None,
        (content.snapshot, "save_snapshot"): lambda *a, **k: None,
        (content.site_profiles, "get_profile"): lambda source: {},
        (structure, "discover_categories"): 하위 or (lambda page, profile: []),
    }
    for (모듈, 이름), 값 in 가짜.items():
        옛[(모듈, 이름)] = getattr(모듈, 이름)
        setattr(모듈, 이름, 값)

    def 되돌리기():
        for (모듈, 이름), 값 in 옛.items():
            setattr(모듈, 이름, 값)
    return 되돌리기


def _씨앗(*주소):
    return [{"text": f"게시판{i}", "url": u} for i, u in enumerate(주소)]


def test_마감이_지났으면_한_쪽도_안_열고_끊겼다고_적는다():
    되돌리기 = _바꿔끼우기()
    try:
        쪽 = _가짜쪽()
        결과 = content.crawl_site(쪽, {"name": "가짜"}, _씨앗("http://a.example.test/f1"),
                                마감=time.time() - 1)
    finally:
        되돌리기()
    # 원래 쪽으로 돌아가는 goto 하나만 있다
    assert 쪽.연것 == ["http://home.example.test/"], 쪽.연것
    assert 결과["_시간상한_끊김"] is True, 결과


def test_하위_게시판이_끝없이_늘어도_마감에서_멈춘다():
    셈 = {"n": 0}

    def 끝없는_하위(page, profile):
        셈["n"] += 1
        return [{"text": f"하위{셈['n']}", "url": f"http://a.example.test/sub{셈['n']}"}]

    되돌리기 = _바꿔끼우기(끝없는_하위)
    옛시계 = content.time.time
    지금 = {"t": 1000.0}

    def 가짜시계():
        지금["t"] += 1.0          # 부를 때마다 1초씩 흐른다
        return 지금["t"]
    content.time.time = 가짜시계
    try:
        쪽 = _가짜쪽()
        결과 = content.crawl_site(쪽, {"name": "가짜"}, _씨앗("http://a.example.test/f1"),
                                마감=1000.0 + 30)
    finally:
        content.time.time = 옛시계
        되돌리기()
    assert len(쪽.연것) < 40, len(쪽.연것)
    assert "시간 상한에서 끊김" in str(결과)


def test_마감이_없으면_예전처럼_끝까지_돈다():
    되돌리기 = _바꿔끼우기()
    try:
        쪽 = _가짜쪽()
        결과 = content.crawl_site(쪽, {"name": "가짜"},
                                _씨앗("http://a.example.test/f1", "http://a.example.test/f2"))
    finally:
        되돌리기()
    assert 쪽.연것[:2] == ["http://a.example.test/f1", "http://a.example.test/f2"], 쪽.연것
    assert "시간 상한에서 끊김" not in str(결과) and 결과["_시간상한_끊김"] is False


def test_http_가_아닌_주소는_안_연다():
    되돌리기 = _바꿔끼우기()
    try:
        쪽 = _가짜쪽()
        content.crawl_site(쪽, {"name": "가짜"},
                           _씨앗("mailto:abuse@example.test", "javascript:void(0)",
                                 "http://a.example.test/f1"))
    finally:
        되돌리기()
    assert all(u.startswith("http") for u in 쪽.연것), 쪽.연것
    assert "http://a.example.test/f1" in 쪽.연것


def test_접속_실패_경고에_주소가_없다():
    막힌주소 = "http://secretonionaddressxyz.onion/forum-1"
    받음: list[str] = []

    class _받기(logging.Handler):
        def emit(self, record):
            받음.append((record.levelno, record.getMessage()))

    h = _받기(level=logging.DEBUG)
    content.logger.addHandler(h)
    옛레벨 = content.logger.level
    content.logger.setLevel(logging.DEBUG)
    되돌리기 = _바꿔끼우기()
    try:
        쪽 = _가짜쪽(막힘=[막힌주소])
        content.crawl_site(쪽, {"name": "가짜"}, _씨앗(막힌주소))
    finally:
        되돌리기()
        content.logger.removeHandler(h)
        content.logger.setLevel(옛레벨)
    경고 = [m for lv, m in 받음 if lv >= logging.WARNING]
    assert 경고, "접속 실패 경고가 아예 안 났다"
    assert not any("onion" in m or "http" in m for m in 경고), 경고
    # 주소는 debug 로만 남는다
    assert any(막힌주소 in m for lv, m in 받음 if lv == logging.DEBUG), 받음


def test_게시처_코드의_경고에_주소_인자를_안_넘긴다():
    """깊은 판과 명부 조사는 공개 Actions 로그에서 돈다. 경고 이상에는 %s 로 값을 싣지 않는다."""
    꼴 = re.compile(r"logger\.(warning|error|exception|critical)\((?:[^()]|\([^()]*\))*%s")
    걸림 = []
    for f in (ROOT / "hub" / "places").rglob("*.py"):
        글 = f.read_text(encoding="utf-8")
        for m in 꼴.finditer(글):
            걸림.append(f"{f.relative_to(ROOT)}: {m.group(0)[:60]}")
    assert not 걸림, 걸림


def test_깊게가_모으기에_한줄_마감을_넘긴다():
    from hub.places import run
    글 = (ROOT / "hub" / "places" / "run.py").read_text(encoding="utf-8")
    assert run.한줄_상한초 <= run.깊은판_상한초
    assert "마감=마감" in 글 and "시작 + 깊은판_상한초" in 글
    모 = (ROOT / "hub" / "places" / "collect" / "모으기.py").read_text(encoding="utf-8")
    assert "crawl_site(page, src, 씨앗, resume=False, 마감=마감)" in 모


if __name__ == "__main__":
    시험들 = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    실패 = 0
    for 이름, f in 시험들:
        try:
            f()
            print("  OK  %s" % 이름)
        except Exception as e:  # noqa: BLE001
            실패 += 1
            print("  !!  %s — %s: %s" % (이름, type(e).__name__, e))
    print("\n%d개 중 %d개 실패" % (len(시험들), 실패))
    sys.exit(1 if 실패 else 0)
