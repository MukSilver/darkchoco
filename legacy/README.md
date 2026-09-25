# legacy — 뗀 옛 수집기

2026-09-26 최현서 결정(인계 E-1, 「권장대로」). **여기 있는 것은 돌리지 않습니다.**

- CI 가 안 봅니다. `ci.yml` 의 앱 자체 테스트 잡을 지웠고, 「설치 없이 --help」 점검에서도 뺐습니다
- `dc.py list` · `dc.py run/auto` · README 도구표에 안 나옵니다(`dc.py` 의 `_안뒤짐`)
- 코드는 남깁니다. 무엇을 했는지 되짚을 때 읽습니다. **여기에 새 기능을 붙이지 않습니다**
- 되살릴 일이 생기면 필요한 부분만 지금 구조(`skills/` · `hub/` · `packages/`)로 옮겨 리뷰를 받습니다

## 무엇이 있나

| 폴더 · 파일 | 만든 사람 | 하던 일 | 무엇으로 대체했나 |
|---|---|---|---|
| `kr-leak-alarm/` | 안유빈 | 랜섬웨어 집계처 세 곳(ransomware.live · ransomlook · ransomfeed)에서 한국 피해와 공급망 위험을 골라 로컬 대시보드와 알림으로 냈다 | 집계처 수집은 `skills/collect/sources/ransomlive.py`(ransomware.live `kr`), 노션 반영은 `hub/events/push.py`. 한국 관련 판정은 2026-09-07 에 `packages/dc_kr` 로 올렸다. 화면은 `apps/dash`, 게시처 DB 의 랜섬 그룹은 `hub/places/probe/ransom.py` |
| `tg-korea-alert/` | 성민서 | 텔레그램 실계정으로 CTI 채널을 상주 감시해 한국 관련 글을 디스코드로 알렸다. 회사 이름의 국가를 DART 기업 목록과 Gemini 로 가렸다 | 공개 미리보기 수집 `skills/collect/sources/telegram_web.py` + `hub/events/sources/tg_preview.py`, 노션 반영 `push.py`. 미리보기가 꺼진 채널은 `hub/events/telegram/`(실계정, 손으로) |
| `ransom_kr.py` | — | `kr-leak-alarm` 의 소스를 불러 수집 표 모양으로 바꾸던 hub 어댑터(`ransom-kr`) | `ransomlive.py` |
| `tests/test_열쇠맞춤.py` | — | 위 어댑터와 `ransomlive.py` 가 같은 사건을 같은 줄로 만드는지 봤다 | 지금 어댑터는 `skills/collect/sources/test_ransomlive.py` 가 본다 |

## 대체하지 않은 것 — 버린다

아래 기능은 지금 파이프라인에 없습니다. 최현서가 「대체 안 된 기능은 버린다」 로 정했습니다.
코드는 이 폴더에 남아 있습니다.

| 기능 | 어디 있었나 |
|---|---|
| ransomlook 소스 | `kr-leak-alarm/collector/sources/ransomlook.py` |
| DART 기업 목록 대조 | `tg-korea-alert/company_country_classifier.py` |
| Gemini 회사-국가 판정기 | `tg-korea-alert/company_country_classifier.py` |
| 텔레그램 실계정 상주 감시 | `tg-korea-alert/korea_alert_monitor.py` |

## 아직 여기를 가리키는 곳

- **텔레그램 실계정 세션을 만드는 스크립트**가 `tg-korea-alert/test.py` 입니다. 남겨 둔
  `hub/events/telegram/`(login · channels · collect)의 안내가 그 경로를 가리킵니다. 세션을 새로 만들 일이
  생기면 그 스크립트만 `hub/events/telegram/` 쪽으로 옮기는 것이 다음 일입니다
- `packages/`(dc_kr · dc_telegram · dc_ransomfeed 등)의 주석에 「원래 apps/kr-leak-alarm 에 있던 것」 같은
  출처 기록이 남아 있습니다. 옮겨 온 경위를 적은 것이라 경로를 안 고쳤습니다
- `docs/기록/` 의 옛 기록은 그때의 경로 그대로 둡니다
