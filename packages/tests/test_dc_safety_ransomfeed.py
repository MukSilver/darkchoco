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
    assert ds.defang_url("https://higen.co.kr/x").startswith("hxxps://")
    assert "[.]" in ds.defang_url("https://higen.co.kr/x")
    assert ds.is_onion("http://abc.onion")
    assert ds.extract_domain("https://www.higen.co.kr/a") == "higen.co.kr"


def test_엔드포인트가_전부_허용목록_안():
    urls = [dr.rl_groups(), dr.rl_country_victims("KR"), dr.rl_recent_victims(),
            dr.rl_victims(2026, 8), dr.look_list("groups"),
            dr.look_detail("groups", "qilin"), dr.RANSOMFEED_RSS]
    for u in urls:
        host = urlparse(u).hostname
        assert host in ds.ALLOWED_HOSTS, f"허용목록 밖: {host} ({u})"


def test_월은_두자리로():
    assert dr.rl_victims(2026, 8).endswith("/2026/08")


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_") and callable(v):
            v(); print(f"  OK  {k}"); n += 1
    print(f"\n{n}개 통과")
