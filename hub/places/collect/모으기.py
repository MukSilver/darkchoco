"""수집기 일곱을 investigate.py 의 차례 그대로 돌려 Place 하나로.

**평평하게 부르면 안 됩니다.** forum-crawler 의 investigate.py 는
271줄인데, 그중 상당수가 「무엇을 먼저 보고 그 결과로 어디를 갈지」입니다.

    (2) structure 가 카테고리 씨앗을 찾습니다
    (4) 그 씨앗이 있으면 **사이트 전체를 재귀로 돌며** 게시글을 모읍니다
        없으면 지금 페이지에서만 봅니다
    (5) 앞에서 모은 글자를 다시 씁니다. 새 요청을 안 만듭니다
    (7) (4) 가 만든 표본 게시글을 받습니다

이 차례를 안 지키면 (4)(5)(7) 이 빈손으로 돕니다. 그러면 「유통 자리」
「개인정보 유출」「최근 활동」이 계속 빕니다.

수집기는 **이미 노션 칸 이름으로** 돌려줍니다.

    result["어니언 주소"] = {"value": ..., "source": ...}
    result["_들어가는_법_가입폼"] = {...}      밑줄은 조각

그래서 여기가 하는 일은 셋입니다 — 차례대로 부르고, 칸 이름을 Place 로
옮기고, **못 돈 수집기를 적습니다.**
"""

from __future__ import annotations

import time

from hub.places.place import Place, 덧붙임, 덮어쓰는칸

# 한 판 안에서 여러 수집기가 낸 값을 합칠 때 이어 붙이지 않고 갈아 끼울 칸.
# 아래 「칸 옮기기」 주석을 봅니다.
_한판에하나 = 덮어쓰는칸 | {"어니언 주소"}

__all__ = ["모으기", "칸이름"]

# 노션 칸 이름 → Place 의 칸 이름
칸이름 = {
    "어니언 주소": "어니언", "사용 언어": "언어", "들어가는 법": "들어가는법",
    "이전 주소": "이전주소", "이전 이름·별칭": "이전이름", "어떤 곳인지": "어떤곳",
    "가입 필요": "가입필요", "피해 대상": "피해대상", "한국 관련 유출": "한국유출",
    "연락수단": "연락수단", "연결된 곳": "연결된곳", "유통 자리": "유통자리",
    "개인정보 유출": "개인정보", "최근 활동": "최근활동", "최근 게시일": "최근활동",
    "주소": "주소", "상태": "상태",
}

# 밑줄로 시작하는 조각을 어느 칸에 합치나
조각 = {"_들어가는_법": "들어가는법", "_어떤_곳인지": "어떤곳",
      "_유통_자리": "유통자리", "_개인정보": "개인정보"}


def _값(v):
    """{"value": ...} 또는 {"state": "CONFIRMED_ABSENT"} 입니다."""
    if not isinstance(v, dict):
        return v
    if v.get("state") == "CONFIRMED_ABSENT":
        return None                 # 없는 것을 확인한 것입니다. 값이 아닙니다
    return v.get("value")


def _조각칸(키: str):
    for 앞, 칸 in 조각.items():
        if 키.startswith(앞):
            return 칸
    return None


def _쉬기():
    from hub.places.collect import config          # noqa: PLC0415
    time.sleep(getattr(config, "REQUEST_DELAY_MIN_SEC", 2))


def _돌리기(모은것: dict, 못돈것: list, 이름: str, 부르기):
    """수집기 하나. 죽어도 나머지를 돕니다.

    **CrawlInterrupted 만 빼고입니다.** 그것은 「이 수집기가 실패했다」가
    아니라 「이 판의 결과가 불완전하다」는 신호입니다(content.py 의
    CrawlInterrupted 문서). 챌린지에 막혀 사이트 순회가 중간에 끊긴 것이라,
    여기서 삼키고 못돈것 에만 적으면 반쪽짜리 값이 그대로 Place 로 가서
    노션에 써집니다. 덮어쓰는칸(상태·확인일·주소·최근 활동)은 조건 없이
    갈아 끼워지니 더 그렇습니다.

    원본 investigate.py:307-316 이 이 예외를 받아 「결과가 불완전하므로
    리포트를 만들지 않습니다」로 멈추고 종료코드 2 를 냈습니다. 통합하면서
    그 자리가 사라졌으므로, 위로 올려 보내 모으기() 가 같은 판단을 합니다.
    """
    from hub.places.collect.content import CrawlInterrupted   # noqa: PLC0415
    try:
        r = 부르기()
    except CrawlInterrupted:
        raise                   # 판을 멈춥니다. 여기서 삼키지 않습니다
    except Exception as e:      # noqa: BLE001
        못돈것.append(f"{이름}({type(e).__name__})")
        return
    if isinstance(r, dict):
        모은것.update(r)


def _주소뺀까닭(까닭: str) -> str:
    """중단 사유에서 괄호로 붙은 주소를 뗍니다.

    content.py 가 `챌린지 감지: <까닭> (<주소>)` 꼴로 던집니다.
    그 주소가 어니언일 수 있어 사람이 보는 칸에 그대로 두지 않습니다.
    """
    i = 까닭.rfind(" (")
    return 까닭[:i] if i > 0 and 까닭.rstrip().endswith(")") else 까닭


def _외부언급적기(p: Place, 모은것: dict) -> None:
    """⑤ crossref 가 내놓는 것은 `_발견된_외부_언급` 하나뿐입니다.

    칸이름 표에도 조각 표에도 이 열쇠가 없어서 「칸 옮기기」 루프가 통째로
    버리고 있었습니다. 원본은 report_generator 가 「발견」 섹션에 실었습니다
    (investigate.py:203-212).

    **값은 안 적습니다.** 규칙/FAQ 원문과 게시글 제목에서 뽑은 것이라
    onion 주소·t.me 채널이 그대로 들어 있고, 살펴볼것 은 화면으로 나갑니다.
    p.연결된곳 에 넣지도 않습니다 — 그 칸은 「우리 명부에 있는 곳」만
    담는데(probe/forum.py 의 links.찾기), 여기 후보는 명부와 대조를 안 한
    것이라 섞으면 칸의 뜻이 무너집니다. 원본도 확정 칸에는 안 넣었습니다.

    그래서 **몇 건을 어떤 갈래로 봤는지만** 남깁니다. 값은 스냅샷에 있습니다.
    """
    언급 = 모은것.get("_발견된_외부_언급") or []
    if not isinstance(언급, list) or not 언급:
        return
    어니언 = sum(1 for x in 언급 if ".onion" in str(x).lower())
    채널 = sum(1 for x in 언급 if "t.me/" in str(x).lower())
    그밖 = len(언급) - 어니언 - 채널
    조각들 = [f"어니언 {어니언}", f"채널 {채널}", f"그 밖 {그밖}"]
    덧붙임(p, f"규칙 페이지·게시글 제목에서 외부 언급 {len(언급)}건 "
             f"({' · '.join(조각들)}) — 스냅샷에서 확인할 것")


def _후보적기(p: Place, 모은것: dict, activity, content) -> None:
    """운영자 후보 · 눈에 띄는 유출 후보 · 최근 한국 관련 건. **건수만.**

    셋 다 `_표본_게시글` 에 category 가 붙어 있어야 뜻이 있습니다. 그것은
    content.crawl_site() 경로에서만 붙으므로 단일 페이지 경로에서는 대개
    빈 결과입니다 — 정상입니다(원본 investigate.py:233-235 주석).

    핸들과 게시글 제목은 안 적습니다. 제목에 유출 대상 이름이 그대로 들어
    있는 것이 흔해서, 화면으로 나가는 살펴볼것 에 올릴 값이 아닙니다.
    """
    표본들 = 모은것.get("_표본_게시글") or []
    if not 표본들:
        return
    try:
        운영자 = activity.find_operator_candidates(표본들) or {}
        눈에띔 = content.find_notable_leak_candidates(표본들) or []
        한국것 = content.find_korea_specific_leaks(표본들) or []
    except Exception:       # noqa: BLE001  후보 뽑기가 죽어도 수집 결과는 씁니다
        return
    조각들 = []
    if 운영자.get("handles"):
        조각들.append(f"운영자 후보 {len(운영자['handles'])}명")
    if 눈에띔:
        조각들.append(f"눈에 띄는 유출 후보 {len(눈에띔)}건")
    if 한국것:
        조각들.append(f"한국 관련 최근 {len(한국것)}건")
    if 조각들:
        덧붙임(p, " · ".join(조각들) + " — 스냅샷에서 확인할 것")


def 모으기(연것, 이름: str, *, 갈래: str = "forum",
        source: dict | None = None, 마감: float | None = None) -> Place:
    """한 곳을 깊게 봅니다. investigate.py 의 차례 그대로입니다.

    마감(time.time() 값)은 사이트 전체 순회에만 겁니다. 나머지 수집기는 쪽을 몇 장만 엽니다.
    """
    p = Place(갈래=갈래, 이름=이름, 주소=연것.최종주소 or 연것.주소)
    if not 연것.봤나():
        p.못본이유 = 연것.못본이유
        return p
    p.두드림 = True

    src = dict(source or {})
    src.setdefault("name", 이름)
    src.setdefault("url", 연것.주소)

    from hub.places.collect import (access, activity, availability,   # noqa: PLC0415
                                    content, crossref, snapshot, stats, structure)
    # 차례와 「무엇을 받아야 도는가」는 collect/__init__.py 에 이미 적혀
    # 있습니다. 여기에 손으로 또 적어 두면 둘이 어긋나도 아무도 모릅니다.
    # 그래서 개수와 page 가 필요한 수집기 목록을 그 표에서 꺼내 씁니다.
    from hub.places.collect import 차례, page가필요한가          # noqa: PLC0415

    모은것: dict = {}
    못돈것: list[str] = []
    page = 연것.page
    돈것 = 0

    # **CrawlInterrupted 는 판 전체를 멈춥니다.** 아래 어느 수집기에서
    # 나든 여기서 받습니다. _돌리기 가 안 삼키고 올려 보냅니다.
    try:
        if page is None:
            # 글자만 있는 것으로 되는 것만 돕니다. 나머지는 왜 못 했는지 적습니다.
            못돈것 += [n for n in 차례 if page가필요한가(n)]
            _돌리기(모은것, 못돈것, "crossref",
                  lambda: crossref.run({"첫 화면": 연것.본문}, src))
            돈것 = 1
        else:
            아이디 = src.get("name") or src.get("url") or "unknown"

            def _찍기(꼬리):
                try:
                    snapshot.save_snapshot(page, 아이디, 꼬리)
                except Exception:   # noqa: BLE001  증거를 못 남겨도 조사는 돕니다
                    pass

            # ① 살아있나
            _돌리기(모은것, 못돈것, "availability", lambda: availability.run(page, src))
            _찍기("availability_home")

            # ② 구조. 규칙 페이지를 봤다가 돌아옵니다
            _쉬기()
            _돌리기(모은것, 못돈것, "structure", lambda: structure.run(page, src))
            _찍기("structure_home_after")

            # ③④ 어디서 표본을 뜨나. **여기가 갈립니다.**
            표본주소 = src.get("sample_list_url")
            씨앗 = 모은것.get("_사이트_카테고리_시드", [])
            if 표본주소:
                try:
                    from hub.places.collect import config      # noqa: PLC0415
                    page.goto(표본주소, timeout=config.PAGE_LOAD_TIMEOUT_MS,
                              wait_until=config.PAGE_WAIT_UNTIL)
                    _찍기("sample_list_page")
                except Exception:       # noqa: BLE001
                    pass
                _쉬기()
                _돌리기(모은것, 못돈것, "stats", lambda: stats.run(page, src))
                _쉬기()
                _돌리기(모은것, 못돈것, "content", lambda: content.run(page, src))
            elif 씨앗:
                _쉬기()
                _돌리기(모은것, 못돈것, "stats", lambda: stats.run(page, src))
                # **사이트 전체를 재귀로 돕니다.** 이것이 빠지면 홈페이지
                # 한 장만 보고 끝나서 (5)(7) 이 빈손이 됩니다.
                _돌리기(모은것, 못돈것, "content",
                      lambda: content.crawl_site(page, src, 씨앗, resume=False, 마감=마감))
            else:
                _쉬기()
                _돌리기(모은것, 못돈것, "stats", lambda: stats.run(page, src))
                _쉬기()
                _돌리기(모은것, 못돈것, "content", lambda: content.run(page, src))

            # ⑤ 앞에서 모은 글자를 다시 씁니다. 새 요청을 안 만듭니다
            글자 = {"표본 게시글 제목": " ".join(
                x.get("title", "") for x in 모은것.get("_표본_게시글", []))}
            규칙 = 모은것.get("_들어가는_법_구조", {})
            if isinstance(규칙, dict) and "value" in 규칙:
                글자["규칙/FAQ 페이지 원문"] = 규칙["value"]
            _돌리기(모은것, 못돈것, "crossref", lambda: crossref.run(글자, src))

            # ⑥ 가입 조건
            _쉬기()
            _돌리기(모은것, 못돈것, "access", lambda: access.run(page, src))

            # ⑦ ④ 가 만든 표본 게시글을 받습니다
            _돌리기(모은것, 못돈것, "activity",
                  lambda: activity.run(모은것.get("_표본_게시글", []), src))

            # ⑦-2 원본 investigate.py:236-239 가 ⑦ 다음에 부르던 셋입니다.
            # 통합하면서 호출부가 통째로 빠져 정의만 남은 죽은 코드였습니다
            # (activity.find_operator_candidates ·
            #  content.find_notable_leak_candidates ·
            #  content.find_korea_specific_leaks).
            #
            # 원본은 결과를 profile_report_generator 의 MD 템플릿에 실었는데
            # hub 에는 그 템플릿이 없고, 노션에 새 칸을 만들지 않는 것이
            # 규칙입니다. 그래서 **건수만** 살펴볼것에 올려 사람이 스냅샷을
            # 되짚게 합니다. 제목·핸들 값은 안 적습니다.
            _후보적기(p, 모은것, activity, content)

            돈것 = len(차례) - len([x for x in 못돈것 if not x.startswith("_")])
    except content.CrawlInterrupted as e:
        # 원본 investigate.py:307-316 과 같은 판단입니다.
        # 「결과가 불완전하므로 리포트를 만들지 않습니다.」
        #
        # 여기서 모은것 을 통째로 버립니다. 아래 「칸 옮기기」로 내려보내면
        # 반쪽짜리 값이 Place 에 실리고, 덮어쓰는칸은 조건 없이 갈아
        # 끼워집니다. 두드림 을 되돌려 놓아 노션값() 이 빈 dict 를 내게
        # 하고(place.py 의 「두드리지 않았으면 아무것도 안 씁니다」),
        # 못본이유 로 봤나() 도 False 로 만듭니다 — 둘 다 겁니다.
        #
        # 자동 재로그인·자동 챌린지 우회는 만들지 않습니다. 사람이 풀고
        # 다시 돌리는 것이 유일한 길입니다.
        까닭 = str(getattr(e, "reason", "") or e)
        p.두드림 = False
        # **주소는 뺍니다.** content.py 가 던지는 글자에 어니언 주소가
        # 붙어 있습니다. 지금은 merge.py 의 안건드림칸 때문에 이 칸이
        # 밖으로 안 나가지만, 그 규칙이 바뀌면 그때 새어 나갑니다.
        # 위 [20][21] 에서 값을 일부러 뺀 것과 같은 기준으로 맞춥니다
        p.못본이유 = f"크롤이 중단됐습니다: {_주소뺀까닭(까닭)}"[:180]
        덧붙임(p, "챌린지로 중단됐습니다 — 결과가 불완전해 이번 판 값은 "
                "안 씁니다. 사람이 챌린지를 푼 뒤 다시 돌리십시오")
        return p

    # ⑤ 가 찾은 외부 언급. page 가 없는 갈래에서도 crossref 는 돌아서
    # 여기서 한 번만 봅니다.
    _외부언급적기(p, 모은것)

    # ── 칸 옮기기
    for 키, 값 in 모은것.items():
        v = _값(값)
        if v in (None, "", [], {}):
            continue
        칸 = 칸이름.get(키) or _조각칸(키)
        if not 칸:
            continue
        옛 = getattr(p, 칸, None)
        if 키 in _한판에하나:
            # **덮어쓰는칸은 이어 붙이지 않고 갈아 끼웁니다.**
            #
            # 「어니언 주소」 도 여기서는 갈아 끼웁니다. 2026-09-24 에 명부 쪽
            # 갈래가 이어붙이는칸으로 바뀌었지만, 그것은 **노션에 있던 값에**
            # 이어 붙이는 일이고 write.py 가 합니다. 한 판 안에서 수집기 여럿이
            # 낸 어니언을 「a · b」 로 붙이면 조사기가 첫 조각만 두드려서
            # 뒤엣것이 없는 셈이 됩니다. 한 판에는 하나만 둡니다.
            # place.py 가 「기계 소관입니다. 볼 때마다 새 값으로 바꿉니다」
            # 로 정해 둔 칸입니다. 아래 이어 붙이기에 걸리면 상태가
            # 「미확인 · online」 처럼 두 값이 붙은 글자가 됩니다 —
            # Place.상태 의 기본값이 "미확인" 이라 언제나 걸렸습니다
            setattr(p, 칸,
                    " · ".join(map(str, v)) if isinstance(v, list) else v)
        elif 칸 == "유통자리":
            이제 = list(옛 or [])
            for x in (v if isinstance(v, list) else [v]):
                if x not in 이제:
                    이제.append(x)
            setattr(p, 칸, 이제)
        elif isinstance(옛, str) and 옛:
            if str(v) not in 옛:
                setattr(p, 칸, f"{옛} · {v}")
        else:
            setattr(p, 칸,
                    " · ".join(map(str, v)) if isinstance(v, list) else v)

    표본수 = len(모은것.get("_표본_게시글", []))

    # ── dls-observatory 의 판정을 얹습니다
    #
    # 수집기는 「무엇이 있나」를 봅니다. infer 는 그것을 보고 「그래서
    # 무엇인가」를 냅니다. 근거 없이는 값을 안 냅니다 — 모든 함수가
    # (값, 근거) 를 같이 돌려주고, 근거가 없으면 값도 없습니다.
    try:
        from hub.places import infer as I                  # noqa: PLC0415
        from hub.places.extract import page as PG          # noqa: PLC0415

        메타 = PG.meta_tags(연것.본문 or "")
        글자 = PG.visible_text(연것.본문 or "")
        제목 = PG.get_title(연것.본문 or "") or 이름
        설명 = 메타.get("meta_description") or ""
        # page.meta_tags() 가 내는 열쇠는 "keywords" 입니다. "meta_keywords"
        # 로 읽고 있어서 infer_format · infer_pii 의 입력 하나가 언제나
        # 빈 글자였습니다. 열쇠 이름을 실제 것에 맞춥니다
        낱말 = 메타.get("keywords") or ""
        h1 = 메타.get("h1") or ""

        if not p.언어:
            언어, _ = PG.detect_language(연것.본문 or "", 글자)
            if 언어:
                p.언어 = 언어

        막힘 = PG.detect_gate(연것.본문 or "", 글자)
        if not p.들어가는법 and 막힘.get("how_to_enter"):
            p.들어가는법 = 막힘["how_to_enter"]
        if p.가입필요 is None and 막힘.get("signup_required") is not None:
            p.가입필요 = bool(막힘["signup_required"])

        꼴, 근거 = I.infer_format(갈래, 설명, 제목, 낱말, h1=h1, name=이름)
        if 꼴 and not p.형식:
            p.형식 = 꼴
        개인, 근거2 = I.infer_pii(갈래, 설명, 제목, 낱말, h1=h1, fmt=꼴)
        if 개인 and not p.개인정보:
            p.개인정보 = 개인
        자리, _ = I.infer_distribution(갈래, 설명, 제목, h1=h1,
                                     listing_links=표본수)
        for x in (자리 or []):
            if x not in p.유통자리:
                p.유통자리.append(x)
    except Exception:       # noqa: BLE001  판정이 죽어도 수집 결과는 씁니다
        pass

    표본 = len(모은것.get("_표본_게시글", []))
    p.받은곳 = f"수집기 {max(돈것, 0)}/{len(차례)} ({연것.여는법})"
    if 표본:
        p.받은곳 += f" · 표본 게시글 {표본}"
    if 못돈것:
        # **조용히 빠뜨리지 않습니다.** 왜 칸이 비었는지 나중에 찾을 수
        # 있어야 합니다.
        덧붙임(p, "못 돈 수집기: " + ", ".join(못돈것))
    return p
