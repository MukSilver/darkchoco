# darkchoco

다크웹 개인정보 유통 생태계 조사 도구 모음 · 화이트햇 스쿨 4기 다크초코

```bash
python dc.py list          # 도구 목록
python dc.py info <이름>    # 사용법
python dc.py doctor        # 돌 수 있는 상태인가
```

> ⚠️ 크롤러는 **VM에서만**. 윈도우 직접 실행 금지 → [안전하게 돌리기](docs/안전하게-돌리기.md)

---

## 1. 채우는 곳

| 갈래 | 노션 DB | 줄 | 묻는 것 |
|---|---|---:|---|
| **명부** | 포럼 · 텔레그램 · 랜섬웨어 | 811 | 어디가 있고 살아있나 |
| **사건 기록** | 수집·검증 | — | 무슨 글이 올라왔나 |

---

## 2. 구조

```
packages/  ←  hub/  ←  dc.py          방향은 한쪽
                ↓
              apps/  ·  skills/
```

```
dc.py                입구
hub/                 긁기 + 노션 쓰기          ← 리뷰 필요
  places/              명부  → 다크웹 DB 3개
  events/              사건  → 수집·검증 DB
  sched.py             주기
packages/            공용 부품 6개              ← 리뷰 필요
apps/                알림 · 대시보드
skills/              모으기 · AI 검증
scripts/             VM 자리 · 올리기 · 돌리기
docs/                운영 4장 + 기록 2장
```

- `packages/` → 위를 모름
- `apps/` → `hub/`을 모름
- `hub/events/sources/` → 앱을 부르는 유일한 곳

---

## 3. 도구

<!-- 도구표 시작 -->
| 도구 | 담당 | 설치 | 비밀값 | 어디서 | 무엇을 하나 |
|---|---|:-:|:-:|:-:|---|
| [collect](skills/collect) | 최현서 | 없음 | 1곳 | 내 PC | 텔레그램·랜섬·브라우저킷 결과를 SQLite 한 표로 모읍니다 |
| [crawler](hub) | 김무근 | 없음 | 2곳 | VM | 포럼·텔레그램·랜섬 명부를 한 명령으로 조사해 노션에 반영합니다 |
| [darkweb-verify-ko](skills/skills/darkweb-verify-ko) | 최현서 | 없음 | 0곳 | 내 PC | 유출 주장 하나를 아홉 단계로 검증합니다 (AI 스킬) |
| [kr-leak-alarm](apps/kr-leak-alarm) | 안유빈 | 필요 | 0곳 | 내 PC | 랜섬 피드 세 곳에서 한국 피해를 골라 대시보드로 냅니다 |
| [tg-korea-alert](apps/tg-korea-alert) | 성민서 | 필요 | 5곳 | 내 PC | 텔레그램에서 한국 관련 글을 골라 디스코드로 알립니다 |
<!-- 도구표 끝 -->

**첫 명령**

| 도구 | |
|---|---|
| crawler | `python dc.py crawl` |
| kr-leak-alarm | `scripts\run.bat run` |
| tg-korea-alert | `python korea_alert_monitor.py` |
| collect | `python -m collect.main --db ...` |

설치 전에도 `--help` 가능 · `.env.example` → `.env` 복사 후 값 입력

---

## 4. 크롤러

```bash
python dc.py crawl                        # 미리보기 (기본)
python dc.py crawl --apply                # 노션 반영
python dc.py crawl --only forum --limit 5
python dc.py auto                         # 스케줄러용
```

**흐름 — 갈래 셋이 같은 여섯 단계**

| | 단계 | 어디서 |
|---|---|---|
| ① | 볼 곳 고르기 | 노션 |
| ② | 나가는 길 | `egress.py` — Tor 없으면 중단 |
| ③ | 열기 | `fetch.py` — http · browser · api |
| ④ | 뽑기 | `collect/` 수집기 일곱 |
| ⑤ | 합치기 | `merge.py` |
| ⑥ | 쓰기 | `write.py` — 관문 다섯 |

갈래 차이 = `run.py`의 표 네 칸

**자리 만들기** (Debian · Ubuntu · Kali)

```bash
bash scripts/돌릴자리-만들기.sh    # tor · torrc · 브라우저 · 부품 · 점검
```

---

## 5. 규칙 셋

| # | 규칙 | 지키는 곳 |
|---|---|---|
| ① | **Tor 없이 안 나감** · 한국 출구 제외 | `egress.py` — 나가는 유일한 문 |
| ② | **노션 스키마 불변** · 칸·선택지 추가 금지 | `write.py` — 보내기 전 필터 |
| ③ | **사람이 쓴 칸 보존** | `place.py` — 칸 다루는 법 셋 |

**③ 칸 다루는 법**

| 법 | 칸 |
|---|---|
| 덮어쓰기 | 상태 · 확인일 · 주소 · 어니언 주소 · 최근 활동 |
| 합치기 | 규모 · 피해 대상 · 한국 관련 유출 |
| 빈칸만 | 사용 언어 · 들어가는 법 · 어떤 곳인지 외 11칸 |

`압수됨`·`인계됨` → 사람 판정. 기계 접근 불가

**실행 위치**

| 무엇 | 어디서 |
|---|---|
| 오픈웹 (ransomware.live · Discord) | 어디든 |
| **Tor 접속** | **Kali VM** — GitHub Actions 금지 |
| 작업 스케줄러 | Windows |

---

## 6. 검사

```bash
for f in packages/tests/test_*.py; do python "$f"; done
```

**233개** · 네트워크 없음 · 표준 라이브러리만

| 파일 | 무엇 |
|---|---|
| `test_맨IP금지.py` | Tor 우회 차단 |
| `test_crawler.py` | 크롤러 전체 |
| `test_toolkit.py` | 도구 목록·README 최신 |

---

## 7. 작업 방식

```bash
git switch -c feat/무엇을-고치나
git push -u origin feat/무엇을-고치나
```

| 대상 | 리뷰 |
|---|---|
| `apps/` · `skills/` 자기 폴더 | 없음 |
| `hub/` · `packages/` | **한 명 필수** |
| `hub/places/write.py` · `egress.py` | **CODEOWNERS 별도 지정** |

한 번에 한 가지만

---

## 8. 문서

| 문서 | 무엇 |
|---|---|
| [지금까지](docs/지금까지.md) | 어디까지 왔나 — **처음이면 이것부터** |
| [안전하게 돌리기](docs/안전하게-돌리기.md) | VM · Tor |
| [흐름](docs/흐름.md) | 무엇이 무엇을 부르나 · 막혔을 때 |
| [팀 GitHub 운영안](docs/팀깃헙_운영안.md) | 소유 · 리뷰 · 브랜치 · 비밀 |
| [기록/각자_할일](docs/기록/각자_할일.md) · [기록/구축절차](docs/기록/구축절차.md) | 끝난 일 — 따라 하지 말 것 |

---

## 9. 주의

**비공개 저장소** · 피해 기업명 · onion 주소 · 조사 기록 포함
외부 산출물은 별도 마스킹 · 토큰과 `.env` 커밋 금지
