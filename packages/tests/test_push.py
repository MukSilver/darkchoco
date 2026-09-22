"""push.py 의 칸 옮기기와 겹침 열쇠 시험. 노션에 붙지 않습니다.

    python packages/tests/test_push.py

2026-09-06 에 여덟 칸을 더했습니다. 검토 여부 · 수집자(자동) · 소스 · UID · 주장 규모 ·
규모 출처 · 발견일 · 한국 관련(+근거). 자동으로 올라간 줄은 「미검토」 라서 사람이
사건 O/X 를 고르기 전에는 지도와 통계에 안 잡힙니다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from hub.events import push  # noqa: E402


class 줄(dict):
    """sqlite3.Row 흉내. r["칸"] 과 r.keys() 만 쓰입니다."""


def _기본(**바꿈) -> 줄:
    r = 줄(uid="u-1", source="ransom", venue="어떤그룹", venue_kind="dls", actor="",
           target_org="어떤 회사", target_domain="example.co.kr", title="어떤 회사",
           post_url="http://example.invalid/post/1", posted_at="2026-09-01T00:00:00+00:00",
           first_seen="2026-09-02", country="KR", kind="랜섬웨어 유출", claimed_size="",
           raw="", forgotten=0, is_new=1)
    r.update(바꿈)
    return r


def _select(p: dict, 칸: str) -> str:
    return p[칸]["select"]["name"]


def _글(p: dict, 칸: str) -> str:
    return "".join(x["text"]["content"] for x in p[칸]["rich_text"])


def test_자동_줄은_미검토_자동이다():
    p = push.만들기(_기본())
    assert _select(p, "검토 여부") == "미검토"
    assert _select(p, "수집자") == "자동"


def test_소스는_items_source_로_간다():
    assert _select(push.만들기(_기본(source="ransom")), "소스") == "랜섬웨어"
    assert _select(push.만들기(_기본(source="ransomlive")), "소스") == "랜섬웨어"
    assert _select(push.만들기(_기본(source="telegram")), "소스") == "텔레그램"
    assert _select(push.만들기(_기본(source="forum")), "소스") == "포럼"
    assert "소스" not in push.만들기(_기본(source="뭔지모름"))


def test_uid_가_올라간다():
    p = push.만들기(_기본(uid="abc"))
    assert _글(p, "UID") == "abc"
    assert "UID" not in push.만들기(_기본(uid=""))


def test_규모가_있으면_출처도_같이_간다():
    p = push.만들기(_기본(claimed_size="12 GB"))
    assert _글(p, "주장 규모") == "12 GB"
    assert _select(p, "규모 출처") == "집계처 API"
    p = push.만들기(_기본(source="telegram", claimed_size="3만 건"))
    assert _select(p, "규모 출처") == "원 출처"
    # 빈 규모는 「없음」 이 아니다. 칸을 아예 안 보낸다
    p = push.만들기(_기본(claimed_size=""))
    assert "주장 규모" not in p and "규모 출처" not in p


def test_대시뿐인_규모는_안_올린다():
    """`-` 나 `n/a` 는 값이 아니라 없다는 표시다. ransomlive 의 DASH 와 같게 본다."""
    for v in ("-", "---", "n/a", "N/A", "Unknown", "?", "  -  "):
        p = push.만들기(_기본(claimed_size=v))
        assert "주장 규모" not in p, v
        assert "규모 출처" not in p, v


def test_규모_출처는_raw_에_적힌_것이_먼저다():
    """ransomlive 가 raw["규모 출처"] 에 진짜 출처를 적어 둔다. 수집기 이름으로 되짚지 않는다."""
    p = push.만들기(_기본(claimed_size="12 GB",
                       raw=json.dumps({"규모 출처": "**안 옴.** 원 출처를 봐야 안다"})))
    assert _select(p, "규모 출처") == "원 출처"
    p = push.만들기(_기본(claimed_size="12 GB", raw=json.dumps({"규모 출처": "집계처 API"})))
    assert _select(p, "규모 출처") == "집계처 API"


def test_출처를_모르는_수집기면_규모_출처를_안_보낸다():
    p = push.만들기(_기본(source="뭔지모름", claimed_size="12 GB"))
    assert _글(p, "주장 규모") == "12 GB"
    assert "규모 출처" not in p


def test_발견일은_raw_에서_온다():
    p = push.만들기(_기본(raw=json.dumps({"발견일": "2026-08-30 12:00:00"})))
    assert p["발견일"]["date"]["start"] == "2026-08-30"
    assert "발견일" not in push.만들기(_기본(raw=""))
    assert "발견일" not in push.만들기(_기본(raw="{깨진 json"))
    assert "발견일" not in push.만들기(_기본(raw=json.dumps({"발견일": ""})))


def test_발견일은_영문_키도_읽는다():
    """팀 어댑터(hub/events/sources/ransom_kr.py)는 raw["discovered"] 로 넣는다."""
    p = push.만들기(_기본(raw=json.dumps({"discovered": "2026-08-30 12:00:00"})))
    assert p["발견일"]["date"]["start"] == "2026-08-30"
    # 둘 다 있으면 한글 키가 먼저다
    p = push.만들기(_기본(raw=json.dumps({"발견일": "2026-08-01 00:00:00",
                                      "discovered": "2026-08-30 12:00:00"})))
    assert p["발견일"]["date"]["start"] == "2026-08-01"


def test_발견일은_KST_로_옮긴_뒤_자른다():
    """집계처 시각은 UTC 다. 그대로 자르면 15시 이후가 하루 앞선 날이 된다."""
    p = push.만들기(_기본(raw=json.dumps({"발견일": "2026-08-30T15:30:00+00:00"})))
    assert p["발견일"]["date"]["start"] == "2026-08-31"
    # 시간대 표시가 없으면 UTC 로 본다. stats.py 의 _kst 와 같은 규칙이다
    p = push.만들기(_기본(raw=json.dumps({"발견일": "2026-08-30 15:30:00"})))
    assert p["발견일"]["date"]["start"] == "2026-08-31"
    # 날짜만 온 것은 그대로 둔다
    p = push.만들기(_기본(raw=json.dumps({"발견일": "2026-08-30"})))
    assert p["발견일"]["date"]["start"] == "2026-08-30"


def test_한국_관련은_country_와_kr_도메인으로_본다():
    p = push.만들기(_기본(country="KR", target_domain=""))
    assert _select(p, "한국 관련") == "직접"
    assert "country=KR" in _글(p, "한국 관련 근거")
    p = push.만들기(_기본(country="", target_domain="foo.co.kr"))
    assert _select(p, "한국 관련") == "직접"
    assert ".kr" in _글(p, "한국 관련 근거")
    # 피해자명이 한글이면 그것만으로도 직접이다. 그래서 여기서는 영문 이름을 쓴다
    p = push.만들기(_기본(country="", target_domain="foo.com", target_org="Acme Ltd",
                       title="Nothing", body=""))
    assert _select(p, "한국 관련") == "미확인"


def test_한국_기업명과_한글은_글에서도_잡는다():
    """텔레그램·포럼 글은 피해자 칸이 비어 본문만 있다. 그래도 근거는 남아야 한다.

    글에서 이름을 본 것은 그 회사가 피해자라는 뜻이 아니라서 「직접」 으로 안 올린다.
    미확인으로 목록에 올리고 근거를 보여 사람이 가른다.
    """
    p = push.만들기(_기본(source="telegram", country="", target_domain="", target_org="",
                       venue="어떤채널", title="Samsung Electronics database", body=""))
    assert _select(p, "한국 관련") == "미확인"
    assert "samsung" in _글(p, "한국 관련 근거").lower()
    p = push.만들기(_기본(source="telegram", country="", target_domain="", target_org="",
                       venue="chan", title="어느 회사 고객 정보", body=""))
    assert _select(p, "한국 관련") == "미확인"
    assert _글(p, "한국 관련 근거")

    # 피해자 칸에 있으면 등급이 올라간다. 그것이 「직접」 이다
    p = push.만들기(_기본(source="telegram", country="", target_domain="",
                       target_org="Samsung Electronics", venue="chan", title="dump", body=""))
    assert _select(p, "한국 관련") == "직접"


def test_설명문에만_걸리면_미확인이되_근거는_남는다():
    """kr_filter 의 review 등급. 사람이 봐야 한다는 뜻이라 미확인으로 둔다."""
    p = push.만들기(_기본(source="telegram", country="", target_domain="", target_org="",
                       title="Some dump", body="the seller mentions korea in passing"))
    assert _select(p, "한국 관련") == "미확인"
    assert _글(p, "한국 관련 근거")          # 근거는 비우지 않는다


def test_북한_건은_한국으로_안_센다():
    p = push.만들기(_기본(country="KP", target_domain="", target_org="",
                       title="North Korea related dump", body=""))
    assert _select(p, "한국 관련") == "미확인"


def test_포럼_줄은_대상_조직이_비어도_올린다():
    """킷은 자동으로 안 돈다. 사람이 골라 돌린 글이라 이미 한 번 걸러진 것이다."""
    올림, 왜 = push.사건인가(_기본(source="forum", target_org="", venue="어느포럼"))
    assert 올림 is True
    assert 왜
    # 랜섬·텔레그램은 대상 조직이 있어야 한다
    for s in ("ransom", "telegram"):
        assert push.사건인가(_기본(source=s, target_org=""))[0] is False
        assert push.사건인가(_기본(source=s, target_org="어떤 회사"))[0] is True


def test_글_안의_한국_도메인을_잡는다():
    """포럼 글은 도메인이 칸이 아니라 제목·본문에 글로만 있다.

    2026-09-07. 애슐리 재유포 조사가 다루는 글이 이 꼴이다 — 제목에 피해 도메인이
    그대로 있고 대상 조직 칸은 비어 있다.
    """
    for 제목 in ("treethink.kr full dump", "selling daouwood.co.kr database",
               "DB: some-univ.ac.kr 2026"):
        p = push.만들기(_기본(source="forum", country="", target_domain="", target_org="",
                           venue="darkforums.st", title=제목, body=""))
        assert "한국 도메인" in _글(p, "한국 관련 근거"), 제목
    # 한국 도메인이 아니면 안 걸린다. 근거 칸 자체가 안 나갈 수도 있다
    p = push.만들기(_기본(source="telegram", country="", target_domain="", target_org="",
                       venue="chan", title="selling example.com database", body=""))
    assert "한국 도메인" not in (_글(p, "한국 관련 근거") if "한국 관련 근거" in p else "")


def test_포럼은_판정이_없어도_근거를_남긴다():
    p = push.만들기(_기본(source="forum", country="", target_domain="", target_org="",
                       title="Selling something", body="nothing korean here"))
    assert _select(p, "한국 관련") == "미확인"
    assert "사람이 고른 글" in _글(p, "한국 관련 근거")


def _외국줄(**바꿈):
    """한국 신호가 하나도 없는 줄. 국가 칸만 보고 싶을 때 쓴다.

    `_기본` 은 도메인이 `.co.kr` 이고 피해자명이 한글이라 판정기가 「직접」 으로
    본다. 2026-09-18 에 외국인가() 가 판정기를 같이 보게 되면서, 그 줄로는 국가
    칸만 따로 시험할 수 없게 됐다.
    """
    r = _기본(target_org="Some Corp", target_domain="example.com",
              title="Some Corp", body="nothing korean here")
    r.update(바꿈)
    return r


def test_명백한_외국만_뺀다():
    """--kr 의 뜻. 국가를 아는데 한국이 아닌 것만 뺀다. 모르는 것은 올린다."""
    assert push.외국인가(_외국줄(country="US")) is True
    assert push.외국인가(_외국줄(country="KR")) is False
    assert push.외국인가(_외국줄(country="")) is False          # 모른다
    assert push.외국인가(_외국줄(country="Unknown")) is False    # 모른다는 표시다


def test_국가_칸이_이름이어도_한국으로_본다():
    """CTI 텔레그램 채널은 `KR` 이 아니라 `Korea` 로 적어 보낸다.

    2026-09-18 실측. 이 줄이 「국가가 한국이 아니다」 로 빠지면서 그날 CTI 채널
    유출 알림 12줄이 전부 노션에 못 올라갔다.
    """
    for 값 in ("Korea", "korea", " South Korea ", "KOR", "Republic of Korea", "한국"):
        assert push.외국인가(_외국줄(country=값)) is False, 값


def test_모르는_나라_이름은_그대로_외국이다():
    """아는 이름만 바꾼다. 못 알아본 이름까지 「모른다」 로 접으면 관문이 헐거워진다."""
    for 값 in ("Turkey", "Argentina", "Kingdom", "USA"):
        assert push.외국인가(_외국줄(country=값)) is True, 값


def test_국가_칸이_틀려도_한국_신호가_있으면_남긴다():
    """국가 칸과 판정기를 같이 본다. 서로 다른 실패를 막는다.

    채널이 국가를 엉뚱하게 적어 보내도 `.kr` 도메인이면 사람이 볼 목록에 올린다.
    """
    assert push.외국인가(_외국줄(country="US", target_domain="lookpin.co.kr")) is False
    assert push.외국인가(_외국줄(country="US", target_org="lookpin.co.kr",
                              target_domain="")) is False


def test_설명문에_korea_만_있으면_그대로_외국이다():
    """판정기가 「미확인」 이라고 한 것은 안 남긴다.

    2026-09-18 에 아르헨티나 건이 그랬다. 「미확인」 까지 남기면 글에 `korea` 가
    한 번 나온 외국 건이 전부 들어온다.
    """
    줄 = _외국줄(country="Argentina", target_org="azuldigital.gob.ar",
               target_domain="azuldigital.gob.ar",
               body="leak also affects korea customers")
    assert push.외국인가(줄) is True


def test_국가_칸이_이름이어도_노션_국가가_채워진다():
    """`나라` 대응표도 두 글자로 맞춘 뒤에 찾는다."""
    assert _select(push.만들기(_기본(country="Korea")), "국가") == "한국"
    assert _select(push.만들기(_기본(country="KR")), "국가") == "한국"
    assert "국가" not in push.만들기(_기본(country="Turkey"))


def test_게시_성격은_kind_가_선택지에_있으면_그것이다():
    assert _select(push.만들기(_기본(kind="랜섬웨어 유출", venue_kind="forum")), "게시 성격") == "랜섬웨어 유출"
    assert _select(push.만들기(_기본(kind="확인 못 함", venue_kind="dls")), "게시 성격") == "확인 못 함"
    # kind 가 비면 전처럼 venue_kind 로
    assert _select(push.만들기(_기본(kind="", venue_kind="dls")), "게시 성격") == "랜섬웨어 유출"
    assert "게시 성격" not in push.만들기(_기본(kind="", venue_kind="그밖"))


def test_전에_보내던_아홉_칸은_그대로다():
    p = push.만들기(_기본())
    for k in ("자료 제목", "대상 조직", "게시자 핸들", "게시 플랫폼", "원문 URL",
              "게시 시각", "수집일", "국가", "게시 성격"):
        if k == "게시자 핸들":
            continue          # actor 가 비어서 안 간다. 전과 같다
        assert k in p, k
    assert _select(p, "국가") == "한국"


def test_본문은_안_간다():
    p = push.만들기(_기본())
    for k in ("body", "raw", "clues", "sample_path", "본문"):
        assert k not in p


def test_열쇠는_uid_가_먼저다():
    assert push._열쇠들(_기본(uid="u", post_url="http://x")) == ("u", "http://x")
    assert push._열쇠들(_기본(uid="", post_url="http://x")) == ("", "http://x")
    assert push._열쇠들(_기본(uid="", post_url="", title="t", venue="v")) == ("", "t|v")


def test_겹침은_uid_나_url_어느_하나로도_걸린다():
    본uid, 본열쇠 = {"u-1"}, {"http://seen"}
    assert push._겹치나(_기본(uid="u-1", post_url="http://new"), 본uid, 본열쇠)
    assert push._겹치나(_기본(uid="u-9", post_url="http://seen"), 본uid, 본열쇠)
    assert not push._겹치나(_기본(uid="u-9", post_url="http://new"), 본uid, 본열쇠)
    # uid 가 없는 줄은 url 로만 본다
    assert not push._겹치나(_기본(uid="", post_url="http://new"), 본uid, 본열쇠)


def test_노션_줄에서_uid_와_열쇠를_읽는다():
    페이지 = {"properties": {
        "자료 제목": {"title": [{"plain_text": "t"}]},
        "원문 URL": {"rich_text": []},
        "게시 플랫폼": {"rich_text": [{"plain_text": "v"}]},
        "UID": {"rich_text": [{"plain_text": "u-7"}]},
    }}
    uid, 열쇠 = push._노션줄의_열쇠(페이지)
    assert uid == "u-7" and 열쇠 == "t|v"
    # UID 칸이 없던 옛 줄
    del 페이지["properties"]["UID"]
    assert push._노션줄의_열쇠(페이지) == ("", "t|v")


def test_뺀_줄의_자취는_uid_와_글번호다():
    r = _기본(uid="u-1", src_id="somechan/1270060")
    assert push._자취(r) == "u-1 somechan/1270060"
    # 글 번호가 없으면 UID 만
    assert push._자취(_기본(uid="u-1", src_id="")) == "u-1"
    # UID 가 없던 옛 줄도 자리를 비우지 않는다
    assert push._자취(_기본(uid="", src_id="")) == "uid없음"


def test_뺀_줄_로그에_제목도_본문도_안_나간다():
    import contextlib
    import io

    뺀 = [push._자취(_기본(uid="u-%d" % i, src_id="somechan/%d" % i,
                          title="피해자 이름이 든 제목", body="본문"))
          for i in range(7)]
    버퍼 = io.StringIO()
    with contextlib.redirect_stdout(버퍼):
        push._뺀줄찍기(뺀)
    글 = 버퍼.getvalue()
    # 일곱 개를 셋씩 끊어 세 줄. 로그가 옆으로 안 흐른다
    assert len(글.strip().split("\n")) == 3
    for i in range(7):
        assert "u-%d somechan/%d" % (i, i) in 글
    # **값이 아니라 표시만 나갑니다**
    assert "제목" not in 글 and "본문" not in 글


if __name__ == "__main__":
    시험 = [(k, v) for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    실패 = 0
    for 이름, f in 시험:
        try:
            f()
            print("  통과  %s" % 이름)
        except AssertionError as e:  # noqa: PERF203
            실패 += 1
            print("  실패  %s  %s" % (이름, e))
        except Exception as e:  # noqa: BLE001
            실패 += 1
            print("  오류  %s  %s: %s" % (이름, type(e).__name__, e))
    print("%d개 중 %d개 실패" % (len(시험), 실패))
    raise SystemExit(1 if 실패 else 0)
