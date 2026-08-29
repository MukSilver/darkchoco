"""윈도우 콘솔에서 한글·기호 때문에 죽는 것을 막습니다.

윈도우 기본 콘솔은 cp949 라서 `—` `✓` `✅` 같은 글자를 못 씁니다.
이 글자가 든 줄을 print 하면 UnicodeEncodeError 가 납니다.

무서운 것은 죽는 것 자체가 아니라 **틀린 결과로 보이는 것** 입니다.
kr-leak-alarm 테스트는 149개가 다 통과해도 한글 콘솔에서는 화면에
「통과 16 / 실패 16」 이 뜨고 종료 코드가 1 로 나옵니다. 검사가 실패한
것이 아니라 결과를 찍다가 죽은 것입니다.

    from dc_console import use_utf8
    use_utf8()

원본은 apps/dls-observatory/dls_fill.py 에 있던 블록입니다. 같은 여덟 줄이
여섯 군데에 복사되어 있어 한 곳으로 모았습니다.
"""

from __future__ import annotations

import sys

__all__ = ["use_utf8"]


def use_utf8() -> None:
    """표준 출력·오류를 UTF-8 로 바꿉니다. 안 되면 조용히 넘어갑니다.

    line_buffering=True 라야 파일로 넘겨도 진행 상황이 바로 보입니다.
    파이프로 넘길 때처럼 reconfigure 가 없는 자리에서는 아무 일도 하지
    않습니다. 여기서 죽으면 본래 하려던 일까지 못 합니다.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
        except (AttributeError, ValueError):
            pass
