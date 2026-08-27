# packages

공용 부품이 들어가는 자리입니다.

앱 여러 개가 같이 쓰는 코드만 여기 둡니다.
**규칙 하나: packages 는 apps 를 import 하지 않습니다.**

| 예정 | 무엇 | 어디서 뽑나 |
|---|---|---|
| dc-telegram | 로그인·채널 목록·메시지 수집 | tg-notion-report / tg-korea-alert |
| dc-notion | 노션 API 래퍼 | dls-observatory / tg-notion-report / skills |
| dc-ransomfeed | ransomware.live·ransomlook·ransomfeed | kr-leak-alarm 의 collector/sources |
| dc-safety | 안전 HTTP·차단 호스트 | kr-leak-alarm 의 http_client |
