/**
 * 엔티티 탭이 쓰는 집계 — 설계서 4.3.5.
 *
 * 표와 KPI 카드가 같은 값을 보게 영토 계산 결과(`score.ts`)를 그대로 쓴다.
 * 여기서 새로 세는 것은 최근 관측 시각 하나다.
 */

import { inScope } from "./score.ts";
import type { Ev } from "./types.ts";

export type RecentKpi = {
  /** 최근 30일 건수 */
  count: number;
  /** 전월 대비 — 직전 30일보다 늘어난 건수. 직전 30일이 0건이면 null */
  trend: number | null;
};

/**
 * KPI 「최근 30일 사건」 — 건수와 전월 대비 (설계서 4.3.5 L725, 피그마 ⑦-7
 * 「▲ 4 · 전월 대비」 · ⑦-7a 「▲ 6 · 전월 대비」).
 *
 * 섬 영토의 `recent30` · `prev30`(영토!AB · AC)을 더한다. **행위자 영토의 값은
 * 그 행위자가 올린 사건이다** (`computeMap` 이 행위자 영토에서 한 번 더 센다).
 * 전에는 사건의 `territoryId` 로만 세어 행위자 섬이 늘 0 이었다. 한 섬 안에서는
 * 사건 하나가 영토 하나에만 들어 겹치지 않는다.
 *
 * 날짜를 대신 넣은 사건은 영토 값에서 이미 빠져 있다 (정본 업데이트 탭).
 * 직전 30일이 0건이면 화살표를 안 낸다 — 표의 「30일」 열(3.7)과 같은 처리다.
 */
export function recentKpi(
  rows: readonly { metrics: { recent30: number; prev30: number } }[],
): RecentKpi {
  let count = 0;
  let prev = 0;
  for (const r of rows) {
    count += r.metrics.recent30;
    prev += r.metrics.prev30;
  }
  return { count, trend: prev === 0 ? null : count - prev };
}

/**
 * 영토별 최근 관측 시각 (ms). 툴팁 다섯째 줄(4.2.3) · 영토 패널(4.3.2) · 엔티티 탭
 * 「최근 관측」 열(4.3.5)이 쓴다.
 *
 * 기준일 뒤에 올라온 사건 · 반출 제외 · 허위는 뺀다 (`inScope`, 점수 집계와 같은
 * 범위). 스냅샷을 과거로 옮겼는데 최근 관측이 미래 날짜로 보이면 안 된다.
 * 행위자 영토는 그 행위자가 올린 사건도 제 것이다 (`Ev.actorTerritoryId`).
 *
 * **글자 대신 시각으로 둔다.** 표가 이 값으로 정렬하는데, 화면 글자 `MM-DD` 로
 * 견주면 해가 바뀌는 자리에서 차례가 뒤집힌다 (설계서 L737-739). 데이터가
 * 2021 년부터라 한 해 안에서만 견주는 열이 아니다.
 */
export function latestSeen(events: readonly Ev[], d: Date): Record<string, number> {
  const out: Record<string, number> = {};
  for (const e of events) {
    if (!inScope(e, d)) continue;
    const t = Date.parse(e.postedAt);
    for (const id of [e.territoryId, e.actorTerritoryId]) {
      if (!id) continue;
      if (!(id in out) || t > out[id]) out[id] = t;
    }
  }
  return out;
}

/**
 * 화면에 적는 최근 관측일 `MM-DD` — 가장 늦은 사건의 **노션이 적은 날짜 글자**다 (설계서 4.3.5
 * 「월-일」). 사건 줄(`stampOf`)도 그 글자를 쓰므로 둘이 같아진다. UTC 로 옮기면 +09:00 새벽
 * 사건이 전날로 보여 같은 패널의 사건 줄과 어긋났다
 */
export function seenDays(events: readonly Ev[], d: Date): Record<string, string> {
  const at: Record<string, number> = {};
  const out: Record<string, string> = {};
  for (const e of events) {
    if (!inScope(e, d)) continue;
    const t = Date.parse(e.postedAt);
    for (const id of [e.territoryId, e.actorTerritoryId]) {
      if (!id) continue;
      if (!(id in at) || t > at[id]) {
        at[id] = t;
        out[id] = e.postedAt.slice(5, 10);
      }
    }
  }
  return out;
}

/** 밀리초를 `MM-DD` (UTC). 시각만 있을 때 쓴다 — 사건이 있으면 `seenDays` 를 쓴다 */
export function monthDay(ms: number): string {
  const dt = new Date(ms);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(dt.getUTCMonth() + 1)}-${p(dt.getUTCDate())}`;
}
