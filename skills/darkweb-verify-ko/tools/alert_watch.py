#!/usr/bin/env python3
"""디스코드 감시 알림을 주기적으로 읽어 큐에 쌓는다.

    python tools/alert_watch.py                 새 알림만 읽어 큐에 쌓는다
    python tools/alert_watch.py --dry           읽기만 하고 파일을 안 쓴다
    python tools/alert_watch.py --limit 100     한 번에 읽을 개수 (기본 50)
    python tools/alert_watch.py --reset         체크포인트를 지우고 처음부터

**거르지 않는다. 표시만 붙인다.**
무엇이 유출 사고인지는 상황마다 달라서 코드가 정할 수 없다.
버리면 사람이 그 건을 다시는 못 본다. 대신 볼 만한 신호에 표시를 달아
③ 사전 확인과 사람이 정하게 한다.

붙이는 표시는 둘이다.

    감시 출처   유출 감시로 알려진 곳에서 왔는가
    규모        게시글이 규모나 표 이름을 적었는가

2026-08-24 에 받은 알림이 러시아 IT 뉴스의 휴대폰 렌더 기사였는데
`Type: Data leak`, `Confidence: 95%` 로 왔다. 둘 다 표시가 붙는 자리다.

**포럼과 onion 에 붙지 않는다.** 우리 디스코드만 읽는다.
그래서 요청 간격 규칙에 걸리지 않고 주기 실행이 된다.

토큰은 저장소 밖 파일에서 읽는다. 값을 출력하거나 로그에 남기지 않는다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alert_parse as A  # noqa: E402

# ── 자리 ────────────────────────────────────────
TOKEN_FILE = Path.home() / ".config" / "darkchoco" / "discord_token"
CHANNEL = "<채널번호는 설정 파일에 있다>"          # 개인 서버
PROJ = Path.home() / "Documents" / "Q.E.D" / "화햇" / "화햇강의자료" / "프젝"
QUEUE = PROJ / "07_케이스" / "_알림큐"
STATE = QUEUE / "_state.json"

# ── 표시 규칙 ───────────────────────────────────
# **막는 목록이 아니라 아는 목록이다.**
# 뉴스 사이트를 다 적을 수는 없다. 유출 감시로 아는 곳을 적고
# 그 밖에서 온 것에 표시를 붙인다. 새 감시처가 생기면 여기 더한다.
KNOWN_WATCH = re.compile(
    r"ransomware\[?\.\]?live|haveibeenransom|ransomlook|ransomfeed"
    r"|breachsense|darkfeed|falconfeeds|dailydarkweb|stealthmole"
    r"|\.onion|t\.me/|telegram", re.I)

# 유출 게시글은 규모나 표 이름을 적는다. 기사 제목은 안 적는다.
SCALE = re.compile(
    r"\b\d[\d,\.]*\s*(k|m|만|천|억)?\s*(rows?|records?|lines?|users?|건|행|명)\b"
    r"|\b\d{1,3}(,\d{3})+\b|\b\d+\s?(gb|tb|mb)\b"
    r"|database|dump|db|leak(ed)?\s+data|victim|breach", re.I)


def token() -> str:
    if not TOKEN_FILE.exists():
        raise SystemExit("토큰 파일이 없다: %s" % TOKEN_FILE)
    return TOKEN_FILE.read_text(encoding="utf-8").strip()


def api(path: str, tok: str):
    req = urllib.request.Request(
        "https://discord.com/api/v10" + path,
        headers={"Authorization": "Bot " + tok,
                 "User-Agent": "darkchoco-alert-watch/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"_오류": e.code, "_본문": e.read().decode("utf-8", "replace")[:200]}
    except OSError as e:
        return {"_오류": type(e).__name__}


def load_state() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"last_id": None, "seen": 0, "runs": []}


def save_state(state: dict, dry: bool) -> None:
    """확인한 시각을 남긴다. 새 알림이 없어도 남긴다.

    **안 남기면 감시기가 죽은 것과 알림이 없는 것이 구별되지 않는다.**
    토큰이 만료되거나 주기 작업이 안 돌아도 조용히 아무 일도 안 일어난다.
    last_check 가 오래됐으면 멈춘 것이다.
    """
    if dry:
        return
    state["last_check"] = datetime.now(timezone.utc).isoformat()
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def marks(r: dict) -> list[str]:
    """볼 만한 신호에 표시를 붙인다. **버리지 않는다.**"""
    out = []
    src = r.get("감시 출처", "")
    if src.startswith(A.MISS):
        out.append("감시 출처를 못 뽑았다")
    elif not KNOWN_WATCH.search(src):
        out.append("유출 감시로 아는 곳이 아니다 (%s)" % src[:48])

    sent = r.get("알림 문장", "")
    if sent.startswith(A.MISS):
        out.append("알림 문장을 못 뽑았다")
    elif not SCALE.search(sent):
        out.append("규모나 표 이름 표기가 없다")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="디스코드 감시 알림을 큐에 쌓는다")
    ap.add_argument("--dry", action="store_true", help="읽기만 하고 파일을 안 쓴다")
    ap.add_argument("--limit", type=int, default=50, help="한 번에 읽을 개수 (최대 100)")
    ap.add_argument("--reset", action="store_true", help="체크포인트를 지우고 처음부터")
    args = ap.parse_args()

    tok = token()
    state = {"last_id": None, "seen": 0, "runs": []} if args.reset else load_state()

    q = "?limit=%d" % max(1, min(100, args.limit))
    if state.get("last_id"):
        q += "&after=" + str(state["last_id"])
    msgs = api("/channels/%s/messages%s" % (CHANNEL, q), tok)
    if isinstance(msgs, dict):
        # 실패도 남긴다. 조용히 넘어가면 멈춘 것을 못 알아본다.
        state["last_error"] = {"at": datetime.now(timezone.utc).isoformat(),
                               "why": str(msgs)[:200]}
        save_state(state, args.dry)
        print("디스코드 읽기 실패: %s" % msgs, file=sys.stderr)
        return 1

    # 디스코드는 최신부터 준다. 오래된 것부터 처리한다.
    msgs = [m for m in reversed(msgs) if (m.get("content") or "").strip()]
    state.pop("last_error", None)
    if not msgs:
        state.setdefault("runs", []).append({
            "at": datetime.now(timezone.utc).isoformat(), "new": 0, "flagged": 0})
        state["runs"] = state["runs"][-50:]
        save_state(state, args.dry)
        print("새 알림 없음")
        return 0

    rows = []
    for m in msgs:
        r = A.parse(m["content"])
        rows.append({
            "id": m["id"],
            "when": m.get("timestamp", ""),
            "who": (m.get("author") or {}).get("username", ""),
            "칸": {k: r[k] for k in A.ORDER},
            "기타": r.get("기타", {}),
            "표시": marks(r),
            "원문": m["content"],
        })

    flagged = [x for x in rows if x["표시"]]
    print("새 알림 %d건 · 표시 붙은 것 %d건" % (len(rows), len(flagged)))
    for x in rows:
        org = x["칸"].get("대상 조직", "")
        print("  %s  %-28s %s" % (x["when"][:16], org[:28],
                                  " / ".join(x["표시"])[:60] or "표시 없음"))

    if args.dry:
        print("\ndry run. 파일을 안 썼다.")
        return 0

    QUEUE.mkdir(parents=True, exist_ok=True)
    day = datetime.now(timezone.utc).astimezone().strftime("%Y%m%d")
    md = QUEUE / ("알림_%s.md" % day)

    L = []
    if not md.exists():
        L += ["# 감시 알림 큐  %s" % day, "",
              "`alert_watch.py` 가 쌓는다. **거르지 않고 표시만 붙인다.**",
              "표시가 붙었다고 버리는 것이 아니다. ③ 사전 확인에서 사람이 정한다.", ""]
    for x in rows:
        L += ["---", "", "## %s · %s" % (x["when"][:19], x["칸"].get("대상 조직", "(대상 미상)")),
              "", "    메시지 %s" % x["id"], ""]
        if x["표시"]:
            L += ["**표시**"]
            L += ["- %s" % t for t in x["표시"]]
            L += [""]
        else:
            L += ["**표시 없음.** 유출 감시처에서 왔고 규모 표기가 있다.", ""]
        L += ["```"]
        L += ["    %-10s %s" % (k, v) for k, v in x["칸"].items()]
        L += ["```", ""]
        if x["기타"]:
            L += ["기타 (버리지 않고 들고 있다)", "```",
                  json.dumps(x["기타"], ensure_ascii=False, indent=2), "```", ""]

    with md.open("a", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")

    state["last_id"] = msgs[-1]["id"]
    state["seen"] = state.get("seen", 0) + len(rows)
    state.setdefault("runs", []).append({
        "at": datetime.now(timezone.utc).isoformat(),
        "new": len(rows), "flagged": len(flagged)})
    state["runs"] = state["runs"][-50:]
    save_state(state, args.dry)

    print("\n쌓음  %s" % md)
    print("누적 %d건" % state["seen"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
