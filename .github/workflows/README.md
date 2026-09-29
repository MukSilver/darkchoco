# 워크플로

    ci.yml         push 마다 시험을 돈다
    security.yml   금지한 코드와 비밀값이 섞였나 본다
    collect.yml    **여섯 시간마다 긁어 노션에 올린다**
    guide.yml      가이드라인(apps/guide)을 빌드해 Cloudflare 에 올린다
    guide-links.yml  한 달에 한 번 가이드라인이 안내하는 기관 주소가 열리는지 본다

## collect.yml 을 켜려면 비밀값 둘이 필요합니다

레포 **Settings → Secrets and variables → Actions → New repository secret** 에서 넣습니다.

| 이름 | 무엇 |
|---|---|
| `NOTION_TOKEN` | 노션 통합 토큰. `ntn_` 으로 시작합니다 |
| `DARKCHOCO_CHANNELS` | 볼 채널 목록. 한 줄에 하나. `#` 로 시작하는 줄은 건너뜁니다 |

**채널 목록을 레포 파일로 두지 않습니다.** 무엇을 보고 있는지가 드러나는 목록이라
비밀값으로 넣습니다. 로컬의 `~/.config/darkchoco/telegram_channels` 를 그대로 붙이면 됩니다.

`NOTION_TOKEN` 이 없으면 워크플로가 첫 단계에서 멈춥니다. 채널 목록이 없으면 텔레그램만
건너뛰고 랜섬은 그대로 돕니다.

## 처음 한 번은 손으로 돌려 보십시오

**Actions 탭 → 수집 → Run workflow** 에서 「올리기」 를 꺼 두면 미리보기만 합니다.
무엇이 올라갈지 보고 괜찮으면 켜서 다시 돌립니다.

## 무엇을 못 하나

    텔레그램 실계정   세션 파일을 올리면 그 계정으로 남이 읽습니다. 로컬에 둡니다
    포럼 킷          사람이 브라우저에서 눌러야 돕니다

둘 다 원래 사람 손이 들어가는 자리입니다. 제어판(`skills/run.py`)에서 합니다.

## 표를 안 남깁니다

실행마다 새 컨테이너라 SQLite 가 안 남습니다. **정본은 노션이고 SQLite 는 통로**라
그것이 문제가 안 됩니다. 실측으로 확인했습니다 — 완전히 빈 표에서 119줄을 긁었는데
`push.py` 가 노션의 UID·원문 URL 로 119줄 전부를 겹침으로 막았습니다.

게시글 본문은 노션에 안 갑니다. 검증할 때는 사람이 원문을 따로 봅니다.

## 집계처가 막을 수 있습니다

GitHub 서버 주소는 여러 곳이 함께 쓰는 것이라 `ransomware.live` 가 막아 둘 수 있습니다.
그래서 랜섬 단계에 `continue-on-error` 를 두었습니다 — 거기서 죽어도 텔레그램은 돕니다.
막히면 랜섬만 로컬로 돌리고 나머지는 여기서 계속합니다.

## guide.yml 을 켜려면 비밀값 다섯과 변수 하나가 필요합니다

| 이름 | 무엇 |
|---|---|
| `GUIDE_SUPABASE_URL` | Supabase 프로젝트 주소 |
| `GUIDE_SUPABASE_ANON_KEY` | 익명 키. guide 스키마는 익명 읽기가 열려 있습니다 |
| `GUIDE_CLOUDFLARE_API_TOKEN` | 가이드라인을 올리는 Cloudflare 계정의 토큰 |
| `GUIDE_CLOUDFLARE_ACCOUNT_ID` | 그 계정의 id |
| `GUIDE_DISCORD_WEBHOOK` | 실패 알림. 없으면 알림만 건너뜁니다 |
| `GUIDE_SITE_URL` (변수) | 사이트 주소 |

**지도의 `CLOUDFLARE_API_TOKEN` 과 계정이 다릅니다.** 그래서 이름 앞에 `GUIDE_` 를 붙였습니다.
같은 이름을 쓰면 가이드라인이 지도 계정으로 올라갑니다.

정제 배치(darkchoco-data)가 Supabase 를 채운 뒤 `data-updated` 신호를 이 저장소로 보내면
guide.yml 이 돕니다. 신호는 기본 가지(main)에 있는 워크플로만 받습니다.
