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


def _칸(외부확인: str = "", 공표: str = "", inc: int = 7, 조직: str = "가상조직 사고") -> dict:
    """유출 사고 DB 한 줄의 properties 흉내. 조직명은 가짜다."""
    return {
        "조직명": {"type": "title", "title": [{"plain_text": 조직}]},
        "사건 ID": {"type": "unique_id", "unique_id": {"prefix": "INC", "number": inc}},
        "외부 확인": {"type": "select", "select": {"name": 외부확인} if 외부확인 else None},
        "공표 시점": {"type": "date", "date": {"start": 공표} if 공표 else None},
    }


class 사고기준선(unittest.TestCase):
    """유출 사고 DB 는 공식 확인 사고 명단(기준선)이다 (2026-09-28 최현서)."""

    def test_공식_셋은_있음_공식(self):
        import notion_find as NF
        for 확인 in ("조직 공식 발표", "규제기관 확정", "언론 보도"):
            갈래, 말 = NF.사고갈래(_칸(확인, "2026-07-03"))
            self.assertEqual(갈래, "있음(공식)", 확인)
            self.assertIn("INC7", 말)
            self.assertIn(확인, 말)
            self.assertIn("2026-07-03", 말)

    def test_게시글만과_연구자_발견은_주장_기록(self):
        import notion_find as NF
        for 확인 in ("게시글만", "연구자 발견", ""):
            갈래, 말 = NF.사고갈래(_칸(확인))
            self.assertEqual(갈래, "있음(주장 기록)", 확인)
            self.assertIn("INC7", 말)
            self.assertIn("공식 확인 아님", 말)

    def test_공표_시점이_없으면_모름(self):
        import notion_find as NF
        self.assertIn("공표 모름", NF.사고갈래(_칸("언론 보도"))[1])

    def test_못_찾으면_게시_시각으로_범위를_가른다(self):
        import notion_find as NF
        for d in ("2025-12-31", "2026-08-20", "2026-09-10T03:00:00+00:00"):
            갈래, 말 = NF.사고없음(d)
            self.assertEqual(갈래, "범위 밖", d)
            self.assertIn("갈래 A 필수", 말)
        for d in ("2026-01-01", "2026-05-05", "2026-08-19"):
            갈래, 말 = NF.사고없음(d)
            self.assertEqual(갈래, "범위 안에 없음", d)
            self.assertIn("8/19 뒤 발표된 사고는 DB 에 없다", 말)

    def test_게시_시각을_모르면_범위_안에_없음이되_그렇게_적는다(self):
        import notion_find as NF
        for d in ("", "모름", "9월 초"):
            갈래, 말 = NF.사고없음(d)
            self.assertEqual(갈래, "범위 안에 없음", d)
            self.assertIn("게시 시각을 몰라", 말)


def _돌리기(db이름: str, 줄들: list, *인자: str) -> str:
    """노션 없이 main 을 돌린다. find_db · rows 를 바꿔 끼운다."""
    import contextlib
    import io

    import notion_find as NF
    원래 = NF.find_db, NF.rows, sys.argv
    NF.find_db = lambda name: ("ds-가짜", db이름)
    NF.rows = lambda ds: [{"properties": p, "url": "https://notion.invalid/x"} for p in 줄들]
    sys.argv = ["notion_find.py", db이름, *인자]
    버퍼 = io.StringIO()
    try:
        with contextlib.redirect_stdout(버퍼):
            NF.main()
    finally:
        NF.find_db, NF.rows, sys.argv = 원래
    return 버퍼.getvalue()


class 사고DB_출력(unittest.TestCase):
    def test_머리에_기준선_한_줄(self):
        글 = _돌리기("유출 사고 DB", [], "가상조직", "--date", "2026-05-05")
        self.assertIn("기준선: 외부 확인 공식 3값", 글)
        self.assertIn("2026-01-01 ~ 2026-08-19", 글)

    def test_못_찾아도_없음으로_적으라고_하지_않는다(self):
        글 = _돌리기("유출 사고 DB", [], "가상조직", "--date", "2026-09-10")
        self.assertIn(">> 범위 밖 —", 글)
        self.assertNotIn("'없음'으로 적는다", 글)

    def test_걸린_줄은_갈래를_찍고_수집_DB_분류기를_안_돌린다(self):
        글 = _돌리기("유출 사고 DB", [_칸("게시글만", inc=40), _칸("규제기관 확정", "2026-03-02", inc=41)],
                  "가상조직", "--date", "2026-05-05")
        self.assertIn(">> 있음(주장 기록) — INC40", 글)
        self.assertIn(">> 있음(공식) — INC41", 글)
        # 수집 DB 용 분류(재게시 · 다른 건 …)가 사고 줄에 붙지 않는다
        for 딴것 in ("재게시", "다른 건", "아예 동일"):
            self.assertNotIn(">> " + 딴것, 글)

    def test_run_queue_가_갈래를_읽는다(self):
        import run_queue as R
        글 = _돌리기("유출 사고 DB", [_칸("언론 보도", inc=3)], "가상조직")
        self.assertEqual(R.VERDICT.findall(글), ["있음(공식)"])

    def test_다른_DB_는_그대로다(self):
        글 = _돌리기("수집 DB", [], "가상조직")
        self.assertIn("'없음'으로 적는다", 글)
        self.assertNotIn("기준선", 글)


if __name__ == "__main__":
    unittest.main(verbosity=2)
