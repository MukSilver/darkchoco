# 🇰🇷 Kr-Leak-alarm

**랜섬웨어 DLS(Data Leak Site) 한국 기업 · 공급망 피해 모니터링 도구**

<img width="2780" height="1446" alt="image" src="https://github.com/user-attachments/assets/cbf01dbc-1331-433f-855b-f1458bef90d3" />

랜섬웨어 조직이 유출 사이트에 올린 피해 기업 중 **한국과 관련된 건을 자동으로 골라내어**
로컬 웹 대시보드의 **NEW 리스트로 갱신**하고 알림을 보냅니다.

판별은 **독립된 두 축**으로 이뤄집니다.

| 축 | 무엇을 잡나 |
|---|---|
| **한국 관련성** | 한국 기업이 직접 피해자로 올라온 건 (`country=KR`, `.kr` 도메인, 한국 기업명·한글) |
| **공급망 위험** | 한국 기업이 피해자가 아니어도 **국내로 번질 수 있는 해외 벤더·협력사** 침해 |

두 번째 축이 필요한 이유는 간단합니다. MOVEit·SolarWinds·Snowflake 사례처럼
**직접 침해보다 공급망 연쇄로 국내 피해가 발생하는 경우가 더 흔한데**,
`country=KR` 필터만 쓰면 그 경로를 통째로 놓칩니다.

핵심 설계 원칙은 하나입니다 — **호스트 PC를 위험에 노출하지 않는다.**
기본 동작에서 이 도구는 **.onion 에 접속하지 않고, Tor를 요구하지 않으며, 랜섬웨어 인프라와 직접 통신하지 않습니다.**

<br>

## 목차

- [무엇을 하나](#무엇을-하나)
- [보안 모델](#보안-모델-가장-중요)
- [빠른 시작](#빠른-시작)
- [한국 관련성 판별 기준](#한국-관련성-판별-기준)
- [공급망 위험 판별 기준](#공급망-위험-판별-기준)
- [자동 실행 (작업 스케줄러)](#자동-실행-작업-스케줄러)
- [알림 설정](#알림-설정)
- [Tor 직접 크롤링 (VMware 전용)](#tor-직접-크롤링-vmware-전용)
- [명령어 레퍼런스](#명령어-레퍼런스)
- [Git 배포](#git-배포)
- [프로젝트 구조](#프로젝트-구조)
- [테스트](#테스트)
- [법적·윤리적 고지](#법적윤리적-고지)

<br>

## 무엇을 하나

```
공개 CTI 애그리게이터 API (HTTPS)
        │   ransomware.live · ransomlook.io · ransomfeed.it
        ▼
  [수집]  살균(sanitize) → 정규화 → 중복 제거
        ▼
  [판별]  한국 관련성 4단계 등급 분류
        ▼
  [저장]  SQLite — 처음 본 건만 NEW 로 표시
        ▼
  [알림]  데스크톱 토스트 / Slack·Discord / 이메일
        ▼
  [표시]  로컬 웹 대시보드 (단일 HTML, 외부 통신 0)
```

**왜 애그리게이터를 쓰나?**
ransomware.live 같은 공개 CTI 프로젝트는 이미 150개 이상 랜섬웨어 조직의 .onion DLS를
24시간 크롤링해 정제된 JSON으로 공개합니다. 우리가 같은 일을 직접 하면 얻는 것은 거의 없고
**호스트 PC를 랜섬웨어 인프라에 직접 노출시키는 위험만 커집니다.** 게다가 애그리게이터는
`country` 필드를 이미 붙여주므로 한국 판별 정확도가 훨씬 높습니다.

<br>

## 보안 모델 (가장 중요)

이 프로젝트는 "다크웹을 다루는 도구"이면서도 **실행하는 PC가 가장 안전한 상태**가 되도록 설계했습니다.

### 1. 랜섬웨어 인프라와 직접 통신하지 않음

| 항목 | 상태 |
|---|---|
| .onion 접속 | ❌ 하지 않음 (기본 모드) |
| Tor 설치 필요 | ❌ 불필요 |
| 파일 다운로드 | ❌ 절대 없음 — JSON/XML 텍스트만 |
| 유출 데이터 취득 | ❌ 없음 — 메타데이터(기업명·그룹·날짜)만 |
| 피해자 스크린샷 로드 | ❌ 없음 — CSP로 원격 이미지 차단 |

### 2. 네트워크 계층 — 하드코딩된 허용목록

`packages/dc_safety/http.py` 의 `ALLOWED_HOSTS` 에 있는 8개 호스트 외에는
**어떤 요청도 나가지 않습니다.**
(`collector/http_client.py` 는 그 이름을 그대로 넘겨주는 껍데기입니다.
원본이 `packages/` 로 옮겨졌습니다.) 리다이렉트를 따라갈 때도 목적지를 재검증하므로
소스가 오염되어도 임의 서버로 끌려가지 않습니다.

```
✅ 통과   https://api.ransomware.live/v2/...
❌ 차단   https://evil.tld/x                     (허용목록 밖)
❌ 차단   http://api.ransomware.live/...         (평문 HTTP)
❌ 차단   https://127.0.0.1:8080/                (SSRF)
❌ 차단   https://169.254.169.254/latest/...     (클라우드 메타데이터)
❌ 차단   https://api.ransomware.live.evil.tld/  (서브도메인 위장)
```

추가로 HTTPS 강제 · 응답 크기 상한(32MiB, 압축폭탄 방어) · Content-Type 화이트리스트 ·
타임아웃 · 쿠키 전면 거부가 적용됩니다.

### 3. 데이터 계층 — 모든 외부 문자열은 적대적 입력으로 취급

피해 기업명과 설명문은 **랜섬웨어 조직이 직접 작성한 문자열**입니다. 전부 살균합니다.

- HTML 태그 제거 → 엔티티 디코드 → 재검사 (이중 인코딩 우회 방어)
- 제어문자 · ANSI 이스케이프 제거 (터미널 스푸핑 방어)
- 유니코드 BiDi override 제거 (`파일.exe` ↔ `파일.txt` 위장 방어)
- NFKC 정규화, 필드별 길이 상한 (메모리 고갈 방어)
- SQLite는 **파라미터 바인딩만** 사용 (SQL 인젝션 차단)

### 4. 표시 계층 — 대시보드는 절대 코드를 실행하지 않음

```
Content-Security-Policy: default-src 'none'; connect-src 'none';
                         img-src data:; object-src 'none'
```

- **`connect-src 'none'`** — 대시보드는 어떤 외부 요청도 보내지 않습니다. 열어도 추적당하지 않습니다.
- **`.innerHTML` 을 한 줄도 쓰지 않습니다.** 모든 데이터는 `textContent` 로만 렌더링 → XSS 불가
- **URL 무력화(defang)** — `hxxp://xxxx[.]onion` 형태로만 표시하고 절대 `<a href>` 를 만들지 않습니다.
  `javascript:` `data:` `vbscript:` `file:` 스킴도 콜론을 무력화합니다.
- CSV 내보내기는 수식 시작 문자(`= + - @`)를 인용 처리 → 엑셀 CSV 인젝션 방어

### 5. 실행 계층

- 런타임 의존성 **`requests` 단 하나** (공급망 공격 표면 최소화). 나머지는 전부 표준 라이브러리
- `serve` 는 `127.0.0.1` 에만 바인딩 — 외부 네트워크에 노출되지 않음
- 작업 스케줄러 등록도 **SYSTEM 권한이 아닌 현재 사용자** 계정으로
- 비밀정보는 `.env` 로 분리하고 `.gitignore` 가 커밋을 차단
- PowerShell 알림에 피해자명을 **문자열 보간하지 않고 환경변수로 전달** → 명령 주입 불가

### 6. 자가 점검

```bash
python -m collector.main doctor
```

현재 PC가 어떤 환경인지, Tor 게이트가 잠겨 있는지, 어떤 호스트만 허용되는지 출력합니다.

<br>

## 빠른 시작

### Windows

```bat
git clone <이 저장소 URL>
cd Kr-Leak-alarm

scripts\check-env.bat        :: 환경 점검 (Python 설치 여부 · 보안 설정)
scripts\run.bat              :: 가상환경 생성 → 의존성 설치 → 수집
scripts\open-dashboard.bat   :: 대시보드 열기 (127.0.0.1:8787)
```

`run.bat` 이 알아서 가상환경 생성 → 의존성 설치 → `config.json` 준비 → 수집까지 수행합니다.

> **배치 파일 오류가 난다면** — `'e" ('은(는) 내부 또는 외부 명령...` 같은 메시지는
> `.bat` 파일이 LF 줄바꿈으로 저장됐을 때 cmd.exe 가 줄을 잘라 읽어서 나는 증상입니다.
> `.gitattributes` 가 `*.bat` / `*.ps1` 을 CRLF 로 강제하므로 clone 하면 자동 해결되지만,
> 에디터로 직접 수정하실 때는 **줄바꿈을 CRLF 로, 인코딩을 ASCII/ANSI 로** 유지하십시오.
> (배치 파일에 한글 주석을 넣으면 같은 오류가 재발합니다.)

### macOS / Linux

```bash
git clone <이 저장소 URL>
cd Kr-Leak-alarm
chmod +x scripts/run.sh
./scripts/run.sh
python -m collector.main serve
```

### 네트워크 없이 대시보드만 미리 보기

```bash
python scripts/make_demo_data.py     # 실제 KR 피해 사례 스냅샷으로 샘플 생성
python -m collector.main serve
```

> **첫 실행 안내** — 최초 실행은 과거 이력 전체를 기준선(baseline)으로 적재하며
> **알림을 보내지 않습니다.** 두 번째 실행부터 진짜 신규 건만 NEW로 뜹니다.

<br>

## 한국 관련성 판별 기준

자동 분류는 4단계입니다. 대시보드에서 등급별로 필터링할 수 있습니다.

| 등급 | 점수 | 판별 근거 | 신뢰도 |
|---|---|---|---|
| **확정** `confirmed` | 100 | 애그리게이터가 `country=KR` 로 태깅 | 매우 높음 |
| **유력** `strong` | 80 | 피해자 도메인이 `.kr` / `.co.kr` / `.ac.kr` 등 | 높음 |
| **추정** `likely` | 60 | 한국 대기업·기관명 매칭, 또는 기업명에 한글 포함 | 보통 — 확인 권장 |
| **검토필요** `review` | 30 | 설명문에만 'Korea' 등이 언급됨 | 낮음 — 반드시 사람이 확인 |

`config.json` 의 `kr_detection.min_tier_to_report` 로 어느 등급부터 NEW 알림을 받을지 정합니다
(기본값 `likely`).

**오탐 방어가 들어 있습니다.** 단어 경계 매칭으로 `Nokia` 가 `kia` 에 걸리지 않고,
북한(DPRK/Pyongyang) 관련 항목과 `Koreatown` 같은 해외 지명은 제외됩니다.
모든 항목에는 **왜 한국 관련으로 분류했는지 근거가 함께 저장**되어 대시보드에서 확인할 수 있습니다.

키워드는 `collector/data/kr_keywords.json` 에서 직접 편집할 수 있고,
`config.json` 의 `extra_keywords` / `exclude_keywords` 로 덮어쓸 수도 있습니다.

<br>

## 공급망 위험 판별 기준

한국 기업이 직접 피해자가 아니어도, 그 기업이 쓰는 벤더가 털리면 국내로 번집니다.
이 축은 **국가와 무관하게** 그런 건을 잡습니다.

| 등급 | 점수 | 판별 근거 | 대응 |
|---|---|---|---|
| **직거래** `direct` | 100 | `vendors.json` 에 등록한 우리 실제 거래처 | 즉시 확인 — 계약·연동 범위 점검 |
| **핵심벤더** `critical` | 80 | 글로벌 핵심 벤더 워치리스트 (289곳, 15개 계층) | 사내 도입 여부 확인 |
| **한국진출** `korea_ops` | 65 | 해외 기업이지만 한국 법인·사업장이 있는 것으로 보임 | 국내 데이터 포함 여부 확인 |
| **업종위험** `sector` | 50 | MSP·3PL·파운드리 등 공급망 증폭 업종 지표 | 거래 관계 있으면 확인 |

### 워치리스트에 들어 있는 계층

파일전송 솔루션(MOVEit·GoAnywhere·Cleo) · 원격관리/RMM(SolarWinds·Kaseya·ConnectWise) ·
계정·인증(Okta·CyberArk·LastPass) · 네트워크·보안장비(Fortinet·Ivanti·Citrix) ·
클라우드·데이터(Snowflake·Rackspace·Veeam) · ERP·업무SW(SAP·Oracle·Workday) ·
개발 공급망(JetBrains·GitLab·JFrog) · 커뮤니케이션 SaaS(Twilio·Mailchimp) ·
MSP·IT서비스(Accenture·NTT Data·Fujitsu) · 급여·금융인프라(ADP·Fiserv·Equifax) ·
물류·포워딩(Kuehne+Nagel·DSV·Maersk) · **반도체 공급망**(TSMC·ASML·Amkor·Foxconn·Wistron) ·
**자동차 1차 협력사**(Bosch·Continental·Denso·ZF) · 화학·소재(BASF·Shin-Etsu·JSR) ·
의료·제약 유통(McKesson·Cencora·Change Healthcare)

목록은 `collector/data/supply_keywords.json` 에서 직접 편집할 수 있습니다.

> **오탐 방지 설계** — 벤더명은 **피해 기업명·도메인·업종·설명문에만** 매칭하고
> **랜섬웨어 그룹명에는 절대 매칭하지 않습니다.** 실제로 `Barracuda`, `Titan`, `Nova` 는
> 보안 벤더명이면서 동시에 랜섬웨어 그룹명이라, 여기서 섞이면 전수 오탐이 납니다.
> 단어 경계 매칭도 적용해 `kla` 가 `Oklahoma` 에 걸리지 않습니다.

### ★ 우리 회사 협력사 등록 (정확도가 압도적으로 높아집니다)

큐레이션 목록은 어디까지나 일반론입니다. **실제로 우리가 거래하는 회사**를 등록하면
그 회사가 DLS 에 올라오는 순간 국가와 무관하게 최상위 `직거래` 등급으로 즉시 알림이 갑니다.

```bash
copy vendors.example.json vendors.json     # Windows
```

`vendors.json` 을 열어 채우세요:

```json
{
  "vendors": [
    {
      "name": "ERP 공급사",
      "names": ["Zeta Industrial Systems"],
      "domains": ["zeta-erp.co.kr"],
      "tier": "핵심",
      "note": "생산 ERP 호스팅 + 원격 유지보수 계정 보유"
    }
  ]
}
```

- `domains` 가 가장 정확합니다. 가능하면 이걸 채우세요.
- `names` 는 단어 경계 부분 매칭입니다. `ABC` 처럼 짧고 흔한 단어는 오탐이 나니 **2단어 이상**을 권장합니다.
- `note` 는 침해 시 영향 범위 판단용 메모이며, 알림과 대시보드에 그대로 표시됩니다.
- `vendors.json` 은 `.gitignore` 로 커밋이 차단됩니다 — 거래처 목록이 공개 저장소에 올라가지 않습니다.

### 벤더 순회 검색

핵심 벤더 침해는 몇 주 전 사고인 경우가 많아 '최근 100건' 피드에 안 잡힙니다.
그래서 매 실행마다 워치리스트의 **일부(기본 5개)만 검색 엔드포인트로 확인**하고,
다음 실행에서는 그다음 구간을 돌립니다. 레이트리밋을 피하면서 며칠에 걸쳐 전체를 훑는 방식입니다.
커서는 DB 에 저장되어 실행 간에 이어집니다.

```json
"vendor_search_per_run": 5,
"vendor_search_delay_seconds": 3.0
```

2026-08-19 에 벤더 검색이 짧은 시간에 수백 건을 쏴서 IP 가 막힌 뒤 완화한 값입니다.
`config.py` 의 `DEFAULTS` 와 `config.example.json` 이 같은 값을 씁니다.

### 알림 노이즈 조절

공급망 건까지 전부 토스트를 띄우면 하루에도 수십 번 울려서 알림 자체를 무시하게 됩니다.
그래서 **두 축의 알림 임계값을 따로** 둡니다.

```json
"notify": {
  "kr_min_score": 60,          // 한국 관련: 추정 등급 이상
  "supply_min_tier": "critical" // 공급망: 핵심벤더 이상만 (기본값)
}
```

기본 설정에서 **`업종위험`·`한국진출` 등급은 알림이 가지 않고 대시보드에만 쌓입니다.**
더 민감하게 받으려면 `"sector"`, 더 조용히 받으려면 `"direct"` 로 바꾸세요.

<br>

## 자동 실행 (작업 스케줄러)

```powershell
# 매일 09:00, 18:00 실행 (기본값)
powershell -ExecutionPolicy Bypass -File scripts\register-task.ps1

# 시각 지정
powershell -ExecutionPolicy Bypass -File scripts\register-task.ps1 -Times "08:00","13:00","20:00"

# 해제
powershell -ExecutionPolicy Bypass -File scripts\register-task.ps1 -Remove
```

관리자 권한 없이 현재 사용자 계정으로 등록되며, `pythonw.exe` 를 써서 콘솔 창이 뜨지 않습니다.

> 하루 2~4회면 충분합니다. 공개 API에는 레이트 리밋이 있으니 과도한 호출은 피하세요.

<br>

## 알림 설정

`.env.example` 을 `.env` 로 복사한 뒤 채우고, `config.json` 의 `notify` 에서 켭니다.
**`.env` 는 절대 git에 커밋되지 않습니다.**

| 채널 | 설정 |
|---|---|
| 데스크톱 토스트 | `notify.desktop_toast: true` (기본 켜짐, 추가 설정 불필요) |
| Slack / Discord | `.env` 의 `KRLEAK_WEBHOOK_URL` + `notify.webhook.enabled: true` |
| 이메일 | `.env` 의 `KRLEAK_SMTP_*` + `notify.email.enabled: true`, `to` 목록 |

웹훅 URL은 `hooks.slack.com` · `discord.com` 계열만 허용됩니다 (오설정으로 인한 유출 방지).
알림 본문의 URL도 전부 무력화되어 채팅에서 클릭되지 않습니다.

<br>

## Tor 직접 크롤링 (VMware 전용)

> ⚠️ **호스트 PC에서는 절대 사용하지 마십시오.**
> 이 기능은 랜섬웨어 조직이 운영하는 서버에 직접 접속합니다.

기본 수집(공개 API)만으로 대부분의 필요는 충족됩니다. 이 모듈은
애그리게이터가 아직 수집하지 않은 신생 조직의 DLS를 직접 확인해야 하는
**연구 목적**을 위한 선택 기능이며, **3중 게이트를 모두 통과해야만** 동작합니다.

```
게이트 1  config.json → tor.enabled = true
게이트 2  실행 시 --i-understand-the-risk 플래그 명시
게이트 3  VMware 가상머신에서 실행 중일 것  ← 요청하신 조건
```

게이트 3은 `Win32_ComputerSystem` / `Win32_BIOS` / VMware Tools 존재 여부(Windows),
`/sys/class/dmi/id/*` 와 `systemd-detect-virt`(Linux)로 확인합니다. **VMware가 아니면 즉시 종료합니다.**

### 사용 절차 (VM 안에서만)

1. VMware에 격리된 VM을 만들고 **깨끗한 상태로 스냅샷**을 찍습니다
   (권장: NAT 네트워크, 공유 폴더 해제, 드래그&드롭 해제, 클립보드 공유 해제)
2. VM 안에 Tor 데몬 또는 Tor Browser를 설치해 `127.0.0.1:9050` SOCKS 프록시를 엽니다
3. VM 안에서 `pip install -r requirements-tor.txt`
4. `config.json` 편집:
   ```json
   "tor": {
     "enabled": true,
     "require_vmware": true,
     "socks_proxy": "socks5h://127.0.0.1:9050",
     "targets": [{"group": "example", "url": "http://xxxxx.onion/"}],
     "delay_seconds": 5
   }
   ```
5. 게이트 검사만 먼저 확인:
   ```bash
   python -m collector.main tor-scan --i-understand-the-risk --dry-run
   ```
6. 실제 실행 후 **VM을 스냅샷으로 되돌립니다.**

모듈 내부에서도 추가 방어가 걸려 있습니다 — `.onion` 이외 호스트로는 요청 자체가 차단되고,
SOCKS 프록시는 로컬호스트만 허용하며(`socks5h` 로 DNS도 Tor가 처리 → 로컬 DNS 유출 없음),
응답은 4MiB 상한 · 텍스트만 추출 후 즉시 폐기하며, 링크 추적을 하지 않습니다.
원문 저장(`save_raw_html`)은 기본 꺼져 있고 켜더라도 `.gitignore` 가 커밋을 막습니다.

<br>

## 명령어 레퍼런스

```bash
python -m collector.main run              # 수집 → 판별 → 저장 → 알림 → 웹 데이터 생성
python -m collector.main run --no-notify  # 알림 없이 수집만
python -m collector.main new              # 미확인 NEW 목록 출력
python -m collector.main stats            # 현황 요약 (등급별/그룹별)
python -m collector.main ack              # 전체 NEW 해제
python -m collector.main ack --uid <uid>  # 특정 건만 해제
python -m collector.main export           # DB → 웹 데이터만 재생성
python -m collector.main serve            # 로컬 대시보드 (127.0.0.1:8787)
python -m collector.main doctor           # 환경/보안/공급망 설정 점검
python -m collector.main tor-scan --dry-run --i-understand-the-risk
```

수집 실행 옵션:

```bash
python -m collector.main run --no-vendor-search   # 벤더 검색 생략(요청 최소화)
python -m collector.main run --baseline           # 이번 수집분을 전부 기준선 처리
```

<br>

## Git 배포

`.gitignore` 가 다음을 **자동으로 제외**합니다 — 그대로 push해도 안전합니다.

- `.env`(웹훅·SMTP), `config.json`, `vendors.json` (비밀정보·개인 설정·거래처 목록)
- `data/` (SQLite DB), `logs/`
- `web/data/*.js`, `web/data/*.json` (수집된 피해 기업 데이터)
- `tor/captures/`, `tor/raw/` (다크웹 원문 스냅샷)

즉 **코드만 공개되고 수집 데이터는 로컬에 남습니다.** 피해 기업 정보가 실수로
공개 저장소에 올라가는 사고를 구조적으로 막습니다.

```bash
git init
git add .
git status                    # ← 위 항목들이 목록에 없는지 꼭 확인
git commit -m "feat: Kr-Leak-alarm 초기 구현"
git remote add origin <저장소 URL>
git push -u origin main
```

> **GitHub Pages 배포 주의** — 대시보드는 정적 파일이라 Pages에도 올라가지만,
> 그러면 수집 데이터가 인터넷에 공개됩니다. **비공개(private) 저장소가 아니라면
> `web/data/` 를 절대 커밋하지 마십시오.** 팀 공유가 필요하면 사내망이나 비공개 저장소를 쓰세요.

<br>

## 프로젝트 구조

이 앱은 저장소 최상위의 `packages/` 를 함께 씁니다. **앱 폴더만 받으면 import 에서
멈춥니다.** `collector/__init__.py` 가 `packages/` 를 `sys.path` 에 넣고,
`http_client.py` 는 `dc_safety`, `sources/ransomlook.py` 는 `dc_ransomfeed`,
`main.py` 는 `dc_console` 을 부릅니다. 저장소 전체를 받으십시오.

```
darkchoco-team/
├── packages/                ← 이 앱이 함께 쓰는 공용 부품 (앱 폴더 밖)
│   ├── dc_safety/           안전 HTTP · 살균 (http_client.py 의 원본)
│   ├── dc_ransomfeed/       랜섬 피드 주소 상수
│   └── dc_console/          콘솔 UTF-8 설정
└── apps/kr-leak-alarm/      ← 아래가 이 앱
```

```
Kr-Leak-alarm/
├── collector/
│   ├── main.py              CLI 진입점
│   ├── safety.py            ★ 살균 · URL 무력화 · VMware 탐지 · Tor 게이트
│   ├── http_client.py       ★ dc_safety.http 로 넘기는 껍데기 (허용목록 원본은 packages/)
│   ├── kr_filter.py         한국 관련성 4단계 판별 엔진 (축 1)
│   ├── supply_filter.py     공급망 위험 4단계 판별 엔진 (축 2)
│   ├── store.py             SQLite 저장소 · NEW 상태 관리
│   ├── export.py            웹 데이터 생성 (URL 무력화 지점)
│   ├── notify.py            토스트 / 웹훅 / 이메일
│   ├── config.py            config.json · .env 로더
│   ├── data/
│   │   ├── kr_keywords.json      한국 기업·기관 키워드 (편집 가능)
│   │   └── supply_keywords.json  글로벌 핵심 벤더 워치리스트 (편집 가능)
│   └── sources/
│       ├── base.py          정규화 스키마 · 중복 제거 키
│       ├── ransomware_live.py   1차 소스 (country 필드 제공)
│       ├── ransomlook.py        2차 소스
│       └── ransomfeed.py        3차 소스 (RSS, 기본 비활성)
├── tor/
│   └── onion_crawler.py     ⚠ VMware 전용 .onion 크롤러 (기본 비활성)
├── web/
│   ├── index.html           단일 파일 대시보드 (CSP 적용, 의존성 0)
│   └── data/                ← 생성물 (gitignore)
├── scripts/
│   ├── run.bat / run.sh             수집 실행
│   ├── open-dashboard.bat           대시보드 열기
│   ├── register-task.ps1            작업 스케줄러 등록/해제
│   └── make_demo_data.py            샘플 데이터 생성
├── tests/
│   ├── test_all.py          149개 테스트 (보안 방어 검증 포함)
│   └── fixtures.py          실데이터 형태 + 악성 페이로드 케이스
├── vendors.example.json     ★ 우리 회사 협력사 목록 템플릿
├── config.example.json
├── .env.example
├── requirements.txt         requests 하나
└── requirements-tor.txt     ⚠ VM 안에서만 설치
```

<br>

## 테스트

```bash
python -m tests.test_all
```

외부 의존성 없이 149개 검사를 수행합니다. 단순 기능 테스트가 아니라
**실제 공격 페이로드를 넣어 방어가 동작하는지** 확인합니다.

| 영역 | 검증 내용 |
|---|---|
| 입력 살균 | 스크립트 태그, 이중 인코딩, 제어문자, BiDi override, 초대형 필드 |
| URL 무력화 | http/https, `javascript:`, `data:`, `vbscript:`, `file:` |
| 네트워크 | 허용목록 밖 호스트, 평문 HTTP, SSRF, 클라우드 메타데이터, 서브도메인 위장 |
| 한국 판별 | 4등급 분류 + 오탐(Nokia/Pyongyang/Koreatown) 제외 |
| 공급망 판별 | 4등급 분류 + ★ 그룹명(Barracuda/Titan)이 벤더로 오인되지 않는지 |
| 벤더 목록 | vendors.json 도메인·사명 매칭, 유사 철자 오탐 방어 |
| 스키마 마이그레이션 | 구버전 DB 에 supply 컬럼 추가 후 기존 이력 보존 확인 |
| 알림 정책 | 두 축의 임계값이 독립적으로 동작하는지 |
| API 스키마 | 엔드포인트별 필드명 차이, 404='결과없음' 처리, 4xx 재시도 금지 |
| 레이트리밋 | 핵심 조회 실패 시 벤더 검색 0회, 연속 실패 조기 중단 |
| 재동기화 | 대량 유입 시 알림 폭주 없이 기준선 처리 |
| 중복 제거 | 소스 간 동일 피해자 병합, 그룹 별칭 통합, 법인격 접미어 제거 |
| NEW 상태 | 최초 실행 baseline, 재실행 시 0건, 신규 정확 검출 |
| SQL 인젝션 | `'; DROP TABLE victims;--` 삽입 후 테이블 보존 확인 |
| Tor 게이트 | 게이트 1·2·3 각각 차단되는지 |
| 대시보드 | CSP 존재, `innerHTML`/`eval`/`document.write`/외부 CDN 미사용 |

<br>

## 법적·윤리적 고지

- 이 도구는 **방어 목적의 위협 인텔리전스(CTI)** 수집기입니다. 공격에 사용될 수 있는 기능은 없습니다.
- 수집 대상은 **공개된 애그리게이터가 제공하는 메타데이터**(기업명·그룹·업종·날짜)이며,
  **유출된 데이터 자체는 취득하지도, 저장하지도, 표시하지도 않습니다.**
- DLS 게시물은 **랜섬웨어 조직의 일방적 주장**입니다. 실제 침해 여부·규모가 사실과 다를 수 있고,
  과거 사건의 재게시이거나 완전한 허위일 수도 있습니다.
- 자동 판별 등급은 참고용입니다. **확정 등급 외에는 반드시 사람이 검증**한 뒤 대응 판단에 쓰십시오.
- 특정 기업이 침해당했다는 사실을 외부에 공표하는 것은 명예훼손 등 법적 책임이 따를 수 있습니다.
  **확인되지 않은 정보를 공개적으로 유포하지 마십시오.**
- 실제 한국 기업 피해를 확인했다면 **KISA 인터넷침해대응센터(118)** 또는
  해당 기업의 보안 담당자에게 제보하는 것이 적절합니다.
- 데이터 출처인 공개 프로젝트들의 이용약관과 레이트 리밋을 존중하십시오.

### 데이터 출처

- [ransomware.live](https://www.ransomware.live/) — Julien Mousqueton
- [RansomLook](https://www.ransomlook.io/)
- [RansomFeed](https://ransomfeed.it/)

<br>

---

MIT License · 이 도구는 방어 목적으로만 사용하십시오.
