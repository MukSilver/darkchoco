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
  parseQuarter,
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
  /**
   * 전년 대비 — 한 해 앞 같은 분기보다 늘어난 누적 건수 (설계서 4.3.7 L806).
   * 그 분기가 목록에 없으면(첫 해) null.
   *
   * 전에는 직전 분기와 견줬다. 칩 이름이 「전년 대비」라 값이 이름과 달랐다
   */
  delta: number | null;
  /** 직전 시점에는 없던 영토 수. 첫 시점은 null */
  fresh: number | null;
  /**
   * 섬 코드 → 누적 사건 수. 추이 그래프가 이것을 쓴다.
   * **0건 섬도 들고, 열쇠 차례가 넘겨 받은 섬 목록 차례다** (`computeMap` 이
   * 섬 목록을 그대로 돈다). 추이 그래프 · 성장 요약이 이 차례를 그대로 쓴다
   */
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

/**
 * 연도 칩이 가리키는 분기. 설계서 4.3.7 L797 「그 해 3분기(9월 말)로 이동」.
 *
 * **분기 목록 안에서 고른다.** 데이터가 2021-Q4 부터라 2021 칩이 늘 Q3 을 찍으면
 * 목록에 없는 시점을 가리킨다 — 슬라이더와 스냅샷이 그 자리를 못 찾아 첫 시점으로
 * 떨어졌다. 그 해에 Q3 이 없으면 Q3 에 가장 가까운 분기(첫 해는 Q4, 올해가 Q2 에서
 * 끝나면 Q2)를 쓴다. 그 해가 목록에 없으면 null.
 */
export function chipQuarter(
  year: number,
  quarters: readonly QuarterKey[],
): QuarterKey | null {
  let best: QuarterKey | null = null;
  let gap = Infinity;
  for (const k of quarters) {
    const p = parseQuarter(k);
    if (p.year !== year) continue;
    const g = Math.abs(p.q - 3);
    // 같은 거리면 뒤 분기. 그 해를 더 많이 담은 쪽이다
    if (g <= gap) {
      best = k;
      gap = g;
    }
  }
  return best;
}

/**
 * ◀ / ▶▶ — 1년 뒤 / 앞 (설계서 4.3.7 L798). 같은 분기 한 해 전 · 뒤로 간다.
 *
 * 끝을 넘으면 끝 분기에서 멈추고, 이미 끝이면 null 이다 (단추를 끈다).
 * `quartersOf` 가 빈틈없는 분기 목록을 내므로 네 칸이 곧 한 해다.
 */
export function stepYear(
  quarters: readonly QuarterKey[],
  current: QuarterKey,
  dir: -1 | 1,
): QuarterKey | null {
  const at = quarters.indexOf(current);
  if (at < 0) return null;
  const to = Math.max(0, Math.min(quarters.length - 1, at + dir * 4));
  return to === at ? null : quarters[to];
}

/**
 * 시점 비교 상태 (설계서 4.3.7 L811-816, 피그마 ⑦-9c).
 *
 * `next` 는 다음 연도 칩 클릭이 채울 자리다. 「첫 번째 클릭이 A, 두 번째가 B」라
 * 누를 때마다 A · B 를 번갈아 채운다.
 */
export type Compare = { a: QuarterKey; b: QuarterKey; next: "a" | "b" };

/**
 * 처음 켤 때 — A 는 B 의 3년 전 같은 분기, B 는 최근 분기 (L813).
 * 데이터가 3년치가 안 되면 첫 분기를 A 로 쓴다. 시점이 둘이 안 되면 null.
 */
export function compareStart(quarters: readonly QuarterKey[]): Compare | null {
  if (quarters.length < 2) return null;
  const b = quarters[quarters.length - 1];
  const { year, q } = parseQuarter(b);
  const want = quarterKey(year - 3, q);
  return { a: quarters.includes(want) ? want : quarters[0], b, next: "a" };
}

/** 비교 중 연도 칩 클릭 — 차례대로 A, B 를 채운다 (L812) */
export function comparePick(c: Compare, q: QuarterKey): Compare {
  return c.next === "a" ? { a: q, b: c.b, next: "b" } : { a: c.a, b: q, next: "a" };
}

/** 연도 칩이나 스냅샷 카드 한 칸 — 그 해를 대표하는 시점 */
export type YearMark = { year: number; snap: Snapshot };

/**
 * 연도 칩 (L797). 칩 아래 숫자는 칩이 가리키는 시점의 누적 건수다 — 누르면 가는
 * 곳과 적힌 숫자가 같아야 한다 (피그마 ⑦-9b 2024 칩 209건 = 2024-09 카드 209건).
 */
export function yearChips(snaps: readonly Snapshot[]): YearMark[] {
  const keys = snaps.map((s) => s.ym);
  const out: YearMark[] = [];
  for (const year of new Set(snaps.map((s) => s.year))) {
    const k = chipQuarter(year, keys);
    const snap = snaps.find((s) => s.ym === k);
    if (snap) out.push({ year, snap });
  }
  return out;
}

/**
 * 시점별 스냅샷 — 해마다 한 장 (설계서 4.3.7 L807, 피그마 ⑦-9b 오른쪽 열).
 *
 * 대표 시점은 연도 칩과 같은 분기이고, **올해만 최신 분기**다. 올해가 Q4 까지
 * 있으면 칩은 Q3 에 서지만 카드는 「현재」를 보여야 한다.
 */
export function yearCards(snaps: readonly Snapshot[]): YearMark[] {
  if (snaps.length === 0) return [];
  const last = snaps[snaps.length - 1];
  return yearChips(snaps).map((m) =>
    m.year === last.year ? { year: m.year, snap: last } : m,
  );
}

/**
 * 스냅샷 썸네일이 같이 쓸 viewBox.
 *
 * 스냅샷마다 viewBox 가 제 섬 크기에 맞춰져 있어 그대로 그리면 2021 과 2026 이
 * 같은 크기로 보인다. 가장 큰 폭 · 높이로 맞추고 제 가운데에 놓아 해가 갈수록
 * 섬이 커지는 것이 보이게 한다 (피그마 ⑦-9b 썸네일).
 */
export function thumbBoxes(viewBoxes: readonly string[]): string[] {
  const size = boxSize(viewBoxes);
  return viewBoxes.map((v) => centerBox(v, size));
}

/** viewBox 들 가운데 가장 큰 폭 · 높이 */
export function boxSize(viewBoxes: readonly string[]): { w: number; h: number } {
  const parsed = viewBoxes.map((v) => v.split(/\s+/).map(Number));
  return {
    w: Math.max(0, ...parsed.map((p) => p[2] || 0)),
    h: Math.max(0, ...parsed.map((p) => p[3] || 0)),
  };
}

/**
 * viewBox 를 크기 `size` 로 넓히고 제 가운데에 놓는다. **모든 분기가 같은 크기 틀을 쓰면
 * 축척이 같다** — 지도 탭 · Historical Map · 시점 비교 A/B 가 모든 분기를 합친 크기로
 * 그린다 (2026-09-28 최현서 3번 · 코드 분석). 전에는 분기마다 그려진 칸에 맞춰 판 배율이
 * 바뀌어, 섬이 하나뿐인 분기는 지나치게 확대되고 슬라이더를 옮길 때마다 판이 튀었다.
 * 크기가 원래보다 작으면 원래 크기를 쓴다(잘리지 않게)
 */
export function centerBox(viewBox: string, size: { w: number; h: number }): string {
  const [x, y, w, h] = viewBox.split(/\s+/).map(Number);
  const W = Math.max(w, size.w);
  const H = Math.max(h, size.h);
  return [x + w / 2 - W / 2, y + h / 2 - H / 2, W, H].join(" ");
}

/** 섬 누적 건수의 최댓값. 추이 그래프 세로축과 성장 요약 막대가 같은 눈금을 쓴다 */
export function peakOf(snaps: readonly Snapshot[]): number {
  let m = 1;
  for (const s of snaps) {
    for (const v of Object.values(s.byIsland)) if (v > m) m = v;
  }
  return m;
}

/** 분기마다 그 끝 기준의 지도와 숫자를 낸다 */
export function snapshots(i: TimelineInput, quarters: QuarterKey[]): Snapshot[] {
  const out: Snapshot[] = [];
  const byYm = new Map<QuarterKey, Snapshot>();
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

    const yearAgo = byYm.get(quarterKey(year - 1, q));
    const snap: Snapshot = {
      ym: qk,
      year,
      q,
      events,
      delta: yearAgo ? events - yearAgo.events : null,
      fresh:
        prevEvents === null
          ? null
          : [...live].filter((id) => !prevLive.has(id)).length,
      byIsland,
      layout,
    };
    out.push(snap);
    byYm.set(qk, snap);

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

/** 두 시점의 섬 코드. 0건 섬도 넣고 섬 목록 차례를 지킨다 (`Snapshot.byIsland`) */
function islandIds(a: Snapshot, b: Snapshot): string[] {
  return [...new Set([...Object.keys(b.byIsland), ...Object.keys(a.byIsland)])];
}

/**
 * 성장 요약 — `from` 시점에서 `to` 시점까지 섬이 얼마나 자랐나 (설계서 4.3.7 L809).
 * 평소에는 첫 시점 → 지금, 시점 비교 중에는 A → B 다 (피그마 ⑦-9c).
 *
 * 피그마가 `48→79 ▲65%` 꼴로 낸다.
 *
 * **섬 넷을 늘 같은 차례로 낸다.** 0건 섬(그 시점까지 사건이 없는 텔레그램 따위)을
 * 거르면 재생 중에 줄이 생겼다 사라지고, 건수로 세우면 줄이 자리를 바꾼다.
 * 피그마 ⑦-9b · ⑦-9c 도 기타(33)가 텔레그램(32)보다 많은데 목록 차례 그대로다.
 */
export function growth(
  from: Snapshot,
  to: Snapshot,
  nameOf: (islandId: string) => { name: string; token: string },
): Growth[] {
  return islandIds(from, to).map((islandId) => {
    const a = from.byIsland[islandId] ?? 0;
    const b = to.byIsland[islandId] ?? 0;
    return {
      islandId,
      ...nameOf(islandId),
      from: a,
      to: b,
      rate: a === 0 ? null : ((b - a) / a) * 100,
    };
  });
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
 *
 * 섬별 증가도 성장 요약처럼 섬 넷을 목록 차례로 낸다 (피그마 ⑦-9c 오른쪽 열).
 */
export function diff(
  a: Snapshot,
  b: Snapshot,
  nameOf: (islandId: string) => { name: string; token: string },
): Diff {
  const islands = islandIds(a, b).map((islandId) => {
    const from = a.byIsland[islandId] ?? 0;
    const to = b.byIsland[islandId] ?? 0;
    return { islandId, ...nameOf(islandId), from, to, delta: to - from };
  });

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
