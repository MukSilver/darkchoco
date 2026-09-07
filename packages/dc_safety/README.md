# dc_safety


kr-leak-alarm 의 것을 표준으로 올렸습니다.
새 출처를 붙일 때 ALLOWED_HOSTS 를 먼저 고쳐야 하는 구조라,
그 자체가 검토 지점이 됩니다.

## 구성

| 파일 | 무엇 |
|---|---|
| `http.py` | 허용목록 HTTP·리다이렉트 재검증·쿠키 거부 |
| `text.py` | 텍스트 살균·defang·도메인 추출 |

`http.py` 는 requests 를 씁니다. 살균만 쓰는 곳까지 requests 를 받지 않게
`__init__.py` 가 늦게 부릅니다.

## 규칙

**이 패키지는 `apps/` 를 import 하지 않습니다.**
