"""NOTION_VERIFY_DB 로 검증 DB 이름 검색을 건너뛰는 것 — 테스트 (2026-09-25).

    python tools/test_notion_dbenv.py

`notion.db_from_env()` 와 그것을 먼저 부르는 `find_db()` 두 벌(notion_find · notion_row)을 본다.
pytest 를 안 쓴다. 노션에 요청하지 않는다 — `notion._call` 과 검색을 가짜로 바꾼다.
**이 레포는 공개다. 실제 id 를 여기 적지 않는다.** 아래 id 는 지어낸 것이다.
"""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import notion  # noqa: E402
import notion_find  # noqa: E402
import notion_row  # noqa: E402

DS = "11111111-2222-3333-4444-555555555555"
DB = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
빈틈없는DS = DS.replace("-", "")


class 환경변수로찾기(unittest.TestCase):
    def setUp(self):
        self.옛 = (notion._call, notion_find.search, notion_row.search,
                  os.environ.get("NOTION_VERIFY_DB"))
        self.부른것 = []
        self.검색 = []

        def 가짜검색(q=""):
            self.검색.append(q)
            return [{"object": "data_source", "id": "검색으로-찾은-것",
                     "title": [{"plain_text": q}]}]

        notion_find.search = 가짜검색
        notion_row.search = 가짜검색

    def tearDown(self):
        notion._call, notion_find.search, notion_row.search, 옛값 = self.옛
        if 옛값 is None:
            os.environ.pop("NOTION_VERIFY_DB", None)
        else:
            os.environ["NOTION_VERIFY_DB"] = 옛값

    def _노션(self, 열리는것):
        def call(path, method="GET", body=None):
            self.부른것.append(path)
            if path in 열리는것:
                return 열리는것[path]
            raise SystemExit("노션 404: " + path)
        notion._call = call

    def test_변수가_없으면_지금처럼_검색한다(self):
        os.environ.pop("NOTION_VERIFY_DB", None)
        self._노션({})
        for 모듈 in (notion_find, notion_row):
            self.assertEqual(모듈.find_db("검증"), ("검색으로-찾은-것", "검증"))
        self.assertEqual(self.부른것, [])
        self.assertEqual(self.검색, ["검증", "검증"])

    def test_data_source_id_면_검색을_건너뛴다(self):
        os.environ["NOTION_VERIFY_DB"] = DS
        self._노션({f"/data_sources/{DS}": {"object": "data_source", "id": DS,
                                            "title": [{"plain_text": "검증 DB"}]}})
        for 모듈 in (notion_find, notion_row):
            self.assertEqual(모듈.find_db("검증"), (DS, "검증 DB"))
        self.assertEqual(self.검색, [], "변수가 있는데 검색했다")

    def test_database_id_면_첫_data_source_로_옮겨_간다(self):
        os.environ["NOTION_VERIFY_DB"] = DB
        self._노션({f"/databases/{DB}": {"object": "database", "id": DB,
                                         "title": [{"plain_text": "검증 DB"}],
                                         "data_sources": [{"id": DS, "name": "검증 DB"}]}})
        self.assertEqual(notion_find.find_db("검증"), (DS, "검증 DB"))
        self.assertEqual(self.부른것, [f"/data_sources/{DB}", f"/databases/{DB}"])

    def test_노션_주소도_받고_보기_id_는_안_쓴다(self):
        os.environ["NOTION_VERIFY_DB"] = (
            f"https://www.notion.so/workspace/검증-DB-{빈틈없는DS}?v=99999999999999999999999999999999")
        self._노션({f"/data_sources/{빈틈없는DS}": {"object": "data_source", "id": DS,
                                               "title": [{"plain_text": "검증 DB"}]}})
        self.assertEqual(notion_row.find_db("검증"), (DS, "검증 DB"))

    def test_다른_DB_이름은_변수를_안_본다(self):
        os.environ["NOTION_VERIFY_DB"] = DS
        self._노션({})
        self.assertEqual(notion_find.find_db("수집"), ("검색으로-찾은-것", "수집"))
        self.assertEqual(self.부른것, [])

    def test_변수가_있는데_못_열면_검색하지_않고_멈춘다(self):
        os.environ["NOTION_VERIFY_DB"] = DS
        self._노션({})
        with self.assertRaises(SystemExit) as cm:
            notion_find.find_db("검증")
        글 = str(cm.exception)
        self.assertIn("NOTION_VERIFY_DB 가 가리키는 DB 를 못 열었다", 글)
        self.assertIn("노션 404", 글)
        self.assertEqual(self.검색, [], "잘못 적은 값을 조용히 검색으로 넘겼다")

    def test_id_꼴이_아니면_멈춘다(self):
        os.environ["NOTION_VERIFY_DB"] = "검증 DB"
        self._노션({})
        with self.assertRaises(SystemExit) as cm:
            notion_find.find_db("검증")
        self.assertIn("id 를 못 읽었다", str(cm.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
