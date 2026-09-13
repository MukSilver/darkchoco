# darkchoco

다크웹 개인정보 유통 생태계 조사 도구 모음입니다.
화이트햇 스쿨 4기 · 다크초코

```bash
python dc.py list          # 도구 목록
python dc.py info <이름>    # 사용법
python dc.py doctor        # 실행 가능 여부 점검
```

> **크롤러는 VM에서만 실행합니다.** 윈도우에서 직접 실행하면 다크웹 쪽 응답이
> 그 PC로 내려오고 백신이 차단합니다. 절차는 [안전하게 돌리기](docs/안전하게-돌리기.md)에 있습니다.

---

## 1. 무엇을 채우는가

노션 데이터베이스 두 갈래를 채웁니다.

| 갈래 | 노션 DB | 줄 수 | 담는 내용 |
|---|---|---:|---|
| **명부** | 포럼 · 텔레그램 · 랜섬웨어 | 811 | 어디가 있고 살아있는가 |
| **사건 기록** | 수집·검증 | — | 무슨 글이 올라왔는가 |

두 갈래는 채우는 대상과 묻는 내용이 다릅니다. 구분하지 않으면 다른 팀의 기록을
덮어씁니다.

---

## 2. 저장소 구조

계층은 넷이며, 참조 방향은 한쪽입니다.

```
packages/  ←  hub/  ←  dc.py
                ↓
              apps/  ·  skills/
```

| 계층 | 역할 | 리뷰 |
|---|---|---|
| `hub/` | 조사 실행 및 노션 반영 | 필수 |
| `packages/` | 공용 부품 6종 | 필수 |
| `apps/` | 알림 · 대시보드 | 불필요 |
| `skills/` | 수집 · AI 검증 | 불필요 |

```
dc.py                진입점
hub/
  places/            명부 조사    → 다크웹 DB 3개
  events/            사건 수집    → 수집·검증 DB
  sched.py           실행 주기
packages/            dc_notion · dc_telegram · dc_ransomfeed
                     dc_safety · dc_store · dc_console
apps/                dash · kr-leak-alarm · talkaid · tg-korea-alert
skills/              collect · darkweb-verify-ko
scripts/             VM 구성 · 배포 · 실행
docs/                운영 문서 4종 · 기록 2종
```

`packages/` 는 상위 계층을 참조하지 않습니다. `apps/` 는 `hub/` 를 참조하지
않습니다. `hub/events/sources/` 만 `apps/` 를 호출합니다.

---

## 3. 도구

도구 하나에 `tool.json` 한 장이 대응합니다. 아래 표는 그 파일에서 생성합니다.

<!-- 도구표 시작 -->
| 도구 | 담당 | 설치 | 비밀값 | 어디서 | 무엇을 하나 |
|---|---|:-:|:-:|:-:|---|
| [collect](skills/collect) | 최현서 | 없음 | 1곳 | 내 PC | 텔레그램·랜섬·브라우저킷 결과를 SQLite 한 표로 모읍니다 |
| [crawler](hub) | 김무근 | 없음 | 2곳 | VM | 포럼·텔레그램·랜섬 명부를 한 명령으로 조사해 노션에 반영합니다 |
| [darkweb-verify-ko](skills/skills/darkweb-verify-ko) | 최현서 | 없음 | 0곳 | 내 PC | 유출 주장 하나를 아홉 단계로 검증합니다 (AI 스킬) |
| [kr-leak-alarm](apps/kr-leak-alarm) | 안유빈 | 필요 | 0곳 | 내 PC | 랜섬 피드 세 곳에서 한국 피해를 골라 대시보드로 냅니다 |
| [talkaid](apps/talkaid) | 최현서 | 필요 | 0곳 | 내 PC | 창을 띄워 클립보드를 옮긴다. 번역이 이 PC 안에서만 돈다 |
| [tg-korea-alert](apps/tg-korea-alert) | 성민서 | 필요 | 5곳 | 내 PC | 텔레그램에서 한국 관련 글을 골라 디스코드로 알립니다 |
<!-- 도구표 끝 -->

### 최초 실행 명령

| 도구 | 명령 |
|---|---|
| crawler | `python dc.py crawl` |
| kr-leak-alarm | `scripts\run.bat run` |
| tg-korea-alert | `python korea_alert_monitor.py` |
| collect | `python -m collect.main --db <경로>` |

설치 전에도 `--help` 를 실행할 수 있습니다. `.env.example` 이 있는 도구는 그
파일을 `.env` 로 복사한 뒤 값을 채웁니다.

---

## 4. 통합 크롤러

명부 811줄을 한 명령으로 조사합니다.

```bash
python dc.py crawl                        # 미리보기 (기본값)
python dc.py crawl --apply                # 노션에 반영
python dc.py crawl --only forum --limit 5
python dc.py auto                         # 스케줄러 호출용
```

기본 동작은 미리보기입니다. `--apply` 를 지정해야 노션에 기록합니다.

### 실행 흐름

세 갈래(포럼 · 텔레그램 · 랜섬웨어)가 동일한 여섯 단계를 거칩니다.

| 단계 | 내용 | 담당 파일 |
|---|---|---|
| ① | 조사 대상 선별 | 노션 조회 |
| ② | 외부 접속 | `egress.py` — Tor 부재 시 중단 |
| ③ | 페이지 열기 | `fetch.py` — http · browser · api |
| ④ | 항목 추출 | `collect/` 수집기 7종 |
| ⑤ | 결과 병합 | `merge.py` |
| ⑥ | 노션 기록 | `write.py` — 검증 5단계 |

갈래별 차이는 `run.py` 의 설정 표 네 칸에만 존재합니다.

### 실행 환경 구성

Debian · Ubuntu · Kali에서 아래 한 줄로 구성합니다.

```bash
bash scripts/돌릴자리-만들기.sh
```

tor 설치, torrc 규칙, 브라우저, 파이썬 부품, 점검까지 자동으로 수행합니다.
노션 토큰만 직접 입력합니다.

---

## 5. 준수 규칙

| # | 규칙 | 강제 지점 |
|---|---|---|
| ① | Tor 미경유 시 요청 차단, 한국 출구 노드 제외 | `egress.py` |
| ② | 노션 스키마 변경 금지 (칸·선택지 추가 불가) | `write.py` |
| ③ | 수동 입력 값 보존 | `place.py` |

### ③ 칸 처리 방식

| 방식 | 대상 칸 |
|---|---|
| 덮어쓰기 | 상태 · 확인일 · 주소 · 어니언 주소 · 최근 활동 |
| 병합 | 규모 · 피해 대상 · 한국 관련 유출 |
| 빈칸 한정 | 사용 언어 · 들어가는 법 · 어떤 곳인지 외 11개 |

`압수됨` 과 `인계됨` 은 사람이 판정하는 값입니다. 기계는 이 두 값을 덮어쓰지
않습니다.

### 실행 위치

| 작업 | 위치 |
|---|---|
| 오픈웹 조회 (ransomware.live · Discord) | 제한 없음 |
| Tor 접속 | **Kali VM** |
| 작업 스케줄러 등록 | Windows |

Tor를 경유하는 작업은 GitHub Actions에서 실행하지 않습니다.

---

## 6. 검사

```bash
for f in packages/tests/test_*.py; do python "$f"; done
```

총 **237개**(2026-08-31 기준)이며, 외부 요청 없이 표준 라이브러리만으로 동작합니다.
검사를 더하면 이 값이 낡습니다. `docs/흐름.md` · `docs/지금까지.md` 에도 같은
값이 적혀 있으니 셋을 같이 고칩니다. 세는 법은 이렇습니다.

```bash
grep -c "^def test_" packages/tests/test_*.py | awk -F: '{s+=$2} END {print s}'
```

| 파일 | 검사 대상 |
|---|---|
| `test_맨IP금지.py` | Tor 우회 경로 차단 |
| `test_crawler.py` | 크롤러 전체 동작 |
| `test_toolkit.py` | 도구 목록 및 README 최신 여부 |

각 파일 상단에 검사 목적이 기재되어 있습니다.

---

## 7. 작업 절차

```bash
git switch -c feat/<작업명>
git push -u origin feat/<작업명>
```

| 대상 | 리뷰 |
|---|---|
| `apps/` · `skills/` 담당 폴더 | 불필요 |
| `hub/` · `packages/` | 1인 필수 |
| `hub/places/write.py` · `hub/places/egress.py` | CODEOWNERS 별도 지정 |

한 번에 한 항목만 수정합니다.

---

## 8. 문서

| 문서 | 내용 |
|---|---|
| [지금까지](docs/지금까지.md) | 진행 현황 — **최초 열람 권장** |
| [안전하게 돌리기](docs/안전하게-돌리기.md) | VM 및 Tor 구성 |
| [흐름](docs/흐름.md) | 호출 관계 및 장애 대응 |
| [팀 GitHub 운영안](docs/팀깃헙_운영안.md) | 소유 · 리뷰 · 브랜치 · 비밀 관리 |
| [기록/각자_할일](docs/기록/각자_할일.md) · [기록/구축절차](docs/기록/구축절차.md) | 완료된 작업 기록 (참조 전용) |

---

## 9. 취급 주의

본 저장소는 비공개입니다. 피해 기업명, onion 주소, 조사 기록이 포함되어 있습니다.
외부 공개용 산출물은 별도로 마스킹합니다. 토큰과 `.env` 파일은 커밋하지 않습니다.
