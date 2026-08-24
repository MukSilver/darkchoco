# darkchoco-skills

WHS 4 darkchoco
다크웹 유출 주장 검증 스킬과 도구

## 설치

### Claude Code

```bash
git clone https://github.com/grute02/darkchoco-skills.git
cp -r darkchoco-skills/skills/darkweb-verify-ko ~/.claude/skills/
```

클로드를 새로 켠 뒤 `유출 주장 검증해줘` 라고 하면 걸린다.

### Codex

레포를 작업 폴더로 쓰거나, `AGENTS.md` 를 작업 폴더에 복사한다.

```bash
git clone https://github.com/grute02/darkchoco-skills.git
cd darkchoco-skills
codex
```

둘 다 같은 `skills/darkweb-verify-ko/references/` 를 읽는다.

### 도커

받은 데이터를 격리해서 다루고 싶으면 쓴다.

```bash
docker build -t darkchoco-verify .
```

**컨테이너는 VM 이 아니다.** 호스트와 커널을 함께 쓴다.
압축을 풀거나 처음 여는 일은 VM 에서 하고, 여기에는 텍스트로 확인된 것만 넣는다.

```bash
docker run --rm \
  --network none \
  --user 1000:1000 \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  --read-only --tmpfs /tmp \
  --memory 2g --pids-limit 128 \
  -v "$PWD/재료:/data:ro" \
  -v "$PWD/결과:/out" \
  darkchoco-verify \
  python /tools/inspect.py /data/<케이스> --out /out/<케이스>
```

| 옵션 | 막는 것 |
|---|---|
| `--network none` | 밖으로 나가는 것 전부 |
| `:ro` | 재료 폴더에 쓰기 |
| `--user 1000:1000` | 루트 실행. 붙인 폴더에 루트 소유 파일이 안 생긴다 |
| `--cap-drop ALL` | 커널 권한 |
| `--read-only` | 컨테이너 파일시스템에 쓰기. 쓸 수 있는 곳은 `/tmp` 와 `/out` 뿐이다 |
| `--memory` `--pids-limit` | 메모리 폭탄, 포크 폭탄 |

**`--tmpfs /tmp` 를 빼면 안 된다.** `--read-only` 와 짝이다.
`verify_cfg.py` 가 설정을 `/tmp` 에 쓰는데 그 자리가 막히면 죽는다.

**디스크는 못 막는다.** bind mount 에는 크기 제한이 안 걸린다.
`/out` 이 차면 호스트 디스크가 찬다. 그래서 **압축을 컨테이너에서 풀지 않는다.**

    -v /var/run/docker.sock:/var/run/docker.sock     ← 절대 붙이지 마라

붙이면 컨테이너 안에서 호스트에 루트로 컨테이너를 띄울 수 있다. 격리가 없어진다.

베이스 이미지를 고정하고 싶으면 태그 대신 다이제스트를 쓴다. 태그는 내용이 바뀐다.

    FROM python:3.12-slim@sha256:<...>

무엇이 VM 과 같고 무엇이 다른지는 `docs/도커와_VM_대조_20260824.md` 에 있다.

`--network none` 이면 노션 도구가 안 돈다. 그건 정상이다.
③ 을 `안 봄(팀 DB 없음)` 으로 적고 ⑥ 은 9번 절을 안 낸다. ④⑤ 는 그대로 돈다.

노션까지 쓰려면 네트워크를 열고 토큰 파일을 붙인다.

```bash
docker run --rm \
  --user 1000:1000 --cap-drop ALL --security-opt no-new-privileges \
  --read-only --tmpfs /tmp \
  -v "$HOME/.config/darkchoco/notion_token:/run/secrets/notion_token:ro" \
  -v "$PWD/재료:/data:ro" -v "$PWD/결과:/out" \
  darkchoco-verify python /tools/notion_find.py 수집 <대상 조직>
```

**토큰 값을 `-e` 로 넘기지 마라.** `docker inspect` 와 셸 히스토리에 남는다.
파일을 붙이고 경로를 준다.

#### 윈도우 Git Bash 에서

`/tmp` 같은 경로를 윈도우 경로로 바꿔 버린다. 앞에 이것을 붙인다.

```bash
MSYS_NO_PATHCONV=1 docker run --rm ... --tmpfs /tmp ...
```

안 붙이면 `invalid mount path: 'C' mount path must be absolute` 가 난다.
PowerShell 과 리눅스에서는 필요 없다.

#### 2026-08-24 확인함

| 확인 | 결과 |
|---|---|
| `/` 와 `/tools` 에 쓰기 | 막힘 |
| `/tmp` 에 쓰기 | 됨. `verify_cfg.py` 가 여기 쓴다 |
| 밖으로 나가는 요청 | 막힘 |
| 루트로 도는가 | 아니다. `uid=1000(verify)` |
| `inspect.py` 로 케이스 하나 | 산출물 다섯 개가 `/out` 에 나옴 |

## 웹 조회 도구

스크래핑 도구가 붙어 있으면 결과가 더 좋다. Firecrawl MCP 같은 것이다.

## 북마클릿

`bookmarklets/` 에 브라우저에서 쓰는 수집 도구가 있다. 사람이 연 페이지에서 누른다.
포럼, 킬린 유출 사이트, 디렉터리 인덱스, 구조 진단 넷이다. 자세한 것은 그 폴더의 README 를 본다.

3단계가 발행처 사이트 검색을 직접 조회하는데, 이 페이지는 검색엔진에 안 잡힌다.
직접 열어야만 보이고 평문 요청은 대부분 막힌다.

없어도 돈다. 못 본 것은 조회 실패로 적힌다.

## 언제 쓰나

포럼에서 유출 판매글을 발견했고 세 가지를 알아야 할 때.

    이게 진짜인가
    이미 우리가 아는 건인가
    사실이라면 얼마나 위험한가

## 무엇을 넣나

게시글 캡처 하나만 있어도 돈다.

| 재료 | 없으면 |
|---|---|
| 게시글 캡처 | 필수 |
| 샘플 원문 | 값 패턴이 못 봄으로 남는다 |
| 파일 트리 | 위험도 근거가 얕아진다 |

## 무엇이 나오나

| | 내용 |
|---|---|
| 1 | 팀 DB에 이미 있는 건인지. 있으면 기존 판정과 링크 |
| 2 | 규제기관·조직 입장·언론 자료 유무. 없으면 무슨 질의로 못 찾았는지 |
| 3 | 샘플 값 패턴. 실제 값은 하나도 안 나온다 |
| 4 | 재료를 한 덩어리로 정리한 표. 출처 태그와 충돌 항목 포함 |
| 5 | 계산. 레코드당 단가, 샘플 비율, 규모 대 이용자 |
| 6 | 핵심 4항목과 보조 7항목 상태 |
| 7 | 반대 증거. 양쪽 방향 다 |
| 8 | 참고 판정 다섯 축 |
| 9 | 판정이 바뀔 조건 |
| 10 | 한계. 무엇을 왜 못 봤는지 |
| 11 | 권고 세 갈래. 추가 조사 / 확인 필요 / 즉시 조치 |

## 무엇을 내가 하나

```
[사람]  1 발견 → 3 게시글 확인 (체크리스트, 파일 트리 확보)
[AI]    2 사전 확인 → 4 마스킹 → 5 재료 합치기 → 6 판정 근거 산출
[사람]  7 검토 → 8 판정
[AI]    9 DB 입력   별도 호출
```

3·7·8이 사람 자리다. 스킬이 대신하지 않는다.
8까지 끝나면 다시 불러서 DB 양식으로 받는다.

## 안 하는 것

| | 왜 |
|---|---|
| 유출 파일 다운로드 | 링크 존재만 기록 |
| 토큰이 살아있는지 확인 | 남의 자격증명을 실제로 쓰는 행위 |
| 대상 사이트 로그인·경로 추측·취약점 점검 | 공개 페이지 조회는 하되 이건 능동 행위 |
| 최종 진위 판정 | 사람이 한다 |
| 게시 | 초안까지만 |

**개인정보 값을 산출물에 내지 않는다.** 원문은 4단계 입력으로 쓰고, 나가는 것은 패턴과 건수뿐이다.
파일 트리는 값이 아니라 이름과 구조라 원문 그대로 본다.

## 도구

### tree_scan.py

유출물 파일 목록으로 초동 분석을 한다. 파일 내용은 열지 않는다.

```bash
python tools/tree_scan.py <트리파일> --md 출력.md
```

입력은 한 줄에 경로 하나, `tree` 출력, `unzip -l`, `find`, `git ls-files` 를 받는다.
자산 민감도 등급별 건수, 진위 신호, 규모 통계, 못 본 것을 낸다.

규칙은 `tools/tree_rules.json` 에 있다. 코드와 분리돼 있어 패턴만 더하면 된다.

### notion.py

노션 읽기 전용 래퍼.

```bash
python tools/notion.py search <검색어>
python tools/notion.py md <page_id> out.md
```

### notion_push.py

마크다운을 노션 페이지로 올린다. 표와 코드블록을 살린다.

```bash
python tools/notion_push.py <parent_id> "<제목>" <md파일> --dry
python tools/notion_push.py <page_id> "<제목>" <md파일> --update
```

### notion_find.py

팀 DB에 이미 있는 줄을 찾는다. 중복 조사와 중복 채번을 막는다.
사건 ID는 노션이 자동 부여하므로 **사건명·대상 조직·게시자 핸들로 찾는다.**

```bash
python tools/notion_find.py 수집 sample-mall
python tools/notion_find.py 수집 Databasehooligan
python tools/notion_find.py 검증 11번가
```

읽기만 한다.

### notion_row.py

9단계 출력을 노션 DB 행으로 만든다. **미리보기가 기본이고 `--commit` 을 붙여야 쓴다.**

```bash
python tools/notion_row.py 검증 out9.txt                       # 미리보기
python tools/notion_row.py 검증 out9.txt --exclude "한계"        # 뺄 칸
python tools/notion_row.py 검증 out9.txt --set "검증자=이름"     # 고칠 칸
python tools/notion_row.py 검증 out9.txt --commit               # 실제로 쓴다
```

선택지에 없는 값은 넣지 않는다. 오타로 새 선택지가 생기는 것을 막는다.
기존 행을 고치지 않고 새 행만 만든다. DB는 이름으로 찾으므로 ID를 코드에 박지 않는다.

## 노션 토큰

노션을 안 쓰면 이 절은 건너뛴다. 팀 DB 대조와 DB 입력만 빠지고 나머지는 그대로 돈다.


토큰은 레포 밖 파일에서 읽는다. **코드에 값을 넣지 않는다.**

찾는 순서는 넷이다. 먼저 걸리는 것을 쓴다.

| 순서 | 자리 | 언제 |
|---|---|---|
| 1 | `NOTION_TOKEN_FILE` 이 가리키는 파일 | 직접 지정할 때 |
| 2 | `/run/secrets/notion_token` | 도커 |
| 3 | `~/.config/darkchoco/notion_token` | 보통 |
| 4 | `./.notion_token.txt` | 지금 폴더 |

3번을 권한다. 사람마다 하나면 되고 레포 밖이다.

```bash
mkdir -p ~/.config/darkchoco
printf '%s' 'ntn_...' > ~/.config/darkchoco/notion_token
chmod 600 ~/.config/darkchoco/notion_token
```

**토큰 값을 환경변수로 받지 않는다.** 값을 넣으면 프로세스 목록과
`docker inspect` 에 남는다. 파일 경로만 받는다.

못 찾으면 어디를 봤는지 전부 알려준다.

토큰은 notion.so/my-integrations 에서 Internal integration 으로 발급한다.
쓸 페이지에서 Connections 에 그 integration 을 추가한다. 안 하면 404가 난다.

## 출력 방식

⑥ 은 로그 전부를 md 로 쓰고 화면에는 요약 네 절만 낸다.

```bash
python tools/verify_cfg.py            지금 설정
python tools/verify_cfg.py 화면=전체   로그도 화면에
python tools/verify_cfg.py --기본값
```

설정 파일은 `~/.config/darkchoco/verify_config.json` 이다.
`DARKCHOCO_CONFIG` 로 자리를 바꾼다. 읽기 전용 환경이면 그쪽을 쓴다.

## 구성

```
skills/darkweb-verify-ko/
  SKILL.md              Claude Code 진입점
  references/           단계별 프롬프트 9개, 파일 트리, 발행처 목록
  tools/                스킬 안에 같이 설치되는 사본
AGENTS.md               Codex 진입점
docs/                   개정 경위
  tools/                도구 전부. 스킬과 같은 자리다
```

## 정본

**프롬프트와 스킬과 도구는 이 레포가 정본이다.** 노션 사본과 다르면 여기가 맞다.
수집 DB와 검증 DB, 회의록과 조사 자료의 정본은 노션이다.

## 판정 다섯 축

| 축 | 값 |
|---|---|
| 검증 분류 | A / B / C / D |
| 진위 판정 | 확인됨 / 신뢰성 높음 / 미확인 / 신뢰성 낮음 / 허위 |
| 신규성 판정 | 신규 유출 / 재유포 / 혼합 / 확인불가 |
| 판정 신뢰도 | 높음 / 중간 / 낮음 |
| 위험도 | 자산 민감도, 즉시 악용 가능성, 신선도, 피해 범위, 확산 정도 |
