"""notion_find.as_text 테스트.

    python -m unittest tools.test_notion_find -v
    python tools/test_notion_find.py

pytest 를 안 쓴다. 표준 라이브러리만으로 돈다. 노션에 요청하지 않는다 —
`as_text` 는 응답 조각을 받아 문자열을 내는 순수 함수다.

**이 레포는 공개다. 실제 페이지 id 와 조직 이름을 여기 적지 않는다.**
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from notion_find import as_text  # noqa: E402


class 기존여덟(unittest.TestCase):
    """전에도 되던 것이 그대로 되는지 본다."""

    def test_텍스트류(self):
        self.assertEqual(as_text({"type": "title",
                                  "title": [{"plain_text": "가"}, {"plain_text": "나"}]}), "가나")
        self.assertEqual(as_text({"type": "rich_text",
                                  "rich_text": [{"plain_text": "다"}]}), "다")

    def test_고르기류(self):
        self.assertEqual(as_text({"type": "select", "select": {"name": "검증 완료"}}), "검증 완료")
        self.assertEqual(as_text({"type": "select", "select": None}), "")
        self.assertEqual(as_text({"type": "multi_select",
                                  "multi_select": [{"name": "이름"}, {"name": "연락처"}]}),
                         "이름, 연락처")

    def test_값류(self):
        self.assertEqual(as_text({"type": "url", "url": "https://example.test"}),
                         "https://example.test")
        self.assertEqual(as_text({"type": "url", "url": None}), "")
        self.assertEqual(as_text({"type": "number", "number": 0}), "0")
        self.assertEqual(as_text({"type": "number", "number": None}), "")
        self.assertEqual(as_text({"type": "unique_id",
                                  "unique_id": {"prefix": "LEAK", "number": 7}}), "LEAK7")
        self.assertEqual(as_text({"type": "date", "date": {"start": "2026-09-18"}}), "2026-09-18")
        self.assertEqual(as_text({"type": "date", "date": None}), "")


class 더한넷(unittest.TestCase):
    """2026-09-18 에 더했다. 전에는 넷 다 빈칸으로 떨어졌고, 그래서 덤프로
    감사하면 「검증DB 반영」과 「같은 사건」이 전 줄 빈칸처럼 보였다."""

    def test_checkbox_는_켜짐과_꺼짐을_가른다(self):
        # 빈 문자열로 내면 「꺼짐」과 「안 뽑힘」이 구분되지 않는다. 그것이 결함이었다.
        self.assertEqual(as_text({"type": "checkbox", "checkbox": True}), "예")
        self.assertEqual(as_text({"type": "checkbox", "checkbox": False}), "아니오")
        self.assertNotEqual(as_text({"type": "checkbox", "checkbox": False}), "")

    def test_relation_은_이어진_개수를_드러낸다(self):
        self.assertEqual(as_text({"type": "relation", "relation": []}), "")
        self.assertEqual(as_text({"type": "relation",
                                  "relation": [{"id": "aaa"}]}), "aaa")
        self.assertEqual(as_text({"type": "relation",
                                  "relation": [{"id": "aaa"}, {"id": "bbb"}]}), "aaa, bbb")

    def test_시각류(self):
        self.assertEqual(as_text({"type": "created_time",
                                  "created_time": "2026-09-18T01:00:00.000Z"}),
                         "2026-09-18T01:00:00.000Z")
        self.assertEqual(as_text({"type": "last_edited_time",
                                  "last_edited_time": "2026-09-18T02:00:00.000Z"}),
                         "2026-09-18T02:00:00.000Z")


class 안다루는것(unittest.TestCase):
    def test_모르는_종류는_빈칸이다(self):
        # 모르는 것을 짐작해 내지 않는다. 빈칸이면 「이 함수가 안 다룬다」는 뜻이다.
        self.assertEqual(as_text({"type": "people", "people": []}), "")
        self.assertEqual(as_text({"type": "files", "files": []}), "")
        self.assertEqual(as_text({}), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
