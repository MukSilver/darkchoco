# apps/map — 생태계 지도 (다크웹 2D)

다크웹의 포럼 · 랜섬웨어 그룹 · 텔레그램 채널 · 행위자를 유형별 섬으로 묶은 헥사 지도다.
칸이 넓을수록 사건과 활동이 많은 곳이다.

    정본        생태계지도_온톨로지(설계서 기반).xlsx · 생태계지도_설계서.docx.pdf (63쪽)
                팀 구글 드라이브. PDF 와 엑셀이 어긋나면 엑셀 수식을 따른다
    담당        최현서
    배포        Cloudflare (정적 파일) — wrangler.jsonc

## 범위

| | 누가 | 지금 |
|---|---|---|
| **다크웹 2D** | 다크초코 | **이것** |
| 연결 3D | 양 팀 | 보류 (2026-09-22, 협업 건) |
| 오픈웹 2D | 닥스훈트 | 저쪽 |

## 여는 법

```
npm install
npm run dev          # http://localhost:3000
npm test             # 반출 검사 + 시험
npm run build        # out/ 에 정적 파일
```

## 자료가 흐르는 길

    노션 (사람이 판정 · 검토 · DB 반영을 찍는다)
      └ tools/bake.py  ── 반출 검사 ──→  src/data/map.json  ──→  화면
                                          (저장소에 들어간다)

**화면은 노션을 직접 부르지 않는다.** 구운 파일만 읽는다. 화면에서 노션을 부르면 반출 관문이
사라진다. 원천은 Supabase(`darkchoco-data` 의 `core` · `map`)로 옮길 예정이다 —
`tools/supa.py` · `tools/supa_schema.py` 가 1단계(칸 목록)까지 되어 있다.

### 굽기

```
NOTION_TOKEN_FILE=~/.config/darkchoco/NOTION_TOKEN_산출물.txt npm run bake
```

읽는 DB 는 `~/.config/darkchoco/map_sources.json` 이나 환경변수 `DC_MAP_<KEY>_DS` 로 받는다.
**DB id 를 저장소에 박지 않는다.** 값은 database id 가 아니라 data_source id 다.

    collect · verify                 수집 DB · 검증 DB
    forum · telegram · ransomware · actor   명부 넷 — 이 줄들이 영토가 된다
    relations                        관계선 DB (없어도 굽는다)

## 계산 규칙 (정본)

    사건 점수     신뢰 × 규모                         허위는 0
    사건 지수     round(100 × ln(1+Σ사건 점수) ÷ ln(1+섬 최댓값))
    활동도        명부 규모 원자료를 같은 식으로 누른 값. 포럼은 회원 · 게시물 · 스레드
                 지수의 평균(빈 지수는 뺀다). 행위자는 사건 수
    영토 점수     (사건 지수 + 기본점 20) × (0.5 + 활동도 ÷ 200)
    섬 몫         round(800 × S(I)^0.6 ÷ Σ) — 합이 어긋나면 가장 큰 섬에 끝전
    칸 수         섬 안에서 최대 나머지 방식. 0칸이면 1칸

`src/lib/score.ts` 가 전부 한다. 반올림은 엑셀 ROUND 와 같다 (0.5 는 0 에서 먼 쪽).

- **행위자 섬은 같은 사건을 한 번 더 센다.** 지도 사건 수는 한 번씩이다
- **날짜를 대신 넣은 사건**(게시 시각이 없어 관측 시각 · 수집일을 넣은 것)은 점수와 칸에는
  들고, 최근 30일 · 7일 창 · 상태 · 급상승에서는 빠진다
- 영토는 첫 사건이 있는 분기부터 나온다. 사건이 없는 명부 영토는 이번 분기에만 나온다

### 시험

`src/lib/canon.test.mjs` 가 정본 엑셀의 계산 결과를 그대로 내는지 본다 — 영토 178곳 전 칸,
분기별 543줄. 기준 자료 `src/lib/fixtures/canon_20260922.json` 은 엑셀에서 숫자 칸만 뽑은
것이다 (`tools/canon_fixture.py`). **엑셀은 저장소에 넣지 않는다** — 사건 탭에 피해 조직
이름이 있다.

## 반출 경계

**피해 조직 이름은 지도에 내지 않는다** (2026-09-23 최현서 결정). 가해 쪽 — 포럼 · 랜섬웨어
그룹 · 텔레그램 채널 · 행위자 DB 에 등록된 행위자 — 는 영토 이름으로 낸다.

    1. 줄 관문      「DB 반영」이 꺼졌거나 「검토 여부」가 미검토 · 사건 X 면 뺀다
    2. 읽는 칸      ALLOWED_COLS 밖의 칸을 읽으면 멈춘다. 대상 조직 · 자료 제목 ·
                   원문 URL · 다크웹 주소는 DENY_COLS. 게시자 핸들은 맞추기 전용
    3. 나가는 키    TERRITORY_KEYS · EV_KEYS · RELATION_KEYS 밖의 키가 있으면 멈춘다
    4. 값 훑기      도메인 · @ · 11자리 넘는 숫자열을 찾는다
    5. 화면         src/lib/mapData.ts 가 아는 칸만 골라 담는다

**셋째가 가장 세다.** 값 검사는 조직 이름 같은 평범한 낱말을 못 잡는다. 키로 막으면 값이
무엇이든 새 칸이면 걸린다. `npm test` 앞에 `bake:check` 가 돈다.

## 배포

```
npx wrangler login      # 한 번만
npm run deploy          # 시험 → 빌드 → out/ 을 Cloudflare 에 올린다
```

코드가 도는 Worker 가 아니라 자산만 올리는 배포다. `out/` 밖의 것은 못 올라간다.
