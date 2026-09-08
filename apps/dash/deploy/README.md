# 대시보드 배포

팀원이 각자 PC 없이 보고 O/X 를 고르게 합니다. **산출물 사이트와 별도 배포**입니다.

    로컬        python apps/dash/serve.py       — 굽기 · O/X · 일감 돌리기
    배포        darkchoco-dash (Cloudflare)     — 보기 · O/X.  일감 돌리기는 없음

일감 돌리기가 배포판에 없는 이유는 단순합니다. 남의 서버는 최현서 PC 의 수집기를
못 돌립니다. 수집은 GitHub Actions 가 여섯 시간마다 합니다
(`.github/workflows/collect.yml`).

## 반드시 자물쇠를 먼저 겁니다

**이 화면에는 피해 조직 실명 139줄과 아직 사람이 안 가른 미검토 줄이 들어 있습니다.**
지도는 같은 데이터에서 「웹에 올림 = 예」 를 통과한 여덟 줄만 이름을 내보냅니다.
자물쇠 없이 올리면 그 관문이 통째로 우회됩니다.

### 1. Cloudflare Access 로 잠급니다

Zero Trust → Access → Applications → Add an application → Self-hosted.
도메인에 배포 주소를 넣고, 정책에 팀원 이메일을 넣습니다.

Worker 는 `Cf-Access-Jwt-Assertion` 헤더가 있는지 봅니다. 없으면 403 입니다.
Access 를 안 거치고 Worker 주소로 곧장 오는 길을 막습니다.

**시험 중에만** `wrangler.jsonc` 의 `ACCESS_OPTIONAL` 을 `"yes"` 로 둘 수 있습니다.
그동안은 주소를 아는 사람이 다 봅니다. 시험이 끝나면 되돌립니다.

### 2. 노션 토큰을 비밀값으로

```bash
cd apps/dash/deploy
npx wrangler secret put NOTION_TOKEN
```

붙여 넣으라고 나오면 토큰을 넣습니다. **파일이나 설정에 적지 않습니다.**

### 3. 굽고 올립니다

```bash
python apps/dash/build.py          # 노션과 표를 읽어 data/dash.js 를 만든다
cd apps/dash/deploy && npx wrangler deploy
```

## 무엇이 올라가나

    index.html      화면
    data/dash.js    구운 데이터
    worker.js       O/X 를 노션에 쓰는 코드

`*.py` 와 `deploy/` 는 안 올라갑니다. 굽는 도구와 로컬 서버는 배포에 필요 없습니다.

## 자동으로 갱신하려면

`collect.yml` 에 굽기와 배포 단계를 더하면 여섯 시간마다 화면도 최신이 됩니다.
그러려면 `CLOUDFLARE_API_TOKEN` 과 `CLOUDFLARE_ACCOUNT_ID` 를 레포 비밀값에 넣습니다.
