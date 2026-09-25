"""notion_prop.res 테스트.

    python tools/test_notion_prop.py

`notion._call` 은 노션 오류를 `SystemExit` 로 바꿔 던진다. `res()` 가 그것을 못 잡아서
data_source 경로가 안 열리면 databases 경로를 안 보고 끝났다 (2026-09-25 고침).

pytest 를 안 쓴다. 노션에 요청하지 않는다 — `notion._call` 을 가짜로 바꾼다.
**이 레포는 공개다. 실제 id 를 여기 적지 않는다.**
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import notion  # noqa: E402
import notion_prop  # noqa: E402


class 경로찾기(unittest.TestCase):
    def setUp(self):
        self.옛 = notion._call
        self.부른것 = []

    def tearDown(self):
        notion._call = self.옛

    def _가짜(self, 열리는것):
        def call(path, method="GET", body=None):
            self.부른것.append(path)
            if path in 열리는것:
                return {"object": "ok"}
            raise SystemExit("노션 404: " + path)
        notion._call = call

    def test_data_source_가_열리면_그것을_쓴다(self):
        self._가짜({"/data_sources/abc"})
        self.assertEqual(notion_prop.res("abc"), "/data_sources/abc")
        self.assertEqual(self.부른것, ["/data_sources/abc"])

    def test_data_source_가_SystemExit_이어도_databases_를_본다(self):
        self._가짜({"/databases/abc"})
        self.assertEqual(notion_prop.res("abc"), "/databases/abc")
        self.assertEqual(self.부른것, ["/data_sources/abc", "/databases/abc"])

    def test_둘_다_안_되면_마지막_까닭을_같이_낸다(self):
        self._가짜(set())
        with self.assertRaises(SystemExit) as cm:
            notion_prop.res("abc")
        self.assertIn("DB 를 찾지 못했다: abc", str(cm.exception))
        self.assertIn("노션 404: /databases/abc", str(cm.exception))

    def test_보통_예외도_잡는다(self):
        def call(path, method="GET", body=None):
            if path.startswith("/data_sources/"):
                raise RuntimeError("연결이 끊겼다")
            return {}
        notion._call = call
        self.assertEqual(notion_prop.res("abc"), "/databases/abc")


if __name__ == "__main__":
    unittest.main(verbosity=2)
