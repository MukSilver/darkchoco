#!/usr/bin/env python3
"""수집한 값 하나가 갖는 꼴. **세 소스가 이것만 공유한다.**

랜섬·텔레그램·포럼은 망도 인증도 원본 구조도 다르다. 같은 방식으로 못 모은다.
같을 수 있는 것은 **모아 놓은 결과의 꼴** 하나뿐이라 그것을 여기서 정한다.

## 네 상태

빈칸을 남기지 않는다. 값이 없으면 왜 없는지를 남긴다.

    값        봤고 있었다                    값 + 언제 + 어디서
    없음      **봤는데 없었다.** 부재의 근거가 된다
    못 봄     보려다 막혔다. 부재의 근거가 못 된다   + 사유
    안 봄     아예 안 봤다                   키를 안 만든다

**`없음` 과 `못 봄` 을 가르는 것이 이 모듈의 핵심이다.**
검색으로 못 찾은 것을 `없음` 으로 적으면 안 된다. 그건 `못 봄` 이다.
DB 를 직접 열어 그 줄이 없는 것을 확인했을 때만 `없음` 이다.

## 확신도는 상태와 다른 축이다

    확인      직접 봤다
    추정      다른 것에서 미루어 알았다
    미확인    값은 있는데 맞는지 모른다

`추정` 을 상태에 섞지 않는다. 추정한 값도 값이고, 다만 확신도가 낮은 것이다.

## 날짜는 언제나 절대 날짜다

"어제", "최근" 같은 표현을 쓰지 않는다. 나중에 읽는 사람이 기준을 모른다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date

# 상태 넷. 이 밖의 값을 쓰지 않는다
값 = "값"
없음 = "없음"
못봄 = "못 봄"
안봄 = "안 봄"
STATES = (값, 없음, 못봄, 안봄)

# 확신도 셋. 상태와 별개 축이다
확인 = "확인"
추정 = "추정"
미확인 = "미확인"
SURE = (확인, 추정, 미확인)


@dataclass
class V:
    """값 하나. 상태·확신도·출처·확인일을 늘 같이 들고 다닌다."""
    state: str = 안봄
    v: object = None
    why: str = ""          # 못 봄일 때의 사유
    src: str = ""          # 어디서 봤나
    day: str = ""          # 언제 봤나. 절대 날짜
    sure: str = 확인

    def __post_init__(self) -> None:
        if self.state not in STATES:
            raise ValueError("모르는 상태: %r. 쓸 수 있는 것은 %s" % (self.state, STATES))
        if self.sure not in SURE:
            raise ValueError("모르는 확신도: %r. 쓸 수 있는 것은 %s" % (self.sure, SURE))
        if self.state == 못봄 and not self.why:
            raise ValueError("못 봄에는 사유가 있어야 한다. 없으면 안 봄이다")
        if self.state == 값 and (self.v is None or self.v == ""):
            raise ValueError("값 상태인데 값이 비었다. 없음이나 못 봄을 쓸 것")

    # ── 만드는 법 ───────────────────────────────
    @staticmethod
    def 봤다(v, src: str = "", day: str = "", sure: str = 확인) -> "V":
        return V(값, v=v, src=src, day=day or date.today().isoformat(), sure=sure)

    @staticmethod
    def 없다(src: str = "", day: str = "") -> "V":
        """**직접 열어 없는 것을 확인했을 때만 쓴다.** 부재의 근거가 된다."""
        return V(없음, src=src, day=day or date.today().isoformat())

    @staticmethod
    def 막혔다(why: str, src: str = "", day: str = "") -> "V":
        """보려다 못 봤다. 부재의 근거가 못 된다."""
        return V(못봄, why=why, src=src, day=day or date.today().isoformat())

    @staticmethod
    def 안봤다() -> "V":
        return V(안봄)

    # ── 읽는 법 ─────────────────────────────────
    def 있나(self) -> bool:
        return self.state == 값

    def 부재의근거인가(self) -> bool:
        """이 칸이 '그 자료는 없다' 의 근거가 되는가.

        `없음` 만 근거가 된다. `못 봄` 과 `안 봄` 은 안 된다."""
        return self.state == 없음

    def 글자(self) -> str:
        """사람이 읽는 한 줄. 산출물에 그대로 쓴다."""
        if self.state == 안봄:
            return 안봄
        if self.state == 못봄:
            return "못 봄(%s)%s" % (self.why, (" · %s" % self.day) if self.day else "")
        tail = " · ".join(x for x in (self.src, self.day) if x)
        if self.state == 없음:
            return "없음" + (" (%s)" % tail if tail else "")
        head = str(self.v)
        if self.sure != 확인:
            head = "%s: %s" % (self.sure, head)
        return head + (" (%s)" % tail if tail else "")

    def 짐(self) -> dict | None:
        """저장할 꼴. `안 봄` 은 키를 아예 안 만들려고 None 을 준다."""
        if self.state == 안봄:
            return None
        d = {"state": self.state}
        if self.state == 값:
            d["v"] = self.v
            if self.sure != 확인:
                d["sure"] = self.sure
        if self.why:
            d["why"] = self.why
        if self.src:
            d["src"] = self.src
        if self.day:
            d["day"] = self.day
        return d

    @staticmethod
    def 풀기(d: dict | None) -> "V":
        if not d:
            return V.안봤다()
        return V(d.get("state", 안봄), v=d.get("v"), why=d.get("why", ""),
                 src=d.get("src", ""), day=d.get("day", ""),
                 sure=d.get("sure", 확인))


@dataclass
class Rec:
    """수집 한 건. 칸마다 V 를 들고, 머리에 무엇을 기준으로 모았는지 적는다."""
    표본기준: str = ""       # "상위 50건 기준. 전체 아님"
    수집방식: str = ""       # api · 킷 · 내보내기 파일
    도구: str = ""           # 어느 도구 몇 판
    칸: dict = field(default_factory=dict)

    def 넣기(self, 이름: str, v: V) -> None:
        self.칸[이름] = v

    def 짐(self) -> dict:
        out = {"표본기준": self.표본기준, "수집방식": self.수집방식, "도구": self.도구,
               "칸": {}}
        for k, v in self.칸.items():
            p = v.짐()
            if p is not None:          # 안 봄은 키를 안 만든다
                out["칸"][k] = p
        return out

    def 글자(self, 순서: list[str] | None = None) -> str:
        ks = 순서 or list(self.칸)
        w = max((len(k) for k in ks), default=0)
        head = [x for x in ("표본 %s" % self.표본기준 if self.표본기준 else "",
                            "방식 %s" % self.수집방식 if self.수집방식 else "",
                            "도구 %s" % self.도구 if self.도구 else "") if x]
        out = ["    " + " · ".join(head)] if head else []
        for k in ks:
            v = self.칸.get(k)
            out.append("    %-*s  %s" % (w, k, v.글자() if v else 안봄))
        return "\n".join(out)

    def 못본칸(self) -> list[str]:
        return [k for k, v in self.칸.items() if v.state == 못봄]

    def json(self) -> str:
        return json.dumps(self.짐(), ensure_ascii=False, indent=2)
