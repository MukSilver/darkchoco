# 3회차 수집 — VM 실행 순서

2회차와 달라진 점은 **파일이 2개**라는 것뿐입니다. `infer.py` 를 같이 올려야
VM 이 본문을 보고 판정할 수 있습니다.

---

## ① VM 으로 파일 3개 보내기

호스트에서 (프로젝트 폴더에서):

```powershell
cd C:\Users\yu040\Documents\Darkweb-project\Notion-DLS
python dls_fill.py --export-targets targets.csv
```

`to-vm` 폴더에 이 3개를 넣고 전송하세요.

| 파일 | 왜 필요한가 |
|---|---|
| `tor_probe.py` | 수집기 |
| **`infer.py`** | **새로 추가.** VM 안에서 판정을 끝내기 위해 |
| `targets.csv` | 대상 목록 |

`infer.py` 를 빼먹어도 수집은 돌아갑니다. 대신 본문 판정만 조용히 건너뜁니다
(`format_hint` 가 안 나옵니다).

## ② VM 에서 Tor 확인

```bash
python3 tor_probe.py --selftest
```

여기서 실패하면 수집을 시작하지 마세요.

## ③ 수집

```bash
python3 tor_probe.py targets.csv -o probe3.json --resume
```

- **4.5~5시간** 걸립니다 (2회차 3시간 + 하위 페이지).
- 중간에 끊겨도 `--resume` 을 붙여 다시 실행하면 이어서 합니다.
- 결과는 매 건마다 저장되므로 강제 종료해도 안 잃습니다.

시간을 줄이고 싶으면:

```bash
python3 tor_probe.py targets.csv -o probe3.json --resume --subpages 2
```

`--subpages 0` 이면 2회차와 똑같이 랜딩 페이지만 읽습니다.

## ④ 호스트로 가져오기

VM 에서:
```bash
python3 -m http.server 8000
ip a | grep inet          # VM 주소 확인
```

**호스트에서 — 반드시 프로젝트 폴더에서 받으세요.**
(2회차 때 `to-vm` 폴더에서 받아 세 번 헛돌았습니다)

```powershell
cd C:\Users\yu040\Documents\Darkweb-project\Notion-DLS
curl.exe -o probe3.json http://<VM주소>:8000/probe3.json
```

## ⑤ 적재 → 검토 → 반영

```powershell
python dls_db.py ingest probe3.json
python dls_db.py export merged.json
python dls_fill.py --probe merged.json --report r.csv
```

`r.csv` 를 보고 이상 없으면:

```powershell
python dls_fill.py --probe merged.json --apply
```

3회차부터는 관측이 3개라 이것도 의미가 생깁니다:

```powershell
python dls_db.py changes --since 2026-08-23
```

---

## 3회차에서 새로 하는 일

**하위 페이지 한 겹.** 랜딩에서 `/victims` `/leaks` `/posts` 같은 경로를 골라
사이트당 최대 3개를 더 읽습니다. 같은 onion 안에서만, 깊이 1단계만,
가입벽이 있으면 안 들어갑니다.

**본문 판정을 VM 에서.** 본문을 `probe3.json` 에 담으면 피해 기업 이름이
호스트로 넘어옵니다. 그래서 VM 이 메모리에서 판정만 하고 결과를 내보냅니다.

```json
"format_hint": "카딩",
"format_why":  "본문 'fullz'",
"pii_hint":    "있음"
```

근거는 매칭된 키워드 자체뿐이고 60자로 잘립니다. 본문은 디스크에 안 닿습니다.

**대기 화면 재시도.** 제목이 `Loading...` / `One moment` / `Access Queue` 면
5초 쉬고 쿠키를 물고 한 번 더 요청합니다. 2회차에 7곳이 여기 걸렸습니다.
**캡차는 여전히 안 풉니다** — 존재만 기록합니다.

**Telegram 오탐 제거.** `t.me/contact`, `t.me/messenger` 같은 시스템 경로를
핸들로 읽던 것을 걸러냅니다 (2회차 33건 중 8건).

---

## 안전 설계 — 그대로입니다

- `socks5h` 만 사용 (DNS 를 Tor 에 위임)
- 수집 전 Tor 검증. 확인 안 되면 시작 안 함
- 25건마다 Tor 재확인. 끊기면 그 구간 판정을 `미확인` 으로 표시하고 중단
- Content-Type 필터 — 유출물 아카이브를 받지 않음
- 하위 페이지는 링크 단계에서 `.zip` `.7z` `.sql` 등을 한 겹 더 차단
- 응답 본문을 디스크에 쓰지 않음
- 가입·로그인 벽 뒤로 안 들어감
- 캡차 안 풂
- 피해자 회사명 저장 안 함 (집계 수치만)
- 세션 쿠키는 재요청에만 쓰고 결과 파일에 기록하지 않음
- DB 는 호스트에만. VM 은 `probe3.json` 하나만 만듦
