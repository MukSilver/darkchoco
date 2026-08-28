"""dc_notion 테스트. 네트워크 호출 없이 로직만 봅니다."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dc_console import use_utf8  # noqa: E402

use_utf8()   # 한글 콘솔에서 결과 줄이 깨지지 않게 한다
import dc_notion as dn
import dc_notion.token  # noqa: F401  # noqa: E402


import contextlib


@contextlib.contextmanager
def 토큰자리_비움():
    """이 PC 에 토큰이 깔려 있어도 도는 검사를 만들기 위한 것입니다.

    자리 목록을 잠시 비워 "아직 아무 데도 없는 상태" 를 만듭니다.
    """
    옛 = list(dn.token.TOKEN_PLACES)
    dn.token.TOKEN_PLACES[:] = [Path("절대로없는자리") / "notion_token"]
    try:
        yield
    finally:
        dn.token.TOKEN_PLACES[:] = 옛


def test_토큰_파일_방식():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "tok"
        p.write_text("ntn_abc", encoding="utf-8")
        os.environ["NOTION_TOKEN_FILE"] = str(p)
        try:
            assert dn.find_token() == "ntn_abc"
        finally:
            del os.environ["NOTION_TOKEN_FILE"]


def test_토큰_환경변수_방식도_계속_받는다():
    """파일이 없을 때만 환경변수를 봅니다. 파일이 먼저입니다."""
    os.environ["NOTION_TOKEN"] = "ntn_env"
    try:
        with 토큰자리_비움():
            assert dn.find_token() == "ntn_env"
    finally:
        del os.environ["NOTION_TOKEN"]


def test_토큰_없으면_어디를_봤는지_알려준다():
    """토큰이 실제로 깔려 있어도 도는 검사여야 한다.

    자리 목록을 잠시 없는 곳으로 바꿔 "못 찾은 상황" 을 만든다.
    """
    keep = {k: os.environ.pop(k, None) for k in ("NOTION_TOKEN", "NOTION_TOKEN_FILE")}
    try:
        with 토큰자리_비움():
            dn.find_token()
    except RuntimeError as e:
        assert "봤습니다" in str(e)
        assert "절대로없는자리" in str(e), "어디를 봤는지 안 알려준다"
        return
    finally:
        for k, v in keep.items():
            if v:
                os.environ[k] = v
    raise AssertionError("토큰 자리를 없앴는데 예외가 안 났습니다")


def test_값_읽기():
    assert dn.read_value({"type": "title", "title": [{"plain_text": "가"}]}) == "가"
    assert dn.read_value({"type": "number", "number": 460}) == 460
    assert dn.read_value({"type": "select", "select": {"name": "허위"}}) == "허위"
    assert dn.read_value({"type": "checkbox", "checkbox": True}) is True


def test_값_쓰기():
    assert dn.build_value("select", "허위") == {"select": {"name": "허위"}}
    assert dn.build_value("number", 3320)["number"] == 3320


def test_빈값_판정():
    assert dn.is_empty(None) and dn.is_empty("") and dn.is_empty([])
    assert not dn.is_empty(0) and not dn.is_empty("값")


if __name__ == "__main__":
    n = 0
    for k, v in sorted(globals().items()):
        if k.startswith("test_") and callable(v):
            v(); print(f"  OK  {k}"); n += 1
    print(f"\n{n}개 통과")
