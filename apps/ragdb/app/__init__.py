# -*- coding: utf-8 -*-
"""질의 쪽 코드 (F-12 부터 F-16, F-18, F-19, F-21).

낱말 쪼개기(tokenize_ko)는 배치와 질의가 같은 함수를 써야 하므로 scripts/ 의 것을 그대로 부른다.
복사본을 두면 색인과 질의가 어긋난다.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCRIPTS = os.path.join(ROOT, "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)
