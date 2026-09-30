# apps/ragdb: LLM 다크웹 RAG DB

노션에 쌓인 다크웹, 개인정보 유출 조사 기록을 근거로 한국어 질문에 문장마다 출처를 붙여 답하는 도구입니다.
근거가 없으면 답을 만들지 않습니다. 방어적 보안 연구와 교육 목적입니다.

    정본        설계서 DC-RAGDB-DES-001. 노션 「LLM 다크웹 RAG DB 구축 / 설계서」에 있습니다. 문서는 설계서 하나입니다
    도는 곳      서버 전에는 각자 컴퓨터에서 손으로. 클라우드 서버 하나에 질의 서버와 주간 배치(cron)를 둘 예정. 깃허브 액션으로 돌지 않습니다
    옮겨 온 날   2026-09-29. 따로 있던 저장소(ragdb)의 그때 판을 옮겼습니다

## 지금 되어 있는 것

| 단계 | 파일 | 상태 |
|---|---|---|
| 표준 문서 받기 (F-01) | scripts/fetch_docs.py | 됨 |
| 조직 이름 찾기 | scripts/find_names.py | 됨 |
| 가리기, 가리기 검사, 조각 (F-03, F-05) | scripts/chunk.py, app/guard.py, app/pii.py | 됨 |
| 금지어 검사, 색인, 넓히기 사전 (F-06) | scripts/build_index.py, scripts/masking.py | 됨 |
| 스냅샷 굽기와 반출 관문 (F-22) | scripts/snapshot.py | 됨. 올리기는 아직 |
| 재조사 추출 (F-20) | scripts/recheck.py | 됨. 빠진 줄 명부는 받기가 같이 받아 옴 |
| 받기부터 갈아 끼우기까지 한 번에 | scripts/refresh.py | 됨 |
| 조각 검색 (F-12) | app/search.py, app/expand.py, app/kinds.py, app/rerank.py | 됨 |
| 답변과 출처, 근거 없음 (F-13, F-14, F-15) | app/answer.py, app/prompts/system.md | 됨 |
| 사전 답변 조회, 답변 재사용 (F-16, F-21) | app/store.py | 됨 |
| 질의 기록, 하루 차단기 (F-19, F-18 일부) | app/store.py, app/limits.py | 됨 |
| 질의 한 건의 순서 (설계서 「질문 한 건」) | app/pipeline.py | 됨 |
| 터미널에서 묻기 | scripts/ask.py | 됨 |
| 예비 측정 | scripts/measure.py | 됨 |
| 사전 답변 만들기와 검토 (F-17) | scripts/prepare_answers.py, scripts/review_answers.py | 됨. 평가 질문이 있어야 돕니다 |
| 평가 질문 평가 (설계서 「검증」) | scripts/evaluate.py, app/questions.py | 됨. 평가 질문이 있어야 돕니다 |
| 질의 서버, 사람 확인 (F-18 나머지) | | 아직 |
| 화면 (묻고 답하기, 출처 원문, 예시 질문) | | 아직. 디자인은 새로 짭니다 |
| 이미지 (F-08) | | 내보내지 않기로 했습니다 |
| 목록, 상세, 전체 내려받기 | | 만들지 않기로 했습니다 (2026-09-30). 훑어보기는 생태계 지도가 맡습니다 |
| 관리 화면 | | 만들지 않습니다. 운영은 터미널 스크립트로 합니다 |

## 자료가 흐르는 길

    노션 (조사, 협업)
      └ 정제 배치 (darkchoco-data) ──→ Supabase rag 스키마
           └ 받기 ──→ 이름 찾기 ──→ 가리기와 조각 ──→ 색인과 사전 ──→ 스냅샷과 반출 관문 ──→ 갈아 끼우기

**이 폴더는 노션을 읽지 않습니다.** 다크웹에도 접속하지 않습니다. 입력구는 Supabase rag 스키마 하나입니다.

**받은 자료는 저장소에 넣지 않습니다.** `data/` 아래(표준 문서, 색인, 스냅샷, 찾은 이름 목록의 사본)는 루트 `.gitignore` 가 막습니다.

**운영 기록은 Supabase 에 있습니다.** 사전 답변, 재사용 답변, 질의 기록, 비용, 재조사 후보, 평가 질문, 찾아 둔 조직 표기가 rag 스키마에 있습니다(`app/store.py`). 그래서 저장소와 `.env` 만 있으면 어느 기계에서든 같은 기록으로 돕니다. 표는 darkchoco-data 의 `migrations/0012_rag_runtime.sql`, `0013_rag_cache_and_examples.sql` 이 만듭니다.

## 나가는 글을 지키는 네 겹

피해 조직 이름, 주소, 개인정보가 답변과 스냅샷에 나오지 않게 합니다.

| 겹 | 어디서 | 무엇을 |
|---|---|---|
| 1 | 정제 배치 | 노션 칸에 적힌 조직 이름, 주소 머리가 있는 링크, 어니언 주소를 가림 |
| 2 | find_names.py, chunk.py | 본문에 다르게 적힌 조직 표기를 모델로 찾아 목록으로 가림. 도메인은 규칙으로 전부 가림. 개인정보 꼴은 그 자리만 가림 |
| 3 | snapshot.py | 구운 파일 전체를 다시 훑음. 하나라도 걸리면 새 판을 쓰지 않음 |
| 4 | pipeline.py | 답을 내보내기 직전에 한 번 더 가림. 저장해 둔 답(사전 답변, 재사용 답변)도 같음 |

장소(포럼, 텔레그램, 랜섬웨어)와 행위자의 이름은 가리지 않습니다. 검색에 필요합니다.
행위자의 다른 이름은 동일인 추정이라 가립니다.

## 돌리기

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt -r requirements-dev.txt
copy .env.example .env                                  값을 채웁니다. .env 는 저장소에 올라가지 않습니다
.venv\Scripts\python scripts\check_keys.py
.venv\Scripts\python scripts\refresh.py                 받기부터 갈아 끼우기까지
.venv\Scripts\python scripts\ask.py "질문"               터미널에서 묻기
.venv\Scripts\python scripts\ask.py --search "질문"      검색까지만 (0원)
.venv\Scripts\python -m pytest tests -q                 시험 (0원, 열쇠 없이 돕니다)
.venv\Scripts\python -m uvicorn server.main:app --host 127.0.0.1 --port 8787 --workers 1   질의 서버 (워커 하나, AD-02)
cd web && npm ci && npm run dev                         화면 개발 서버 (/api 와 /data 를 로컬로 넘김)
```

평가 질문으로 재기와 사전 답변 (평가 질문은 Supabase 에 있습니다)

```
.venv\Scripts\python scripts\question_set.py pull data\q.json   평가 질문을 파일로 받아 고칩니다
.venv\Scripts\python scripts\question_set.py push data\q.json   고친 평가 질문을 올립니다
.venv\Scripts\python scripts\evaluate.py                평가 질문으로 검색을 세 벌 잼
.venv\Scripts\python scripts\evaluate.py --answers      답변까지 잼 (모델을 부릅니다)
.venv\Scripts\python scripts\prepare_answers.py --count 사전 답변을 몇 개 만들지, 얼마쯤 들지
.venv\Scripts\python scripts\prepare_answers.py         사전 답변 만들기
.venv\Scripts\python scripts\review_answers.py          검토 전 목록. show, pass, drop
```

평가 질문 파일의 모양은 `app/questions.py` 맨 위에 적혀 있습니다. 파일은 `data/` 아래나 저장소 밖에 둡니다.

처음 한 번은 조직 이름 찾기가 문서 전체를 봅니다. 4달러쯤 듭니다. 그 뒤로는 바뀐 문서만 봅니다.

## 값을 바꾸는 곳

| 바꿀 것 | 파일 |
|---|---|
| 숫자 (후보 수, 넓히기 무게, 대기 상한, 하루 한도 등) | `.env`. 기본값과 설명은 `.env.example`, `app/config.py` |
| 내보내는 칸 | `export_columns.json`. 여기 없는 칸은 나가지 않습니다 |
| 종류를 알아내는 낱말 | `app/kind_synonyms.json` |
| 지시문 | `app/prompts/system.md`. 고치면 평가를 다시 돌리고 답 글도 읽습니다. 옛 지시문으로 만든 재사용 답변은 저절로 새로 만들어지고, 검토 전 사전 답변은 `scripts/prepare_answers.py` 로 다시 만듭니다 |

## 읽을 것

| 파일 | 무엇 |
|---|---|
| CLAUDE.md | 코드를 쓸 때 지킬 것 |

설계서와 인수인계 문서는 노션 「LLM 다크웹 RAG DB 구축」 페이지에 있습니다. 화면 디자인은 새로 짭니다.
코드 주석의 F-12, SR-19 같은 번호의 뜻은 설계서 「코드 주석의 번호」에 있습니다.
