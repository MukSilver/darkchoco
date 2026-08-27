# packages

공용 부품이 들어가는 자리입니다.

**규칙 하나: `packages/` 는 `apps/` 를 import 하지 않습니다.**
부품이 앱을 모르면, 앱이 아무리 바뀌어도 부품은 안전하고
부품을 고쳐도 각 앱은 자기 속도로 따라오면 됩니다.

## 무엇이 있나

| 패키지 | 무엇 | 어디서 왔나 |
|---|---|---|
| `dc_telegram` | 텔레그램 접속·수집 | 두 텔레그램 앱을 한 벌로 |
| `dc_notion` | 노션 API·토큰 | 세 곳의 래퍼 중 HTTP 계층만 |
| `dc_safety` | 안전 HTTP·텍스트 살균 | kr-leak-alarm |
| `dc_ransomfeed` | 랜섬 피드 주소·가져오기 | 두 앱이 각자 긁던 것 |

## 왜 이렇게 나눴나

**실행부는 안 합쳤습니다.** 포럼·DLS·텔레그램이 세는 대상이 다릅니다.
한 프로그램으로 합치면 `if source == ...` 분기 덩어리가 됩니다.

**밑에 깔린 것만 합쳤습니다.** 텔레그램 로그인 방식이 바뀌면
`dc_telegram` 한 곳만 고치면 두 앱에 같이 반영됩니다.

`dc_ransomfeed` 도 같은 이유로 주소와 가져오는 계층까지만 공유합니다.
`dls-observatory` 는 사이트 정보를 보고 `kr-leak-alarm` 은 피해 건을 보므로,
모델을 하나로 합치면 둘 다 망가집니다.

## 쓰는 법

각 앱에서 `packages/` 를 경로에 넣고 import 합니다.

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages"))

from dc_notion import Notion
from dc_safety import SafeHttpClient
```

## 새 출처를 붙일 때

`dc_safety.ALLOWED_HOSTS` 에 먼저 넣어야 합니다.
거기 없으면 요청 자체가 차단됩니다. 그 자체가 검토 지점입니다.

## 테스트

```bash
python packages/tests/test_dc_telegram.py
python packages/tests/test_dc_notion.py
python packages/tests/test_dc_safety_ransomfeed.py
```

전부 네트워크 없이 돕니다.
