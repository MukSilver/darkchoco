# apps/ragdb: LLM 다크웹 RAG DB

노션에 쌓인 다크웹, 개인정보 유출 조사 기록을 근거로 한국어 질문에 문장마다 출처를 붙여 답하는 도구입니다.
근거가 없으면 답을 만들지 않습니다. 방어적 보안 연구와 교육 목적입니다.

    정본        시스템 명세서 DC-RAGDB-SYS-001 판 1.6. **이 저장소에 넣지 않았습니다** (공개 저장소라서)
    담당        김무근
    도는 곳      운영 PC. 깃허브 액션으로 돌지 않습니다
    옮겨 온 날   2026-09-29. 따로 있던 저장소(ragdb)의 그때 판을 옮겼습니다

## 지금 되어 있는 것

| 단계 | 파일 | 상태 |
|---|---|---|
| 표준 문서 받기 (F-01) | scripts/fetch_docs.py | 됨 |
| 조각 나누기 (F-05) | scripts/chunk.py, scripts/tokenize_ko.py | 됨 |
| 금지어 검사와 색인 (F-06) | scripts/masking.py, scripts/build_index.py | 됨 |
| 받기부터 색인까지 한 번에 | scripts/refresh.py | 됨 |
| 색인 검색 (손으로 확인용) | scripts/search.py | 됨 |
| 키 확인 | scripts/check_keys.py | 됨 |
| 질의 서버, 답변과 출처, 화면 | | 아직 |

## 자료가 흐르는 길

    노션 (조사, 협업)
      └ 정제 배치 (darkchoco-data) ──→ Supabase rag 스키마
                                        └ scripts/fetch_docs.py ──→ data/standard/ ──→ 조각 ──→ 색인

**이 폴더는 노션을 읽지 않습니다.** 다크웹에도 접속하지 않습니다. 입력구는 Supabase rag 스키마 하나입니다.

**받은 자료는 저장소에 넣지 않습니다.** `data/` 아래(표준 문서, 색인, SQLite)는 루트 `.gitignore` 가 막습니다.
스크립트가 필요한 폴더를 그때 만듭니다.

## 돌리기

```
pip install -r requirements.txt
cp .env.example .env      # 값을 채웁니다. .env 는 저장소에 올라가지 않습니다
python scripts/check_keys.py
python scripts/refresh.py
python scripts/search.py "질문"
```

## 읽을 것

| 파일 | 무엇 |
|---|---|
| CLAUDE.md | 코드를 쓸 때 지킬 것 |
| DESIGN.md | 화면을 만들 때 보는 시각 기준 |

명세서, 계획안, 로드맵은 담당자(김무근)에게 있습니다. 설계서는 노션 「LLM RAG DB」 페이지에 있습니다.
