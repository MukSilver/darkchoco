"""alert_watch 를 처음부터 끝까지 돌려 본다.

    python tools/test_alert_watch.py

**디스코드에 안 붙는다.** 큐 자리와 api 를 바꿔치기해서
진짜 큐도 안 건드린다.
"""
#
#
# 실제 채널에는 알림이 하나뿐이라 아래 길이 아직 안 돌아봤다.
#   - 두 번째 실행에서 기존 파일에 덧붙이는가
#   - 머리말이 두 번 찍히지 않는가
#   - 체크포인트가 앞으로만 가는가
#   - 표시 없는 건과 붙은 건이 한 파일에 섞여도 되는가
#
# 큐 자리와 api 를 임시로 바꿔치기해서 진짜 큐를 안 건드린다.
import json
import os
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import alert_watch as W  # noqa: E402

RUMOR = (TOOLS / "alert_samples" / "product_rumor_fp.txt").read_text(encoding="utf-8")
RANSOM = (TOOLS / "alert_samples" / "ransom_dlm.txt").read_text(encoding="utf-8")

FAKE = {
    "1": {"id": "1", "timestamp": "2026-08-25T09:00:00.000Z",
          "author": {"username": "테스트"}, "content": RUMOR},
    "2": {"id": "2", "timestamp": "2026-08-25T10:00:00.000Z",
          "author": {"username": "테스트"}, "content": RANSOM},
}

serve = []          # 이번 호출에 내줄 메시지 id 목록
asked = []          # api 가 받은 경로를 적어 둔다


def fake_api(path, tok):
    asked.append(path)
    return [FAKE[i] for i in reversed(serve)]   # 디스코드는 최신부터 준다


def run(argv):
    old = sys.argv
    sys.argv = ["alert_watch.py"] + argv
    try:
        return W.main()
    finally:
        sys.argv = old


fails = []


def check(name, got, want):
    if got != want:
        fails.append("%s\n     받음 %r\n     기대 %r" % (name, got, want))


with tempfile.TemporaryDirectory() as d:
    # **경로를 환경변수로 준다.** 코드에 개인 폴더를 박지 않기로 하면서
    # 상수가 함수가 됐다. 모듈 속성을 덮어쓰면 함수가 그것을 안 본다
    QUEUE = Path(d) / "_알림큐"
    STATE = QUEUE / "_state.json"
    os.environ["DARKCHOCO_ALERT_QUEUE"] = str(QUEUE)
    os.environ["DARKCHOCO_DISCORD_CHANNEL"] = "0"      # 가짜. api 를 갈아끼우므로 안 쓰인다
    W.api = fake_api
    W.token = lambda: "가짜토큰"

    # ── 1회차. 루머 알림 하나 ──────────────────
    serve = ["1"]
    check("1회차 종료코드", run([]), 0)
    md = list(QUEUE.glob("알림_*.md"))
    check("파일이 하나 생김", len(md), 1)
    t1 = md[0].read_text(encoding="utf-8")
    check("머리말 한 번", t1.count("# 감시 알림 큐"), 1)
    check("루머 표시 둘", t1.count("- 유출 감시로 아는 곳이 아니다"), 1)
    check("Testronics 한 번", t1.count("· Testronics"), 1)
    st = json.loads(STATE.read_text(encoding="utf-8"))
    check("체크포인트 1", st["last_id"], "1")
    check("누적 1", st["seen"], 1)

    # ── 2회차. 새 것 없음 ─────────────────────
    serve = []
    check("2회차 종료코드", run([]), 0)
    check("파일이 안 늘어남", len(list(QUEUE.glob("알림_*.md"))), 1)
    check("내용이 안 바뀜", md[0].read_text(encoding="utf-8"), t1)
    st = json.loads(STATE.read_text(encoding="utf-8"))
    check("체크포인트 그대로", st["last_id"], "1")

    # ── 3회차. 랜섬 알림이 새로 옴 ─────────────
    serve = ["2"]
    check("3회차 종료코드", run([]), 0)
    t3 = md[0].read_text(encoding="utf-8")
    check("같은 파일에 덧붙임", len(list(QUEUE.glob("알림_*.md"))), 1)
    check("머리말은 여전히 한 번", t3.count("# 감시 알림 큐"), 1)
    check("Testronics 그대로 한 번", t3.count("· Testronics"), 1)
    check("랜섬 건이 붙음", t3.count("Testwave") > 0, True)
    check("표시 없음 문구", t3.count("**표시 없음.**"), 1)
    check("앞 내용이 남아 있음", t3.startswith(t1), True)
    st = json.loads(STATE.read_text(encoding="utf-8"))
    check("체크포인트 2", st["last_id"], "2")
    check("누적 2", st["seen"], 2)
    check("실행 기록 3줄", len(st["runs"]), 3)
    check("빈 실행도 기록됨", st["runs"][1]["new"], 0)
    check("확인 시각이 남음", "last_check" in st, True)

    # ── after 를 붙여 물어봤는가 ───────────────
    check("2회차에 after 를 붙임", "after=1" in asked[1], True)
    check("3회차에 after 를 붙임", "after=1" in asked[2], True)

    print("=== 3회차 뒤 큐 파일 ===")
    for ln in t3.split("\n"):
        if ln.startswith("## ") or ln.startswith("- ") or ln.startswith("**표시"):
            print("   " + ln[:88])

print()
if fails:
    print("실패 %d" % len(fails))
    for f in fails:
        print("  - %s" % f)
    raise SystemExit(1)
print("통과. 처음부터 끝까지 3회차")
