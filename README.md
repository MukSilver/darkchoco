# darkchoco

다크웹 개인정보 유통 생태계 조사 도구 모음
화이트햇 스쿨 4기 · 다크초코

```bash
python dc.py list        # 어떤 도구가 있나
python dc.py info <이름>  # 어떻게 쓰나
python dc.py doctor      # 지금 돌 수 있나
```

> **크롤러를 돌리기 전에 [안전하게 돌리기](docs/안전하게-돌리기.md)를 보십시오.**
> 윈도우에서 그냥 돌리면 안 됩니다.

---

## 1. 이 저장소가 하는 일

노션 DB 두 갈래를 채웁니다.

| 갈래 | 줄 | 묻는 것 |
|---|---:|---|
| **명부** — 포럼 · 텔레그램 · 랜섬웨어 | 811 | 어디가 있고 살아있나 |
| **사건 기록** — 수집·검증 | — | 무슨 글이 올라왔나 |

둘은 채우는 곳도 묻는 것도 다릅니다. 헷갈리면 남의 데이터를 지웁니다.

---

## 2. 층이 넷입니다

```
packages/  ←  hub/  ←  dc.py
                ↓
              apps/  ·  skills/
```

| 층 | 하는 일 | 리뷰 |
|---|---|:-:|
| `hub/` | **긁고 노션에 씁니다** | 필요 |
| `packages/` | 공용 부품. 아무도 안 부릅니다 | 필요 |
| `apps/` | 골라서 **사람에게 알립니다** | 자유 |
| `skills/` | 모으기와 AI 검증 스킬 | 자유 |

**방향이 한쪽입니다.** `packages/`는 위를 모르고 `apps/`는 `hub/`를 모릅니다.
`hub/events/sources/`만 앱을 부릅니다.

```
dc.py                입구
hub/
  places/            어디가 있고 살아있나  → 다크웹 DB 3개
  events/            무슨 글이 올라왔나    → 수집·검증 DB
  sched.py           주기
packages/            dc_notion · dc_telegram · dc_ransomfeed
                     dc_safety · dc_store · dc_console
apps/                kr-leak-alarm · tg-korea-alert
skills/              collect · darkweb-verify-ko
scripts/             VM 자리 만들기 · 올리기 · 돌리기
docs/                운영 문서 4장 + 기록 2장
```

---

## 3. 도구

`tool.json` 한 장이 도구 하나입니다. 아래 표는 그것으로 만듭니다.

<!-- 도구표 시작 -->
| 도구 | 담당 | 설치 | 비밀값 | 어디서 | 무엇을 하나 |
|---|---|:-:|:-:|:-:|---|
| [collect](skills/collect) | 최현서 | 없음 | 1곳 | 내 PC | 텔레그램·랜섬·브라우저킷 결과를 SQLite 한 표로 모읍니다 |
| [crawler](hub) | 김무근 | 없음 | 2곳 | VM | 포럼·텔레그램·랜섬 명부를 한 명령으로 조사해 노션에 반영합니다 |
| [darkweb-verify-ko](skills/skills/darkweb-verify-ko) | 최현서 | 없음 | 0곳 | 내 PC | 유출 주장 하나를 아홉 단계로 검증합니다 (AI 스킬) |
| [kr-leak-alarm](apps/kr-leak-alarm) | 안유빈 | 필요 | 0곳 | 내 PC | 랜섬 피드 세 곳에서 한국 피해를 골라 대시보드로 냅니다 |
| [tg-korea-alert](apps/tg-korea-alert) | 성민서 | 필요 | 5곳 | 내 PC | 텔레그램에서 한국 관련 글을 골라 디스코드로 알립니다 |
<!-- 도구표 끝 -->

### 처음 돌릴 때

| 도구 | 첫 명령 |
|---|---|
| crawler | `python dc.py crawl` — 미리보기. 노션에 안 씁니다 |
| kr-leak-alarm | `scripts\run.bat run` — 가상환경·설정까지 혼자 합니다 |
| tg-korea-alert | `python korea_alert_monitor.py` |
| collect | `python -m collect.main --db ...` |

설치 전에도 `--help`는 뜹니다. `.env.example`이 있는 도구는 그것을 `.env`로
복사해 값을 채웁니다.

---

## 4. 통합 크롤러

명부 811줄을 한 명령으로 채웁니다.

```bash
python dc.py crawl                        # 미리보기. 노션에 안 씁니다
python dc.py crawl --apply                # 실제로 반영합니다
python dc.py crawl --only forum --limit 5
python dc.py auto                         # 수집 + 명부 조사 (스케줄러가 부릅니다)
```

**기본이 미리보기입니다.** `--apply`를 줘야 씁니다. 811줄에는 팀원이 몇 주간
손으로 적은 것이 섞여 있습니다.

### 한 줄이 지나는 길

```
① 볼 곳 고르기   노션에서 읽습니다
② 나가는 길      egress.py — 갈래 상관없이 하나. Tor 가 없으면 멈춥니다
③ 열기           http · browser · api 를 갈아 끼웁니다
④ 뽑기           수집기 일곱
⑤ 합치기         merge.py
⑥ 쓰기           write.py — 관문 다섯을 다 지나야 씁니다
```

갈래(포럼·텔레그램·랜섬)의 차이는 `run.py`의 **표 네 칸**으로만 남습니다.
갈래가 늘어도 표에 한 줄만 더합니다.

---

## 5. 지키는 규칙 셋

### ① Tor 없이는 안 나갑니다

나가는 문은 `hub/places/egress.py` 하나입니다. Tor가 없으면 요청을 만들지 않고
예외를 냅니다. `ExcludeExitNodes {kr}`로 한국 출구도 뺐습니다.

다크웹 쪽을 여는 것은 **저쪽 로그에 우리 주소를 남기는 일**입니다. 그게 한국
주소면 우리가 누구인지 좁혀집니다.

자리를 만드는 것은 한 줄입니다. Debian · Ubuntu · Kali에서 됩니다.

```bash
bash scripts/돌릴자리-만들기.sh
```

tor 설치 · torrc 규칙 · 브라우저 · 파이썬 부품 · 점검까지 합니다. 노션 토큰만
사람이 넣습니다.

### ② 노션 스키마를 안 바꿉니다

칸도 선택지도 안 늘립니다. 저 DB가 LLM 위키의 근간입니다. `write.py`가 노션에서
스키마를 읽어 **보내기 전에** 없는 칸과 없는 값을 거릅니다.

### ③ 사람이 쓴 칸은 안 덮습니다

| 다루는 법 | 칸 |
|---|---|
| 덮어쓰기 | 상태 · 확인일 · 주소 · 어니언 주소 · 최근 활동 |
| 합치기 | 규모 · 피해 대상 · 한국 관련 유출 — 기계 줄만 갈아 끼움 |
| 빈칸만 | 사용 언어 · 들어가는 법 · 어떤 곳인지 외 11칸 |

`압수됨`·`인계됨`은 기계가 안 덮습니다. 「살아있나」가 아니라 「무슨 일이
있었나」라서 사람이 판정한 값입니다.

---

## 6. 검사

밖에 요청을 안 보냅니다. 표준 라이브러리만 씁니다.

```bash
for f in packages/tests/test_*.py; do python "$f"; done
```

**233개**입니다. 몇 개만 보려면 이렇게 합니다.

```bash
python packages/tests/test_맨IP금지.py    # Tor 없이 안 나가는지
python packages/tests/test_crawler.py     # 크롤러 전체
```

검사가 무엇을 지키는지는 그 파일 맨 위에 적혀 있습니다. 대부분은 **한 번 겪은
사고**에서 나왔습니다.

---

## 7. 작업 방식

```bash
git switch -c feat/무엇을-고치나
# 고치고 검사 돌리고
git push -u origin feat/무엇을-고치나
```

- `apps/`·`skills/`의 자기 폴더는 리뷰 없이 머지해도 됩니다.
- **`hub/`와 `packages/`는 리뷰 한 명이 필요합니다.** 깨지면 여러 곳이 함께 멈춥니다.
- **한 번에 한 가지만 고칩니다.** 여러 개를 같이 고치면 무엇이 깨졌는지 못 찾습니다.

`hub/places/write.py`(노션에 쓰는 유일한 곳)와 `egress.py`(나가는 유일한 길)는
CODEOWNERS에 리뷰어를 따로 걸어 두었습니다.

---

## 8. 실행 위치

| 무엇 | 어디서 |
|---|---|
| 오픈웹 (ransomware.live · Discord) | 어디든 |
| **Tor 접속 (크롤러 전체)** | **Kali VM** |
| 작업 스케줄러 등록 | Windows |

**Tor를 타는 작업은 GitHub Actions에서 돌리지 않습니다.** GitHub 서버가 다크웹에
붙는 셈이라 규정에 걸리고 토큰도 노출됩니다.

---

## 9. 문서

**보고 일하는 것**

- [지금까지](docs/지금까지.md) — 어디까지 왔나. **처음이면 이것부터**
- [안전하게 돌리기](docs/안전하게-돌리기.md) — VM과 Tor
- [흐름](docs/흐름.md) — 무엇이 무엇을 부르나. 막혔을 때 어디를 보나
- [팀 GitHub 운영안](docs/팀깃헙_운영안.md) — 소유 · 리뷰 · 브랜치 · 비밀 관리

**끝난 일의 기록** — 따라 하는 문서가 아닙니다

- [각자 할 일](docs/기록/각자_할일.md) · [구축 절차](docs/기록/구축절차.md)

---

## 10. 주의

이 저장소는 **비공개**입니다. 피해 기업명 · onion 주소 · 조사 기록이 들어
있습니다. 외부 공개용 산출물을 만들 때 따로 마스킹합니다.

토큰과 `.env`는 커밋하지 않습니다.
