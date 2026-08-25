# DLS 관측 DB (SQLite)

## 왜 DB인가

지금까지는 실행할 때마다 결과를 **덮어썼습니다.** 그래서 이런 질문에 답할 수 없었습니다.

- 이 사이트가 **언제부터** offline인가
- 주소가 **언제 바뀌었나**
- 캡차·로그인 벽이 **언제 생겼나**
- 지난달 대비 **새로 등장한** 사이트는

`observation` 테이블에 관측을 **지우지 않고 계속 쌓는 것**, 이게 설계의 전부입니다. 나머지는 거기서 파생됩니다.

## 위치

```
[Kali VM]  수집 → probe.json ──┐
                               ├─→ [호스트] dls.sqlite3 ─→ 노션 (표시용 뷰)
[ransomware.live/ransomlook] ──┘                       └─→ 통계·보고서
```

**DB는 호스트에만 둡니다.** VM은 지금처럼 `probe.json`만 뱉고, 적재는 호스트에서 합니다. 자문 요청서에 쓰신 경계 구조가 그대로 유지됩니다.

노션이 원본이 아니라 **DB의 뷰**가 되는 게 핵심입니다. 지금은 노션이 원본이라 덮어쓰기가 무섭죠.

## 파일

| 파일 | 역할 |
|---|---|
| `db.py` | 스키마 + 적재·조회 함수 |
| `dls_db.py` | CLI |
| `test_db.py` | 검증 (네트워크·노션 없이 실행) |
| `dls.sqlite3` | 실제 DB (자동 생성, `.gitignore` 대상) |

표준 라이브러리만 씁니다. `pip install` 불필요.

## 테이블

| 테이블 | 내용 |
|---|---|
| `site` | 사이트 하나 = 한 행. 표기 차이로 갈라지지 않게 정규화된 `key`로 식별 |
| `alias` | 별칭·이전 이름 |
| `address` | 주소 이력. 주소가 바뀌면 예전 행을 고치지 않고 `active=0`으로 내림 |
| `observation` | **관측 기록 (append-only)** ← 핵심 |
| `victim` | ransomware.live 피해자 |
| `run` | 수집 실행 이력 |
| `current_state` | (뷰) 사이트별 가장 최근 관측 한 줄 |

## 사용법

### 처음 한 번

```powershell
python dls_db.py init            # DB 생성
python dls_db.py ingest-cache    # 지금 .cache에 있는 API 응답 적재
```

`ingest-cache`는 `dls_fill.py`가 남긴 `.cache` 폴더를 그대로 읽습니다. 이미 받아둔 ransomware.live 그룹 388개, 피해자 4,467건, ransomlook 목록이 한 번에 들어갑니다.

### 수집 때마다

```powershell
python dls_db.py ingest probe.json
```

같은 파일을 두 번 넣어도 중복되지 않습니다 (`(사이트, 시각, 출처)` 유일 제약). Tor가 끊긴 구간(`unreliable`)은 자동으로 제외됩니다.

### 조회

```powershell
python dls_db.py stats                       # 현황 요약
python dls_db.py list --status offline       # 현재 죽은 사이트
python dls_db.py list --gate                 # 가입·로그인 필요한 곳
python dls_db.py list --kind market
python dls_db.py history "THE MATRIX"        # 한 사이트의 전체 이력
python dls_db.py changes --since 2026-08-01  # 상태가 바뀐 지점만
python dls_db.py addresses "Savastan0"       # 주소 변경 이력
python dls_db.py kr                          # 한국 관련 유출
```

`changes`는 **관측이 2회 이상 쌓여야** 의미가 생깁니다. 이번 수집이 1회차라 다음 수집부터 결과가 나옵니다.

### 노션 반영

```powershell
python dls_db.py export merged.json
python dls_fill.py --probe merged.json --report r.csv
python dls_fill.py --probe merged.json --apply
```

`export`는 DB의 최신 상태를 `dls_fill.py --probe`가 읽는 형식으로 내보냅니다. 기존 흐름을 그대로 쓰면서 원본만 DB로 바뀝니다.

## SQL로 직접 보기

```powershell
sqlite3 dls.sqlite3
```

```sql
-- 30일 넘게 죽어 있는 사이트
SELECT name, MAX(observed_at) last_seen FROM current_state
WHERE status='offline' GROUP BY name;

-- 캡차가 새로 생긴 사이트
SELECT s.name, o.observed_at, o.how_to_enter
FROM observation o JOIN site s ON s.id=o.site_id
WHERE o.gate_signals LIKE '%캡차%' ORDER BY o.observed_at DESC;

-- 언어별 분포
SELECT language, COUNT(DISTINCT site_id) FROM observation
WHERE language <> '' GROUP BY language ORDER BY 2 DESC;
```

DB 파일 하나라 백업은 복사만 하면 됩니다. 다만 **원본 DB는 백업본과 같은 곳에 두지 마세요.**

## 검증

```powershell
python test_db.py
```

2회 수집 시나리오(사이트 하나가 죽고, 다른 하나는 주소를 옮겨 살아남는 상황)를 만들어 상태 변화 추적, 주소 이력, 중복 방지, 신뢰불가 구간 제외를 확인합니다.

## 다음 단계 (필요해지면)

- 노션의 다른 DB(포럼·행위자·텔레그램)도 같은 스키마에 통합
- 주간 변화 리포트 자동 생성
- 규모가 커지면 Postgres로 이전 — 스키마는 그대로 씁니다
