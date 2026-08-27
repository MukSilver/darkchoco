"""dc_safety · dc_ransomfeed 테스트. 실제 네트워크 호출은 하지 않습니다."""
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dc_ransomfeed as dr  # noqa: E402
import dc_safety as ds  # noqa: E402


def test_평문HTTP_차단():
    c = ds.SafeHttpClient()
    try:
        c.get_bytes("http://api.ransomware.live/v2")
    except ds.BlockedHostError:
        return
    finally:
        c.close()
    raise AssertionError("HTTP 가 통과했습니다")


def test_허용목록_밖_차단():
    c = ds.SafeHttpClient()
    try:
        c.get_bytes("https://evil.example.com/x")
    except ds.BlockedHostError:
        return
    finally:
        c.close()
    raise AssertionError("허용목록 밖 호스트가 통과했습니다")


def test_서브도메인_위장_차단():
    c = ds.SafeHttpClient()
    try:
        c.get_bytes("https://api.ransomware.live.evil.tld/")
    except ds.BlockedHostError:
        return
    finally:
        c.close()
    raise AssertionError("서브도메인 위장이 통과했습니다")


def test_텍스트_살균():
    assert len(ds.sanitize_text("가" * 50, 10)) <= 11      # 말줄임 포함
    assert "\x00" not in ds.sanitize_text("정상\x00값")


def test_주소_defang():
    assert ds.defang_url("https://samplemotor.co.kr/x").startswith("hxxps://")
    assert "[.]" in ds.defang_url("https://samplemotor.co.kr/x")
    assert ds.is_onion("http://abc.onion")
    assert ds.extract_domain("https://www.samplemotor.co.kr/a") == "samplemotor.co.kr"


def test_엔드포인트가_전부_허용목록_안():
    urls = [dr.rl_groups(), dr.rl_country_victims("KR"), dr.rl_recent_victims(),
            dr.rl_victims(2026, 8), dr.look_list("groups"),
            dr.look_detail("groups", "qilin"), dr.RANSOMFEED_RSS]
    for u in urls:
        host = urlparse(u).hostname
        assert host in ds.ALLOWED_HOSTS, f"허용목록 밖: {host} ({u})"


def test_월은_두자리로():
    assert dr.rl_victims(2026, 8).endswith("/2026/08")



def test_리다이렉트를_따라가도_헤더가_유지된다():
    """http.py 의 리다이렉트 재요청에 headers 가 빠져 있던 것을 막는다."""
    import inspect
    src = inspect.getsource(ds.SafeHttpClient._get_once)
    gets = [b for b in src.split("self._session.get(")[1:]]
    assert len(gets) == 2, "요청이 두 군데(최초·리다이렉트)여야 한다"
    for i, g in enumerate(gets):
        head = g[:g.index(")")]
        assert "headers" in head, f"{i}번째 요청에 headers 가 없다"


def test_랜섬웨어라이브_간격이_실측값이다():
    """1req/분/엔드포인트 를 실측했다. 그보다 빠른 값이 들어오면 막는다."""
    from dc_ransomfeed.fetch import THROTTLE
    assert THROTTLE["ransomware.live"] >= 60.0

if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_") and callable(v):
            v(); print(f"  OK  {k}"); n += 1
    print(f"\n{n}개 통과")
