# 유출 대응 가이드라인

개인정보 유출 안내를 받은 사람이 무엇부터 해야 하는지 한 장으로 보여 주는 사이트입니다. 설계는 노션 「개인 대응 가이드라인」의 설계서를 따릅니다.

    담당        김무근
    배포        Cloudflare (정적 파일). 설정은 wrangler.jsonc, 올리는 것은 루트의 `.github/workflows/guide.yml`
    옮겨 온 날   2026-09-29. 따로 있던 저장소(guide)의 그때 판을 옮겼습니다

## 돌리기

```
npm install
npm run dev        # 개발 서버
npm test           # 규칙 시험 (Vitest)
npm run build      # 정적 빌드 → dist/
npm run e2e        # 브라우저 시험 (Playwright). 처음 한 번 npx playwright install chromium
```

**새 클론은 사고 목록이 빈 채로 뜹니다.** 사고 목록(`src/data/cases.json`)과 칸 그림(`flow.json`)은
저장소에 없습니다. `dev`, `build`, `test` 앞에 `scripts/ensure-data.mjs` 가 빈 파일을 만듭니다.
조치, 창구, 등급표 같은 고정 내용은 저장소에 있어서 안내문 경로(/notice/)는 그대로 됩니다.
실제 사고를 보려면 `.env` 에 `SUPABASE_URL` 과 `SUPABASE_ANON_KEY` 를 넣고 아래를 돌립니다.

```
npm run fetch-db
```

## 구조

| 자리 | 위치 |
|---|---|
| 규칙 (등급표, 조치 고르기, 순서) | src/lib/rules.ts, tests/rules.test.ts |
| 고정 내용 (조치, 창구, 등급표, 항목 이름) | src/data/*.json |
| 구워 오는 파일 (저장소에 없음) | src/data/cases.json, src/data/flow.json |
| 화면 | src/pages, src/islands (Preact), src/layouts/Base.astro |
| 공통 동작 (도움말, 연결 강조, 알림, 진행 막대) | src/lib/ui.ts |
| 가이드 DB 표 | supabase/schema.sql |
| 받기와 배포 | scripts/, 루트의 .github/workflows/guide.yml, guide-links.yml |

## 자료 흐름

노션(협업) → darkchoco-data 배치 → Supabase guide 스키마 → `scripts/fetch-db.mjs` → 스냅샷 → 빌드 → 정적 페이지 → 방문자

- 방문자는 정적 페이지만 받습니다. DB나 노션을 직접 부르지 않습니다.
- 사고 하나는 수집 DB의 게시글 하나입니다. 「같은 사건」으로 이어진 게시글은 사고 하나로 묶습니다. 업종은 거르는 기준일 뿐 사고를 합치지 않습니다.
- 사고 제목은 들여올 때 「{업종} 분야 유출 사고, {게시 연월} (LEAK-{번호})」로 만듭니다.
- 검증 DB 「DB 반영」은 지도, RAG DB와 함께 쓰는 공개 스위치 하나입니다. 가이드는 거기에 「유출 항목이 하나라도 있어야 함」만 더합니다. 수집 DB에 「DB 반영」 칸이 아직 없으면 「웹에 올림」이 예인 줄을 같은 뜻으로 읽습니다.
- 체크한 진행은 방문자의 브라우저에만 저장됩니다. 서버에 두지 않습니다.

## 처음 한 번 할 것

1. GitHub 비밀값: GUIDE_SUPABASE_URL, GUIDE_SUPABASE_ANON_KEY, GUIDE_CLOUDFLARE_API_TOKEN, GUIDE_CLOUDFLARE_ACCOUNT_ID, GUIDE_DISCORD_WEBHOOK. 변수: GUIDE_SITE_URL. 지도의 Cloudflare 비밀값과 계정이 달라 이름을 나눴습니다.
2. 노션 읽기와 사고 들여오기는 정제 배치(darkchoco-data)가 합니다. 이 폴더는 Supabase 의 guide 스키마를 읽기만 합니다.
3. 조치, 등급표, 단계, 창구를 새로 넣을 때만 `node scripts/seed-db.mjs` 를 씁니다 (서비스 키가 필요합니다).
4. 검증 DB 「핵심 검증 결과」에 「샘플 확인」이 찍혀 있으면 그 게시글의 유출 항목을 확인된 것으로 봅니다. 따로 채울 칸은 없습니다.

## 지킬 것

- 이름, 전화번호 같은 개인정보를 입력받는 곳을 두지 않습니다.
- 진행 기록을 서버에 두지 않습니다. 로그인이나 저장 기능을 붙이지 않습니다.
- 외부 요청을 두지 않습니다. 글꼴은 public/fonts 에 직접 둡니다.
- Worker 코드를 두지 않습니다. 헤더는 public/_headers 로만 다룹니다.
- 창구와 주소는 기관 공식 자료로 확인한 것만 넣습니다.
- 회사 이름을 싣지 않습니다. 사고 제목은 업종, 게시 연월, 사건 번호로만 만듭니다.
- 사고 목록을 저장소에 넣지 않습니다. 루트 `.gitignore` 가 막습니다.
