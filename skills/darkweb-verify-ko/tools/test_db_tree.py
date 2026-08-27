"""db_tree.py 행 수 집계와 표 단위 등급 테스트.

    python -m unittest tools.test_db_tree -v
    python tools/test_db_tree.py

pytest 를 안 쓴다. 표준 라이브러리만으로 돈다.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import db_tree  # noqa: E402

HERE = Path(__file__).resolve().parent

# 실물 재료로 돌려 보는 시험. 없으면 건너뛴다.
#
# **이 레포는 공개다. 케이스 이름과 대상 도메인을 여기 적지 않는다.**
# 2026-08-27 까지 실제 케이스 경로가 박혀 있었다. 그 한 줄이 공유폴더 구조와
# 케이스 이름과 피해 조직의 도메인을 한꺼번에 드러냈다.
# 돌려 보려면 환경변수로 자리를 준다.
#
#     DARKCHOCO_REAL_DUMP=<덤프가 든 폴더> python tools/test_db_tree.py
_real = os.environ.get("DARKCHOCO_REAL_DUMP", "")
REAL = Path(_real) if _real else Path(tempfile.gettempdir()) / "_없는자리_"


def scan_sql(sql: str):
    """SQL 문자열을 임시 파일로 써서 scan 에 넣는다."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "dump.sql"
        p.write_text(sql, encoding="utf-8")
        return db_tree.scan(p)


class 행수집계(unittest.TestCase):
    def test_줄바꿈으로_나뉜_튜플을_센다(self):
        """phpMyAdmin 내보내기 형식. 튜플이 한 줄에 하나씩 온다."""
        sql = (
            "INSERT INTO `t` (`a`, `b`) VALUES\n"
            "(1, 'x'),\n"
            "(2, 'y'),\n"
            "(3, 'z');\n"
        )
        _, rows, _, _ = scan_sql(sql)
        self.assertEqual(rows["t"], 3)

    def test_확장_INSERT_를_센다(self):
        """mysqldump 기본 형식. 한 줄에 튜플이 이어 붙는다."""
        sql = "INSERT INTO `t` VALUES (1,'x'),(2,'y'),(3,'z');\n"
        _, rows, _, _ = scan_sql(sql)
        self.assertEqual(rows["t"], 3)

    def test_공백이_들어간_확장_INSERT_를_센다(self):
        sql = "INSERT INTO `t` VALUES (1,'x'), (2,'y'), (3,'z');\n"
        _, rows, _, _ = scan_sql(sql)
        self.assertEqual(rows["t"], 3)

    def test_문장당_한_튜플을_센다(self):
        sql = (
            "INSERT INTO `t` VALUES (1,'x');\n"
            "INSERT INTO `t` VALUES (2,'y');\n"
            "INSERT INTO `t` VALUES (3,'z');\n"
        )
        _, rows, _, _ = scan_sql(sql)
        self.assertEqual(rows["t"], 3)

    def test_한_줄에_INSERT_가_둘이면_각각_센다(self):
        """앞 문장의 집계 범위가 뒤 문장까지 넘어가면 중복으로 센다."""
        sql = "INSERT INTO `a` VALUES (1); INSERT INTO `b` VALUES (2),(3);\n"
        _, rows, _, _ = scan_sql(sql)
        self.assertEqual(rows["a"], 1)
        self.assertEqual(rows["b"], 2)

    def test_표가_여럿이면_따로_센다(self):
        sql = (
            "INSERT INTO `a` (`x`) VALUES\n(1),\n(2);\n"
            "INSERT INTO `b` (`x`) VALUES\n(1),\n(2),\n(3);\n"
        )
        _, rows, _, _ = scan_sql(sql)
        self.assertEqual(rows["a"], 2)
        self.assertEqual(rows["b"], 3)

    def test_값_안에_세미콜론이_있어도_뒤_튜플을_잃지_않는다(self):
        """읽기 버퍼는 세미콜론이 든 줄에서 비워진다.

        그래서 INSERT 헤더와 떨어진 자리에 남는 튜플이 생긴다.
        헤더가 앞 버퍼에 있었다는 것을 기억하지 않으면 그 줄들이 통째로 버려진다.
        """
        sql = (
            "INSERT INTO `t` (`a`) VALUES\n"
            "('세미콜론 ; 이 든 값'),\n"
            "('둘째 줄'),\n"
            "('셋째 줄');\n"
        )
        _, rows, _, _ = scan_sql(sql)
        self.assertEqual(rows["t"], 3)

    def test_값_안에_괄호가_있어도_튜플로_세지_않는다(self):
        sql = (
            "INSERT INTO `t` (`a`) VALUES\n"
            "('여는 괄호 ( 가 든 값'),\n"
            "('닫는 괄호 ) 가 든 값');\n"
        )
        _, rows, _, _ = scan_sql(sql)
        self.assertEqual(rows["t"], 2)


class 집계방식표기(unittest.TestCase):
    def test_줄_단위_튜플이면_방식을_알려준다(self):
        sql = "INSERT INTO `t` (`a`) VALUES\n(1),\n(2);\n"
        *_, methods = scan_sql(sql)
        self.assertIn("줄 단위 튜플", methods)

    def test_확장_INSERT_면_방식을_알려준다(self):
        sql = "INSERT INTO `t` VALUES (1),(2);\n"
        *_, methods = scan_sql(sql)
        self.assertIn("확장 INSERT", methods)

    def test_문장당_한_튜플이면_방식을_알려준다(self):
        sql = "INSERT INTO `t` VALUES (1);\n"
        *_, methods = scan_sql(sql)
        self.assertIn("문장당 한 튜플", methods)

    def test_출력에_어림값_표기와_집계_방식이_함께_나온다(self):
        sql = "INSERT INTO `t` (`a`) VALUES\n(1),\n(2),\n(3);\n"
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "dump.sql"
            src.write_text(sql, encoding="utf-8")
            out = Path(d) / "구조.md"
            r = subprocess.run(
                [sys.executable, str(HERE / "db_tree.py"), str(src), "--md", str(out)],
                capture_output=True, text=True, encoding="utf-8",
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            md = out.read_text(encoding="utf-8")
        self.assertIn("어림값", md)
        self.assertIn("줄 단위 튜플", md)
        self.assertIn("3", md)


class 치명등급(unittest.TestCase):
    """치명은 시스템 접근으로 가른다. 개인정보의 양이 아니다.

    세 무리가 치명이고 축이 같다. **그 값으로 어딘가에 들어갈 수 있느냐**다.

        1. 관리자 자격증명      그 시스템의 운영 권한이다
        2. 결제·정산 연동 키    돈이 오가는 시스템에 붙는다
        3. 인프라 접속 자격     그 시스템 밖으로 넘어간다

    도구는 칸 이름만 보고 값을 못 본다. 그래서 애매하면 올린다.
    낮게 매기면 사람이 못 보고, 높게 매기면 사람이 확인한다. 놓치는 쪽이 더 나쁘다.
    """

    def 확인(self, table, cols, want, what):
        got, why = db_tree.grade_of(table, cols)
        self.assertEqual(got, want, "%s (%s) -> %s. 왜: %s" % (table, what, got, why))

    def test_관리자_자격증명은_치명이다(self):
        for cols, what in [
            (["idx", "admin_userid", "admin_passwd"], "실제 케이스의 관리자 표"),
            (["idx", "admin_userid", "admin_pw"], "pw 단독형"),
            (["idx", "admin_userid", "admin_pass"], "pass 단독형"),
            (["idx", "admin_userid", "admin_hash"], "hash 영문"),
            (["idx", "user_id", "master_pwd"], "칸 이름이 관리자 계열"),
        ]:
            with self.subTest(what=what):
                self.확인("cs_admin", cols, "치명", what)

    def test_표_이름이_관리자_계열이면_치명이다(self):
        self.확인("tb_manager", ["seq", "login_id", "passwd"], "치명", "영문 표 이름")
        self.확인("관리자", ["idx", "아이디", "비밀번호"], "치명", "한글 표 이름")

    def test_결제_연동_칸은_치명이다(self):
        """가맹점 ID 하나로는 결제를 못 일으키지만 설정 표는 키를 같은 표에 둔다.

        한 케이스가 그랬다. 관리자 비밀번호와 pg_id 와 은행계좌가 한 행에 있었다.
        """
        for table, cols, what in [
            ("cs_pg", ["idx", "pg_company", "pg_id"], "PG 가맹점"),
            ("shop_config", ["idx", "pg_mid", "pg_key"], "PG 키"),
            ("tb_iamport", ["idx", "imp_key", "imp_secret"], "아임포트"),
            ("설정", ["idx", "merchant_id", "merchant_key"], "가맹점 ID"),
            ("payment", ["idx", "inicis_mid", "inicis_key"], "이니시스"),
        ]:
            with self.subTest(what=what):
                self.확인(table, cols, "치명", what)

    def test_인프라_접속_자격은_치명이다(self):
        for table, cols, what in [
            ("config", ["idx", "db_host", "db_user", "db_pass"], "DB 접속"),
            ("setting", ["idx", "smtp_host", "smtp_pass"], "메일 서버"),
            ("cloud", ["idx", "aws_access_key", "aws_secret_key"], "클라우드"),
            ("deploy", ["idx", "ssh_host", "private_key"], "SSH 개인키"),
        ]:
            with self.subTest(what=what):
                self.확인(table, cols, "치명", what)

    def test_인프라_이름만_있으면_안_올린다(self):
        """db_name 은 접속 자격이 아니다. 자격증명 칸이 같이 있어야 올린다."""
        self.확인("config", ["idx", "db_name", "db_charset"], "미분류", "이름만 있다")


class 올리지않는것(unittest.TestCase):
    """건수·평문 여부·주민번호로는 치명이 되지 않는다.

    평문이냐 해시냐는 즉시 악용 가능성 축이다. 자산 민감도를 움직이지 않는다.
    두 축이 섞이면 같은 성격의 유출이 케이스마다 다르게 매겨진다.
    """

    def 확인(self, table, cols, want, what):
        got, why = db_tree.grade_of(table, cols)
        self.assertEqual(got, want, "%s (%s) -> %s. 왜: %s" % (table, what, got, why))

    def test_회원_비밀번호는_건수와_무관하게_높음이다(self):
        self.확인("member", ["idx", "user_id", "passwd", "name", "hp"], "높음", "회원표")

    def test_주민번호는_높음이다(self):
        """주민번호는 시스템 접근이 아니다. 피해 범위 쪽에서 잡힌다."""
        self.확인("tb_jumin", ["idx", "name", "jumin"], "높음", "주민번호")

    def test_카드와_금융은_높음이다(self):
        self.확인("card", ["idx", "card_no", "bank_account"], "높음", "카드·금융")

    def test_신원_종수로_등급이_갈린다(self):
        self.확인("user", ["idx", "name", "email", "tel"], "높음", "신원 2종 이상")
        self.확인("board", ["idx", "name", "content"], "중간", "신원 1종")

    def test_공개_데이터는_낮음이다(self):
        self.확인("zipcode", ["zip", "sido", "gugun"], "낮음", "우편번호")

    def test_개인정보_칸이_없으면_미분류다(self):
        self.확인("log", ["idx", "ip", "created"], "미분류", "로그")


class 이름칸(unittest.TestCase):
    """`_name` 을 통째로 잡으면 안 된다.

    file_name, shop_name, menu_name, table_name 이 다 사람 이름이 된다.
    한 케이스의 관리자 표에 shop_name 이 실제로 있었다.
    사람을 가리키는 앞말이 붙은 것만 잡는다.
    """

    def 확인(self, table, cols, want, what):
        got, why = db_tree.grade_of(table, cols)
        self.assertEqual(got, want, "%s (%s) -> %s. 왜: %s" % (table, what, got, why))

    def test_사람_앞말이_붙으면_이름이다(self):
        for col in ["writer_name", "buyer_name", "member_name", "cust_name",
                    "recv_name", "sender_name", "emp_name", "owner_name",
                    "user_name", "real_name", "성명"]:
            with self.subTest(col=col):
                self.assertEqual(db_tree.sens_of(col), "이름")

    def test_사람이_아닌_앞말은_이름이_아니다(self):
        for col in ["file_name", "shop_name", "menu_name", "table_name",
                    "company_name", "board_name", "category_name", "bank_name"]:
            with self.subTest(col=col):
                self.assertNotEqual(db_tree.sens_of(col), "이름")

    def test_이름_두_종이면_높음이_된다(self):
        """전에는 writer_name 을 못 잡아서 게시판 표가 미분류로 떨어졌다."""
        self.확인("board", ["idx", "writer_name", "writer_tel", "content"],
                 "높음", "이름과 전화")


class 여권(unittest.TestCase):
    def test_여권번호를_잡는다(self):
        for col in ["passport", "passport_no", "여권번호"]:
            with self.subTest(col=col):
                self.assertEqual(db_tree.sens_of(col), "여권")

    def test_여권은_자격증명이_아니다(self):
        """passport 가 pass 로 시작하지만 비밀번호 칸이 아니다."""
        self.assertFalse(db_tree.PWD.search("passport_no"))


class 키값표(unittest.TestCase):
    """칸이 name 과 value 뿐이면 칸 이름으로 아무것도 안 보인다.

    안에 DB 접속 정보가 들어 있어도 못 잡는다. 사람이 값을 봐야 한다.
    등급을 새로 만들지 않고 미분류로 두되 왜 칸에 적는다.
    """

    def test_키값표는_신원으로_잡히지_않는다(self):
        """name 칸 하나 때문에 신원 칸이 하나다로 잡히던 오탐이다."""
        g, why = db_tree.grade_of("config", ["idx", "name", "value"])
        self.assertEqual(g, "미분류", why)
        self.assertIn("값을 사람이 봐야 한다", why)

    def test_설정표라도_자격증명_칸이_있으면_올린다(self):
        g, why = db_tree.grade_of("config", ["idx", "db_host", "db_pass"])
        self.assertEqual(g, "치명", why)

    def test_설정처럼_안_생긴_표는_그대로다(self):
        g, _ = db_tree.grade_of("board", ["idx", "name", "value"])
        self.assertNotEqual(g, "미분류")


class 오탐(unittest.TestCase):
    """도구가 아무 표나 치명으로 매기면 등급이 뜻을 잃는다.

    pw·pass·hash 는 앞뒤 경계를 함께 본다. 경계가 없으면 아래가 잘못 걸린다.
    """

    def 확인(self, table, cols, want, what):
        got, why = db_tree.grade_of(table, cols)
        self.assertEqual(got, want, "%s (%s) -> %s. 왜: %s" % (table, what, got, why))

    def test_passport_는_자격증명이_아니다(self):
        """여권번호는 개인정보이되 자격증명은 아니다. 치명이 아니라 높음이다."""
        self.확인("member", ["idx", "name", "passport_no"], "높음", "여권 번호")

    def test_pass_yn_은_통과_여부다(self):
        self.확인("order", ["idx", "buyer_name", "pass_yn"], "중간", "통과 여부")

    def test_hashtag_는_해시가_아니다(self):
        self.확인("post", ["idx", "title", "hashtag"], "미분류", "해시태그")

    def test_mid_가_들었다고_PG_가_아니다(self):
        self.확인("menu", ["idx", "menu_mid", "menu_title"], "미분류", "메뉴 아이디")

    def test_메일_주소는_인프라가_아니다(self):
        self.확인("mail", ["idx", "mail_addr", "mail_title"], "중간", "메일 주소")

    def test_메모_칸은_자격증명이_아니다(self):
        """order_admin_memo 가 관리자 자격증명으로 잡히던 오탐이다."""
        self.확인("order", ["idx", "order_admin_memo", "buyer_tel"], "중간", "관리자 메모")

    def test_pwr_은_pw_가_아니다(self):
        self.확인("stat", ["idx", "pwr_usage", "created"], "미분류", "전력 사용량")


@unittest.skipUnless(
    REAL.exists(), "실물 재료 없음. DARKCHOCO_REAL_DUMP 로 자리를 준다")
class 실물대조(unittest.TestCase):
    """같은 데이터의 CSV 사본이 옆에 있어 정답을 안다."""

    def test_cs_member_는_2691행이다(self):
        _, rows, _, _ = db_tree.scan(REAL / "cs_member.sql")
        self.assertEqual(rows["cs_member"], 2691)

    def test_cs_trade_는_4149행이다(self):
        _, rows, _, _ = db_tree.scan(REAL / "cs_trade.sql")
        self.assertEqual(rows["cs_trade"], 4149)


if __name__ == "__main__":
    unittest.main(verbosity=2)
