# 변경 이력

형식: [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/) · 버전: [SemVer](https://semver.org/lang/ko/)

## [1.0.0] — 2026-08-24

인수인계 기준 버전.

### 기능
- 공개 CTI 애그리게이터(ransomware.live · ransomlook.io · ransomfeed.it) 다중 소스 수집
- **한국 관련성** 4단계 판별 (확정 / 유력 / 추정 / 검토필요) + 판별 근거 기록
- **공급망 위험** 4단계 판별 (직거래 / 핵심벤더 / 한국진출 / 업종위험) — 두 축 독립 평가
- 글로벌 핵심 벤더 워치리스트 289곳 / 15개 계층
- `vendors.json` 으로 자사 협력사 등록 시 최상위 등급 즉시 알림
- 소스 간 중복 제거 (그룹 별칭 통합 · 법인격 접미어 제거 · 도메인 우선 매칭)
- SQLite 기반 NEW 상태 관리 — 처음 본 건만 알림
- 단일 HTML 대시보드 (의존성 0, `file://` 동작, CSP 적용)
- 알림: Windows 토스트 / Slack·Discord 웹훅 / 이메일
- Tor 직접 크롤러 — 3중 게이트(설정 + 명시 플래그 + VMware 검증) 통과 시에만 동작

### 보안
- 하드코딩 호스트 허용목록 — SSRF·클라우드 메타데이터·서브도메인 위장 차단
- 외부 문자열 전수 살균 — HTML 태그 · 제어문자 · ANSI · BiDi override 제거
- 공격자 URL 무력화 — `hxxp://x[.]onion`, `javascript:`/`data:`/`file:` 스킴 포함
- 대시보드 `innerHTML` 미사용, CSP `connect-src 'none'`
- SQLite 파라미터 바인딩 전용, CSV 인젝션 방어
- PowerShell 알림에 환경변수 전달 — 명령 주입 차단
- 비밀정보·수집 데이터 `.gitignore` 차단

### 수정 (운영 중 발견)
- **API 스키마 불일치** — `/recentvictims` 는 `victim`/`domain`/`claim_url`/`attackdate`,
  `/countryvictims` 는 `post_title`/`website`/`post_url`/`published` 를 씀.
  후자만 읽어 최근 피드 건의 도메인이 통째로 비었고, `.kr` 판별이 동작하지 않았음
- **404 를 오류로 취급** — 이 API 는 '검색 결과 없음'을 404 로 응답. 재시도 3회가
  붙어 요청 폭증 → IP 레이트리밋 유발
- **레이트리밋 방어 부재** — 회로 차단기, 연속 실패 조기 중단, 기본값 완화 추가
- **알림 폭주** — DB 초기화·장기 공백 복구 시 수백 건이 한꺼번에 NEW 로 잡히던 문제.
  임계값 초과 시 재동기화로 판단해 기준선 처리
- **스키마 마이그레이션 실패** — 기존 DB 에 인덱스를 컬럼보다 먼저 만들어 기동 불가
- **로컬 서버 무한 로딩** — 단일 스레드 서버가 브라우저 선연결 소켓에 물림.
  `ThreadingHTTPServer` 로 교체
- **배치 파일 실행 불가** — LF 줄바꿈 + 한글 주석으로 cmd.exe 가 줄을 잘라 읽음.
  CRLF + ASCII 로 재작성, `.gitattributes` 로 고정
- `.gitignore` 의 `data/` 가 `collector/data/kr_keywords.json`(필수 코드)까지 제외하던 문제

### 검증
- 자체 테스트 149개 — 실제 공격 페이로드 기반 방어 검증 포함
