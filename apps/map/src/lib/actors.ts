/**
 * 행위자의 활동 영토 — 설계서 4.3.8 「주 활동 영토: 사건이 가장 많은 영토, 나머지 활동 영토」.
 *
 * 두 자리가 같은 규칙을 쓴다. 전에는 검색 색인(`search.ts` `buildIndex`)만 세었다.
 *
 *   검색         전체 기간. 행위자를 고르면 주 활동 영토로 간다 (4.2.2 결과 선택)
 *   행위자 패널   기준일까지. [개요]의 주 활동 영토와 나머지 활동 영토 (4.3.8)
 *
 * 어느 사건을 셀지는 부르는 쪽이 `keep` 으로 정한다 — 검색은 이미 거른 색인 사건을,
 * 패널은 기준일에 지도에 든 사건(`inScope`)만 넘긴다. 건수는 활동 관계의 건수와
 * 같은 값이다 (설계서 3.9 「활동 관계의 건수는 그 행위자가 그 영토에 올린 사건 수」,
 * `relations.ts` `withActivity`).
 */

import type { Ev } from "./types.ts";

/** 활동 영토 한 줄 */
export type ActivityRow = {
  territoryId: string;
  /** 그 영토에 올린 사건 수 */
  count: number;
  /** 그 영토에 가장 늦게 올린 게시 시각 */
  last: string;
};

/**
 * 최신순 비교. 노션이 적은 날짜 · 시각 글자로 먼저 세운다 — 검색(`search.ts`
 * `newer`)과 사건 목록(`eventsIn`)이 같은 규칙이다. `a` 가 늦으면 음수
 */
function newerFirst(a: string, b: string): number {
  return b.slice(0, 16).localeCompare(a.slice(0, 16)) || Date.parse(b) - Date.parse(a) || 0;
}

/**
 * 행위자가 사건을 올린 영토별 건수. **많은 순, 같으면 늦게 올린 곳이 앞**이다.
 * 그래도 같으면 영토 id 순이다 — 늘 같은 줄이 주 활동 영토가 되게 한다.
 *
 * 행위자 영토 자신에 올라온 사건은 안 센다. 활동 관계가 행위자 → 다른 영토라서다.
 */
export function activityTerritories(
  events: readonly Ev[],
  actorId: string,
  keep: (e: Ev) => boolean = () => true,
): ActivityRow[] {
  const tally = new Map<string, ActivityRow>();
  for (const e of events) {
    if (e.actorTerritoryId !== actorId || e.territoryId === actorId || !keep(e)) continue;
    const row = tally.get(e.territoryId) ?? { territoryId: e.territoryId, count: 0, last: e.postedAt };
    row.count += 1;
    if (newerFirst(e.postedAt, row.last) < 0) row.last = e.postedAt;
    tally.set(e.territoryId, row);
  }
  return [...tally.values()].sort(
    (a, b) => b.count - a.count || newerFirst(a.last, b.last) || a.territoryId.localeCompare(b.territoryId),
  );
}

/** 주 활동 영토 — 사건이 가장 많은 곳. 올린 곳이 없으면 null */
export function mainTerritory(rows: readonly ActivityRow[]): string | null {
  return rows[0]?.territoryId ?? null;
}
