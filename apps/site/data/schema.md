# 데이터 계약 — `leak-map.json`

화면과 노션 사이의 약속입니다. 화면은 이 파일만 읽고, 노션을 직접 부르지 않습니다.
칸 이름을 바꾸려면 여기부터 고칩니다.

**옛 2D · 3D 지도는 지웠습니다.** 지금 이 파일을 읽는 화면은 가이드뿐입니다.
새 생태계 지도는 팀 저장소 `apps/map` 에 따로 있습니다. 아래에 나오는 지도 이야기는 옛 지도 기준입니다.

---

## 맨 위

```json
{
  "meta":     { ... },
  "layers":   [ ... ],
  "kinds":    [ ... ],
  "places":   [ ... ],
  "flows":    [ ... ],
  "cases":    [ ... ],
  "actors":   [ ... ],
  "stats":    { ... }
}
```

---

## `meta`

| 칸 | 뜻 |
|---|---|
| `basis_date` | 기준일. 이 날짜 이후의 관측은 안 들어 있습니다 |
| `edition` | 판 이름. 예 `2026.09` |
| `generated` | 이 파일을 뽑은 시각 |
| `is_sample` | **예시 데이터면 `true`.** 화면이 경고 띠를 답니다 |

`is_sample`이 참이면 화면 맨 위에 「예시 데이터입니다」가 크게 뜹니다.
실명과 예시 숫자가 붙어 나가는 것을 막기 위한 장치입니다.

---

## `layers` — 층

```json
{ "id": "sky", "name": "오픈웹", "sub": "검색하면 나오는 세계" }
```

두 개뿐입니다. `sky`(오픈웹) · `deep`(다크웹).
층은 **그 자리에 닿는 데 필요한 것**으로 가릅니다. 우리 조사 진척도가 아닙니다.

---

## `kinds` — 업종

```json
{ "id": "forum", "name": "해킹 포럼", "color": "#8b6fe0" }
```

다섯입니다 — `forum` · `ransom` · `telegram` · `archive` · `broker`.
**여섯 번째를 만들지 않습니다.** 어두운 배경에서 구분할 색이 다섯이 한계이고,
업종이 늘면 범례와 대륙이 같이 무너집니다.

---

## `places` — 자리

지도의 육각 한 칸이 이것 하나입니다.

```json
{
  "id": "forum-darkforums",
  "name": "DarkForums",
  "layer": "sky",
  "kind": "forum",
  "status": "online",
  "investigated": true,
  "cases": 17,
  "korea": true,
  "seized": false,
  "first_seen": "2026-06-11",
  "last_seen": "2026-08-19",
  "note": "데이터베이스 게시판이 있는 곳"
}
```

| 칸 | 노션 원천 | 화면에서 |
|---|---|---|
| `layer` | 포럼 DB 주소 · 어니언 주소 칸에서 계산 | 어느 판에 앉는가 |
| `kind` | 어느 DB에서 왔는가 | 칸 색 |
| `investigated` | 조사 단계가 「확인만 함」 이상 | **진한 칸 / 옅은 칸** |
| `cases` | 수집 DB에서 이 자리를 게시 플랫폼으로 적은 줄 수 | 덩어리 크기 |
| `status` | 각 DB 상태 칸 | `offline`·`seized`면 채도를 낮춥니다 |
| `korea` | 한국 관련 유출 칸에 내용이 있는가 | 한국 보기에서 밝아짐 |

**`cases`가 0이어도 자리는 그립니다.** 옅은 칸으로 남습니다.
「이름만 확보하고 아직 못 본 곳」이 몇인지가 이 지도의 정직함입니다.

**도메인·어니언 주소는 넣지 않습니다.** 이름까지만입니다.

---

## `flows` — 길

```json
{
  "from": "ransom-qilin",
  "to": "forum-breachforums",
  "kind": "drop",
  "cases": 9,
  "label": "내려가 팔림",
  "confidence": "confirmed"
}
```

| `kind` | 뜻 | 그리는 법 |
|---|---|---|
| `flat` | 같은 층 안의 이동 | 흰 곡선 |
| `drop` | 위층 → 아래층 | 빨간 점선 |
| `rise` | 아래층 → 위층. **다시 공개됨** | 노란 굵은 선 |
| `exposure` | 노출에서 거래로 (닥스훈트 몫) | 초록 점선 |
| `succession` | 압수·분화 후 옮겨 간 자리 | 노란 점선 |

`confidence`는 `confirmed` · `probable` · `unknown` 셋입니다.
`confirmed`가 아니면 선을 점선으로 그립니다.

**`cases`는 양 끝 자리의 `cases`보다 클 수 없습니다.**
화면이 그리기 전에 검사하고, 어기면 그 선을 안 그리고 콘솔에 적습니다.
셀 수 없는 선은 `cases`를 `null`로 두고 라벨에 「집계 안 함」을 답니다.

---

## `cases` — 사건

```json
{
  "id": 13,
  "title": "가나다몰 배송정보",
  "org": "가나다몰",
  "posted": "2026-08-14",
  "verdict": "신뢰성 높음",
  "items_claimed": ["이름", "이메일", "계정"],
  "items_confirmed": ["이름", "이메일"],
  "path": ["ransom-qilin", "forum-breachforums", "tg-relay", "archive-public"]
}
```

`items_claimed`는 **게시글의 주장**이고 `items_confirmed`는 **샘플에서 확인한 것**입니다.
가이드의 조치는 `items_confirmed`로만 냅니다. 이 둘을 섞으면 조작된 데이터를
유출 사실로 안내하게 됩니다.

`verdict`는 다섯입니다 — `확인됨` · `신뢰성 높음` · `미확인` · `신뢰성 낮음` · `허위`.
**`허위`면 가이드가 조치를 만들지 않습니다.**

`path`는 그 사건이 지난 자리를 순서대로 적습니다. 지도에서 사건을 고르면 이 경로만 밝아집니다.

---

## `actors` — 행위자

```json
{ "handle": "max987", "places": ["forum-darkforums", "ransom-qilin"], "role": "판매자" }
```

핸들까지만 적습니다. 실명·국적 추정·소재지는 넣지 않습니다.

---

## `stats`

```json
{ "reported": 316, "matched": 199, "circulating": 108, "judged": 12 }
```

**깔때기 순서입니다.** 앞 값이 뒤 값보다 큽니다.
화면은 이 넷을 막대로 그리고, 차이를 뺄셈으로 직접 보여 줍니다.
어느 두 값의 차이인지 말할 수 없는 숫자는 화면에 올리지 않습니다.

---

## 검사

화면이 데이터를 읽자마자 확인하는 것들입니다. 어기면 콘솔에 적고 그 요소만 안 그립니다.

1. `flows[].from` · `to` 가 `places`에 있는가
2. `flows[].cases` ≤ 양 끝 자리의 `cases`
3. `flows[].kind` 가 `drop`인데 `from`이 아래층이 아닌가 (방향과 층이 맞는가)
4. `cases[].path` 의 자리들이 전부 `places`에 있는가
5. `stats` 가 내림차순인가
6. `places[].name` 에 도메인꼴 문자열이 있는가 — 있으면 **그리지 않고 멈춥니다**
