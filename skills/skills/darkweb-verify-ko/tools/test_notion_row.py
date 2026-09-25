"""notion_row 의 ⑨-3 행위자 규칙 테스트 (2026-09-25).

    python tools/test_notion_row.py

행위자 DB 에 같은 핸들이 있고 그 줄 비고에 「수집 DB 게시자 핸들에서」 가 있으면 기계가 만든
얇은 줄이다. 새 줄을 만들지 않고 **그 줄의 빈 칸만** 채운다. 사람이 만든 줄이면 멈춘다.

pytest 를 안 쓴다. 노션에 요청하지 않는다 — `_call` 과 `_모든줄` 을 가짜로 바꾼다.
**이 레포는 공개다. 실제 페이지 id 와 조직 이름을 여기 적지 않는다.**
"""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import notion_row  # noqa: E402

표지비고 = "2026-09-25 수집 DB 게시자 핸들에서 자동 등록"

스키마 = {
    "핸들": {"type": "title"},
    "다른 이름": {"type": "rich_text"},
    "국가": {"type": "multi_select", "multi_select": {"options": [{"name": "한국"}, {"name": "러시아"}]}},
    "지갑 주소": {"type": "rich_text"},
    "연결된 곳": {"type": "rich_text"},
    "비고": {"type": "rich_text"},
    "DB 반영": {"type": "checkbox"},
}


def _글(종류, 값):
    return {"type": 종류, 종류: [{"plain_text": 값}] if 값 else []}


def 기존줄(핸들, 비고, *, 다른="", 곳="", 국가=()):
    return {"id": "page-" + 핸들, "url": "https://notion.example/" + 핸들, "properties": {
        "핸들": _글("title", 핸들),
        "다른 이름": _글("rich_text", 다른),
        "국가": {"type": "multi_select", "multi_select": [{"name": x} for x in 국가]},
        "지갑 주소": _글("rich_text", ""),
        "연결된 곳": _글("rich_text", 곳),
        "비고": _글("rich_text", 비고),
        "DB 반영": {"type": "checkbox", "checkbox": True},
    }}


def 보낼것(핸들, **칸):
    body = {"핸들": {"title": [{"text": {"content": 핸들}}]}}
    for k, v in 칸.items():
        body[k.replace("_", " ")] = {"rich_text": [{"text": {"content": v}}]}
    return body


class 기존줄찾기(unittest.TestCase):
    def setUp(self):
        self.옛 = notion_row._모든줄

    def tearDown(self):
        notion_row._모든줄 = self.옛

    def test_핸들과_다른_이름과_0o_로_찾는다(self):
        notion_row._모든줄 = lambda ds: [기존줄("Seller0ne", 표지비고, 다른="alt_nick (forum)")]
        self.assertIsNotNone(notion_row.행위자_기존줄("ds", 스키마, 보낼것("sellerone")))
        self.assertIsNotNone(notion_row.행위자_기존줄("ds", 스키마, 보낼것("New", 다른_이름="AltNick")))
        self.assertIsNone(notion_row.행위자_기존줄("ds", 스키마, 보낼것("Someone")))

    def test_열쇠가_actor_py_와_같다(self):
        root = Path(__file__).resolve().parents[4]
        if not (root / "hub" / "events" / "actor.py").is_file():
            self.skipTest("떼어 간 스킬이라 hub 가 없다")
        sys.path.insert(0, str(root))
        from hub.events import actor
        for s in ("Cl0p Team!", "다크 초코_0", "Max_98"):
            self.assertEqual(notion_row._키(s), actor.키(s), s)
        self.assertEqual(notion_row.자동표지, actor.표지)


class 빈칸만채우기(unittest.TestCase):
    def test_빈_칸만_쓰고_찬_칸과_체크는_안_쓴다(self):
        옛 = 기존줄("SellerA", 표지비고, 곳="SomeForum")
        body = {**보낼것("SellerA", 연결된_곳="OtherForum", 지갑_주소="bc1-지어낸-주소"),
                "국가": {"multi_select": [{"name": "러시아"}]},
                "DB 반영": {"checkbox": False}}
        쓸것, 안씀 = notion_row.빈칸만(옛, body, "2026-10-01")
        self.assertEqual(set(쓸것), {"지갑 주소", "국가", "비고"})
        self.assertEqual(set(안씀), {"핸들", "연결된 곳", "DB 반영"})
        비고 = 쓸것["비고"]["rich_text"][0]["text"]["content"]
        self.assertTrue(비고.startswith(표지비고), "표지를 지웠다")
        self.assertIn("2026-10-01 ⑨-3 에서 빈 칸 채움 (지갑 주소 · 국가)", 비고)

    def test_채울_것이_없으면_비고도_안_건드린다(self):
        옛 = 기존줄("SellerA", 표지비고, 곳="SomeForum")
        쓸것, _ = notion_row.빈칸만(옛, 보낼것("SellerA", 연결된_곳="X"), "2026-10-01")
        self.assertEqual(쓸것, {})


class 도구로돌리기(unittest.TestCase):
    """main 을 가짜 노션으로 돌린다. 무엇을 보냈는지만 본다."""

    def setUp(self):
        self.옛 = (notion_row._call, notion_row._모든줄, notion_row.find_db, sys.argv)
        self.보낸것 = []

        def 가짜call(path, method="GET", body=None):
            if method == "GET":
                return {"properties": 스키마}
            self.보낸것.append((method, path, body))
            return {"id": "새줄", "url": "https://notion.example/새줄"}

        notion_row._call = 가짜call
        notion_row.find_db = lambda name: ("ds-actor", "행위자 DB")

    def tearDown(self):
        notion_row._call, notion_row._모든줄, notion_row.find_db, sys.argv = self.옛

    def _돌리기(self, 줄들, 출력, *추가):
        notion_row._모든줄 = lambda ds: 줄들
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "out9.txt"
            f.write_text(출력, encoding="utf-8")
            sys.argv = ["notion_row.py", "행위자", str(f), *추가]
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                try:
                    notion_row.main()
                    return 0, buf.getvalue()
                except SystemExit as e:
                    return e.code, buf.getvalue()

    def test_사람이_만든_줄이면_멈추고_아무것도_안_보낸다(self):
        code, out = self._돌리기([기존줄("SellerA", "검증하며 넣음")],
                               "핸들: SellerA\n지갑 주소: bc1-지어낸-주소\n", "--commit")
        self.assertEqual(code, 1)
        self.assertIn("사람이 만든 줄이 이미 있다", out)
        self.assertEqual(self.보낸것, [])

    def test_기계가_만든_줄이면_빈_칸만_고친다(self):
        code, out = self._돌리기([기존줄("SellerA", 표지비고, 곳="SomeForum")],
                               "핸들: SellerA\n연결된 곳: OtherForum\n지갑 주소: bc1-지어낸-주소\n",
                               "--commit")
        self.assertEqual(code, 0, out)
        self.assertEqual(len(self.보낸것), 1)
        method, path, body = self.보낸것[0]
        self.assertEqual((method, path), ("PATCH", "/pages/page-SellerA"))
        self.assertEqual(set(body["properties"]), {"지갑 주소", "비고"})

    def test_미리보기는_기계_줄이어도_안_쓴다(self):
        code, out = self._돌리기([기존줄("SellerA", 표지비고)], "핸들: SellerA\n지갑 주소: bc1-x\n")
        self.assertEqual(code, 0)
        self.assertIn("빈 칸만 채운다", out)
        self.assertEqual(self.보낸것, [])

    def test_없으면_지금처럼_새_줄을_만든다(self):
        code, _ = self._돌리기([기존줄("Other", 표지비고)], "핸들: SellerA\n", "--commit")
        self.assertEqual(code, 0)
        self.assertEqual([m for m, _, _ in self.보낸것], ["POST"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
