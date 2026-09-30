# -*- coding: utf-8 -*-
"""질의 서버 — 설계서 「질문 한 건」 의 순서(app/pipeline.py)를 감싸 웹으로 낸다 (설계서 「API와 스냅샷 파일」).

    .venv\\Scripts\\python -m uvicorn server.main:app --host 127.0.0.1 --port 8787 --workers 1

워커는 하나다 (AD-02). 배치와 다른 프로세스에서 돈다. 정적 파일(화면, 스냅샷)은 여기서 내주지 않는다.
"""
