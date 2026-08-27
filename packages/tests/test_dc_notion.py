"""dc_notion 테스트. 네트워크 호출 없이 로직만 봅니다."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import dc_notion as dn  # noqa: E402


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
    os.environ["NOTION_TOKEN"] = "ntn_env"
    try:
        assert dn.find_token() == "ntn_env"
    finally:
        del os.environ["NOTION_TOKEN"]


def test_토큰_없으면_어디를_봤는지_알려준다():
    keep = {k: os.environ.pop(k, None) for k in ("NOTION_TOKEN", "NOTION_TOKEN_FILE")}
    try:
        dn.find_token()
    except RuntimeError as e:
        assert "봤습니다" in str(e)
        return
    finally:
        for k, v in keep.items():
            if v:
                os.environ[k] = v
    raise AssertionError("토큰이 없는데 예외가 안 났습니다")


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
