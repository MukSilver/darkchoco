"""notion_prop.res 테스트.

    python tools/test_notion_prop.py

`notion._call` 은 노션 오류를 `SystemExit` 로 바꿔 던진다. `res()` 가 그것을 못 잡아서
data_source 경로가 안 열리면 databases 경로를 안 보고 끝났다 (2026-09-25 고침).

같은 날 머지 전 검토에서 하나 더 나왔다. 우리가 박아 둔 판(2025-09-03)의 GET /databases 는 칸이
없다. database id 를 받으면 그 data_source 경로로 옮겨 가야 show · add 가 칸을 본다.

pytest 를 안 쓴다. 노션에 요청하지 않는다 — `notion._call` 을 가짜로 바꾼다.
**이 레포는 공개다. 실제 id 를 여기 적지 않는다.**
"""
import contextlib
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import notion  # noqa: E402
import notion_prop  # noqa: E402

데이터베이스 = {"object": "database", "id": "abc", "title": [{"plain_text": "옛 DB"}],
            "data_sources": [{"id": "ds1", "name": "옛 DB"}]}
데이터소스 = {"object": "data_source", "id": "ds1", "title": [{"plain_text": "옛 DB"}],
          "properties": {"이름": {"type": "title"},
                         "등급": {"type": "select", "select": {"options": [{"name": "A"}]}}}}


class 경로찾기(unittest.TestCase):
    def setUp(self):
        self.옛 = notion._call
        self.부른것 = []

    def tearDown(self):
        notion._call = self.옛

    def _가짜(self, 열리는것: dict):
        def call(path, method="GET", body=None):
            self.부른것.append((method, path))
            if path in 열리는것:
                return 열리는것[path]
            raise SystemExit("노션 404: " + path)
        notion._call = call

    def test_data_source_가_열리면_그것을_쓴다(self):
        self._가짜({"/data_sources/abc": 데이터소스})
        self.assertEqual(notion_prop.res("abc"), "/data_sources/abc")
        self.assertEqual(self.부른것, [("GET", "/data_sources/abc")])

    def test_database_id_면_그_data_source_로_옮겨_간다(self):
        self._가짜({"/databases/abc": 데이터베이스})
        self.assertEqual(notion_prop.res("abc"), "/data_sources/ds1")

    def test_옛_꼴처럼_칸이_딸려_오면_databases_를_쓴다(self):
        self._가짜({"/databases/abc": {"object": "database", "properties": {"이름": {"type": "title"}}}})
        self.assertEqual(notion_prop.res("abc"), "/databases/abc")

    def test_data_source_가_여럿이면_고르지_않고_멈춘다(self):
        여럿 = dict(데이터베이스, data_sources=[{"id": "ds1", "name": "가"}, {"id": "ds2", "name": "나"}])
        self._가짜({"/databases/abc": 여럿})
        with self.assertRaises(SystemExit) as cm:
            notion_prop.res("abc")
        self.assertIn("ds1", str(cm.exception))
        self.assertIn("ds2", str(cm.exception))

    def test_둘_다_안_되면_두_까닭을_다_낸다(self):
        self._가짜({})
        with self.assertRaises(SystemExit) as cm:
            notion_prop.res("abc")
        글 = str(cm.exception)
        self.assertIn("DB 를 찾지 못했다: abc", 글)
        self.assertIn("노션 404: /data_sources/abc", 글)     # 첫 경로의 까닭이 안 가려진다
        self.assertIn("노션 404: /databases/abc", 글)

    def test_보통_예외도_잡는다(self):
        def call(path, method="GET", body=None):
            if path.startswith("/data_sources/"):
                raise RuntimeError("연결이 끊겼다")
            return 데이터베이스
        notion._call = call
        # 첫 경로의 보통 예외를 잡고 database 로 넘어가 data_source 경로를 돌려준다
        self.assertEqual(notion_prop.res("abc"), "/data_sources/ds1")

    def test_database_id_로_show_하면_칸을_본다(self):
        """전에는 GET /databases 의 칸 없는 객체를 받아 「칸 0개」 를 냈다."""
        self._가짜({"/databases/abc": 데이터베이스, "/data_sources/ds1": 데이터소스})
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            notion_prop.cmd_show("abc")
        self.assertIn("칸 2개", buf.getvalue())
        self.assertIn("등급", buf.getvalue())

    def test_database_id_로_add_하면_data_source_에_기존_선택지를_지키며_보낸다(self):
        self._가짜({"/databases/abc": 데이터베이스, "/data_sources/ds1": 데이터소스})
        보낸것 = []
        원래 = notion._call

        def call(path, method="GET", body=None):
            if method == "PATCH":
                보낸것.append((path, body))
                return {}
            return 원래(path, method, body)
        notion._call = call
        with contextlib.redirect_stdout(io.StringIO()):
            notion_prop.cmd_add("abc", "등급", ["B"], multi=False, dry=False)
        self.assertEqual(len(보낸것), 1)
        경로, 몸 = 보낸것[0]
        self.assertEqual(경로, "/data_sources/ds1")
        self.assertEqual([o["name"] for o in 몸["properties"]["등급"]["select"]["options"]], ["A", "B"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
