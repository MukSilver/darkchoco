"""hub — 수집기들을 한 자리에서 부릅니다.

도구를 새로 만들지 않습니다. 이미 있는 도구를 어댑터로 감싸 부르고,
결과를 한 표(dc_store)에 넣습니다. 각 도구는 자기 자리에 그대로 있고
주인도 그대로입니다.

    python dc.py run                모든 어댑터
    python dc.py run --only tg-preview
    python dc.py run --dry          밖에 요청을 안 보내고 준비만 봅니다
"""
