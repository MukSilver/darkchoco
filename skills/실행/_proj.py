# 배치 파일이 쓰는 프젝 폴더와 큐 자리. **배치 안에 한글 경로를 적지 않으려고 둔다.**
#
# cmd 는 배치 파일을 시작 시점의 코드페이지로 읽는다. 더블클릭하면 cp949 로 시작하는데
# 파일은 UTF-8 이라, 중간의 chcp 65001 로도 뒤의 한글 set 줄이 온전히 안 읽힌다
# (2026-09-06 실측: 같은 파일이 cp949 시작에서는 PROJ 가 비고 65001 시작에서는 맞게 나왔다).
# 그래서 한글은 여기 파이썬에 두고, 배치는 이 출력을 받아 set 한다.
#
# run.py 의 proj() · queue_dir() 과 같은 규칙이다.
#
#   DARKCHOCO_PROJ    프젝 폴더. 없으면 아래 기본 자리
#   DARKCHOCO_QUEUE   큐 폴더. 없으면 <프젝>/VM공유폴더
#
# **큐 자리를 2026-09-09 에 바꿨다.** 전에는 `07_케이스/_큐` 였는데 거기는 결과가
# 쌓이는 자리고 재료는 공유폴더로 들어온다. 재료가 있는 자리를 큐로 본다.
# 공유폴더 이름은 VirtualBox 설정에서 정하는 것이라 사람마다 다를 수 있다.
import os
import pathlib

p = os.environ.get("DARKCHOCO_PROJ") or str(
    pathlib.Path.home() / "Documents" / "Q.E.D" / "화햇" / "화햇강의자료" / "프젝")
q = os.environ.get("DARKCHOCO_QUEUE") or os.path.join(p, "VM공유폴더")
print("PROJ=%s" % p)
print("QUEUE=%s" % q)
