# Tor 수집 운영 가이드 (Windows 호스트 + VMware + Kali 게스트)

## 왜 이 구조인가

```
[Windows 호스트]                      [Kali VM + Tor]
 dls_fill.py                           tor_probe.py
   ├ 노션 읽기/쓰기                       ├ .onion / clearnet HTTP GET
   └ targets.csv 생성  ──── git ────▶     └ probe.json 생성
                        ◀─── git ────
   probe.json 반영 → 노션
```

**노션 토큰은 VM 에 넣지 않습니다.** 남의 워크스페이스 토큰이라 관리 범위를 좁게 유지하고,
사람이 probe.json 을 한 번 보는 검토 게이트를 둡니다.

**브라우저를 쓰지 않습니다.** Tor Browser 로 클릭하며 돌아다니는 게 이 작업에서 가장
위험합니다 — JS 실행과 렌더링 엔진 취약점 표면이 열립니다. `tor_probe.py` 는 HTML
텍스트만 받으므로 실행되는 코드가 없습니다.

---

## 1. VM 격리 설정 (VMware)

VM 종료 상태에서 설정합니다.

| 항목 | 값 | 이유 |
|---|---|---|
| Network Adapter | **NAT** | Bridged 는 VM 을 학교/사내망에 직접 노출 |
| Shared Folders | **Disabled** | 호스트로 오는 경로를 git 하나로 제한 |
| Drag and Drop | **Disabled** | 게스트→호스트 탈출의 흔한 경로 |
| Copy and Paste | **Disabled** | 위와 동일 |
| USB Controller | 필요 없으면 제거 | 표면 축소 |
| 3D 그래픽 가속 | **끄기** | 그래픽 드라이버가 게스트 탈출 CVE 의 단골 |

설정 후 **스냅샷을 찍으세요** (VM → Snapshot → Take Snapshot, 이름 `clean-tor`).
수집 세션이 끝나면 되돌리면 됩니다.

> VMware Tools 의 공유 기능은 위에서 다 껐으니, 편의 기능만 남습니다. 더 엄격하게
> 가려면 Tools 자체를 설치하지 않아도 `tor_probe.py` 는 동작합니다.

## 2. Kali 에 Tor 설치

```bash
sudo apt update && sudo apt install -y tor
sudo systemctl enable --now tor
ss -ltnp | grep 9050          # 127.0.0.1:9050 이 보이면 정상
```

Tor Browser 만 쓰신다면 포트가 **9150** 이고, 브라우저가 실행 중이어야 합니다.
자동화에는 데몬(9050)이 안정적입니다.

`tor_probe.py` 는 파이썬 표준 라이브러리만 씁니다. `pip install` 이 필요 없습니다.

## 3. 코드·데이터 전달

GitHub 을 쓰신다면 **반드시 비공개 저장소**로 하세요. 공개로 올리면 onion 주소 목록과
조사 대상이 그대로 공개됩니다.

VM 에서 push 까지 하려면 **그 저장소 하나에만 쓰기 권한이 있는 fine-grained PAT** 를
따로 발급하세요. 계정 전체 권한 토큰을 VM 에 두지 마세요.

```bash
# VM 최초 1회
git clone https://github.com/<you>/<private-repo>.git
cd <private-repo>
git config user.name "kali-probe"
git config user.email "kali@local"
```

git 을 쓰기 싫으면 `python3 -m http.server` 로 호스트에서 파일을 받아오는 방법도
있습니다. 어느 쪽이든 **공유 폴더는 켜지 마세요.**

## 4. 실행 순서

### 호스트 — 수집 대상 뽑기
```powershell
python dls_fill.py --export-targets targets.csv
```
주소가 있는 행의 `name,url` 만 CSV 로 나옵니다. 일부만 시험하려면:
```powershell
python dls_fill.py --row "THE MATRIX" --export-targets targets.csv
```

### VM — Tor 경유 확인 (매번 하세요)
```bash
python3 tor_probe.py --selftest
```
`[O] Tor 경유 확인 — 출구 IP x.x.x.x` 가 나와야 합니다.
`IsTor: false` 면 **실제 IP 가 노출되는 상태**입니다. 즉시 중단하세요.
확인이 실패하면 스크립트는 아무것도 수집하지 않고 종료합니다.

### VM — 수집
```bash
python3 tor_probe.py targets.csv -o probe.json --limit 5 --verbose   # 먼저 5개
python3 tor_probe.py targets.csv -o probe.json                        # 전체
```

- 요청 간 기본 3초 + 지터. 61개면 5분 안팎, 500개면 40분쯤.
- 매 건마다 `probe.json` 을 저장하므로 중간에 끊겨도 결과가 남습니다.
- Tor Browser 포트면 `--proxy-port 9150`.

### 호스트 — 노션 반영
```powershell
python dls_fill.py --probe probe.json --report r.csv    # dry-run + 검토용 CSV
python dls_fill.py --probe probe.json --apply           # 반영
```

Tor 실측값은 API 추정값보다 우선합니다. `출처` 칼럼에 `직접 확인` 이 추가되어
어느 값이 실측인지 나중에 구분됩니다.

## 5. 채워지는 칼럼

| 칼럼 | 근거 |
|---|---|
| 상태 | 실제 접속 성공 여부 + HTTP 상태코드 |
| 어떤 곳인지 | `<title>` (비어 있을 때만 `사이트 제목: …` 으로) |
| 사용 언어 | 문자 체계 비율(키릴·한글·CJK…) + 불용어 빈도 |
| 가입 필요 | 로그인/회원가입 폼·초대코드·가입비 신호 |
| 들어가는 법 | `캡차 있음, 회원가입 필요` 처럼 감지된 진입 조건 |
| 확인일 | 수집 시각 |

## 6. 안전장치 (코드에 박아둔 것)

- **socks5h 전용** — .onion 이름 해석을 Tor 가 담당합니다. `socks5://` 는 로컬 DNS 로
  이름을 물어보다 새어나가므로 쓰지 않습니다.
- **사전 Tor 확인** — check.torproject.org 로 경유를 검증하고, 실패하면 수집을 시작조차
  하지 않습니다.
- **HTML 만 수신** — `text/html`·`text/plain` 이 아니면 본문을 받지 않고 끊습니다.
  유출 데이터 아카이브를 실수로 내려받는 사고를 막는 장치입니다.
- **1.5MB 상한 · 리다이렉트 3회 제한 · GET 전용**
- **본문 미저장** — 추출한 메타데이터만 남기고 HTML 은 디스크에 쓰지 않습니다.

## 7. 하지 않는 것, 하지 마셔야 하는 것

**캡차·로그인 우회는 하지 않습니다.** 대신 존재 여부를 기록합니다 — 그게 `가입 필요`,
`들어가는 법` 칼럼의 답이고, ransomlook 도 같은 방식(`captcha: true/false`)을 씁니다.

캡차를 넘어 계정을 만들고 마켓에 진입하는 것은 성격이 다른 행위입니다. 카딩 마켓
기준으로는 법적 위험이 있고, 대학 연구라면 연구윤리 심의 대상입니다. 지도교수·기관
담당자와 먼저 합의하지 않은 상태에서 진행할 일이 아닙니다.

**유출 데이터는 내려받지 마세요.** 피해자 개인정보라 소지 자체가 문제가 됩니다.
인덱스 페이지만 읽고 첨부·다운로드 링크는 건드리지 않는 것이 원칙입니다. 코드의
Content-Type 필터가 1차 방어선이지만, 손으로 URL 을 넣을 때는 직접 지켜야 합니다.

**VPN 은 익명성에 도움이 되지 않습니다.** VPN→Tor 순서의 효용은 "이 사람이 Tor 를
쓴다" 를 망 관리자에게 숨기는 것 하나입니다. 대학 네트워크 정책을 먼저 확인하세요.
Tor→VPN 순서는 오히려 익명성을 해치니 쓰지 마세요.

## 8. 세션 종료 후

```bash
history -c            # VM 셸 기록 정리
```
VMware 에서 스냅샷 `clean-tor` 로 되돌리면 VM 안의 모든 흔적이 사라집니다.
probe.json 은 미리 git 으로 내보낸 뒤에 되돌리세요.
