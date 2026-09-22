"""대시보드가 읽을 데이터 하나를 굽습니다.

    python apps/dash/build.py              굽는다
    python apps/dash/build.py --no-notion  노션을 안 읽는다 (제어판 쪽만)

## 왜 굽나

화면은 각자 PC 에서 뜨고 데이터는 노션에 있습니다. 그런데 브라우저가 노션을 직접
부르면 **토큰이 브라우저에 있어야 합니다.** 토큰은 최현서 권한으로 돌고 팀원에게
넘기지 않는 것이 규칙입니다. 그래서 여기서 한 번 읽어 파일로 굽고 화면은 그 파일만
읽습니다. 토큰은 이 스크립트가 도는 자리에만 있습니다.

`file://` 로 열어도 보이게 `<script>` 로 읽는 `.js` 를 냅니다. `fetch` 로 읽으면
브라우저가 로컬 파일을 막습니다. apps/kr-leak-alarm 이 같은 방식을 씁니다.

## 무엇을 담나

    제어판   수집 실행 이력 · 표 현황 · 설정 점검 · 자주 쓰는 명령
    사건     수집 DB 줄. 검토 여부 · 소스 · 한국 관련 · 근거
    요약     자리 수 (굽기 산출물에서) · 사건 수 · 미검토 수

## 무엇을 안 담나

**게시글 본문과 개인정보 값은 안 담습니다.** 화면은 브라우저에 뜨고 파일로 남습니다.
수집 DB 에 본문 칸이 없는 것과 같은 이유입니다. 원문 URL 은 팀 안에서 쓰는 것이라
그대로 둡니다 (`hub/events/push.py` 와 같은 방침).
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages"))
sys.path.insert(0, str(ROOT))

HERE = Path(__file__).resolve().parent
KST = timezone(timedelta(hours=9))

# 화면이 읽을 파일. `.js` 인 이유는 머리 주석에 있습니다.
낼것 = HERE / "data" / "dash.js"

# 설정이 없으면 무엇이 안 도는지. 제어판(run.py)의 목록과 같은 뜻입니다.
설정 = [
    ("telegram_channels", "볼 채널 목록", "텔레그램 수집"),
    ("telegram_api", "텔레그램 api_id·api_hash", "미리보기가 꺼진 채널"),
    ("notion_token", "노션 토큰", "노션 조회와 기록"),
    ("discord_webhook", "디스코드 웹훅", "알림 보내기"),
    ("discord_channel", "감시 채널 id", "알림 읽기"),
]

# 화면에 보일 명령. **여기서 실행하지 않습니다.** 눌러서 복사만 합니다.
# 브라우저가 명령을 돌리게 하면 그 포트에 닿는 것이 곧 실행이 됩니다.
명령 = [
    ("수집 한 바퀴", "cd ~/darkchoco-team/skills && python -m collect.main --db ../hub/data/darkchoco.db"),
    ("랜섬만", "cd ~/darkchoco-team/skills && python -m collect.sources.ransomlive kr --db ../hub/data/darkchoco.db"),
    ("집계처 한 판 (게시 상태)", "cd ~/darkchoco-team && python skills/collect/track.py agg"),
    ("사람 관측 가져오기", "cd ~/darkchoco-team && python skills/collect/track.py pull"),
    ("게시 상태 보고서", "cd ~/darkchoco-team && python skills/collect/track.py report"),
    ("노션에 올리기 (미리보기)", "cd ~/darkchoco-team && python hub/events/push.py --db hub/data/darkchoco.db --kr"),
    ("제어판", "cd ~/darkchoco-team/skills && python run.py"),
    ("이 화면 다시 굽기", "cd ~/darkchoco-team && python apps/dash/build.py"),
]


def _표자리() -> Path:
    import os
    쓸것 = os.environ.get("DARKCHOCO_DB")
    if 쓸것:
        return Path(쓸것)
    for p in (ROOT / "hub" / "data" / "darkchoco.db",
              Path.home() / "data" / "darkchoco.db"):
        if p.is_file():
            return p
    return ROOT / "hub" / "data" / "darkchoco.db"


def _설정자리() -> Path:
    import os
    return Path(os.environ.get("DARKCHOCO_CONFIG_DIR",
                               Path.home() / ".config" / "darkchoco"))


def _표표기(db: Path) -> str:
    """화면에 보일 표 자리. **절대 경로를 그대로 안 냅니다.**

    구운 결과가 배포되어 팀 전체가 같이 봅니다. `str(db)` 를 그대로 담았더니
    `C:\\Users\\<이름>\\...` 이 화면에 그대로 나왔습니다 (2026-09-08). 사용자
    이름과 개인 폴더 배치가 남에게 보일 이유가 없습니다.

    2026-08-23 에 노션 토큰 자리를 도구에서 뺀 것과 같은 종류입니다. 그때는
    개인 경로가 공개 저장소에 올라가 있었습니다.

    레포 안이면 레포 기준으로, 홈 아래면 `~/` 기준으로, 둘 다 아니면 파일명만
    냅니다. 어느 쪽이든 어느 표를 보는지는 알아볼 수 있습니다.
    """
    p = db.resolve()
    for base, prefix in ((ROOT, ""), (Path.home(), "~/")):
        try:
            return prefix + p.relative_to(base).as_posix()
        except ValueError:
            continue
    return p.name


def 제어판(db: Path) -> dict:
    """수집이 언제 무엇을 얼마나 가져왔나. 표에 지금 무엇이 있나."""
    d: dict = {"표": _표표기(db), "표있음": db.is_file(), "실행": [], "소스별": {},
               "줄수": 0, "관측": 0, "마지막수집": "", "설정": []}
    cfg = _설정자리()
    d["설정"] = [{"이름": 이름, "무엇": 무엇, "쓰는곳": 쓰는곳,
                 "있음": (cfg / 이름).is_file()} for 이름, 무엇, 쓰는곳 in 설정]
    d["명령"] = [{"이름": 이름, "줄": 줄} for 이름, 줄 in 명령]
    # 화면에서 눌러 돌릴 수 있는 것. **여기 목록은 이 PC 에서 도는 것입니다.**
    # 배포판은 이 PC 의 수집기를 못 부르므로 `deploy/worker.js` 의 `일감표` 를 쓰고,
    # 그쪽 단추는 GitHub Actions 를 시작시킵니다. 두 목록은 일부러 다릅니다.
    try:
        import run_jobs

        d["일감"] = run_jobs.목록()
    except Exception:  # noqa: BLE001
        d["일감"] = []
    if not db.is_file():
        return d

    c = sqlite3.connect(str(db))
    c.row_factory = sqlite3.Row
    d["줄수"] = c.execute("SELECT COUNT(*) FROM items WHERE forgotten=0").fetchone()[0]
    for r in c.execute("SELECT source, COUNT(*) FROM items WHERE forgotten=0 GROUP BY 1"):
        d["소스별"][r[0] or "?"] = r[1]
    d["마지막수집"] = c.execute("SELECT MAX(first_seen) FROM items").fetchone()[0] or ""
    try:
        d["관측"] = c.execute("SELECT COUNT(*) FROM post_obs").fetchone()[0]
    except sqlite3.Error:
        d["관측"] = 0
    for r in c.execute("SELECT * FROM runs ORDER BY rowid DESC LIMIT 20"):
        d["실행"].append({"날": r["started"], "무엇": r["source"],
                         "받음": r["got"], "새것": r["fresh"], "메모": r["note"]})
    return d


def _rt(p: dict, 칸: str) -> str:
    v = (p.get(칸) or {}).get("rich_text") or []
    return "".join(x.get("plain_text", "") for x in v).strip()


def _sel(p: dict, 칸: str) -> str:
    return ((p.get(칸) or {}).get("select") or {}).get("name", "")


def _date(p: dict, 칸: str) -> str:
    return ((p.get(칸) or {}).get("date") or {}).get("start", "") or ""


def _ms(p: dict, 칸: str) -> list:
    """다중 선택. **값이 아니라 분류 이름입니다.**

    「유출 항목」이 여기 걸립니다. 이름·전화·이메일 같은 **항목 이름**이 들어가지
    털린 값이 들어가는 것이 아닙니다. 그래서 그대로 내보내도 됩니다.
    """
    return [x.get("name", "") for x in ((p.get(칸) or {}).get("multi_select") or [])]


def _누가(p: dict) -> str:
    """「수집자」를 **사람 이름 대신 갈래로** 접습니다 (2026-09-22, 최현서).

    이 칸의 선택지 아홉 중 일곱이 팀원 실명입니다. 화면에서 쓸모 있는 것은
    「누가」가 아니라 **「기계가 넣었나 사람이 넣었나」**입니다. 그 비율은 그대로
    읽히면서 실명은 브라우저에 아예 안 실립니다.

    2026-09-13 에 배포판에서만 이 칸을 뺐고 로컬은 그대로 담고 있었습니다.
    구운 파일 197줄 중 65줄에 실명이 있었습니다. **이제 양쪽이 같습니다.**
    """
    v = _sel(p, "수집자")
    if not v or v == "미기입":
        return "미기입"
    return "자동" if v == "자동" else "사람"


def 사건(수집DB: str) -> list:
    """노션 수집 DB 를 줄 목록으로. **본문과 개인정보 값은 안 담습니다.**"""
    from dc_notion import Notion

    n = Notion(verbose=False, allow_env_token=False)
    out = []
    for r in n.query_all(수집DB):
        p = r.get("properties") or {}
        제목 = "".join(x.get("plain_text", "")
                     for x in ((p.get("자료 제목") or {}).get("title") or []))
        번호 = (p.get("사건 ID") or {}).get("unique_id") or {}
        out.append({
            "id": r.get("id", ""),
            "번호": ("%s-%s" % (번호.get("prefix") or "", 번호.get("number"))
                   if 번호.get("number") is not None else ""),
            # 2026-09-22 에 칸을 열셋으로 좁혔습니다 (최현서).
            #
            # **이 화면은 모든 데이터를 보는 곳이 아니라 사건 요약입니다.**
            # 전에는 21칸을 실어 보내고 아홉만 그렸습니다. 「뽑되 안 그린다」가
            # 가장 나쁩니다 — 값은 브라우저까지 가는데 아무도 안 보니 무엇이
            # 나가는지 알아차릴 사람이 없습니다. 2026-09-13 일이 그 모양이었습니다.
            #
            # 빠진 것 중 하나를 적어 둡니다. **「한국 관련 근거」를 뺐습니다.**
            # 153줄 중 사람이 쓴 27줄이 있었고 그중 여덟 줄에 이메일 꼴이
            # 들어 있었습니다. 그 칸이 화면에 그대로 그려지고 있었습니다.
            "제목": 제목.strip(),
            "검토": _sel(p, "검토 여부"),
            "상태": _sel(p, "상태"),
            "대상": _rt(p, "대상 조직"),
            "업종": _sel(p, "산업 분야"),
            "국가": _sel(p, "국가"),
            "항목": _ms(p, "유출 항목"),
            "자리": _rt(p, "게시 플랫폼"),
            "핸들": _rt(p, "게시자 핸들"),
            "게시": _date(p, "게시 시각")[:10],
            "수집일": _date(p, "수집일")[:10],
            "수집자": _누가(p),
            # 열로는 안 그립니다. **거르개가 이 값을 씁니다.**
            # 선택지 글자(랜섬웨어·텔레그램·포럼) 셋뿐이라 그대로 내도 됩니다.
            "소스": _sel(p, "소스"),
        })
    return out


def 요약(지도: Path) -> dict:
    """첫 화면 숫자. **자리 수는 굽기 산출물에서 가져옵니다.** 새로 안 읽습니다."""
    d = {"자리": {}, "자리합": 0, "지도날": ""}
    if not 지도.is_file():
        return d
    try:
        m = json.loads(지도.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return d
    meta = m.get("meta") or {}
    counts = meta.get("counts") or {}
    d["자리"] = {k: v for k, v in counts.items() if k != "collected"}
    d["자리합"] = len(m.get("places") or [])
    d["지도날"] = meta.get("basis_date") or ""
    return d


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="대시보드가 읽을 데이터를 굽습니다")
    ap.add_argument("--db", type=Path, default=None, help="수집 표. 기본은 hub/data")
    ap.add_argument("--no-notion", action="store_true", help="노션을 안 읽는다")
    ap.add_argument("--지도", type=Path,
                    default=Path.home() / "dcsite" / "apps" / "site" / "data" / "leak-map.json",
                    help="자리 수를 가져올 굽기 산출물")
    ap.add_argument("--out", type=Path, default=낼것)
    a = ap.parse_args(argv)

    db = a.db or _표자리()
    d = {"구운때": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
         "제어판": 제어판(db), "요약": 요약(a.지도), "사건": [], "노션읽음": False}

    if not a.no_notion:
        try:
            from hub.events.push import 수집DB
            d["사건"] = 사건(수집DB)
            d["노션읽음"] = True
        except Exception as e:  # noqa: BLE001  노션이 없어도 제어판은 보여야 합니다
            d["노션오류"] = "%s: %s" % (type(e).__name__, str(e)[:200])
            print("  노션을 못 읽었다: %s" % d["노션오류"])

    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(
        "// 굽는 도구가 만든 파일이다. 손으로 고치지 않는다.\n"
        "// python apps/dash/build.py\n"
        "window.DASH = " + json.dumps(d, ensure_ascii=False, indent=1) + ";\n",
        encoding="utf-8")

    ev = d["제어판"]
    print()
    print("  구웠다  %s" % a.out)
    print("    표      %s줄 (%s) · 관측 %s건"
          % (ev["줄수"], " · ".join("%s %s" % kv for kv in ev["소스별"].items()) or "빔", ev["관측"]))
    print("    사건    %d줄%s" % (len(d["사건"]), "" if d["노션읽음"] else "  (노션 안 읽음)"))
    빠짐 = [s["이름"] for s in ev["설정"] if not s["있음"]]
    if 빠짐:
        # 엠대시를 쓰면 윈도 기본 코드페이지(cp949)에서 찍다가 죽는다.
        # 굽기는 이미 끝난 뒤라 파일은 나오는데 종료 코드가 1 이 되어
        # 부르는 쪽(serve.py)이 실패로 읽는다. 2026-09-22 에 실물로 겪었다.
        print("    설정    빠진 것 %d개 : %s" % (len(빠짐), " · ".join(빠짐)))
    print()
    print("  보려면:  python apps/dash/serve.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
