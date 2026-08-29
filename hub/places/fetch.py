"""여는 법. 갈아 끼웁니다.

갈래마다 여는 코드가 따로였습니다. 텔레그램은 urllib, 포럼도 urllib,
랜섬은 API 로 목록을 받고 다시 urllib. 클라우드플레어에 막히면 손쓸
데가 없었습니다 — 오늘 실측으로 **461줄**이 그렇게 막혔습니다.

여는 법을 셋으로 두고 **같은 것을 돌려주게** 합니다.

    http      urllib. 가볍고 빠릅니다. 대부분은 이걸로 됩니다
    browser   Playwright. JS 로 그리는 화면 · 클라우드플레어 앞단
    api       그 서비스의 API. 텔레그램처럼 API 가 있는 곳

부르는 쪽은 **무엇으로 열었는지 몰라도 됩니다.** `연것` 하나만 봅니다.
http 로 막히면 browser 로 다시 여는 것도 여기 한 곳에서 합니다.

**밖으로 나가는 길은 여전히 egress.py 하나입니다.** 셋 다 그것을
지납니다. browser 도 Tor 프록시를 받아야만 뜹니다.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["연것", "열기", "여는법들", "브라우저없음", "브라우저세션"]

여는법들 = ("http", "browser", "api")


class 브라우저없음(RuntimeError):
    """Playwright 가 안 깔렸습니다."""


@dataclass
class 연것:
    """연 결과. 무엇으로 열었든 같은 모양입니다.

    수집기는 `본문` 만 있으면 되는 것과 `page` 가 있어야 하는 것이
    갈립니다. page 가 없으면 그 수집기는 건너뛰고 **왜 건너뛰었는지**
    적습니다. 조용히 빠뜨리면 나중에 왜 칸이 비었는지 못 찾습니다.
    """

    주소: str = ""
    본문: str = ""
    헤더: dict = field(default_factory=dict)
    최종주소: str = ""
    상태코드: int = 0
    여는법: str = ""
    page: object | None = None          # browser 로 열었을 때만
    못본이유: str = ""

    def 봤나(self) -> bool:
        return not self.못본이유

    @property
    def 깊게봤나(self) -> bool:
        """page 가 있으면 수집기 일곱을 다 돌릴 수 있습니다."""
        return self.page is not None


def 열기(주소: str, *, 법: str = "http", 프록시: str | None = None,
       오프너=None, timeout: int = 30, 갈래: str = "", 세션=None) -> 연것:
    """한 곳을 엽니다. 법 을 갈아 끼웁니다.

    법 을 안 주면 http 입니다. http 로 막히면 부르는 쪽이 browser 로
    다시 부르면 됩니다 — 여기서 자동으로 안 바꿉니다. 브라우저는
    무겁고, 언제 쓸지는 부르는 쪽이 정하는 것이 맞습니다.
    """
    if 법 not in 여는법들:
        raise ValueError(f"모르는 여는 법입니다: {법}")
    if 법 == "http":
        return _http로(주소, 프록시=프록시, 오프너=오프너,
                     timeout=timeout, 갈래=갈래)
    if 법 == "browser":
        return _브라우저로(주소, 프록시=프록시, timeout=timeout, 세션=세션)
    return 연것(주소=주소, 여는법="api",
              못본이유="api 는 갈래별 조사기가 직접 부릅니다")


def _http로(주소, *, 프록시, 오프너, timeout, 갈래) -> 연것:
    import urllib.error
    import urllib.request

    from hub.places.egress import 보호없음, 오프너 as _오프너만들기

    r = 연것(주소=주소, 여는법="http")
    try:
        op = 오프너 or _오프너만들기(프록시, 갈래=갈래)
    except 보호없음 as e:
        r.못본이유 = str(e)[:180]
        return r

    req = urllib.request.Request(주소, headers={
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/128.0.0.0 Safari/537.36"),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    try:
        with op.open(req, timeout=timeout) as resp:
            원본 = resp.read(600_000)
            r.상태코드 = getattr(resp, "status", 200) or 200
            r.헤더 = {k.lower(): v for k, v in resp.headers.items()}
            r.최종주소 = resp.geturl()
    except urllib.error.HTTPError as e:
        r.상태코드 = e.code
        try:
            원본 = e.read(600_000)          # 4xx 본문에 까닭이 적혀 있습니다
        except Exception:                   # noqa: BLE001
            원본 = b""
        r.헤더 = {k.lower(): v for k, v in (e.headers or {}).items()}
        r.최종주소 = 주소
    except Exception as e:                  # noqa: BLE001
        r.못본이유 = f"{type(e).__name__}: {e}"[:180]
        return r

    for 인코딩 in ("utf-8", "cp1251", "latin-1"):
        try:
            r.본문 = 원본.decode(인코딩)
            break
        except UnicodeDecodeError:
            continue
    else:
        r.본문 = 원본.decode("utf-8", "replace")
    return r


class 브라우저세션:
    """크롬을 한 번만 띄워 돌려 씁니다.

    줄마다 띄우면 786번입니다. 뜨는 데만 1~2초씩이라 그것만 20분이
    넘습니다. 한 번 띄우고 페이지만 새로 엽니다.

    **Tor 없이는 안 뜹니다.** 브라우저는 urllib 과 달리 우리가 안 건
    요청(폰트·이미지·텔레메트리)도 스스로 보냅니다. 프록시를 안 걸면
    그것들이 전부 맨 IP 로 나갑니다.

        with 브라우저세션(프록시) as 세션:
            for 주소 in 주소들:
                r = 열기(주소, 법="browser", 세션=세션)
    """

    def __init__(self, 프록시: str | None):
        if not 프록시:
            raise 브라우저없음(
                "브라우저는 Tor 없이 안 씁니다. 안 건 요청까지 새 나갑니다")
        self.프록시 = 프록시
        self._pw = None
        self._br = None

    def __enter__(self):
        try:
            from playwright.sync_api import sync_playwright   # noqa: PLC0415
        except ImportError:
            raise 브라우저없음(
                "playwright 가 안 깔렸습니다. "
                "bash scripts/돌릴자리-만들기.sh 가 깝니다") from None
        호스트포트 = self.프록시.split("://", 1)[-1]
        self._pw = sync_playwright().start()
        self._br = self._pw.chromium.launch(
            headless=True, proxy={"server": f"http://{호스트포트}"})
        return self

    def __exit__(self, *a):
        for x in (self._br, self._pw):
            try:
                (x.close if x is self._br else x.stop)()
            except Exception:       # noqa: BLE001
                pass
        self._br = self._pw = None
        return False

    def 새페이지(self):
        if self._br is None:
            raise 브라우저없음("세션이 안 열렸습니다. with 로 감싸십시오")
        ctx = self._br.new_context(locale="en-US")
        return ctx.new_page()


def _브라우저로(주소, *, 프록시, timeout, 세션=None) -> 연것:
    """Playwright 로 엽니다. 세션을 주면 그것을 돌려 씁니다."""
    r = 연것(주소=주소, 여는법="browser")
    혼자 = 세션 is None
    if 혼자:
        if not 프록시:
            r.못본이유 = "브라우저는 Tor 없이 안 씁니다. 안 건 요청까지 새 나갑니다"
            return r
        try:
            세션 = 브라우저세션(프록시).__enter__()
        except 브라우저없음 as e:
            r.못본이유 = str(e)[:180]
            return r
    try:
        page = 세션.새페이지()
        resp = page.goto(주소, timeout=timeout * 1000,
                         wait_until="domcontentloaded")
        r.상태코드 = resp.status if resp else 0
        r.헤더 = {k.lower(): v for k, v in (resp.headers if resp else {}).items()}
        r.최종주소 = page.url
        r.본문 = page.content()
        r.page = page
    except Exception as e:          # noqa: BLE001
        r.못본이유 = f"{type(e).__name__}: {e}"[:180]
    finally:
        if 혼자 and r.page is None:
            세션.__exit__(None, None, None)
    return r
