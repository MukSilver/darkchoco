# 유출물 분석 도구만 든 이미지. 검증에 쓰는 파이썬 스크립트가 전부다.
#
# 이 이미지는 받은 데이터를 **실행하지 않는다.** 읽고 세기만 한다.
# 그래도 컨테이너는 VM 이 아니다. 호스트와 커널을 함께 쓴다.
# 압축을 풀거나 처음 여는 일은 VM 에서 하고, 여기에는 텍스트로 확인된 것만 넣는다.
#
#   docker build -t darkchoco-verify .
#
# 실행은 README 의 도커 절을 그대로 쓴다. 격리 옵션이 붙어 있다.

FROM python:3.12-slim

# 표준 라이브러리만 쓴다. 외부 패키지가 없으므로 받을 것이 없다.
# 받을 것이 없다는 뜻은 공급망에 기댈 자리가 없다는 뜻이다.

WORKDIR /work

COPY skills/darkweb-verify-ko/tools/ /tools/

# 루트로 돌지 않는다. 붙인 폴더에 루트 소유 파일을 만들지 않는다.
RUN useradd --create-home --uid 1000 verify \
 && chmod -R a-w /tools
USER 1000:1000

ENV PYTHONIOENCODING=utf-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    DARKCHOCO_CONFIG=/tmp/verify_config.json

# 아무것도 안 주면 무엇을 하는 이미지인지 알린다.
CMD ["python", "/tools/inspect.py", "--help"]
