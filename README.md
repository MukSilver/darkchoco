# Notion-DLS — 다크웹 유출 사이트(DLS) 관측 자동화

공개 CTI API 와 Tor 직접 접속으로 다크웹 유출 사이트·마켓·포럼의 **메타데이터**를
주기적으로 수집해 SQLite 에 시계열로 쌓고, 노션 DB 를 그 표시용 뷰로 갱신합니다.

수집 대상은 **사이트에 대한 정보**입니다 — 살아 있는지, 어떤 성격인지, 어떻게
들어가는지, 어떤 연락 수단을 쓰는지. **유출된 데이터 자체는 수집하지 않습니다.**


<img width="938" height="598" alt="image" src="https://github.com/user-attachments/assets/437dd419-3fc8-4ae7-9c63-e7bfaa32bc5e" />
<img width="1046" height="1318" alt="image" src="https://github.com/user-attachments/assets/e14041f4-2e3f-484d-b98a-4025a8ca20ed" />
<img width="2564" height="1402" alt="image" src="https://github.com/user-attachments/assets/eb0a371e-64d6-45f9-9ca6-2bdfcd3d97e2" />


---

## 왜 이렇게 나뉘어 있나

```
  ┌─────────────────── 호스트 (Windows) ───────────────────┐
  │  dls_fill.py   노션 읽기/쓰기 · 추론 · 리포트            │
  │  dls_db.py     DB 관리 CLI                              │
  │  db.py         SQLite 스키마 · 적재                      │
  │  sources.py    ransomware.live / ransomlook.io API       │
  │  infer.py      분류 추론 (형식·개인정보·유통자리·국가)     │
  │  notion.py     Notion REST 래퍼                          │
  │                                                          │
  │  dls.sqlite3   ← 원본. 여기에만 존재                      │
  └──────────────────────────────────────────────────────────┘
                            ▲
                            │  probe*.json (메타데이터만)
                            │
  ┌─────────────────── Kali VM (격리) ──────────────────────┐
  │  tor_probe.py  Tor 경유 수집기 (표준 라이브러리만)         │
  │  infer.py      ← 같은 파일. 본문 판정을 VM 안에서 끝냄     │
  └──────────────────────────────────────────────────────────┘
```

**Tor 접속은 격리된 VM 에서만** 합니다. 호스트는 onion 주소를 조회하지 않습니다.

**VM 은 `probe*.json` 하나만 만듭니다.** DB 도, 노션 토큰도 VM 에 두지 않습니다.

**본문은 VM 밖으로 나오지 않습니다.** 분류 추론에 본문 전체가 필요한데, 본문을
호스트로 넘기면 피해 기업 이름이 따라옵니다. 그래서 `infer.py` 를 VM 에도 올려
판정까지 거기서 끝내고, 결과와 **매칭된 키워드만**(60자 제한) 내보냅니다.

---

## 절대 바꾸면 안 되는 것

통합·수정하실 때 아래는 설계의 전제입니다. 하나라도 풀면 나머지가 무의미해집니다.

| 규칙 | 이유 |
|---|---|
| `socks5h` 만 사용 | 이름 해석을 Tor 에 위임. `socks5` 로 바꾸면 호스트가 onion 이름을 DNS 로 물어봐 노출됩니다 |
| 수집 전 Tor 검증, 실패 시 시작 안 함 | 검증 없이 돌면 전부 `offline` 로 잘못 기록됩니다 |
| Content-Type 필터 (`text/html`·`text/plain` 만) | **유출 데이터 아카이브를 받지 않기 위한 코드 차원의 방어선입니다** |
| 응답 본문을 디스크에 쓰지 않음 | 위와 같은 이유 |
| 피해 기업 이름을 저장하지 않음 (개수만) | 집계는 남기되 유출 대상은 남기지 않습니다 |
| 브라우저를 쓰지 않음 | JS 미실행 = 렌더링 엔진 취약점 표면 없음 |
| 가입·로그인 벽 뒤로 들어가지 않음 | 존재만 기록합니다 |
| **캡차를 풀지 않음** | 제3자 캡차 해결 서비스도 쓰지 않습니다. `ROADMAP.md` §3 참고 |
| 세션 쿠키를 결과 파일에 기록하지 않음 | 대기 화면 통과에만 쓰고 버립니다 |
| 관측 테이블은 append-only | 덮어쓰면 "언제부터 죽었나"에 영원히 답할 수 없습니다 |

---

## 저장소에 없는 것

`.gitignore` 로 제외됩니다. 코드는 공유해도 **무엇을 보고 있는지는 별개**입니다.

- `.env` — 노션 통합 토큰. **저장소 주인이 아니라 워크스페이스 소유자의 토큰입니다.**
  한 번이라도 커밋되면 히스토리에 영구히 남으므로, 실수로 올렸다면 파일 삭제로
  끝나지 않고 **노션에서 폐기 후 재발급**해야 합니다.
- `dls.sqlite3` — 관측 DB
- `probe*.json`, `merged*.json`, `targets*.csv`, `r.csv` — onion 주소 목록 포함
- `.cache/` — API 응답 캐시

`.env.example` 을 복사해 `.env` 를 만들고 토큰을 넣으면 동작합니다.

---

## 실행

### 1. 노션 연결 확인

```bash
python diagnose.py          # 토큰·권한·데이터소스 진단
python dls_fill.py --schema # 노션 칼럼 이름/타입 확인
```

`mapping.json` 의 `columns` 를 실제 노션 칼럼명에 맞춰야 합니다.
못 찾은 칼럼은 경고만 내고 건너뜁니다.

### 2. Tor 수집 (VM)

```bash
python dls_fill.py --export-targets targets.csv   # 호스트에서 대상 생성
# targets.csv, tor_probe.py, infer.py 를 VM 으로 전송

python3 tor_probe.py --selftest                    # 버전과 Tor 경유 확인
python3 tor_probe.py targets.csv -o probe.json --resume
```

> `--selftest` 가 찍는 **`[버전] tor_probe 3.0`** 을 반드시 확인하세요.
> 옛 버전도 셀프테스트는 통과합니다. 실제로 이것 때문에 5시간을 헛돌린 적이 있습니다.

### 3. 적재 → 검토 → 반영 (호스트)

```bash
python dls_db.py ingest probe.json
python dls_db.py export merged.json
python dls_fill.py --probe merged.json --report r.csv   # dry-run
python dls_fill.py --probe merged.json --apply          # 실제 기록
```

`--apply` 없이는 노션에 아무것도 쓰지 않습니다. `r.csv` 로 먼저 검토하세요.

### 조회

```bash
python dls_db.py stats
python dls_db.py changes --since 2026-08-19    # 상태 변화 (출처별 비교)
python dls_db.py list --status online --gate
python dls_db.py kr                            # 한국 관련 유출
python dls_db.py indicators                    # 연락 수단·지갑
```

---

## 데이터 모델

| 테이블 | 내용 |
|---|---|
| `site` | 사이트 하나 = 한 행. 정규화 key 로 식별 |
| `alias` | 별칭·이전 이름 |
| `address` | 주소 이력 (사이트당 여러 개, `active` 플래그) |
| `observation` | **관측 기록. append-only — 핵심** |
| `victim` | ransomware.live 피해자 (집계용) |
| `run` | 수집 실행 이력 |

`observation` 이 append-only 이므로 "어느 사이트가 언제 죽었나", "언제 캡차가
생겼나", "주소를 언제 옮겼나" 를 나중에 되물을 수 있습니다.

**출처(`source`)를 섞어서 비교하지 마세요.** API 추정값과 Tor 실측이 서로 다르게
말하는 것을 시간에 따른 변화로 오독하게 됩니다. `changes` 명령이 기본으로
`tor_probe` 안에서만 비교하는 이유입니다 — 섞었더니 실제 변화 22건이 100건으로
부풀었습니다.

---

## 추론 계층 (`infer.py`)

원자료에서 `형식`·`개인정보 유출`·`유통 자리`·`국가` 를 판별합니다. 원칙 세 가지:

1. **근거 없는 추론은 하지 않는다.** 모든 함수가 `(값, 근거)` 를 함께 반환합니다.
2. **확신 수준을 값에 드러낸다.** 약한 근거면 `추정: ` 접두어. 사람이 확인하고
   접두어를 지우면 확정값이 됩니다.
3. **애매하면 비운다.** 잘못 채운 칸은 빈 칸보다 나쁩니다.

근거는 노션 `추론 근거` 칼럼에 그대로 남으므로 검수할 수 있습니다.

**출처에 따라 같은 단어를 다르게 읽습니다.** 상점 keywords 의 `rdp` 는 파는
물건이지만, ransomware.live 그룹 설명문의 `rdp` 는 침투 경로입니다. 섞으면
랜섬웨어 그룹이 액세스 브로커로 분류됩니다. 그래서 페이지 텍스트 · 사이트 이름 ·
API 설명문을 각각 다른 규칙으로 봅니다.

`mapping.json` 의 `format_overrides` / `country_overrides` 에 적은 값은 규칙을
무조건 이깁니다. 조사한 내용을 한 줄씩 늘려가는 자리입니다.

---

## 현재 상태 (2026-08)

- 대상 507곳, 관측 3회차 (8/19, 8/23, 8/25)
- 접속 가능 136 / 불가 371 / 압수·인계 3
- 8/19 → 8/23 사이 22곳 상태 변화 (죽음 10 · 부활 12)

**알려진 미완:** 3회차 하위 페이지 크롤링이 VM 버전 불일치로 실행되지 않았습니다.
접속되는 92곳 대상 보충 수집이 남아 있습니다. `ROADMAP-3.md` 참고.

---

## 문서

| 파일 | 내용 |
|---|---|
| `ROADMAP.md` | 칼럼별 채우기 계획 · 회차 로드맵 · 캡차 처리 권고 |
| `ROADMAP-3.md` | 3회차 기획 (근거 수치 포함) |
| `VM-TOR-GUIDE.md` | VM · Tor 환경 구성 |
| `VM-3회차.md` | 3회차 실행 순서 |
| `DB-GUIDE.md` | DB 스키마와 조회 방법 |

---

## 의존성

**없습니다.** 전부 파이썬 표준 라이브러리로만 동작합니다 (SOCKS5 구현 포함).
`pip install` 이 필요한 곳은 한 군데도 없습니다. Python 3.10+.
