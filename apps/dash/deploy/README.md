# 대시보드 배포

팀원이 각자 PC 없이 보고 O/X 를 고르고 수집을 돌립니다. **산출물 사이트와 별도 배포**입니다.

    로컬        python apps/dash/serve.py       — 굽기 · O/X · 이 PC 에서 일감 돌리기
    배포        darkchoco-dash (Cloudflare)     — 보기 · O/X · Actions 로 수집 돌리기

**최현서 PC 가 꺼져 있어도 팀원이 최신을 봅니다.** 화면이 열릴 때마다 Worker 가
노션을 직접 읽습니다. 굽고 올리는 일이 필요 없습니다.

    지금    노션 → Worker 가 열릴 때마다 직접 읽음 → 팀원이 봄
    전에    노션 → 최현서 PC 에서 굽기 → 배포 → 그제야 팀원이 봄

전에는 최현서가 굽고 올려야만 팀원 화면이 갱신됐습니다. 그러면 서버에 올린 뜻이
없습니다. 2026-09-08 에 그것을 지적받아 바꿨습니다.

## 배포판과 로컬판이 다른 것

| | 로컬 | 배포 |
|---|---|---|
| 사건 목록 | 구운 파일 | **노션을 직접 읽음** (60초 캐시) |
| 게시처 DB 집계 | 구운 파일 | 노션을 직접 읽음 (60초 캐시, 갈래마다 8판 상한. 하위 요청 최대 44) |
| O/X | 노션에 씀 | 노션에 씀 |
| 수집 표 절 | 이 PC 의 SQLite | **안 냅니다** |
| 일감 돌리기 | 이 PC 에서 실행 | **GitHub Actions 에 맡김** |
| 최근 실행 · 설정 | 냅니다 | 안 냅니다 |

「수집 표」 절을 배포판에 안 내는 이유는, 그 숫자가 최현서 PC 의 SQLite 를 센 것이라
남의 서버에서는 셀 수가 없기 때문입니다. 0 을 내면 「표가 비었다」 로 읽혀 더 나쁩니다.

`track.py` 쪽 일감 셋(집계처 · 관측 가져오기 · 보고서)은 워크플로가 아직 없어
로컬에만 있습니다. 워크플로를 만들면 `worker.js` 의 `일감표` 에 더하면 됩니다.

## 반드시 자물쇠를 먼저 겁니다

**이 화면에는 피해 조직 실명 139줄과 아직 사람이 안 가른 미검토 줄이 들어 있습니다.**
지도는 같은 데이터에서 「웹에 올림 = 예」 를 통과한 여덟 줄만 이름을 내보냅니다.
자물쇠 없이 올리면 그 관문이 통째로 우회됩니다.

#### 실제로 한 번 우회됐습니다 (2026-09-08)

`wrangler.jsonc` 에 **`run_worker_first: true`** 를 안 적고 올렸습니다. 기본값에서는
정적 자산이 Worker 보다 먼저 서빙되어, 인증 코드가 아예 안 돕니다. 배포 주소를
열어 보니 비밀번호를 안 묻고 화면이 그대로 나왔습니다. 실명 139줄이 보이는 상태로
잠깐 열려 있었습니다.

한 줄이 빠져 안전장치가 통째로 무력화된 것은 이번이 세 번째입니다.
8/28 에는 잡 ID 가 한글이라 워크플로 쉰 번이 전부 실패했고, 9/8 오후에는 같은 이유로
`collect.yml` 이 통째로 거부됐습니다. **셋 다 문법 오류가 아니라 조용한 무시였습니다.**
그래서 배포 뒤에 실물로 확인하는 절차를 아래 3번에 두었습니다.

### 1. 비밀번호와 토큰을 비밀값으로

```bash
cd apps/dash/deploy
npx wrangler secret put DASH_PASSWORD
npx wrangler secret put NOTION_TOKEN
npx wrangler secret put GH_TOKEN
```

붙여 넣으라고 나오면 값을 넣습니다. **파일이나 설정에 적지 않습니다.**

| 비밀값 | 없으면 |
|---|---|
| `DASH_PASSWORD` | **아무도 못 들어옵니다** |
| `NOTION_TOKEN` | 화면이 통째로 안 나옵니다. 사건 목록을 이 토큰으로 읽습니다 |
| `GH_TOKEN` | 보기와 O/X 는 되고 **수집 돌리기만** 안 됩니다 |

`DASH_PASSWORD` 는 팀이 함께 쓰는 비밀번호입니다. 브라우저 기본 인증이라 처음 열 때
창이 뜨고 한 번 넣으면 브라우저가 기억합니다. **아이디 칸은 아무거나 됩니다.**

**이 값이 없으면 아무도 못 들어옵니다.** 깜빡하고 배포했을 때 화면이 통째로 열려 있는
것보다 낫다고 보고 그렇게 뒀습니다.

`NOTION_TOKEN` 은 사건 목록을 읽고 O / X 를 쓰는 데 씁니다. 배포판은 구운 파일을
안 쓰므로 이 값이 없으면 화면에 이유만 나옵니다.

`GH_TOKEN` 은 화면의 [돌리기] 단추가 GitHub Actions 를 시작시킬 때 씁니다.
GitHub → Settings → Developer settings → Personal access tokens 에서 만듭니다.

    fine-grained 를 고르고 MukSilver/darkchoco 하나만 고릅니다
    권한은 Actions: Read and write 하나면 됩니다
    만료를 짧게 둡니다. 마감이 9/14 이므로 그 언저리가 적당합니다

**Contents 나 Secrets 권한을 주지 않습니다.** 이 토큰으로 할 수 있는 것은
`worker.js` 의 `일감표` 에 적힌 워크플로를 시작시키는 것뿐이어야 합니다.

### 왜 Cloudflare Access 가 아닌가

**Access 는 Cloudflare 에 등록된 도메인에만 걸립니다.** `workers.dev` 주소에는 못 겁니다.
도메인이 생기면 그때 Access 로 옮기면 되고, Worker 가 `Cf-Access-Jwt-Assertion` 헤더도
같이 보므로 코드를 안 고쳐도 됩니다. 둘 중 하나만 맞으면 통과합니다.

### 2. 올립니다

```bash
cd apps/dash/deploy && npx wrangler deploy
```

**굽지 않아도 됩니다.** 배포판은 화면이 열릴 때마다 Worker 가 노션을 직접 읽습니다.
`build.py` 는 로컬 화면(`serve.py`)에만 씁니다.

올린 뒤 나오는 주소를 열면 비밀번호 창이 뜹니다.

### 3. 올린 뒤 반드시 실물로 확인합니다

**배포가 성공했다는 말은 자물쇠가 걸렸다는 뜻이 아닙니다.** 위에 적은 우회 사고에서
wrangler 는 「Success!」 를 냈고 화면은 열려 있었습니다. 아래 둘을 직접 봅니다.

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://<주소>/index.html
curl -s -o /dev/null -w "%{http_code}\n" https://<주소>/data/dash.js
```

**둘 다 401 이어야 합니다.** 200 이 하나라도 나오면 그 순간 실명이 공개된 상태입니다.
`run_worker_first` 부터 확인하고, 고칠 때까지 주소를 아무에게도 주지 않습니다.

## 무엇이 올라가나

    index.html      화면
    worker.js       노션을 읽고 쓰고, Actions 를 시작시키는 코드
    data/dash.js    올라가긴 하지만 **안 쓰입니다**

`data/dash.js` 는 Worker 가 그 경로를 가로채므로 배포판에서 나가지 않습니다. 로컬
화면이 쓰는 파일이라 폴더에 남아 있을 뿐입니다. 굽지 않은 채 올려도 화면은 정상입니다.

`*.py` 와 `deploy/` 는 안 올라갑니다. 굽는 도구와 로컬 서버는 배포에 필요 없습니다.

무엇이 실제로 올라가는지는 올리기 전에 볼 수 있습니다. `Ignoring asset:` 줄이
제외된 것이고, 그 뒤 목록에 남은 것만 올라갑니다.

```bash
cd apps/dash/deploy && WRANGLER_LOG=debug npx wrangler deploy --dry-run 2>&1 | grep -i "ignoring asset"
```

맨 위에 나오는 「Read N files」 는 **거르기 전 숫자입니다.** 그 수가 크다고 다 올라가는
것이 아니고, 반대로 그 수만 보고 안심해서도 안 됩니다. `Ignoring asset:` 줄을 셉니다.

## 자동으로 갱신하려면

`collect.yml` 에 굽기와 배포 단계를 더하면 여섯 시간마다 화면도 최신이 됩니다.
그러려면 `CLOUDFLARE_API_TOKEN` 과 `CLOUDFLARE_ACCOUNT_ID` 를 레포 비밀값에 넣습니다.
