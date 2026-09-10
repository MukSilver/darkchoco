#!/usr/bin/env python3
"""윈도우 바로가기 흔적에서 **시스템 식별 정보**를 뽑는다.

    python tools/lnk_read.py <폴더>
    python tools/lnk_read.py <폴더> --요약

유출물에 사용자 프로필(`C:\\Users\\...`)이 들어 있으면 여기를 먼저 돌린다.
`.lnk` 와 점프 목록에는 **파일 목록에는 없는 것**이 박혀 있다.

    만든 컴퓨터 이름   그 바로가기를 만든 PC 의 NetBIOS 이름
    볼륨 일련번호      드라이브를 가른다. 라벨도 같이 나온다
    UNC 공유          `\\\\SERVER37\\GCC` 처럼 내부 파일 서버 이름과 공유 이름
    대상 경로          지금 없는 드라이브의 폴더 구조까지 남는다

2026-09-10 에 sampleenc 케이스에서 처음 썼다. 바로가기 414개와 점프 목록 53개에서
883건을 뽑아 **내부 서버 아홉 · 공유 열넷 · 사설 IP 둘**이 나왔고,
대상 특정 근거가 셋에서 다섯으로 늘었다. 파일 목록만 봐서는 하나도 안 보이던 것이다.

## 개인정보

**값을 그대로 내보내지 않는다.** 대상 경로에 사람 이름이 든 문서가 있을 수 있다.
`--요약` 은 컴퓨터 이름 · 공유 · 볼륨만 세어 내므로 **산출물에는 이쪽을 쓴다.**
칸 전체를 내는 기본 출력은 도구 입력으로만 쓰고 보고서에 붙이지 않는다.

## 점프 목록

`*.automaticDestinations-ms` 는 OLE 복합 문서이고 스트림마다 `.lnk` 가 통으로 들어 있다.
OLE 를 해석하지 않고 **파일 전체에서 `.lnk` 서명을 찾아** 그 자리부터 읽는다.
스트림 경계를 몰라도 되고, 잘린 조각은 그냥 건너뛴다.
"""
import argparse
import collections
import datetime
import io
import struct
import sys
from pathlib import Path

MAGIC = b"L\x00\x00\x00\x01\x14\x02\x00\x00\x00\x00\x00\xc0\x00\x00\x00\x00\x00\x00F"

DRIVE = {0: "알수없음", 1: "루트없음", 2: "이동식", 3: "고정", 4: "네트워크", 5: "CD", 6: "램"}

칸 = ["파일", "만든컴퓨터", "볼륨일련번호", "볼륨라벨", "드라이브종류", "UNC", "기본경로", "꼬리경로", "수정시각", "대상크기"]


def _시각(값: int) -> str:
    """윈도우 FILETIME 을 초 단위 문자열로 바꾼다. UTC 다."""
    if 값 == 0:
        return ""
    기준 = datetime.datetime(1601, 1, 1, tzinfo=datetime.timezone.utc)
    try:
        return (기준 + datetime.timedelta(microseconds=값 // 10)).strftime("%Y-%m-%d %H:%M:%S")
    except OverflowError:
        return ""


def _문자열(버퍼: bytes, 시작: int) -> str:
    """널로 끝나는 바이트열을 읽는다. 한글 경로가 있어 cp949 로 푼다."""
    if 시작 <= 0 or 시작 >= len(버퍼):
        return ""
    끝 = 버퍼.index(b"\x00", 시작) if b"\x00" in 버퍼[시작:] else len(버퍼)
    return 버퍼[시작:끝].decode("cp949", "replace")


def 읽기(바이트: bytes) -> dict:
    """바로가기 한 덩어리를 읽는다. 모양이 아니면 빈 사전을 준다."""
    if len(바이트) < 76 or 바이트[:20] != MAGIC:
        return {}

    결과 = {}
    플래그 = struct.unpack("<I", 바이트[20:24])[0]
    결과["수정시각"] = _시각(struct.unpack("<Q", 바이트[44:52])[0])
    결과["대상크기"] = struct.unpack("<I", 바이트[52:56])[0]

    자리 = 76
    if 플래그 & 0x1:  # HasLinkTargetIDList
        자리 += 2 + struct.unpack("<H", 바이트[자리 : 자리 + 2])[0]

    if 플래그 & 0x2 and 자리 + 4 <= len(바이트):  # HasLinkInfo
        크기 = struct.unpack("<I", 바이트[자리 : 자리 + 4])[0]
        정보 = 바이트[자리 : 자리 + 크기]
        if len(정보) >= 28:
            정보플래그 = struct.unpack("<I", 정보[8:12])[0]
            볼륨자리, 기본경로자리, 망자리, 꼬리자리 = struct.unpack("<IIII", 정보[12:28])

            if 정보플래그 & 0x1 and 볼륨자리 and len(정보) >= 볼륨자리 + 16:
                결과["드라이브종류"] = DRIVE.get(struct.unpack("<I", 정보[볼륨자리 + 4 : 볼륨자리 + 8])[0], "?")
                결과["볼륨일련번호"] = "%08X" % struct.unpack("<I", 정보[볼륨자리 + 8 : 볼륨자리 + 12])[0]
                라벨자리 = struct.unpack("<I", 정보[볼륨자리 + 12 : 볼륨자리 + 16])[0]
                if 라벨자리:
                    결과["볼륨라벨"] = _문자열(정보, 볼륨자리 + 라벨자리)
                결과["기본경로"] = _문자열(정보, 기본경로자리)

            # 잘린 조각에서 여기가 자주 모자란다. 길이를 먼저 본다
            if 정보플래그 & 0x2 and 망자리 and len(정보) >= 망자리 + 16:
                망 = 정보[망자리:]
                망플래그 = struct.unpack("<I", 망[4:8])[0]
                이름자리, 장치자리 = struct.unpack("<II", 망[8:16])
                결과["UNC"] = _문자열(망, 이름자리)
                if 망플래그 & 0x1 and 장치자리:
                    결과["장치"] = _문자열(망, 장치자리)

            결과["꼬리경로"] = _문자열(정보, 꼬리자리) if 꼬리자리 else ""
        자리 += 크기

    # 문자열 데이터 구간을 건너뛴다
    for 비트 in (0x4, 0x8, 0x10, 0x20, 0x40):
        if 플래그 & 비트 and 자리 + 2 <= len(바이트):
            글자수 = struct.unpack("<H", 바이트[자리 : 자리 + 2])[0]
            자리 += 2 + 글자수 * (2 if 플래그 & 0x80 else 1)

    # 추가 데이터. TrackerDataBlock(0xA0000003) 에 만든 컴퓨터 이름이 있다
    while 자리 + 8 <= len(바이트):
        덩어리 = struct.unpack("<I", 바이트[자리 : 자리 + 4])[0]
        if 덩어리 < 8 or 자리 + 덩어리 > len(바이트):
            break
        if struct.unpack("<I", 바이트[자리 + 4 : 자리 + 8])[0] == 0xA0000003 and 덩어리 >= 0x60:
            결과["만든컴퓨터"] = 바이트[자리 + 16 : 자리 + 32].split(b"\x00")[0].decode("ascii", "replace")
        자리 += 덩어리
    return 결과


def 훑기(뿌리: Path):
    """폴더 아래 바로가기와 점프 목록을 모두 읽어 한 줄씩 낸다."""
    for p in sorted(뿌리.rglob("*")):
        if not p.is_file():
            continue
        이름 = p.name.lower()
        점프 = 이름.endswith(("automaticdestinations-ms", "customdestinations-ms"))
        if not (이름.endswith(".lnk") or 점프):
            continue
        try:
            바이트 = p.read_bytes()
        except OSError:
            continue
        상대 = p.relative_to(뿌리).as_posix()

        if not 점프:
            r = 읽기(바이트)
            if r:
                r["파일"] = 상대
                yield r
            continue

        # 점프 목록은 서명을 찾아 그 자리부터 읽는다
        자리 = 0
        while True:
            자리 = 바이트.find(MAGIC, 자리)
            if 자리 < 0:
                break
            try:
                r = 읽기(바이트[자리:])
            except Exception:
                r = {}
            자리 += 20
            if r:
                r["파일"] = 상대
                yield r


def 요약내기(줄들):
    """산출물에 쓸 수 있는 집계만 낸다. 경로는 내지 않는다."""
    컴퓨터, 공유, 볼륨 = collections.Counter(), collections.Counter(), collections.Counter()
    for r in 줄들:
        if r.get("만든컴퓨터"):
            컴퓨터[r["만든컴퓨터"]] += 1
        unc = r.get("UNC") or ""
        조각 = [x for x in unc.split("\\") if x]
        if len(조각) >= 2 and all(x.isascii() for x in 조각[:2]):
            공유["\\\\%s\\%s" % (조각[0].upper(), 조각[1].upper())] += 1
        if r.get("볼륨일련번호"):
            볼륨["%s  %s  [%s]" % (r["볼륨일련번호"], r.get("드라이브종류", "?"), r.get("볼륨라벨", ""))] += 1

    for 이름, 표 in (("만든 컴퓨터", 컴퓨터), ("공유 폴더", 공유), ("볼륨", 볼륨)):
        print("=== %s ===" % 이름)
        for k, v in 표.most_common():
            print("  %5d  %s" % (v, k))
        print()


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="바로가기와 점프 목록에서 시스템 식별 정보를 뽑는다")
    ap.add_argument("폴더", help="사용자 프로필을 푼 폴더")
    ap.add_argument("--요약", action="store_true", help="컴퓨터·공유·볼륨만 센다. **산출물에는 이쪽을 쓴다**")
    a = ap.parse_args()

    뿌리 = Path(a.폴더)
    if not 뿌리.is_dir():
        print("폴더가 없다: %s" % 뿌리, file=sys.stderr)
        return 1

    줄들 = list(훑기(뿌리))
    if not 줄들:
        print("바로가기를 못 찾았다", file=sys.stderr)
        return 1

    if a.요약:
        print("바로가기 흔적 %d 건\n" % len(줄들))
        요약내기(줄들)
    else:
        print("\t".join(칸))
        for r in 줄들:
            print("\t".join(str(r.get(c, "")) for c in 칸))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
