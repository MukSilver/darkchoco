# darkchoco

다크웹 개인정보 유통 생태계 조사 도구 모음
화이트햇 스쿨 4기 · 다크초코

도구마다 주인이 있습니다. 하나만 골라 써도 되고, 필요한 것만 설치해도 됩니다.

```bash
python dc.py list
```

---

## 처음 오셨으면

**[docs/지금까지.md](docs/지금까지.md)** 를 먼저 보십시오.
무엇이 생겼고 무엇이 안 됐는지 한 장으로 적혀 있습니다.

그다음은 필요한 것만 봅니다.

| 하려는 일 | 볼 것 |
|---|---|
| 남의 도구를 돌려 본다 | `python dc.py list` · `dc.py info <이름>` |
| 크롤러를 돌린다 | [안전하게 돌리기](docs/안전하게-돌리기.md) — **VM 이 필요합니다** |
| 어디가 막혔는지 찾는다 | [흐름](docs/흐름.md) |
| PR 을 올린다 | [팀 GitHub 운영안](docs/팀깃헙_운영안.md) |

---

## 통합 크롤러 — 명부를 채웁니다

다크웹 DB 세 개(포럼 · 텔레그램 · 랜섬웨어)가 24~30칸을 공유합니다.
한 명령으로 세 갈래를 조사해 그 칸들을 채웁니다.

```bash
python dc.py crawl              # 미리보기. 노션에 안 씁니다
python dc.py crawl --apply      # 실제로 반영합니다
python dc.py crawl --only forum --limit 5
python dc.py auto               # 수집 + 명부 조사 (스케줄러가 부릅니다)
```

**밖으로 나가려면 Tor 가 있어야 합니다.** 없으면 요청을 아예 안 보냅니다.
다크웹 쪽을 여는 일은 저쪽 로그에 우리 주소를 남기는 일이고, 그것이
한국 주소면 우리가 누구인지 좁혀집니다.

자리를 만드는 것은 한 줄입니다. Debian · Ubuntu · Kali 에서 됩니다.

```bash
bash scripts/돌릴자리-만들기.sh
```

tor 설치 · torrc 규칙 · 띄우기 · 실제로 나가 보기 · 파이썬 부품 ·
환경 변수 · 점검까지 합니다. 노션 토큰만 사람이 넣습니다.

```bash
mkdir -p ~/.config/darkchoco
echo 'ntn_...' > ~/.config/darkchoco/notion_token.txt
python dc.py doctor --net       # 밖에 어떤 주소가 남는지 봅니다
```

**윈도우에서 그냥 돌리지 마십시오.** 다크웹 쪽이 그 PC 로 내려오고 V3 가
막습니다. VM 이나 WSL 에서 돌립니다. 왜 그런지와 자리를 어떻게 만드는지는
[docs/안전하게-돌리기.md](docs/안전하게-돌리기.md) 에 있습니다.
무엇이 무엇을 부르는지는 [docs/흐름.md](docs/흐름.md) 에 있습니다.

---

## 구조

```
dc.py         입구. 목록 · 사용법 · 상태를 봅니다
hub/          통합 크롤러. 언제 돌릴지 정하고 노션에 씁니다
  places/       어디가 있고 살아있나  → 다크웹 DB 3개
  events/       무슨 글이 올라왔나    → 수집·검증 DB
apps/         도구. 각자 소유하고 자기 폴더에서 자유롭게 고칩니다
packages/     공용 부품. 여기만 리뷰가 필요합니다
skills/       수집기와 검증 스킬
scripts/      VM 자리 만들기 · 올리기 · 돌리기
docs/         운영안 · 흐름 · 할 일
```

층이 셋입니다. **방향이 한쪽입니다.**

```
packages/  ←  hub/  ←  dc.py
                ↓
              apps/  ·  skills/
```

`packages/` 는 아무도 안 부릅니다. `apps/` 는 `hub/` 를 모릅니다.
`hub/events/sources/` 만 앱을 부릅니다.

도구 폴더마다 `tool.json` 이 한 장 있습니다. 아래 표는 그것으로 만듭니다.

<!-- 도구표 시작 -->
| 도구 | 담당 | 설치 | 비밀값 | 어디서 | 무엇을 하나 |
|---|---|:-:|:-:|:-:|---|
| [collect](skills/collect) | 최현서 | 없음 | 1곳 | 내 PC | 텔레그램·랜섬·브라우저킷 결과를 SQLite 한 표로 모읍니다 |
| [crawler](hub) | 김무근 | 없음 | 2곳 | VM | 포럼·텔레그램·랜섬 명부를 한 명령으로 조사해 노션에 반영합니다 |
| [darkweb-verify-ko](skills/skills/darkweb-verify-ko) | 최현서 | 없음 | 0곳 | 내 PC | 유출 주장 하나를 아홉 단계로 검증합니다 (AI 스킬) |
| [dls-observatory](apps/dls-observatory) | 안유빈 | 없음 | 2곳 | 내 PC | 유출 사이트가 살아 있는지 보고 노션 명부를 갱신합니다 |
| [forum-crawler](apps/forum-crawler) | 성민서 | 필요 | 0곳 | 도커 | 다크웹 포럼 한 곳을 훑어 조사 초안 MD 한 장을 냅니다 |
| [kr-leak-alarm](apps/kr-leak-alarm) | 안유빈 | 필요 | 0곳 | 내 PC | 랜섬 피드 세 곳에서 한국 피해를 골라 대시보드로 냅니다 |
| [tg-korea-alert](apps/tg-korea-alert) | 성민서 | 필요 | 5곳 | 내 PC | 텔레그램에서 한국 관련 글을 골라 디스코드로 알립니다 |
| [tg-notion-report](apps/tg-notion-report) | 이수빈 | 필요 | 3곳 | 내 PC | 텔레그램 채널을 모아 노션 보고서로 반영합니다 |
<!-- 도구표 끝 -->

---

## 남의 앱을 처음 돌릴 때

`git clone` 다음부터 결과가 나오기까지 손으로 해야 하는 일입니다. 실측한 값입니다.

| 앱 | 첫 명령 | 설치 | 비밀값 받을 곳 | 로그인 |
|---|---|:-:|:-:|:-:|
| kr-leak-alarm | `scripts\run.bat` | 자동 | 0곳 | 없음 |
| dls-observatory | `python diagnose.py` | 없음 | 1곳 (노션) | 없음 |
| forum-crawler | `docker run -e TARGET_URL=...` | docker build | 0곳 | 없음 |
| skills/collect | `python -m collect.main --db ...` | pip | 0곳 | 없음 |
| tg-notion-report | `python telegram_pipeline.py <url>` | pip | 2곳 | 텔레그램 |
| tg-korea-alert | `python korea_alert_monitor.py` | pip | 4곳 | 텔레그램 |

설치하기 전에 `--help` 로 먼저 훑어볼 수 있습니다. 여섯 앱 전부 됩니다.

kr-leak-alarm 은 `scripts\run.bat` 이 가상환경을 만들고 설정 파일까지 복사합니다.
`.env.example` 이 있는 앱은 그것을 `.env` 로 복사해 값을 채웁니다.

---

## 공용 부품

| 패키지 | 무엇 |
|---|---|
| dc_telegram | 텔레그램 접속 · 수집 |
| dc_notion | 노션 API · 토큰 |
| dc_safety | 안전 HTTP · 텍스트 살균 |
| dc_ransomfeed | 랜섬 피드 주소 · 가져오기 |
| dc_console | 윈도우 한글 콘솔 대응 |

사용법은 각 패키지 README 에 있습니다.

**규칙 하나: packages 는 apps 를 참조하지 않습니다.**

---

## 작업 방식

```
git switch -c feat/앱이름-무엇
수정 후 동작 확인
git push -u origin feat/앱이름-무엇
```

자기 앱 폴더는 리뷰 없이 머지해도 됩니다.
packages 를 고치면 리뷰 한 명이 필요합니다.

**앱 1개씩 합니다. 한 번에 여러 앱을 고치면 무엇이 깨졌는지 못 찾습니다.**

---

## 테스트

전부 한 줄로 돕니다. 밖에 요청을 안 보냅니다.

```bash
for f in packages/tests/test_*.py; do python "$f"; done
```

**15파일 199개입니다.** 표준 라이브러리만 씁니다.

무거운 것을 안 깔고 한두 개만 보려면 이렇게 합니다.

```bash
python packages/tests/test_맨IP금지.py    # Tor 없이 안 나가는지
python packages/tests/test_crawler.py     # 크롤러 전체
```

---

## 실행 위치

저장소는 코드만 관리합니다. 실행 위치는 나눕니다.

| 무엇 | 어디서 |
|---|---|
| 오픈웹 (ransomware.live · Discord) | 어디든 |
| Tor 접속 (포럼 · onion) | Kali VM 또는 Docker |
| 작업 스케줄러 등록 | Windows |

**Tor 를 타는 작업은 GitHub Actions 에서 돌리지 않습니다.**

---

## 문서

**보고 일하는 것**

- [지금까지](docs/지금까지.md) — 어디까지 왔나. **처음이면 이것부터**
- [안전하게 돌리기](docs/안전하게-돌리기.md) — VM 과 Tor. **크롤러를 돌리기 전에 보십시오**
- [흐름](docs/흐름.md) — 무엇이 무엇을 부르나. 막혔을 때 어디를 보나
- [팀 GitHub 운영안](docs/팀깃헙_운영안.md) — 소유 · 리뷰 · 브랜치 · 비밀 관리

**끝난 일의 기록** — 따라 하는 문서가 아닙니다

- [각자 할 일](docs/기록/각자_할일.md) — 8/28 부품 통합 때 나눈 몫
- [구축 절차](docs/기록/구축절차.md) — 8/26 에 저장소를 어떻게 세웠나

---

## 주의

이 저장소는 **비공개** 입니다.
피해 기업명 · onion 주소 · 조사 기록이 들어 있습니다.
외부 공개용 산출물을 만들 때는 별도로 마스킹합니다.

토큰과 `.env` 는 커밋하지 않습니다.
