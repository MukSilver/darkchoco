# dc_ransomfeed


두 앱이 같은 API 를 각자 긁고 있던 것을 정리했습니다.

무엇을 합쳤나 — 주소와 가져오는 계층뿐입니다.

  · 엔드포인트 주소 (endpoints.py)
  · 속도 제한을 지키는 fetcher (fetch.py)

무엇을 안 합쳤나 — 받은 것을 어떻게 해석하는지는 앱마다 다릅니다.

  dls-observatory  사이트 정보를 봅니다 (살아 있나·주소가 뭔가)

## 규칙

**이 패키지는 `apps/` 를 import 하지 않습니다.**
