/**
 * 예시 데이터. **실제 데이터가 아니다.**
 *
 * 설계서 3.4 의 실측 표를 재현하도록 만들었다 — 수집 DB 195건, 2026-09-21 기준,
 * 영토 점수 33.7 / 20.8 / 7.2 / 4.0 / 4.0, 섬 점수 랜섬웨어 91.2 · 포럼 37.6 ·
 * 텔레그램 13.6, 소스 빈 26건 12.9점이다. 이 입력으로 칸 수가 87 / 54 / 19 / 10 / 10
 * 이 나오면 계산이 설계서와 맞는 것이다.
 *
 * **영토 이름을 지어 썼다.** 설계서에는 실제 포럼명과 그룹명이 적혀 있는데
 * 여기에 옮기지 않았다. 까닭 둘이다.
 *
 *   1. 실제 이름은 노션에서 와야 한다. 그 길에 반출 관문 셋이 있다
 *      (프젝 `DEV.md` 4-2). 예시 데이터에 박으면 그 관문을 우회하는 셈이다
 *   2. 이 저장소가 나중에 공개될 수 있다
 *
 * 굽기가 붙으면 이 파일은 시험용으로만 남는다.
 */

import type { Ev, MapData, SizeGrade, Territory, Verdict } from "./types.ts";
import { DARK_ISLANDS } from "./islands.ts";

/** 설계서 3.4 가 계산 기준으로 삼은 날 */
export const SAMPLE_BASIS = "2026-09-21";

type Spec = {
  id: string;
  name: string;
  islandId: Territory["islandId"];
  /** 사건 수 */
  n: number;
  /** 노리는 영토 점수. 이 값이 나오도록 판정을 섞는다 */
  score: number;
};

/**
 * 설계서 3.4 표의 다섯 줄과, 섬 점수를 맞추기 위한 나머지다.
 *
 * 섬 점수가 랜섬웨어 91.2 · 포럼 37.6 · 텔레그램 13.6 이므로, 표에 안 나온
 * 몫을 「그 밖」 영토로 묶어 채운다. 실제 데이터에서는 이 자리가 여러 영토로
 * 갈리지만 계산을 확인하는 데는 묶어도 같다.
 */
const SPECS: Spec[] = [
  { id: "t-forum-1", name: "포럼 A", islandId: "FORUM", n: 43, score: 33.7 },
  { id: "t-forum-etc", name: "포럼 그 밖", islandId: "FORUM", n: 5, score: 3.9 },
  { id: "t-ransom-1", name: "랜섬웨어 A", islandId: "RANSOMWARE", n: 26, score: 20.8 },
  { id: "t-ransom-2", name: "랜섬웨어 B", islandId: "RANSOMWARE", n: 5, score: 4.0 },
  { id: "t-ransom-etc", name: "랜섬웨어 그 밖", islandId: "RANSOMWARE", n: 73, score: 66.4 },
  { id: "t-tg-1", name: "텔레그램 A", islandId: "TELEGRAM", n: 9, score: 7.2 },
  { id: "t-tg-2", name: "텔레그램 B", islandId: "TELEGRAM", n: 5, score: 4.0 },
  { id: "t-tg-etc", name: "텔레그램 그 밖", islandId: "TELEGRAM", n: 3, score: 2.4 },
  // 소스가 빈 26건(미분류 섬)은 2026-09-23 에 섬과 함께 뺐다 (islands.ts)
];

export const SAMPLE_TERRITORIES: Territory[] = SPECS.map((s) => ({
  id: s.id,
  name: s.name,
  islandId: s.islandId,
  web: "dark",
}));

/**
 * 한 사건이 가질 수 있는 점수. 설계서 3.2 의 가중치를 곱한 값이다.
 *
 * 규모는 전부 `unknown`(1.0) 이다. 설계서 3.4 가 「규모는 전부 모름으로 계산」
 * 했다고 적었기 때문이다.
 */
const MENU: { verdict: Verdict; repost: boolean; v: number }[] = [
  { verdict: "high", repost: false, v: 1.0 },
  { verdict: "unverified", repost: false, v: 0.8 },
  { verdict: "unknown", repost: false, v: 0.7 },
  { verdict: "high", repost: true, v: 0.5 },
  { verdict: "unverified", repost: true, v: 0.4 },
  { verdict: "unknown", repost: true, v: 0.35 },
  { verdict: "low", repost: true, v: 0.2 },
];

/**
 * 점수를 맞춰 사건을 지어낸다.
 *
 * **난수를 안 쓴다.** 같은 입력이면 같은 지도가 나와야 화면을 눈으로 검수할 수
 * 있다.
 *
 * **처음에는 판정 둘(0.8 · 1.0)만 섞었는데 그것으로는 안 됐다.** 43건짜리
 * 영토가 33.7점인데 0.8 × 43 = 34.4 라서 두 값 사이에 목표가 없다. 미분류는
 * 26건에 12.9점이라 평균이 0.496 이고 재게시(×0.5)까지 써야 닿는다.
 *
 * 그래서 목표 평균을 감싸는 이웃한 두 값을 고르고 그 둘의 개수를 푼다.
 *
 *     lo × (n − k) + hi × k = target   →   k = (target − lo·n) / (hi − lo)
 */
function makeEvents(s: Spec, startDay: number): Ev[] {
  const avg = s.score / s.n;
  const asc = [...MENU].sort((a, b) => a.v - b.v);

  let lo = asc[0];
  let hi = asc[asc.length - 1];
  const 딱맞음 = asc.find((m) => Math.abs(m.v - avg) < 1e-9);
  if (딱맞음) {
    lo = 딱맞음;
    hi = 딱맞음;
  } else {
    for (let i = 0; i < asc.length - 1; i++) {
      if (asc[i].v <= avg && avg <= asc[i + 1].v) {
        lo = asc[i];
        hi = asc[i + 1];
        break;
      }
    }
  }

  const k =
    hi.v === lo.v ? 0 : Math.round((s.score - lo.v * s.n) / (hi.v - lo.v));
  const 높은개수 = Math.max(0, Math.min(s.n, k));

  // 최근일수록 촘촘하게 흩는 정도. 영토마다 달라야 활동도에 차이가 난다
  const 기울기 = 0.3 + (startDay % 3) * 0.1;

  return Array.from({ length: s.n }, (_, i) => {
    const m = i < 높은개수 ? hi : lo;
    const size: SizeGrade = "unknown";
    /*
     * 게시일을 2023-10-01 부터 1090일에 걸쳐 흩는다. 스냅샷 바 · 월별 막대 ·
     * 타임라인이 움직이는 것을 눈으로 보려면 날짜가 퍼져 있어야 한다.
     *
     * **처음에는 340일, 곧 한 해였다.** 그러면 타임라인 탭의 연도 칩이 둘뿐이고
     * 성장 요약이 전부 `0 → N` 이 되어 자란 모양을 못 본다. 세 해로 늘렸다.
     *
     * **처음에는 `(startDay + i × 7) % 350` 이었는데 그러면 안 됐다.** 7일
     * 간격이라 73건짜리 영토는 511일치가 되어 `% 350` 으로 한 바퀴 돌고,
     * 돌아온 자리가 앞쪽에 겹쳐 **최근 몇 달이 통째로 빈다.** 월별 막대가
     * 오른쪽으로 갈수록 0 에 가까워지고 활동도도 따라 낮아졌다.
     *
     * 건수와 무관하게 기간 안에 다 들어오도록 비율로 흩는다.
     *
     * **지수는 1 보다 작아야 최근이 촘촘하다.** `t^g` 에서 `g > 1` 이면 `t` 가
     * 1 근처일 때 날짜가 성큼성큼 벌어져 오히려 최근이 성겨진다. 처음에 1.0~1.7
     * 로 뒀다가 **영토마다 최근 30일에 사건이 딱 한 건씩만 들어와 활동도가
     * 전부 100 으로 같아졌다.** 활동도는 섬 안 최댓값 대비라서, 다 같으면
     * 다 100 이 된다.
     */
    const t = (i + 1) / s.n;
    const day = Math.round(1090 * Math.pow(t, 기울기));
    const d = new Date(Date.UTC(2023, 9, 1));
    d.setUTCDate(d.getUTCDate() + day);
    return {
      id: `${s.id}#${i}`,
      territoryId: s.id,
      postedAt: d.toISOString(),
      verdict: m.verdict,
      size,
      repost: m.repost,
      excluded: false,
    };
  });
}

export const SAMPLE_EVENTS: Ev[] = SPECS.flatMap((s, i) => makeEvents(s, i * 13));

export const SAMPLE: MapData = {
  generatedAt: `${SAMPLE_BASIS}T00:00:00.000Z`,
  islands: DARK_ISLANDS,
  territories: SAMPLE_TERRITORIES,
  events: SAMPLE_EVENTS,
  // 관계선 DB 와 연결선 DB 가 노션에 아직 없다 (설계서 5.1-4 · 5.1-5).
  // 그것이 생기기 전까지 관계 탭과 [연결] 탭은 못 만든다
  relations: [],
  links: [],
};
