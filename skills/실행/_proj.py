# 배치 파일이 쓰는 프젝 폴더와 큐 자리. **배치 안에 한글 경로를 적지 않으려고 둔다.**
#
# cmd 는 배치 파일을 시작 시점의 코드페이지로 읽는다. 더블클릭하면 cp949 로 시작하는데
# 파일은 UTF-8 이라, 중간의 chcp 65001 로도 뒤의 한글 set 줄이 온전히 안 읽힌다
# (2026-09-06 실측: 같은 파일이 cp949 시작에서는 PROJ 가 비고 65001 시작에서는 맞게 나왔다).
# 그래서 한글은 여기 파이썬에 두고, 배치는 이 출력을 받아 set 한다.
#
# run.py 의 proj() 와 같은 규칙이다. 환경변수 DARKCHOCO_PROJ 가 있으면 그것이 먼저다.
import os
import pathlib

p = os.environ.get("DARKCHOCO_PROJ") or str(
    pathlib.Path.home() / "Documents" / "Q.E.D" / "화햇" / "화햇강의자료" / "프젝")
print("PROJ=%s" % p)
print("QUEUE=%s" % os.path.join(p, "07_케이스", "_큐"))
