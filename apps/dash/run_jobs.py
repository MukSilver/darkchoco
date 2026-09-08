"""화면에서 고른 명령을 돌립니다. **로컬에서만 됩니다.**

## 왜 이것은 되나

「웹이 명령을 돌리게 하면 그 포트에 닿는 것이 곧 명령 실행」 이라는 걱정은 **임의 명령**을
받을 때의 이야기입니다. 여기는 다릅니다.

    임의 명령      화면이 보낸 문자열을 셸에 넘긴다.  **안 합니다**
    정해진 목록     화면은 번호만 보낸다. 무엇을 돌릴지는 이 파일이 정한다

제어판(`skills/run.py`)이 이미 같은 일을 합니다 — 메뉴에서 고르면 미리 정해진 명령이 돕니다.
이 화면은 그것을 웹으로 옮긴 것입니다. 목록에 없는 것은 못 돌리고, 화면이 인자를 못 넣습니다.

## 지키는 것

    한 번에 하나       돌고 있으면 새로 안 받습니다. 같은 표에 둘이 쓰면 줄이 뭉칩니다
    셸을 안 거칩니다    shell=False 로 인자 목록을 그대로 넘깁니다
    시간 제한          오래 걸리는 것도 상한을 둡니다. 멈춘 채로 매달리지 않습니다
    로그 상한          화면에 보일 만큼만 들고 있습니다

## 로그에 무엇이 나오나

수집 로그에는 **게시글 제목이 나옵니다.** 로컬 화면이고 그 값은 이미 수집 표에 있는 것이라
새로 나가는 것은 아닙니다. 다만 **배포판에는 이 기능을 안 올립니다** — 남의 서버에서 돌 수도
없고, 로그를 남의 화면에 보일 이유도 없습니다.
"""
from __future__ import annotations

import subprocess
import sys
import threading
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KST = timezone(timedelta(hours=9))
PY = sys.executable


def _표() -> str:
    import os

    쓸것 = os.environ.get("DARKCHOCO_DB")
    if 쓸것:
        return 쓸것
    for p in (ROOT / "hub" / "data" / "darkchoco.db", Path.home() / "data" / "darkchoco.db"):
        if p.is_file():
            return str(p)
    return str(ROOT / "hub" / "data" / "darkchoco.db")


# 돌릴 수 있는 것. **여기 있는 것만 됩니다.** 화면은 열쇠만 보냅니다.
#   인자   실행할 인자 목록. 셸을 안 거칩니다
#   자리   어느 폴더에서 도나
#   제한   초. 넘으면 끊습니다
#   밖     밖으로 요청을 보내나. 화면에 표시해서 사람이 알고 누르게 합니다
def 일감() -> dict:
    db = _표()
    return {
        "수집": {
            "이름": "수집 한 바퀴 (텔레그램 + 랜섬)",
            "인자": [PY, "-m", "collect.main", "--db", db],
            "자리": str(ROOT / "skills"), "제한": 1800, "밖": True,
            "설명": "채널을 훑고 랜섬 집계처를 한 번 봅니다. 몇 분 걸립니다",
        },
        "랜섬": {
            "이름": "랜섬웨어만",
            "인자": [PY, "-m", "collect.sources.ransomlive", "kr", "--db", db],
            "자리": str(ROOT / "skills"), "제한": 600, "밖": True,
            "설명": "ransomware.live 한국 피해자 한 판",
        },
        "집계처": {
            "이름": "집계처 한 판 (게시 상태)",
            "인자": [PY, str(ROOT / "skills" / "collect" / "track.py"), "agg"],
            "자리": str(ROOT), "제한": 600, "밖": True,
            "설명": "목록에 있나 없나를 봅니다. 하루 한 번이면 됩니다",
        },
        "관측가져오기": {
            "이름": "사람 관측 가져오기",
            "인자": [PY, str(ROOT / "skills" / "collect" / "track.py"), "pull"],
            "자리": str(ROOT), "제한": 600, "밖": False,
            "설명": "노션에 적은 관측을 이력에 붙입니다",
        },
        "보고서": {
            "이름": "게시 상태 보고서",
            "인자": [PY, str(ROOT / "skills" / "collect" / "track.py"), "report"],
            "자리": str(ROOT), "제한": 300, "밖": False,
            "설명": "공개됨 · 사라짐 · 불명 세 숫자",
        },
        "올리기미리보기": {
            "이름": "노션에 올리기 — 미리보기",
            "인자": [PY, str(ROOT / "hub" / "events" / "push.py"), "--db", db, "--kr"],
            "자리": str(ROOT), "제한": 900, "밖": False,
            "설명": "무엇이 올라갈지만 봅니다. 안 씁니다",
        },
        "다시굽기": {
            "이름": "이 화면 다시 굽기",
            "인자": [PY, str(ROOT / "apps" / "dash" / "build.py")],
            "자리": str(ROOT), "제한": 600, "밖": False,
            "설명": "노션과 표를 다시 읽습니다. 끝나면 새로고침하십시오",
        },
    }


class _판:
    """지금 도는 것 하나. 같은 표에 둘이 쓰면 줄이 뭉칩니다."""

    def __init__(self):
        self.자물쇠 = threading.Lock()
        self.돌고있나 = False
        self.열쇠 = ""
        self.시작 = ""
        self.끝 = ""
        self.코드 = None
        self.줄 = deque(maxlen=400)      # 화면에 보일 만큼만
        self.차수 = 0                    # 화면이 새 줄만 받아 가려고 씁니다

    def 상태(self) -> dict:
        with self.자물쇠:
            return {"돌고있나": self.돌고있나, "열쇠": self.열쇠, "시작": self.시작,
                    "끝": self.끝, "코드": self.코드, "차수": self.차수,
                    "줄": list(self.줄)}


_판하나 = _판()


def _적기(s: str) -> None:
    with _판하나.자물쇠:
        _판하나.줄.append(s.rstrip())
        _판하나.차수 += 1


def _돌리기(열쇠: str, 일: dict) -> None:
    try:
        p = subprocess.Popen(
            일["인자"], cwd=일["자리"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            # **셸을 안 거칩니다.** 인자 목록을 그대로 넘깁니다
            shell=False, text=True, encoding="utf-8", errors="replace",
            env=_환경(),
        )
    except Exception as e:  # noqa: BLE001
        _적기("못 돌렸다: %s: %s" % (type(e).__name__, e))
        with _판하나.자물쇠:
            _판하나.돌고있나 = False
            _판하나.코드 = -1
            _판하나.끝 = datetime.now(KST).strftime("%H:%M:%S")
        return

    def 지켜보기():
        try:
            for 줄 in p.stdout:            # type: ignore[union-attr]
                _적기(줄)
        except Exception:  # noqa: BLE001
            pass

    t = threading.Thread(target=지켜보기, daemon=True)
    t.start()
    try:
        코드 = p.wait(timeout=일["제한"])
    except subprocess.TimeoutExpired:
        p.kill()
        _적기("시간 제한 %d초를 넘겨 끊었다" % 일["제한"])
        코드 = -9
    t.join(timeout=5)
    with _판하나.자물쇠:
        _판하나.돌고있나 = False
        _판하나.코드 = 코드
        _판하나.끝 = datetime.now(KST).strftime("%H:%M:%S")


def _환경() -> dict:
    import os

    e = dict(os.environ)
    e["PYTHONUTF8"] = "1"
    e["PYTHONIOENCODING"] = "utf-8"
    e["PYTHONUNBUFFERED"] = "1"     # 줄이 바로바로 올라오게 합니다
    return e


def 시작(열쇠: str) -> tuple[bool, str]:
    """(시작했나, 왜). 목록에 없으면 안 돌립니다."""
    일 = 일감().get(열쇠)
    if not 일:
        return False, "그런 일감이 없습니다"
    with _판하나.자물쇠:
        if _판하나.돌고있나:
            return False, "이미 %s 가 돌고 있습니다" % _판하나.열쇠
        _판하나.돌고있나 = True
        _판하나.열쇠 = 열쇠
        _판하나.시작 = datetime.now(KST).strftime("%H:%M:%S")
        _판하나.끝 = ""
        _판하나.코드 = None
        _판하나.줄.clear()
        _판하나.차수 = 0
    _적기("── %s ──" % 일["이름"])
    threading.Thread(target=_돌리기, args=(열쇠, 일), daemon=True).start()
    return True, ""


def 상태() -> dict:
    return _판하나.상태()


def 목록() -> list:
    """화면에 보일 목록. 인자는 안 보냅니다 — 화면이 알 필요가 없습니다."""
    return [{"열쇠": k, "이름": v["이름"], "설명": v["설명"], "밖": v["밖"]}
            for k, v in 일감().items()]
