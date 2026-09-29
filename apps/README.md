# apps

각 팀원이 소유하는 도구가 들어가는 자리입니다.
자기 폴더 안에서는 자유롭게 고치면 됩니다.

| 폴더 | 담당 | 무엇 |
|---|---|---|
| map | 최현서 | 생태계 지도 (다크웹 2D). 노션에서 굽고 Cloudflare 에 정적으로 올린다 |
| guide | 김무근 | 유출 대응 가이드라인. Supabase guide 스키마를 읽어 Cloudflare 에 정적으로 올린다 |
| ragdb | 김무근 | LLM 다크웹 RAG DB. Supabase rag 스키마를 받아 운영 PC 에서 조각과 색인을 만든다 |

kr-leak-alarm(안유빈)과 tg-korea-alert(성민서)는 2026-09-26 에 `legacy/` 로 뗐습니다.
무엇으로 대체했고 무엇을 대체하지 않았는지는 `legacy/README.md` 에 있습니다.

guide 와 ragdb 는 2026-09-29 에 따로 있던 저장소에서 옮겨 왔습니다. 둘 다 노션을 읽지 않습니다.
노션을 읽어 Supabase 를 채우는 것은 정제 배치(darkchoco-data) 하나이고, 그 저장소는 따로 둡니다.

    노션 → 정제 배치(darkchoco-data) → Supabase → 산출물 (map, guide, ragdb)

지도는 아직 노션에서 직접 굽습니다. Supabase 로 옮기는 일은 `apps/map/README.md` 에 적혀 있습니다.
