/**
 * 타임라인 탭이 쓰는 시점별 집계 — 설계서 4.3.7.
 *
 * **모든 값이 누적이다.** 설계서가 「그 시점까지의 사건 전부」라고 못박았다.
 * 그래서 어느 시점을 보든 `computeMap` 을 그 기준일로 한 번 더 돌린다.
 * 시점이 여섯이면 여섯 번 도는데, 예시 데이터 195건에서는 눈에 안 띈다.
 * 실제 데이터가 커지면 그때 결과를 쟁여 둔다.
 */

import { layoutMap, type MapLayout } from "./layout.ts";
import {
  quarterEnd,
  quarterKey,
  quarterOfDate,
  quarterRange,
  spanOf,
  type QuarterKey,
} from "./quarter.ts";
import { computeMap } from "./score.ts";
import type { Ev, Island, Territory, Web } from "./types.ts";

export type Snapshot = {
  /** `2026-Q3` */
  ym: QuarterKey;
  year: number;
  /** 1~4 */
  q: number;
  /** 그 시점까지 누적 사건 수 */
  events: number;
  /** 직전 시점 대비 늘어난 건수. 첫 시점은 null */
  delta: number | null;
  /** 직전 시점에는 없던 영토 수. 첫 시점은 null */
  fresh: number | null;
  /** 섬 코드 → 누적 사건 수. 추이 그래프가 이것을 쓴다 */
  byIsland: Record<string, number>;
  layout: MapLayout;
};

export type TimelineInput = {
  islands: readonly Island[];
  territories: readonly Territory[];
  events: readonly Ev[];
  web: Web;
  /** 오늘. 「이번 분기는 오늘까지」 예외에 쓴다 (설계서 3.1) */
  today?: Date;
};

/**
 * 사건이 걸쳐 있는 분기 전부.
 *
 * **판 1.2 에서 시점 단위가 해에서 분기로 바뀌었다** (설계서 4.3.7 「단위는
 * 분기. 한 해에 4 시점」). 눈금을 고정해 두면 데이터 기간이 바뀔 때마다
 * 앞뒤가 비거나 잘린다.
 */
export function quartersOf(events: readonly Ev[], today?: Date): QuarterKey[] {
  const live = events.filter((e) => !e.excluded && e.verdict !== "false");
  if (live.length === 0) return [];
  const [from, last] = spanOf(live);
  // 오늘이 든 분기까지는 늘 둔다. 새 분기에 사건이 아직 없어도 이번 분기
  // 스냅샷이 있어야 사건 없는 명부 영토가 지도에 나온다 (score.ts presentAt)
  const now = today ? quarterOfDate(today) : last;
  return quarterRange(from, now > last ? now : last);
}

/** 연도 칩이 가리키는 분기. 설계서 4.3.7 「그 해 3분기(9월 말)로 이동」 */
export function chipQuarter(year: number): QuarterKey {
  return quarterKey(year, 3);
}

/** 분기마다 그 끝 기준의 지도와 숫자를 낸다 */
export function snapshots(i: TimelineInput, quarters: QuarterKey[]): Snapshot[] {
  const out: Snapshot[] = [];
  let prevEvents: number | null = null;
  let prevLive = new Set<string>();

  for (const qk of quarters) {
    const [ys, qs] = qk.split("-Q");
    const year = Number(ys);
    const q = Number(qs);
    const d = quarterEnd(qk, i.today);
    const result = computeMap(
      { islands: i.islands, territories: i.territories, events: i.events, today: i.today },
      d,
    );
    const layout = layoutMap(
      { islands: i.islands, territories: i.territories, web: i.web },
      result,
    );

    const mine = result.territories.filter((t) => t.web === i.web);
    // 영토 사건 수를 더하면 행위자 섬 몫이 두 번 들어간다. 한 번씩 센 값을 쓴다
    const events = result.eventCount[i.web];
    const live = new Set(
      mine.filter((t) => t.eventCount > 0).map((t) => t.territoryId),
    );

    const byIsland: Record<string, number> = {};
    for (const isl of result.islands) {
      if (isl.web !== i.web) continue;
      byIsland[isl.islandId] = isl.eventCount;
    }

    out.push({
      ym: qk,
      year,
      q,
      events,
      delta: prevEvents === null ? null : events - prevEvents,
      fresh:
        prevEvents === null
          ? null
          : [...live].filter((id) => !prevLive.has(id)).length,
      byIsland,
      layout,
    });

    prevEvents = events;
    prevLive = live;
  }
  return out;
}

export type Growth = {
  islandId: string;
  name: string;
  token: string;
  from: number;
  to: number;
  /** 늘어난 비율 (%). 시작이 0건이면 null */
  rate: number | null;
};

/**
 * 성장 요약 — 첫 시점에서 고른 시점까지 섬이 얼마나 자랐나 (설계서 4.3.7).
 *
 * 피그마가 `48→79 ▲65%` 꼴로 낸다.
 */
export function growth(
  snaps: Snapshot[],
  atIndex: number,
  nameOf: (islandId: string) => { name: string; token: string },
): Growth[] {
  if (snaps.length === 0) return [];
  const first = snaps[0];
  const now = snaps[Math.max(0, Math.min(snaps.length - 1, atIndex))];
  const ids = Object.keys(now.byIsland).filter((k) => now.byIsland[k] > 0);
  return ids
    .map((islandId) => {
      const from = first.byIsland[islandId] ?? 0;
      const to = now.byIsland[islandId] ?? 0;
      return {
        islandId,
        ...nameOf(islandId),
        from,
        to,
        rate: from === 0 ? null : ((to - from) / from) * 100,
      };
    })
    .sort((a, b) => b.to - a.to);
}

export type Diff = {
  a: Snapshot;
  b: Snapshot;
  /** 누적 사건이 얼마나 늘었나 */
  deltaEvents: number;
  /** 몇 배가 됐나. A 가 0건이면 null */
  times: number | null;
  islands: {
    islandId: string;
    name: string;
    token: string;
    from: number;
    to: number;
    delta: number;
  }[];
  /** B 에는 있고 A 에는 없던 영토 이름 */
  fresh: string[];
};

/**
 * 두 시점을 견준다 — 설계서 4.3.7 시점 비교.
 *
 * **가해 쪽 이름만 나간다.** 「신규 엔티티」에 뜨는 것은 영토 이름이고,
 * 영토는 포럼 · 랜섬웨어 그룹 · 텔레그램 채널이다. 피해 조직 이름은 애초에
 * 굽기가 안 싣는다 (2026-09-23 결정).
 */
export function diff(
  a: Snapshot,
  b: Snapshot,
  nameOf: (islandId: string) => { name: string; token: string },
): Diff {
  const ids = new Set([...Object.keys(a.byIsland), ...Object.keys(b.byIsland)]);
  const islands = [...ids]
    .map((islandId) => {
      const from = a.byIsland[islandId] ?? 0;
      const to = b.byIsland[islandId] ?? 0;
      return { islandId, ...nameOf(islandId), from, to, delta: to - from };
    })
    .filter((x) => x.to > 0 || x.from > 0)
    .sort((x, y) => y.to - x.to);

  const was = new Set(a.layout.territories.map((t) => t.territoryId));
  const fresh = b.layout.territories
    .filter((t) => !was.has(t.territoryId))
    .map((t) => t.name);

  return {
    a,
    b,
    deltaEvents: b.events - a.events,
    times: a.events === 0 ? null : b.events / a.events,
    islands,
    fresh,
  };
}
