# darkchoco

다크웹 개인정보 유통 생태계 조사 도구 모음
화이트햇 스쿨 4기 · 다크초코

---

## 처음 오셨으면

**[docs/각자_할일.md](docs/각자_할일.md)** 를 먼저 보십시오.
각자 무엇을 고쳐야 하는지 그대로 따라 할 수 있게 적혀 있습니다.

---

## 구조

```
apps/         각자 소유. 자기 폴더에서 자유롭게 고칩니다
packages/     공용 부품. 여기만 공유합니다
skills/       검증 스킬
docs/         운영안 · 구축 절차 · 할 일
```

| 폴더 | 담당 | 무엇 |
|---|---|---|
| apps/forum-crawler | 성민서 | 포럼 크롤링 |
| apps/dls-observatory | 안유빈 | 다크웹 유출 사이트 관측 |
| apps/kr-leak-alarm | 안유빈 | 랜섬웨어 한국 피해 알림 |
| apps/tg-notion-report | 이수빈 | 텔레그램 수집 · 노션 반영 |
| apps/tg-korea-alert | 성민서 | 텔레그램 한국 알림 |
| skills | 최현서 | 유출 주장 검증 |

---

## 공용 부품

| 패키지 | 무엇 |
|---|---|
| dc_telegram | 텔레그램 접속 · 수집 |
| dc_notion | 노션 API · 토큰 |
| dc_safety | 안전 HTTP · 텍스트 살균 |
| dc_ransomfeed | 랜섬 피드 주소 · 가져오기 |

사용법은 각 패키지 README 에 있습니다.

**규칙 하나: packages 는 apps 를 참조하지 않습니다.**

---

## 작업 방식

```
git switch -c feat/앱이름-무엇
수정 후 동작 확인
git push -u origin feat/앱이름-무엇
```

자기 앱 폴더는 리뷰 없이 머지해도 됩니다.
packages 를 고치면 리뷰 한 명이 필요합니다.

**앱 1개씩 합니다. 한 번에 여러 앱을 고치면 무엇이 깨졌는지 못 찾습니다.**

---

## 테스트

```
python packages/tests/test_dc_telegram.py
python packages/tests/test_dc_notion.py
python packages/tests/test_dc_safety_ransomfeed.py
```

부품이 멀쩡한지 보는 테스트입니다. 네트워크 없이 돕니다.

---

## 실행 위치

저장소는 코드만 관리합니다. 실행 위치는 나눕니다.

| 무엇 | 어디서 |
|---|---|
| 오픈웹 (ransomware.live · Discord) | 어디든 |
| Tor 접속 (포럼 · onion) | Kali VM 또는 Docker |
| 작업 스케줄러 등록 | Windows |

**Tor 를 타는 작업은 GitHub Actions 에서 돌리지 않습니다.**

---

## 문서

- [각자 할 일](docs/각자_할일.md) — 지금 무엇을 고쳐야 하는지
- [팀 GitHub 운영안](docs/팀깃헙_운영안.md) — 왜 이 구조인지
- [구축 절차](docs/구축절차.md) — 저장소를 어떻게 만들었는지

---

## 주의

이 저장소는 **비공개** 입니다.
피해 기업명 · onion 주소 · 조사 기록이 들어 있습니다.
외부 공개용 산출물을 만들 때는 별도로 마스킹합니다.

토큰과 `.env` 는 커밋하지 않습니다.
