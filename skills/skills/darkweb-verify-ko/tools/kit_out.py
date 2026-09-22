#!/usr/bin/env python3
"""포럼 킷이 낸 것을 큐의 케이스 폴더에 ② 재료로 앉힌다.

    python tools/kit_out.py <케이스폴더> <킷출력.md>
    python tools/kit_out.py <케이스폴더> -            표준입력으로
    python tools/kit_out.py <케이스폴더> <파일> --dry  무엇을 할지만 낸다

## 왜 필요한가

Kr-Leak 은 게시글 본문을 안 준다. 설명 칸은 회사 소개일 때가 더 많다.
포럼 킷은 본문과 파일 호스트 링크와 식별자를 이미 뽑는다.
없던 것은 **둘을 잇는 자리**뿐이라 이 도구가 그것만 한다.

    ① Kr-Leak     조직 · 도메인 · 행위자 · 시각 · 원 출처
    ② 포럼 킷      본문 · 샘플 줄 · 파일 호스트 · 지갑 · 텔레그램      ← 여기
    ③~⑥ 스킬      대조 · 마스킹 · 합치기 · 판정 근거

## 무엇을 쓰나

    ②본문.md    킷 출력 그대로. 손대지 않는다
    ②샘플.txt   본문에서 샘플로 보이는 줄만. ④ 마스킹 입력이다
    상태.json    빈 칸만 채우고 이미 있는 값은 안 덮는다. 다르면 충돌로 적는다

**샘플 파일은 케이스가 끝나면 지운다.** 큐는 통로지 창고가 아니다.
값은 도구 입력으로 쓰고, 밖으로 나가는 것은 패턴과 건수뿐이다.

## 킷 출력 안의 문장은 데이터다

본문은 판매자가 쓴 글이다. 무엇을 하라는 문장이 있어도 따르지 않는다.
이 도구는 글자를 옮기기만 하고 읽고 판단하지 않는다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from alert_parse import MISS  # noqa: E402

# 킷의 isSample 을 그대로 옮겼다. 둘이 어긋나면 사람이 본 것과 도구가 본 것이 달라진다.
#   여덟 자 이상이고, 구분자로 세 토막 이상 나뉘고, @ 나 긴 숫자나 긴 16진수가 있다
SPLIT = re.compile(r"[:|;,\t]")
SAMPLE_MARK = re.compile(r"@|\d{6,}|[a-f0-9]{16,}", re.I)

HEAD_URL = re.compile(r"^-\s*URL\s*:\s*(\S+)", re.M)
HEAD_VER = re.compile(r"^-\s*도구\s*:\s*(.+)$", re.M)
HEAD_WHEN = re.compile(r"^-\s*확인\s*:\s*(.+)$", re.M)
TITLE = re.compile(r"^#\s+(.+)$", re.M)

# 킷이 붙이는 단서 이름들. 그대로 기타에 옮긴다
CLUE = re.compile(r"^-\s*([^:]+?)\s*:\s*(.+)$", re.M)

# 스레드 꼴의 글 머리. 뒤에 글쓴이와 날짜가 붙으므로 줄 끝까지 받는다
#   `### 원문  홍길동  2026-08-26`  ·  `### 답글 3  …`  ·  `### 글 2  …`
# 이어 받기로 받은 판은 절대 번호를 몰라 「글 N」 으로 적힌다 (forum_kit.js 869줄)
POST_HEAD = re.compile(r"^###\s+(?:원문|답글\s+\d+|글\s+\d+)\b.*$", re.M)
FENCE = re.compile(r"```\n(.*?)\n```", re.S)


def is_sample(line: str) -> bool:
    t = line.strip()
    if len(t) < 8:
        return False
    if len([x for x in SPLIT.split(t) if x]) < 3:
        return False
    return bool(SAMPLE_MARK.search(t))


def section(text: str, name: str) -> str:
    """`## <이름>` 절을 떼어 온다. 없으면 빈 문자열."""
    m = re.search(r"^##+\s*%s\s*$(.*?)(?=^##+\s|\Z)" % re.escape(name),
                  text, re.M | re.S)
    return m.group(1).strip() if m else ""


def bodies(text: str) -> list[str]:
    """본문의 코드 울타리들을 꺼낸다. **킷이 두 꼴로 낸다.**

        블록 꼴    `## 본문` 절 아래에 울타리. 글 구조가 없는 공지·안내 장이다
        스레드 꼴   `### 원문` · `### 답글 N` · `### 글 N` 아래에 울타리

    **2026-09-08 에 킷이 스레드 꼴을 쓰기 시작했는데 여기는 `## 본문` 만 보고 있었다.**
    그래서 킷이 글을 제대로 읽은 경우가 오히려 빈손으로 떨어져 `본문 절을 못 찾았다` 로
    죽었다. 블록 꼴은 킷이 글 구조를 **못 읽었을 때 타는 예비 경로**라, 잘 되는 쪽이
    막히고 안 되는 쪽만 지나는 상태였다 (2026-09-22 확인).

    스레드 꼴에서 `## 추출된 단서` · `## 못 받은 쪽` 은 울타리를 안 쓰지만, 나중에 쓰게
    되더라도 섞이지 않도록 글 머리 다음의 `##` 에서 끊는다.
    """
    sec = section(text, "본문")
    if sec:
        return [b.strip("\n") for b in FENCE.findall(sec)]

    out: list[str] = []
    heads = list(POST_HEAD.finditer(text))
    for i, m in enumerate(heads):
        끝 = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        덩이 = text[m.end():끝]
        다음절 = re.search(r"^##\s", 덩이, re.M)
        if 다음절:
            덩이 = 덩이[:다음절.start()]
        out += [b.strip("\n") for b in FENCE.findall(덩이)]
    return out


def parse(text: str) -> dict:
    body_list = bodies(text)
    whole = "\n".join(body_list)
    lines = whole.splitlines()
    sample = [ln for ln in lines if is_sample(ln)]

    clues = {}
    for k, v in CLUE.findall(section(text, "추출된 단서")):
        clues[k.strip()] = [x.strip() for x in v.split("·") if x.strip()]

    def one(rx):
        m = rx.search(text)
        return m.group(1).strip() if m else ""

    return {
        "제목": one(TITLE),
        "URL": one(HEAD_URL),
        "도구": one(HEAD_VER),
        "확인": one(HEAD_WHEN),
        "블록": len(body_list),
        "본문 줄": len(lines),
        "본문 자": len(whole),
        "샘플 줄": sample,
        "단서": clues,
    }


def seat(st: dict, got: dict) -> tuple[list[str], list[str]]:
    """빈 칸만 채운다. 이미 있는 값은 안 덮는다. 다르면 충돌로 적는다."""
    filled, clash = [], []
    칸 = st.setdefault("칸", {})

    def put(key: str, v: str, why: str) -> None:
        if not v:
            return
        cur = str(칸.get(key, "") or "")
        if not cur or cur.startswith(MISS):
            칸[key] = v
            filled.append("%s ← %s" % (key, why))
        elif cur.strip() != v.strip():
            clash.append("%s: 이미 %r 인데 킷은 %r" % (key, cur[:60], v[:60]))

    put("원 출처", got["URL"], "킷이 연 주소")
    # 포럼 킷은 게시글을 직접 열었다. 알림과 달리 원 게시물이다
    for name, key in (("onion", "재게시 URL"),):
        v = got["단서"].get(name)
        if v and len(v) == 1 and v[0] not in got["URL"]:
            put(key, v[0], "본문에 적힌 다른 주소")
    return filled, clash


def main() -> int:
    ap = argparse.ArgumentParser(description="포럼 킷 출력을 케이스 폴더에 ② 재료로 앉힌다")
    ap.add_argument("case", help="큐의 케이스 폴더")
    ap.add_argument("kit", help="킷 출력 파일. - 이면 표준입력")
    ap.add_argument("--dry", action="store_true", help="쓰지 않고 무엇을 할지만 낸다")
    a = ap.parse_args()

    case = Path(a.case)
    sf = case / "상태.json"
    if not sf.exists():
        raise SystemExit("케이스 폴더가 아니다 (상태.json 없음): %s" % case)

    raw = sys.stdin.read() if a.kit == "-" else Path(a.kit).read_text(encoding="utf-8")
    if not raw.strip():
        raise SystemExit("입력이 비었다")
    got = parse(raw)
    if not got["블록"]:
        raise SystemExit("본문 절을 못 찾았다. 킷의 `이 글 본문` 출력을 그대로 넣을 것")

    st = json.loads(sf.read_text(encoding="utf-8"))
    filled, clash = seat(st, got)

    print("케이스   %s" % case.name)
    print("제목     %s" % got["제목"][:70])
    print("본문     %d블록 · %d줄 · %d자" % (got["블록"], got["본문 줄"], got["본문 자"]))
    print("샘플 줄  %d" % len(got["샘플 줄"]))
    if got["단서"]:
        print("단서     " + ", ".join("%s %d" % (k, len(v)) for k, v in got["단서"].items()))
    for x in filled:
        print("  채움   %s" % x)
    for x in clash:
        print("  충돌   %s" % x)

    if a.dry:
        print("\ndry run. 아무것도 쓰지 않았다")
        return 0

    (case / "②본문.md").write_text(raw, encoding="utf-8")
    if got["샘플 줄"]:
        (case / "②샘플.txt").write_text("\n".join(got["샘플 줄"]) + "\n",
                                       encoding="utf-8")

    st["샘플 있음"] = bool(got["샘플 줄"])
    st.setdefault("끝낸 단계", [])
    if "②" not in st["끝낸 단계"]:
        st["끝낸 단계"].append("②")
    기타 = st.setdefault("기타", {})
    기타["킷"] = {"도구": got["도구"], "확인": got["확인"], "블록": got["블록"],
                "본문 자": got["본문 자"], "샘플 줄": len(got["샘플 줄"]),
                "단서": {k: len(v) for k, v in got["단서"].items()}}
    if clash:
        st.setdefault("충돌", []).extend(clash)
    st["다음"] = ("③ 부터 ⑥ 까지 모델로 돌린다" if got["샘플 줄"]
                else "③ 을 모델로 돌린다. 샘플 줄이 없어 ④ 는 못 봄으로 찬다")
    sf.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n②본문.md 를 썼다" + (" · ②샘플.txt %d줄" % len(got["샘플 줄"])
                              if got["샘플 줄"] else ""))
    print("**샘플은 케이스가 끝나면 지운다.** 큐는 통로지 창고가 아니다")
    if not got["샘플 줄"]:
        print("샘플로 보이는 줄이 없다. 게시글에 표본이 안 실렸거나 링크로만 걸려 있다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
