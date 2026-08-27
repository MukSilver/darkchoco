# dc_notion

노션 API 공용 부품입니다.

## 왜 만들었나

세 곳이 각자 래퍼를 갖고 있었습니다.

| 어디 | 줄 수 | 무엇이 강했나 |
|---|---|---|
| `dls-observatory/notion.py` | 240 | 재시도·속도 제한·값 변환 |
| `skills/tools/notion.py` | 208 | 토큰 파일 탐색·읽기 도구 |
| `tg-notion-report/notion_safe_update.py` | 743 | 안전 갱신 판정 |

토큰 읽는 방식도 갈라져 있었습니다. 한쪽은 `NOTION_TOKEN`, 한쪽은 `NOTION_TOKEN_FILE`.

## 무엇을 합쳤고 무엇을 남겼나

**합친 것 — HTTP 계층과 토큰**

`dls-observatory` 의 재시도 로직이 셋 중 가장 잘 되어 있어 그것을 표준으로 삼았습니다.

- 평균 3req/s 로 스스로 속도를 늦춤
- 429 는 `Retry-After` 만큼 대기
- 502·503·504 와 연결 끊김은 지수 백오프 재시도

**남긴 것 — 앱마다 다른 판정 로직**

`tg-notion-report` 의 743줄은 "주소가 정확히 일치하는 페이지만 갱신하고,
후보가 0개거나 2개 이상이면 중단"하는 안전장치입니다. 그 앱에만 필요한
규칙이므로 옮기지 않았습니다.

## 토큰

두 방식을 모두 받습니다. 순서대로 찾습니다.

1. `NOTION_TOKEN_FILE` 이 가리키는 파일 **(권장)**
2. `/run/secrets/notion_token` · `~/.config/darkchoco/notion_token` · `~/.notion_token`
3. `NOTION_TOKEN` 환경변수 (예전 방식, 계속 지원)

파일을 권하는 이유는 환경변수가 프로세스 목록이나 로그에 묻어 나오기 쉬운
반면, 파일은 권한으로 막을 수 있기 때문입니다.

## 쓰는 법

```python
from dc_notion import Notion, read_value, build_value

n = Notion()                       # 토큰은 알아서 찾습니다
rows = n.query_all(data_source_id)
for row in rows:
    print(read_value(row["properties"]["이름"]))

n.update_page(page_id, {"판정": build_value("select", "허위")})
```

## 테스트

```bash
python packages/tests/test_dc_notion.py
```

## 규칙

**이 패키지는 `apps/` 를 import 하지 않습니다.**
